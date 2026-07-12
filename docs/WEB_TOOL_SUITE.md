# Blackreach Web-Tool Suite

> Architecture and operations source of truth. Updated 2026-07-12 EDT;
> validation evidence is scoped explicitly below.

## Contract

The suite is a local-first web execution and intelligence stack for Josii's
agent fleet. It replaces the locally useful Firecrawl and managed-browser calls
without claiming infrastructure that is not present.

| Layer | Sole responsibility |
| --- | --- |
| Blackreach | Goal-driven planning, interaction, recovery, downloads, and agent jobs |
| Huginn / BlackCrawl | Deterministic search, scrape, crawl, map, extraction, batch, cache, replay, schedules, and durable jobs |
| StarSearch | Browser/session lifecycle, fingerprints, humanized input, screenshots, request policy, per-session socket egress, and browser capacity |
| blackreach-mcp | Thin MCP schemas, authentication, transport errors, and bounded job polling |
| Huginn egress provider | Direct-vs-proxied policy, proxy leases, rotation/stickiness, provider health, and cooldown |

No adapter owns a second browser. `blackreach-mcp` no longer launches
Playwright or stores a private browser profile.

```text
Hermes / Claude / Codex / Anubis / Herdr
                    |
              blackreach-mcp
              /             \
 deterministic work          goal-driven work
          |                         |
     Huginn :7432              Blackreach :7434
          |                    /           \
          +---- StarSearch :7676       Huginn for data
                   |
         per-session loopback socket gateway
                   |
      direct host egress OR one Huginn proxy lease
```

Production rules:

1. Huginn is the deterministic data-plane gateway.
2. StarSearch is the browser boundary. Production mode fails closed if it is
   unavailable or a request needs an unimplemented browser control.
3. Playwright compatibility fallback requires the explicit
   `HUGINN_ALLOW_PLAYWRIGHT_FALLBACK=true` opt-in. `render_mode=light` remains
   an explicit caller-selected HTTP path. `render_mode=starsearch` forces the
   daemon path and fails closed even when compatibility fallback is enabled.
4. Explicit URLs are preserved. Blackreach forwards `start_url` unchanged and
   Huginn scrapes the requested URL; neither substitutes a search/default page.
5. A result with an upstream status of 400 or greater is a failure and is not
   cached or counted as a completed page.
6. Cache identity includes output-affecting options and egress policy. Requests
   with actions, cookies, headers, inline extraction, or change tracking do not cache.
   The `starsearch_socket_gateway_v1` contract discriminator prevents
   pre-gateway provider-only entries from being served as enforcement proof.
7. Stealth changes browser-visible identity. It never implies a new IP,
   residential egress, geolocation, or proxy reputation.
8. Every StarSearch Chromium process is forced through an owned per-session
   loopback HTTP gateway. Huginn rejects a session or scrape whose daemon
   response does not attest `gateway_enforced=true` and
   `resolution=local_frozen`; it does not infer enforcement from requested
   proxy options.

## Stable API and MCP surface

### Huginn REST

| Capability | Start/status routes | Notes |
| --- | --- | --- |
| Search | `POST /v1/search` (`/v1/seek`) | Health-scored, StarSearch-rendered Bing and Brave; `auto` can fall back, an explicit engine never silently changes |
| Search health | `GET /v1/search/engines` | Process-local scores, latency EMA, failures, and circuit state for Bing and Brave |
| Scrape | `POST /v1/scrape` (`/v1/probe`) | Markdown, HTML, raw HTML, links, metadata, screenshot, actions, retries, cache |
| Crawl | `POST /v1/crawl`, `GET /v1/crawl/{id}` | Durable SQLite job, progress, cancellation, JSONL/SSE support |
| Batch scrape | `POST /v1/batch/scrape`, `GET /v1/batch/scrape/{id}` | Durable job IDs and partial results; `/v1/flock` remains synchronous |
| Extract | `POST /v1/extract`, `GET /v1/extract/{id}` | Scrape plus schema/prompt/template extraction |
| Browser sessions | `POST/GET /v1/browser/sessions` | Authenticated StarSearch lifecycle |
| Browser command | `POST /v1/browser/sessions/{id}/commands` | Navigate, click, type, scroll, hover, wait, screenshot, content, JS, cookies, history |
| Browser close | `DELETE /v1/browser/sessions/{id}` | Idempotent close and capacity release |
| Named contexts | `GET /v1/browser/contexts`, `DELETE /v1/browser/contexts/{context_id}` | Authenticated host-local persistent profile lifecycle (`id`/`name` remain deprecated response aliases) |
| Context maintenance | `POST /v1/browser/contexts/prune`, `POST /v1/browser/contexts/{context_id}/recover` | Dry-run retention/quota planning and explicitly confirmed, fail-closed quarantine recovery |
| Health | `/health`, `/health/ready`, `/health/detailed` | StarSearch capacity plus explicit egress mode/health |
| Metrics | `/v1/metrics` | Per-endpoint count, latency, and success rate |

