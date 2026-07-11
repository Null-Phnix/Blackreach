# Blackreach Web-Tool Suite

> Architecture source of truth. Audit snapshot: 2026-07-11.

## Vision

Own the web execution and intelligence stack end to end: no Firecrawl bill, no
Browserbase session dependency, no search API key, and no opaque third-party
browser control plane. The suite should remain personal/self-hosted rather than
grow SaaS billing, tenancy, or fleet-management machinery.

That goal has four separate planes. Treating them as one feature is how false
"replacement complete" claims happen.

| Plane | Owner | Responsibility |
|---|---|---|
| Browser execution | StarSearch | Chromium lifecycle, fingerprints, stealth, humanized input, cookies, screenshots, SSRF/capability boundaries, session routing |
| Web data | Huginn | Search, scrape, crawl, map, batch, extraction, cache, jobs, streaming, replay, throttling |
| Agent decisions | Blackreach | Goal planning, interactive browsing, recovery, downloads, research workflows |
| Egress | Not complete | Proxy inventory, health, rotation, sticky sessions, geography, and IP reputation |

MCP servers and HTTP wrappers are adapters. They must not grow their own browser
implementation or independent search policy.

## Request flow

```text
MCP / CLI / application
        |
        +-- structured web operation --> Huginn :7432
        |                                  |
        |                                  +--> StarSearch :7676 --> Bing/site
        |                                  +--> Playwright only for an explicitly
        |                                       unsupported StarSearch option
        |
        +-- autonomous interaction ------> Blackreach :7434
                                           |
                                           +--> Huginn for search/data operations
                                           +--> StarSearch for interactive Hand
```

Rules:

1. Huginn is the data-plane gateway. Blackreach does not maintain a competing
   primary search stack.
2. StarSearch is the browser product boundary. A stealth setup failure fails
   closed; it must never silently become a naked automated Chromium session.
3. A returned `ScrapeData` with `status_code >= 400` is a failure. It is not
   cacheable, crawlable, or countable as a completed page.
4. Cache identity includes every option that changes output. Stateful requests
   (actions, cookies, custom headers, extraction, change tracking) do not cache.
5. Unsupported options fall back explicitly and are documented. They are never
   silently discarded.
6. Public listeners stay on loopback unless authentication is deliberately
   added. StarSearch TCP rejects non-loopback binds.
7. Tests must select a backend explicitly. A developer daemon must not change
   unit-test behavior at import time.

## Current validated state

### StarSearch

- Unix and loopback TCP JSON-lines transports with a required handshake.
- Request-scoped sessions, navigation, content, click/type/hover/scroll,
  evaluate, waits, screenshots, and cookies.
- Fingerprint/profile selection and stealth setup fail closed.
- `navigator.webdriver` is absent/undefined, not `false`.
- User-Agent and Client Hints are applied through the correct CDP emulation
  domain.
- SSRF protection allows safe non-network fixtures (`about:blank`, `data:`) and
  rejects local, private, link-local, shared, documentation, multicast, and
  reserved address ranges by default. DNS availability errors have a distinct
  wire error and are no longer misreported as attacks.
- Configurable socket path, live capacity status, five-process real capacity,
  and wired cross-daemon session forwarding.
- Builds use committed fingerprint data. Network refresh requires the explicit
  `STARSEARCH_REFRESH_PROFILES=1` build flag.
- The user service can opt into an isolated resolver view. This repaired the
  live machine's broken router DNS without changing host-wide network settings.
- The signed installer now targets `Null-Phnix/StarSearch`, re-verifies an
  existing binary, and replaces it only after an atomic verified download.
  There are currently no published release assets and no repository Actions
  secrets configured, so source build/install is still the working deployment
  path. A signing key must be provisioned deliberately before the first release.

### Huginn

- StarSearch is primary for browser-rendered scrape and search; `render_mode=light`
  is the explicit plain-HTTP opt-out.
- Actions, waits, scroll, cookies, selectors, screenshots, proxy server, locale,
  timeouts, and daemon errors traverse the StarSearch protocol.
- Action enums are serialized to their JSON values at both API boundaries;
  supported actions no longer silently fall back to Playwright.
- Custom headers, mobile emulation, ad interception, and strict TLS currently
  use the Playwright fallback because StarSearch does not yet expose those
  controls.
- Failed scrape results are not cached, do not reset circuit breakers, and are
  not counted by batch or crawl.
- Crawl forwards all `scrapeOptions`, enforces `robots.txt` unless ignored, and
  streams each page as it completes.
- `/v1/flock` remains a synchronous native batch endpoint. The Firecrawl-style
  `/v1/batch/scrape` alias is an asynchronous job with status and cancellation.
- MCP job IDs, search limits, and synchronous flock behavior match the REST API.
- Health/readiness reports live StarSearch reachability and session capacity.
- `HUGINN_DATA_DIR` now drives the derived SQLite path; jobs, replay data, and
  research memory land on the `/data` volume instead of disappearing from
  `/root/.huginn` when the container is recreated.

### Blackreach

- Browser selection is controlled by `BLACKREACH_BROWSER_BACKEND=auto|starsearch|playwright`.
  Importing the module no longer creates a probe session.
