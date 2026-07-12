# Blackreach

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-7c3aed?style=flat-square&labelColor=07061a)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee?style=flat-square&labelColor=07061a)](LICENSE)
[![Version](https://img.shields.io/badge/version-v5.0.0--beta.2-9f6ff3?style=flat-square&labelColor=07061a)](https://github.com/Null-Phnix/Blackreach/releases)
[![Tests](https://img.shields.io/badge/tests-3%2C053_passing-4ade80?style=flat-square&labelColor=07061a)](tests/)

**The goal-driven browser orchestrator in a local-first web-tool suite.**

Blackreach accepts an objective, observes a real page, chooses typed browser
actions, and reports a durable job result. It no longer tries to own every web
capability:

| Component | Responsibility |
|---|---|
| **Blackreach** | Goal decomposition, ReAct loop, recovery, memory, and agent jobs |
| **Huginn / BlackCrawl** | Deterministic search, scrape, crawl, extract, batch, cache, and job API |
| **StarSearch** | Shared stealth browser runtime, authenticated sessions, and capacity |
| **blackreach-mcp** | Stable MCP adapter for Hermes, Claude, Codex, and future agents |

The complete architecture, routes, environment, runbook, live validation, and
honest replacement boundary are in [docs/WEB_TOOL_SUITE.md](docs/WEB_TOOL_SUITE.md).

## Production request path

```text
MCP client
    │
    ▼
blackreach-mcp
    ├── deterministic operation ──▶ Huginn ──▶ StarSearch
    └── goal-driven browse ───────▶ Blackreach ──▶ StarSearch
```

Blackreach delegates deterministic work to Huginn. The agent browser backend
is StarSearch in production and fails closed if its client/runtime is missing.
Playwright remains an explicit development compatibility backend; it is not a
silent production fallback.

An explicit `start_url` is forwarded unchanged and visited directly. It is
never replaced with a search page or unrelated default target.

## What the agent does

- Converts a goal into an observe → reason → act loop.
- Uses a compact DOM observation rather than feeding raw page HTML to the LLM.
- Executes navigation, click, type, scroll, wait, extraction, download, and
  screenshot work through StarSearch's shared pool.
- Detects stuck loops, blocked pages, invalid actions, and unhealthy sessions.
- Persists agent session state and exposes asynchronous jobs on loopback.
- Supports local Ollama plus optional hosted LLM providers for reasoning.

Search, scraping, crawling, batch work, screenshots, browser sessions, and
structured extraction schemas are exposed through Huginn and `blackreach-mcp`,
not duplicated inside the orchestrator.

## Install for development

```bash
git clone https://github.com/Null-Phnix/Blackreach.git
cd Blackreach
uv sync --locked --extra dev --extra server
```

For the production backend, also install the sibling StarSearch Python client
into this environment and start the authenticated daemon. The suite runbook
contains the exact dependency order and service files.

```bash
uv pip install --python .venv -e /mnt/WorkDrive/AI_Projects/Project_StarSearch/client
.venv/bin/pytest -q
```

## CLI

```bash
blackreach setup
blackreach doctor
blackreach run "collect the titles from the first page" --steps 20
blackreach run "summarize this page" --steps 10
blackreach sessions
blackreach run --resume 42
```

Useful commands:

| Command | Purpose |
|---|---|
| `blackreach run "goal"` | Run the goal-driven agent |
| `blackreach doctor` | Diagnose model, browser, and local dependencies |
| `blackreach validate` | Validate configuration |
| `blackreach sessions` / `resumable` | Inspect or resume agent state |
| `blackreach scancode URL` | Preview routing for a URL |
| `blackreach stats` / `logs` | Inspect agent behavior |
| `blackreach serve` | Development REST surface on port 7433 |

The CLI can deliberately select Playwright for isolated development. The
installed suite service sets `BLACKREACH_BROWSER_BACKEND=starsearch`.

## Production service

The asynchronous agent gateway binds `127.0.0.1:7434`:

```bash
install -m 644 deploy/systemd/blackreach-http.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now blackreach-http
curl --fail http://127.0.0.1:7434/health
```

Data-bearing routes require the bearer key in
`~/.config/blackreach/api-key` when installed with the supplied unit.
Retained jobs are atomically journaled under
`~/.local/state/blackreach/jobs.json`; interrupted jobs become explicit
`service_restarted` failures on recovery.

| Route | Purpose |
|---|---|
| `POST /browse` | Submit a goal and optional explicit `start_url` |
| `GET /jobs/{job_id}` | Poll a durable agent result |
| `GET /jobs` | List retained jobs |
| `GET /jobs/{job_id}/screenshots` | List step screenshots |
| `GET /jobs/{job_id}/screenshots/{name}` | Fetch a screenshot safely |
| `GET /health` | Probe liveness without exposing job data |

## One MCP surface

Build and register only the Node adapter:

```bash
cd /mnt/WorkDrive/AI_Projects/blackreach-mcp
npm ci
npm run check
```

```json
{
  "mcpServers": {
    "blackreach_web": {
      "command": "node",
      "args": ["/mnt/WorkDrive/AI_Projects/blackreach-mcp/dist/index.js"]
    }
  }
}
```

Do not register the legacy Blackreach or BlackCrawl Python MCP servers beside
this adapter. `blackreach-mcp` already exposes the orchestrator plus every
deterministic Huginn capability with consistent schemas, job IDs, trace data,
and structured errors.

## Security and egress

- Installed services bind loopback and use key files rather than secrets in
  process arguments.
- Huginn and StarSearch enforce HTTP(S)-only navigation plus private-network,
  redirect, and browser-subresource policy.
- StarSearch capacity is bounded; crashes invalidate stale sessions and free
  capacity for new work.
- StarSearch changes fingerprint signals. It does **not** change the host IP,
  supply residential egress, or create geographic routing.
- Proxy routing is configured in Huginn. `direct` means the host's real egress;
  configured proxy failures do not silently fall back to direct.

## Honest boundary

The suite implements the useful local vertical slice: search, scrape, crawl,
extract, screenshots, batch jobs, progress, caching, typed browser sessions,
proxy leases, observability, and goal-driven browsing. It does not claim full
Firecrawl wire compatibility or Browserbase parity. There is no managed proxy
network, multi-host scheduler, public live-view URL, durable remote CDP
context, or complete DNS-rebinding defense yet.

## Troubleshooting

```bash
systemctl --user status starsearch-daemon blackreach-http
curl --fail http://127.0.0.1:7432/health/ready
curl --fail http://127.0.0.1:7434/health
cd /mnt/WorkDrive/AI_Projects/blackreach-mcp && npm run check
```

- `BrowserNotReadyError`: install the StarSearch client and verify its daemon.
- Huginn reports `egress.mode=direct`: no proxy provider is configured; this is
  truthful local egress, not rotation.
- Explicit StarSearch mode never falls back silently. Repair the daemon or
  deliberately opt into a development backend.

## License

MIT. See [LICENSE](LICENSE).