Data-bearing routes require `Authorization: Bearer ...` when the deployment key
is configured. Basic health/liveness remains probeable; detailed health and
metrics require the key. Persistent context operations refuse to run unless an
API key is configured. Browser-origin access is disabled by default;
`HUGINN_CORS_ORIGINS` is an explicit allowlist and wildcard CORS requires auth.

Search `engine` accepts only `auto`, `bing`, or `brave`. `auto` orders eligible
engines by measured success and latency and, when `fallback_chain=true`, tries
the next healthy rendered engine after an error or empty result. Choosing
`bing` or `brave` is fail-closed to that engine: Huginn reports its typed
attempt/error and does not substitute the other engine. Two consecutive
failures open that engine's circuit for 30 seconds. Scores and circuits are
process-local operational evidence and reset on a Huginn restart; they are not
durable user data. Both engines share the same StarSearch browser and selected
egress route, so this is search-origin resilience, not IP-path diversity. A
single Huginn provider lease is held across SERP fallback and optional result
scraping; configured proxy exhaustion fails before search and never falls back
to direct host egress.

### MCP tools

The Node adapter publishes 12 tools:

- `blackreach_search`, `blackreach_fetch`, `blackreach_fetch_many`
- `blackreach_crawl`, `blackreach_extract`, `blackreach_search_page`
- `blackreach_screenshot`, `blackreach_job`
- `blackreach_browser_session`, `blackreach_browser_command`
- `blackreach_browse`, `blackreach_doctor`

The original six names remain compatible, but now route through Huginn instead
of a private Playwright browser. Long operations return durable job IDs by
default. Poll with repeated `blackreach_job` calls; explicit blocking waits are
capped below common MCP 60-second transport timeouts.

Every adapter error includes a stable code, handling layer, HTTP status,
retryability, and request ID. Screenshot bytes return through MCP and the old
arbitrary host `save_path` input is intentionally ignored.

`blackreach_fetch` defaults to explicit `render_mode=starsearch`; callers must
choose `light` to opt into the direct HTTP path. `blackreach_doctor` accepts
`check_egress=true` plus an optional `probe_url` to run a real fail-closed
StarSearch navigation and report the browser runtime, handling layer, upstream
status, request ID, and direct-vs-proxied egress.

`blackreach_browser_session` supports `list_contexts`, `delete_context`,
`prune_contexts`, and `recover_context` in addition to live-session operations.
Pruning defaults to `dry_run=true`; deletion requires the caller to send
`dry_run=false`. Recovery requires a path-safe `context_id` plus
`confirm=true`, and the MCP adapter rejects an unconfirmed request before it
contacts Huginn.

## StarSearch session and security boundary

StarSearch exposes two transports:

- owner-only Unix socket, protected by filesystem mode and peer UID;
- opt-in loopback TCP at `127.0.0.1:7676`, used by the Huginn container and
  requiring a 32-character-or-longer handshake token.

TCP never binds to a non-loopback address. The preferred secret setting is
`STARSEARCH_TCP_TOKEN_FILE`; the systemd deployment uses
`~/.config/starsearch/tcp-token` with mode `0600`.

