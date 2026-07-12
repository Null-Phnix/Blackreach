# Blackreach Web-Tool Suite

> Architecture and operations source of truth. Validated 2026-07-12 EDT.

## Contract

The suite is a local-first web execution and intelligence stack for Josii's
agent fleet. It replaces the locally useful Firecrawl and managed-browser calls
without claiming infrastructure that is not present.

| Layer | Sole responsibility |
| --- | --- |
| Blackreach | Goal-driven planning, interaction, recovery, downloads, and agent jobs |
| Huginn / BlackCrawl | Deterministic search, scrape, crawl, map, extraction, batch, cache, replay, schedules, and durable jobs |
| StarSearch | Browser/session lifecycle, fingerprints, humanized input, screenshots, request policy, and browser capacity |
| blackreach-mcp | Thin MCP schemas, authentication, transport errors, and bounded job polling |
| Huginn egress provider | Direct-vs-proxied policy, proxy leases, rotation/stickiness, health, and cooldown |

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
   direct host egress OR a configured real proxy lease
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
7. Stealth changes browser-visible identity. It never implies a new IP,
   residential egress, geolocation, or proxy reputation.

## Stable API and MCP surface

### Huginn REST

| Capability | Start/status routes | Notes |
| --- | --- | --- |
| Search | `POST /v1/search` (`/v1/seek`) | StarSearch-rendered Bing is the keyless primary engine |
| Scrape | `POST /v1/scrape` (`/v1/probe`) | Markdown, HTML, raw HTML, links, metadata, screenshot, actions, retries, cache |
| Crawl | `POST /v1/crawl`, `GET /v1/crawl/{id}` | Durable SQLite job, progress, cancellation, JSONL/SSE support |
| Batch scrape | `POST /v1/batch/scrape`, `GET /v1/batch/scrape/{id}` | Durable job IDs and partial results; `/v1/flock` remains synchronous |
| Extract | `POST /v1/extract`, `GET /v1/extract/{id}` | Scrape plus schema/prompt/template extraction |
| Browser sessions | `POST/GET /v1/browser/sessions` | Authenticated StarSearch lifecycle |
| Browser command | `POST /v1/browser/sessions/{id}/commands` | Navigate, click, type, scroll, hover, wait, screenshot, content, JS, cookies, history |
| Browser close | `DELETE /v1/browser/sessions/{id}` | Idempotent close and capacity release |
| Health | `/health`, `/health/ready`, `/health/detailed` | StarSearch capacity plus explicit egress mode/health |
| Metrics | `/v1/metrics` | Per-endpoint count, latency, and success rate |

Data-bearing routes require `Authorization: Bearer ...` when the deployment key
is configured. Basic health/liveness remains probeable; detailed health and
metrics require the key.

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
- typed lifecycle and commands, idle expiry, domain allowlists, cookies, and
  optional per-session proxy routing;
- stealth/fingerprint setup fails closed;
- authenticated HTTP proxy credentials cross the Huginn-to-StarSearch protocol
  as structured fields and are handled through Chromium authentication;
- daemon restart invalidates old session IDs cleanly and returns capacity for
  new sessions.

Network policy checks the top-level URL and every Chromium request paused by
CDP Fetch, including redirects and subresources. It rejects local/private,
link-local, metadata, carrier-grade NAT, documentation, benchmark, multicast,
and reserved destinations by default. `file:`, `javascript:`, and other unsafe
schemes remain forbidden; `about:blank` and `data:` are allowed only as
non-network documents. Internal access requires both server policy and an
explicit session request.

This materially narrows SSRF and redirect bypasses, but it is not a claim that
DNS rebinding is mathematically eliminated: resolution and Chromium's eventual
connection are still separate operations. A future socket-level egress proxy
or browser network service is the stronger enforcement boundary.

## Real proxy boundary

Default health reports:

```json
{
  "mode": "direct",
  "configured": false,
  "direct_egress": true,
  "endpoints": 0
}
```

That means the host's public IP is in use. To bring real proxy endpoints:

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
It does not supply IPs, test residential reputation, or guarantee geography;
endpoint procurement remains an infrastructure decision.

## Deployment configuration

