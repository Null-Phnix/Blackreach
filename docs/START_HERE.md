# Start Here — Blackreach Web-Tool Suite

Blackreach is the goal-driven orchestrator. For search, scrape, crawl,
extraction, batch jobs, caching, screenshots, and browser-session lifecycle,
agents should call `blackreach-mcp`, which routes deterministic work through
Huginn and browser execution through StarSearch.

Read [WEB_TOOL_SUITE.md](WEB_TOOL_SUITE.md) first. It is the ground-truth
architecture, route, environment, security, deployment, validation, and
remaining-boundary document.

## Verify the installed suite

```bash
systemctl --user status starsearch-daemon blackreach-http
docker compose -f /mnt/WorkDrive/AI_Projects/BlackCrawl/docker-compose.yml ps
curl --fail http://127.0.0.1:7432/health/ready
curl --fail http://127.0.0.1:7434/health
cd /mnt/WorkDrive/AI_Projects/blackreach-mcp && npm run check
```

## Develop Blackreach

```bash
cd /mnt/WorkDrive/AI_Projects/Blackreach
uv sync --locked --extra dev --extra server
uv pip install --python .venv -e /mnt/WorkDrive/AI_Projects/Project_StarSearch/client
.venv/bin/pytest -q
```

Production sets `BLACKREACH_BROWSER_BACKEND=starsearch`. An explicit
`start_url` must be honored exactly. If StarSearch is unavailable, explicit
production mode fails closed instead of weakening to a different browser.

## Give agents one entry point

Register only:

```text
node /mnt/WorkDrive/AI_Projects/blackreach-mcp/dist/index.js
```

The older per-repository Python MCP servers are compatibility code, not the
installed agent surface.