Session properties:

- five real process-isolated slots, with the sixth request returning
  `CapacityExceeded`;
- atomic launch reservations, typed lifecycle and commands, idle expiry,
  domain allowlists, cookie/evaluate capability gates, and optional per-session
  proxy routing;
- stealth/fingerprint setup fails closed;
- proxy credentials cross the Huginn-to-StarSearch protocol as structured
  fields, are consumed by the owned session gateway, and are never exposed in
  the public descriptor or status;
- the daemon's `new_session` and `describe_session` responses carry an
  authoritative, password-free egress descriptor. Huginn closes and rejects a
  session if that descriptor is missing, inconsistent with the requested
  direct/upstream mode, or does not attest local frozen resolution;
- daemon restart changes an explicit runtime `instance_id`; Huginn marks old
  handles `interrupted` instead of falsely reporting them active.

Named contexts are separate from runtime sessions. They use hashed directories
under `~/.local/state/starsearch/contexts`, store the complete fingerprint
snapshot, and hold an exclusive filesystem lease until Chromium has closed and
exited. Persistent cookies, local storage, IndexedDB, and related Chromium
profile state can survive close/reopen and daemon restart; session IDs, open
tabs, and live CDP attachments do not. `close_session` preserves a named
profile, while `delete_context` rejects an active lease and removes it
explicitly. Locale, proxy-server identity, allowed domains, internal-network
policy, and cookie/evaluate permissions are immutable across reopen.
If Chromium cannot be confirmed stopped, StarSearch writes a durable quarantine
marker before releasing control; reopen and delete then fail closed across
daemon restart instead of risking concurrent writers.

The context store enforces `STARSEARCH_MAX_CONTEXTS` (default `100`) when a new
named context is created. `STARSEARCH_CONTEXT_RETENTION_DAYS` (default `90`;
`0` disables age-based selection) supplies the explicit prune policy. Listing
reports idle age, retention deadline/expiry, prune eligibility, active lease,
and quarantine cause/time/session metadata. Pruning never runs in the
background: `prune_contexts` defaults to a plan-only dry run, protects active
and quarantined profiles, selects retention-expired inactive profiles, then
selects the oldest inactive profiles needed to satisfy a lowered quota.

Quarantine recovery is a separate, confirmed mutation. On Linux, StarSearch
takes the durable profile lease, checks same-user processes for the profile's
`--user-data-dir`, and only then removes verified-stale Chromium singleton
locks and the quarantine marker. A live lease, relevant process, uninspectable
process, unsupported recovery platform, or malformed marker fails closed.

Profile directories are `0700` and manifests/locks are `0600`. This is access
control, not encryption: StarSearch adds no application-level profile
encryption, so Chromium/OS keyring behavior and encrypted host storage remain
the at-rest boundary.

Network policy checks the top-level URL and every Chromium request paused by
CDP Fetch, including redirects and subresources. It rejects local/private,
link-local, metadata, carrier-grade NAT, documentation, benchmark, multicast,
and reserved destinations by default. `file:`, `javascript:`, and other unsafe
schemes remain forbidden; `about:blank` and `data:` are allowed only as
non-network documents. Internal access requires both server policy and an
explicit session request.
Document-level navigation and domain policy is also rechecked for redirects,
links/forms, frames, page-script navigation, and history traversal; third-party
CDN subresources may load only after the same internal-network check.

The socket gateway is the stronger connection boundary. Each Chromium process
is launched with a random loopback HTTP gateway, direct DNS/prefetch and QUIC
disabled, and proxy bypass disabled. The gateway parses HTTP targets and
`CONNECT`, resolves the whole destination answer set itself, rejects the request
if any resolved address violates the internal/reserved-address policy, connects
the exact approved `SocketAddr`, and verifies the connected peer. Direct mode
uses that pinned socket. Upstream `http`, `https`, and `socks5` modes pass the
locally resolved IP literal to the configured proxy; HTTPS proxy transport
verifies its certificate and SOCKS authentication cannot silently downgrade.
Closing or quarantining a session revokes the gateway and aborts its tunnels.