- The production unit pins `starsearch` and explicit mode fails closed if it
  cannot load; `auto` is a developer convenience, not the production policy.
- Huginn is primary search; direct StarSearch/Bing is the availability fallback.
- Both HTTP entrypoints forward caller `start_url`, limits, and runtime options.
- StarSearch JavaScript shims encode user strings as data rather than interpolating
  raw selectors/text into scripts.
- The persistent HTTP worker closes browser/API resources after every job, uses
  a blocking queue, validates limits, and bounds retained jobs/screenshots.

## Replacement boundary: honest assessment

### Firecrawl

Huginn replaces the calls used locally today: single scrape, crawl, map, search,
batch, extraction, streaming, and change tracking. It is not full current
Firecrawl v2 parity. Missing or incomplete surfaces include the complete v2
request/response schema, batch pagination/advanced controls, persistent profiles,
interactive scrape sessions, and some advanced actions/extraction modes.

Reference: [Firecrawl v2 API](https://docs.firecrawl.dev/api-reference/v2-introduction)

### Browserbase

StarSearch replaces the need for a managed browser during local Blackreach and
Huginn execution. It does not yet provide a Browserbase-compatible remote CDP
connect URL, HTTP session lifecycle API, context persistence API, session replay,
or fleet autoscaling.

Reference: [Browserbase session API](https://docs.browserbase.com/reference/api/create-a-session)

### Proxy services

This is not replaced yet. StarSearch can launch through a supplied proxy and
Huginn can forward configured proxy credentials, but the suite does not create
fresh public IPs. Anti-detect fingerprints do not change network reputation.
An owned egress plane still needs proxy inventory, health scoring, rotation,
sticky sessions, geography verification, and an intentional source of IPs.

Reference: [Browserbase proxies](https://docs.browserbase.com/platform/identity/proxies)

## Ports and configuration

| Service | Bind | Key configuration |
|---|---|---|
| StarSearch | Unix socket + `127.0.0.1:7676` | `STARSEARCH_SOCKET_PATH`, `STARSEARCH_TCP_ADDR`, optional `~/.config/starsearch/resolver/` |
| Huginn | `127.0.0.1:7432` | `HUGINN_STARSEARCH_TCP`, `HUGINN_BROWSER_BACKEND`, `HUGINN_PROXY_*`, `HUGINN_DNS_PRIMARY`, `HUGINN_DNS_SECONDARY` |
| Blackreach HTTP | `127.0.0.1:7434` | `BLACKREACH_BROWSER_BACKEND`, `BLACKREACH_HUMAN_LEVEL`, `BLACKREACH_MAX_RETAINED_JOBS` |

## Roadmap in dependency order

1. **Request-level network policy:** enforce destination policy for redirects
   and subresources at the browser/egress boundary. The current URL preflight is
   useful but cannot, by itself, eliminate DNS-rebinding time-of-check/time-of-use
   risk.
2. **Protocol controls:** add StarSearch session commands/options for extra HTTP
   headers, mobile viewport/device hints, request blocking, strict TLS, and
   authenticated proxy URLs. Remove Playwright fallback one capability at a time.
3. **Egress plane:** define a `ProxyLease` contract, persistent health/reputation
   store, sticky domain sessions, location verification, and safe credential
   storage. Bring-your-own endpoints first; owned IP supply is a separate infra
   decision.
4. **Browserbase-compatible gateway:** expose authenticated HTTP session create,
   inspect, close, keep-alive, and a remote CDP/WebSocket connection boundary.
   Map those sessions onto StarSearch rather than adding another browser.
5. **Firecrawl v2 contract suite:** vendor the official OpenAPI schema as a test
   fixture, produce a machine-readable diff, and implement only the calls used by
   local consumers first.
6. **Search resilience:** add at least one StarSearch-rendered engine fallback,
   engine health scoring, and result-quality fixtures. Keep keys optional, never
   required.
7. **Session durability:** context persistence, crash recovery, replay artifacts,
   and bounded storage lifecycle.
8. **Release pipeline:** publish signed StarSearch assets from the current
   private repository and exercise a clean authenticated install in CI.
9. **Retire duplicate browser code:** turn the separate `blackreach-mcp` browser
   into a thin gateway client or archive it after consumers migrate.

## Verification snapshot

- StarSearch: 164 Rust tests; 71 Python client/integration tests.
- Huginn: 809 passed; 6 explicitly deselected integration cases.
- Blackreach: 3,046 passed in 339.43 seconds (full run).

Live checks on the installed services:

| Contract | Result |
|---|---|
| StarSearch status | v0.2.0, 5/5 slots available after work |
| Huginn full scrape | `example.com`, HTTP 200, `render_mode=starsearch` |
| Actions + screenshot | selector wait and scroll stayed on StarSearch; PNG returned |
| Cache | second identical stateless scrape returned `cached=true` |
| SSRF | loopback target rejected before either browser backend |
| Search | 3/3 results through Huginn → StarSearch → Bing |
| Blackreach search | 3/3 results, source `huginn-starsearch` |
| Async batch and crawl | both completed 1/1 through StarSearch |
| Container persistence | completed batch job remained queryable after recreate |

The snapshot is evidence for this audit, not a permanent badge. CI is the source
of truth after the next change.