| Service | Bind | Required production settings |
| --- | --- | --- |
| StarSearch | Unix + `127.0.0.1:7676` | `STARSEARCH_TCP_ADDR`, `STARSEARCH_TCP_TOKEN_FILE` |
| Huginn | `127.0.0.1:7432` | `HUGINN_API_KEY_FILE`, `HUGINN_STARSEARCH_TCP`, `HUGINN_STARSEARCH_TOKEN_FILE`, `HUGINN_BROWSER_BACKEND=starsearch` |
| Blackreach | `127.0.0.1:7434` | `BLACKREACH_API_KEY_FILE`, `HUGINN_API_KEY_FILE`, `BLACKREACH_JOB_STATE_FILE`, `BLACKREACH_BROWSER_BACKEND=starsearch` |
| blackreach-mcp | stdio | base URLs plus key files; defaults point at `~/.config/...` |

Current secret files:

```text
~/.config/starsearch/tcp-token
~/.config/huginn/api-key
~/.config/blackreach/api-key
```

All are local, mode `0600`, excluded from Git, and mounted/read by path rather
than copied into images or process arguments.

Huginn state lives in the named `huginn-data` volume at `/data/huginn.db`.
Jobs, replay data, scheduler state, cache metadata, and research memory survive
container recreation. StarSearch fingerprint profile data remains in its
dedicated repository and must never be discarded during deployment.

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

An MCP deep doctor probe distinguishes service reachability from usable public
DNS/navigation. If it returns `DNSResolutionFailed`, verify the host resolver
with `resolvectl query <probe-host>` before restarting browser services;
StarSearch intentionally does not bypass or silently replace host DNS policy.

## Validated installed state

Automated suites after the final runtime change:

- StarSearch: 166 Rust tests and 72 Python tests.
- Huginn: 834 passed, 6 explicitly deselected integration cases.
- Blackreach: 3,055 passed in the full repository suite.
- blackreach-mcp: TypeScript build, 6 client/config tests, one routed-tool/deep
  doctor integration test, real stdio MCP `tools/list` smoke, and zero npm
  audit findings.

Live evidence from the rebuilt services:

| Contract | Proof |
| --- | --- |
| Authentication | missing/wrong StarSearch TCP token rejected; unauthenticated Huginn/Blackreach data routes returned 401 |
| Search | 3 results for Prometheus through Huginn to StarSearch/Bing; first host `prometheus.io` |
| Explicit scrape | `https://prometheus.io/`, title and H1 extracted, explicit `render_mode=starsearch` |
| Actions/screenshot | selector wait plus scroll completed; valid 71,252-character base64 PNG returned |
| Cache | unique first request `cached=false`, second `cached=true` |
| Egress truth | metadata reported `mode=direct`, `proxied=false`, endpoint null |
| SSRF | top-level loopback rejected; data-page subresource and public HTTP redirect produced zero hits on a live loopback canary |
| Browser lifecycle | create/navigate/evaluate/close passed; five slots filled, sixth rejected, all five recovered |
| Crash recovery | stale session returned `SessionNotFound` after daemon restart; new session succeeded with 5/5 available |
| Batch/crawl | batch completed 2/2; crawl extracted `Example Domain` |
| Persistence | completed 2/2 batch `afe95c30-ed3b-4d3d-b395-c8975d987833` remained queryable after container restart |
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
actions. Extraction quality also depends on the configured local/remote LLM.

Reference: [Firecrawl v2 API](https://docs.firecrawl.dev/api-reference/v2-introduction)

### Browserbase

The suite now has authenticated local HTTP session lifecycle, isolated browser
processes, capacity limits, per-session proxy routing, typed commands, cookies,
screenshots, health, and daemon restart behavior. It does not expose a public
CDP/WebSocket connection URL, durable named contexts, hosted live-view/debug
URLs, session replay artifacts, multi-host scheduling, autoscaling, or managed
proxy networks. Those are the honest Browserbase boundary.

Reference: [Browserbase session API](https://docs.browserbase.com/reference/api/create-a-session)

### Highest-leverage next slices

1. Persist named StarSearch contexts and encrypted cookie state across daemon restart.
2. Put DNS and socket connection policy behind one owned egress gateway to close the remaining rebinding gap.
3. Add a controlled CDP/WebSocket gateway only if Anubis/Herdr truly need third-party browser attachment.
4. Generate a machine-readable Firecrawl v2 contract diff and implement only consumer-visible gaps.
5. Add search-engine health scoring and a second StarSearch-rendered keyless engine.
6. Publish signed StarSearch release artifacts and validate a clean install in CI.