This is application/process-level enforcement, not a kernel egress firewall.
StarSearch controls the route of the Chromium process it launches, but does not
provide a network namespace, cgroup/eBPF policy, multi-user host isolation, or
proof that separately compromised native code cannot create a raw socket. Add
OS-level isolation when hostile code shares the daemon account or a kernel-level
no-bypass guarantee is required.

## Real proxy boundary

There are two deliberate layers:

1. Huginn owns endpoint inventory, lease selection, stickiness/rotation,
   health, cooldown, and the rule that an exhausted configured provider never
   falls back to direct egress.
2. StarSearch owns socket enforcement for the one lease assigned to a browser
   session. A per-session gateway is present even in direct mode; direct means
   "pinned host egress," not "unenforced Chromium networking."

Default Huginn provider health reports:

```json
{
  "mode": "direct",
  "configured": false,
  "direct_egress": true,
  "endpoints": 0
}
```

That means the host's public IP is in use, through the StarSearch socket
gateway. The corresponding daemon/session evidence is shaped as:

```json
{
  "gateway_enforced": true,
  "mode": "direct",
  "upstream_scheme": null,
  "upstream_identity": null,
  "resolution": "local_frozen"
}
```

With a proxy lease, `mode` becomes `upstream`, `upstream_scheme` is `http`,
`https`, or `socks5`, and `upstream_identity` is a password-free opaque hash.
The StarSearch aggregate status also reports active gateway count, modes,
accepted/active/completed/blocked/failed connections, and byte counters. Huginn
preserves this enforcement descriptor in scrape metadata and nests its own
provider selection under `metadata.egress.provider`. A missing or inconsistent
StarSearch descriptor fails closed: session creation closes the daemon session
and returns 502, while scrape navigation aborts. Huginn never turns requested
proxy configuration into a fake enforcement claim.

To bring real proxy endpoints:

```bash
install -d -m 700 ~/.config/huginn
install -m 600 /path/to/proxy-urls ~/.config/huginn/proxy-urls
```

Set:

```dotenv
HUGINN_PROXY_PROVIDER=static
HUGINN_PROXY_URLS_FILE=/home/phnix/.config/huginn/proxy-urls
HUGINN_PROXY_ROTATION=round_robin   # or sticky
HUGINN_PROXY_FAILURE_THRESHOLD=3
HUGINN_PROXY_COOLDOWN_SECONDS=60
```

The Compose file mounts the host file at
`/run/secrets/huginn_proxy_urls`; `/dev/null` is mounted in direct mode so no
fake endpoint is created. Supported schemes are `http`, `https`, and `socks5`.
Credentials may be embedded in the secret file. Public status and errors never
return them.

The provider issues per-request/per-session leases, rotates or sticks by key,
tracks successes and proxy-like failures, cools unhealthy endpoints, and never
silently falls back to direct egress when all configured endpoints are down.
Named contexts use deterministic rendezvous selection even when ordinary
requests use round-robin; if the bound endpoint is cooling down, reopen fails
closed instead of changing egress identity.
The binding and health key includes proxy server plus account/session username
but never the password, so credential rotation is stable while a geographic or
account identity change cannot silently reuse the profile. Launch, DOM actions,
and close do not reset proxy failures; only a successful HTTP(S) navigation is
currently treated as proof of healthy browser egress (`data:`/`about:` do not).
It does not supply IPs, test residential reputation, or guarantee geography;
endpoint procurement remains an infrastructure decision.

StarSearch rejects a loopback, private, or LAN upstream proxy endpoint by
default. Set `STARSEARCH_ALLOW_PRIVATE_UPSTREAM_PROXY=1` only when that endpoint
is an operator-owned local/LAN proxy service. This permits the gateway to reach
the upstream proxy itself; destination SSRF validation remains in force. It is
not needed for normal public proxy inventory.

## Deployment configuration

| Service | Bind | Required production settings |
| --- | --- | --- |
| StarSearch | Unix + `127.0.0.1:7676` | `STARSEARCH_TCP_ADDR`, `STARSEARCH_TCP_TOKEN_FILE`, `STARSEARCH_CONTEXTS_DIR`, `STARSEARCH_MAX_CONTEXTS`, `STARSEARCH_CONTEXT_RETENTION_DAYS` |
| Huginn | `127.0.0.1:7432` | `HUGINN_API_KEY_FILE`, `HUGINN_STARSEARCH_TCP`, `HUGINN_STARSEARCH_TOKEN_FILE`, `HUGINN_BROWSER_BACKEND=starsearch` |
| Blackreach | `127.0.0.1:7434` | `BLACKREACH_API_KEY_FILE`, `HUGINN_API_KEY_FILE`, `BLACKREACH_JOB_STATE_FILE`, `BLACKREACH_BROWSER_BACKEND=starsearch` |
| blackreach-mcp | stdio | base URLs plus key files; defaults point at `~/.config/...` |

StarSearch lifecycle and egress settings:

| Variable | Default | Meaning |
| --- | --- | --- |
| `STARSEARCH_CONTEXTS_DIR` | `~/.local/state/starsearch/contexts` | Owner-controlled host-local profile store |
| `STARSEARCH_MAX_CONTEXTS` | `100` | Hard limit on new named contexts; lowering it does not delete profiles until an explicit prune |
| `STARSEARCH_CONTEXT_RETENTION_DAYS` | `90` | Age threshold used by explicit pruning; `0` disables age selection |
| `STARSEARCH_ALLOW_PRIVATE_UPSTREAM_PROXY` | unset/false | Permit an operator-owned private/loopback upstream proxy endpoint; never relaxes target validation |

Search health currently uses code-defined operational policy: Bing and Brave,
two failures to open a circuit, and a 30-second cooldown. It has no environment
toggle that silently re-enables a direct HTTP or API-key search path.

Current secret files:

```text
~/.config/starsearch/tcp-token
~/.config/huginn/api-key
~/.config/blackreach/api-key
```

All are local, mode `0600`, excluded from Git, and mounted/read by path rather
than copied into images or process arguments. StarSearch and Huginn reject
symlinks, non-regular files, untrusted owners, and group/world-readable secret
files. The root-run Huginn container requires an explicit trusted host UID for
its read-only mounts.

Huginn state lives in the named `huginn-data` volume at `/data/huginn.db`.
Jobs, replay data, scheduler state, cache metadata, and research memory survive
container recreation. StarSearch's embedded fingerprint catalog remains in its
dedicated repository, while named browser profiles remain under the configured
context state directory; neither should be discarded during deployment.
The production Huginn image is StarSearch-only and does not install a second
Playwright Chromium. A compatibility image requires the explicit build arg
`HUGINN_INSTALL_PLAYWRIGHT_BROWSER=1` plus runtime fallback opt-in.

Blackreach and Huginn commit `uv.lock`; the Huginn production image installs
with `uv sync --locked`. StarSearch commits Cargo's lock and a separate Python
client lock. `requirements.txt` files are compatibility shims back to
`pyproject.toml`, not competing dependency declarations.

Blackreach atomically journals retained agent jobs to
`~/.local/state/blackreach/jobs.json` with mode `0600`. Terminal results remain
pollable after a service restart. Work interrupted by a crash is recovered as
an explicit `service_restarted` failure; the server never pretends that an
in-memory browser run resumed. A corrupt/unwritable journal degrades health and
rejects new jobs with `job_store_unavailable` instead of overwriting state.

## Runbook

Build and install StarSearch atomically:

```bash
cd /mnt/WorkDrive/AI_Projects/Project_StarSearch
cargo test --manifest-path daemon/Cargo.toml
cargo build --release --manifest-path daemon/Cargo.toml
install -m 755 daemon/target/release/starsearch-daemon ~/.starsearch/bin/starsearch-daemon.new
mv -f ~/.starsearch/bin/starsearch-daemon.new ~/.starsearch/bin/starsearch-daemon
install -m 644 deploy/systemd/starsearch-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user restart starsearch-daemon
```

Build/recreate Huginn and restart Blackreach:

```bash
cd /mnt/WorkDrive/AI_Projects/BlackCrawl
docker compose build huginn
docker compose up -d --force-recreate huginn

cd /mnt/WorkDrive/AI_Projects/Blackreach
uv sync --locked --extra server
uv pip install --python .venv -e /mnt/WorkDrive/AI_Projects/Project_StarSearch/client
install -m 644 deploy/systemd/blackreach-http.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user restart blackreach-http
```

Build and test the MCP adapter:

```bash
cd /mnt/WorkDrive/AI_Projects/blackreach-mcp
npm ci
npm run check
npm audit --audit-level=low
```

Register that adapter once. Hermes uses:

```yaml
mcp_servers:
  blackreach_web:
    command: node
    args:
      - /mnt/WorkDrive/AI_Projects/blackreach-mcp/dist/index.js
    timeout: 120
    connect_timeout: 60
```

Remove or disable the older `blackreach` and `blackcrawl` Python MCP entries;
running them beside `blackreach_web` recreates duplicate browser and timeout
paths. Apply a Hermes configuration change with:

```bash
systemctl --user restart hermes-gateway
systemctl --user status hermes-gateway
```

Quick doctor calls:

```bash
curl -s http://127.0.0.1:7432/health | jq
curl -s -H "Authorization: Bearer $(<~/.config/huginn/api-key)" \
  http://127.0.0.1:7432/health/detailed | jq
systemctl --user status starsearch-daemon blackreach-http
docker ps --filter name=huginn
```

Inspect the new enforcement, search, and context-maintenance state without
allocating a browser manually:

```bash
HUGINN_KEY="$(<~/.config/huginn/api-key)"

# StarSearch aggregate gateway counters and retention policy flow through
# authenticated Huginn detailed health.
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  http://127.0.0.1:7432/health/detailed \
  | jq '{gateway: .starsearch.egress_gateway, retention: .starsearch.context_retention}'

# Process-local Bing/Brave health, score, latency EMA, and circuits.
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  http://127.0.0.1:7432/v1/search/engines | jq

# Auto mode may use the next healthy rendered engine.
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"query":"Prometheus monitoring","search_options":{"engine":"auto"},"scrape_results":false}' \
  http://127.0.0.1:7432/v1/search | jq '{success, error_code, metadata}'

# Explicit mode is pinned to the requested engine and never substitutes one.
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"query":"Prometheus monitoring","search_options":{"engine":"brave"},"scrape_results":false}' \
  http://127.0.0.1:7432/v1/search | jq '{success, error_code, metadata}'
```

Context maintenance is always inspect-first:

```bash
# Inventory includes active/quarantined state, idle age, and retention evidence.
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  http://127.0.0.1:7432/v1/browser/contexts | jq

# Safe default: calculate candidates, delete nothing.
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  -H 'Content-Type: application/json' -d '{"dry_run":true}' \
  http://127.0.0.1:7432/v1/browser/contexts/prune | tee /tmp/starsearch-prune-plan.json | jq

# Only after reviewing the plan. Active and quarantined contexts stay protected.
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  -H 'Content-Type: application/json' -d '{"dry_run":false}' \
  http://127.0.0.1:7432/v1/browser/contexts/prune | jq

# Recovery is not a generic force-unlock. Inspect the quarantine and host
# processes first; the daemon repeats same-user process/lock checks and fails closed.
CONTEXT_ID='replace-with-reviewed-context-id'
curl -s -H "Authorization: Bearer $HUGINN_KEY" \
  -H 'Content-Type: application/json' -d '{"confirm":true}' \
  "http://127.0.0.1:7432/v1/browser/contexts/$CONTEXT_ID/recover" | jq
```

The equivalent MCP calls use `blackreach_browser_session` with
`operation=prune_contexts` plus `dry_run`, or `operation=recover_context` plus
`context_id` and `confirm=true`. Prefer that adapter for agents; reserve raw
REST commands for operations and debugging.

An MCP deep doctor probe distinguishes service reachability from usable public
DNS/navigation. If it returns `DNSResolutionFailed`, verify the host resolver
with `resolvectl query <probe-host>` before restarting browser services;
StarSearch intentionally does not bypass or silently replace host DNS policy.

## Validation record

Current slice, validated against rebuilt installed services on 2026-07-12 EDT:

- StarSearch: 207/207 Rust tests, Clippy with warnings denied, 82/82 Python
  tests, release build with the lockfile, and unchanged live fingerprint blob
  (`git hash-object` `6a84f00c26b13d6279318e95fc53c0a58b8118c5`).
- Huginn: 887 passed, 6 explicitly deselected network cases; Ruff and OpenAPI
  generation clean; the rebuilt container is healthy.
- blackreach-mcp: TypeScript build and 11/11 tests; npm audit reports zero
  vulnerabilities.

| Current contract | Installed-service proof |
| --- | --- |
| Socket egress | Direct StarSearch `new_session` and `describe_session` both returned `gateway_enforced=true`, `mode=direct`, and `resolution=local_frozen`; an active five-session pool reported five gateways and close returned it to zero |
| Explicit scrape/screenshot | Huginn scraped `https://example.com`, extracted `Example Domain`, returned Markdown and 21,200 base64 screenshot characters, and preserved the authoritative gateway descriptor plus Huginn provider metadata |
| SSRF | StarSearch rejected `http://127.0.0.1:7432/health` as `SSRFBlocked`; Huginn returned `success=false`/`invalid_url` for the same explicit target |
| Search resilience | Explicit Brave returned Prometheus, Wikipedia, and Reddit destinations; explicit Bing returned Prometheus and its documentation; both reported healthy scores after one successful rendered request, and neither explicit route substituted the other |
| Context durability | A named proof context persisted a cookie through close, StarSearch restart, `open_existing`, and a fresh navigation; runtime/session IDs changed, the context stayed unquarantined, and the proof context was deleted afterward |
| Context maintenance | REST and MCP prune calls defaulted to `dry_run=true` with no deletions; recovery with `confirm=false` was rejected as `recovery_confirmation_required`; successful recovery safety is covered by the Rust process/lease/lock tests rather than a fabricated live quarantine |
| Capacity/recovery | Five Chromium sessions filled all five slots, the sixth returned `CapacityExceeded`, and closing all sessions restored `active_sessions=0`, `available=5`, `active_gateways=0` |
| Jobs and persistence | One-page crawl and two-URL batch jobs completed with real extracted results; both remained pollable with their data after a safe Huginn container restart |
| Streaming | JSONL crawl emitted a real document carrying `gateway_enforced=true`, then a terminal `__done__` record with `completed=1`, `total=1` |
| MCP path | The real stdio adapter exposed 12 tools; doctor, fetch, and context-prune calls reached the installed Huginn/StarSearch stack, and doctor verified the socket-egress contract rather than accepting page content alone |

The following table is the older installed baseline. It predates the
per-session socket gateway, Bing/Brave health scoring, and explicit context
prune/recovery slice. Preserve it as regression evidence, but use the current
record above for the new boundaries.

Automated suites in that baseline:

- StarSearch: 189 Rust tests and 44 Python client tests.
- Huginn: 873 passed, 6 explicitly deselected network cases.
- Blackreach: 3,055 passed in the full repository suite.
- blackreach-mcp: TypeScript build and 11 tests covering client errors, routed
  tools, real stdio schemas, named contexts, and zero npm audit findings.

Live evidence from that baseline:

| Contract | Proof |
| --- | --- |
| Authentication | missing/wrong StarSearch TCP token rejected; unauthenticated Huginn/Blackreach data routes returned 401 |
| Search | 3 rendered results for Prometheus through Huginn to StarSearch/Bing; first URL `https://prometheus.io/` |
| Explicit scrape | `https://prometheus.io/`, title and H1 extracted, explicit `render_mode=starsearch` |
| Actions/screenshot | MCP selector wait completed and returned a valid 15,900-byte PNG |
| Cache | unique first request `cached=false`, second `cached=true` |
| Egress truth | provider metadata reported `mode=direct`, `proxied=false`, endpoint null; this row is not socket-gateway proof |
| SSRF | top-level loopback rejected; data-page subresource and public HTTP redirect produced zero hits on a live loopback canary through the prior CDP guard |
| Domain policy | an allowed `example.com` page clicked a link to another public domain; Fetch blocked the document and Chromium entered its local error page instead of reaching the target |
| Browser lifecycle | create/navigate/evaluate/close passed; five slots filled, sixth rejected, all five recovered |
| Named persistence | persistent cookie, localStorage, IndexedDB, and fingerprint survived close plus StarSearch restart; SID and runtime instance changed |
| Context exclusivity | simultaneous open and active delete returned `ContextInUse`; inactive delete succeeded and `open_existing` then returned `ContextNotFound` |
| Crash recovery | StarSearch restart marked Huginn handle `interrupted` and commands returned structured 410; Huginn crash left an authoritative active SID that the restarted API closed |
| Batch/crawl | crawl completed 1/1; batch `263a4dc8-1dfd-4825-9a99-2a24c3e391f0` completed 2/2 |
| Persistence | that completed 2/2 batch remained queryable after a Huginn container restart |
| MCP | 12 tools; default fail-closed fetch and deep doctor both navigated Prometheus through Huginn/StarSearch with request and egress metadata |
| MCP failures | Huginn `success=false` envelope surfaced as MCP `isError=true` with `invalid_url`, layer, retryability, and request ID |
| Agent start URL | MCP agent job retained `https://example.com/` and completed with `H1: Example Domain` |
| Agent persistence | completed job `ce151a9e` retained `Example Domain` and remained queryable after a Blackreach/Waitress service restart; journal mode `0600` |
| Fail closed | unsupported header control and invalid render mode returned `unsupported_option`; explicit StarSearch never fell back to Playwright |

## Honest replacement boundary

### Firecrawl

The suite covers the local calls in use: search, scrape, screenshots/actions,
crawl, batch jobs, extraction, progress/status, streaming, caching, retries,
change tracking, and structured failures. It is not complete Firecrawl v2
schema parity. Remaining gaps include full v2 request/response compatibility,
advanced batch controls/pagination, profile APIs, and some interactive scrape
actions. Search now has two independent rendered origins and visible health,
but those engines still share one browser/egress path. Extraction quality also
depends on the configured local/remote LLM.

Reference: [Firecrawl v2 API](https://docs.firecrawl.dev/api-reference/v2-introduction)

### Browserbase

The suite now has authenticated local HTTP session lifecycle, isolated browser
processes, atomic capacity limits, typed commands, deterministic per-context
proxy routing, an owned per-session socket gateway, durable host-local profile
contexts with quotas/retention/quarantine recovery, screenshots, runtime IDs,
and restart reconciliation. It does not expose a public CDP/WebSocket
connection URL, hosted live-view/debug URLs, live-browser recovery, profile
migration, multi-host context storage, autoscaling, or managed proxy networks.
It also does not provide a kernel network-isolation boundary. Those are the
honest Browserbase and host-security boundaries.

Reference: [Browserbase session API](https://docs.browserbase.com/reference/api/create-a-session)

### Highest-leverage next slices

1. Add an OS-owned network namespace/cgroup firewall around Chromium if the
   threat model requires kernel-level no-bypass egress rather than the current
   application/process boundary.
2. Add explicit fingerprint/browser-version rotation policy, operator tooling
   for reviewing quarantine evidence, and encrypted-storage deployment
   guidance; do not auto-recover quarantined profiles.
3. Add a controlled CDP/WebSocket gateway only if Anubis/Herdr truly need
   third-party browser attachment.
4. Generate a machine-readable Firecrawl v2 contract diff and implement only
   consumer-visible gaps.
5. Persist or export search-engine health only if restart-continuous scoring is
   operationally useful, and add a truly distinct provider/egress source only
   when the fleet needs path diversity rather than rendered-origin diversity.
6. Publish signed StarSearch release artifacts and validate a clean install in CI.
