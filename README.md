# Blackreach

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-7c3aed?style=flat-square&labelColor=07061a)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee?style=flat-square&labelColor=07061a)](LICENSE)
[![Version](https://img.shields.io/badge/version-v5.0.0--beta.1-9f6ff3?style=flat-square&labelColor=07061a)](https://github.com/Null-Phnix/Blackreach/releases)
[![Tests](https://img.shields.io/badge/tests-2%2C904_passing-4ade80?style=flat-square&labelColor=07061a)](tests/)

**Autonomous browser agent. Give it a goal, it handles the rest.**

![Blackreach Demo](assets/demo.gif)

```bash
blackreach run "download all Linear A inscription tables from sigla.phis.me"
```

Every autonomous web agent I tried worked on the demo site and fell apart on anything real. Cloudflare caught it in seconds. JavaScript-rendered content was invisible to it. Rate limit responses came back as 200 OK and the agent saved garbage, reported success, and moved on.

Blackreach is built for actual research tasks. Overnight runs. Academic databases. Sites that actively resist automation. 2,904 tests because agents that fail silently are worse than agents that don't run at all.

---

## How it works

Blackreach uses a **DOM walker** instead of raw HTML. A typical page is 50k–500k tokens of noise. The DOM walker extracts visible text, interactive elements, navigation landmarks, and ARIA roles. A 200k token page becomes a 2k token observation the LLM can actually reason about.

```
Thought: I need the inscription table on this page
Action: navigate("https://sigla.phis.me/")
Observation: Page loaded. Nav: [About, Database, Signs].
  Main: table, 847 rows, columns [ID, Site, Text, Image].
  Interactive: pagination controls, export button.
Thought: extract all rows and handle pagination
Action: extract_table(selector=".inscription-table", paginate=True)
```

The loop: **Observe** (DOM walker extracts page state) → **Think** (LLM reasons about next action) → **Act** (Playwright executes it) → repeat until done.

---

## Features

- **DOM Walker** — Live element extraction assigns numeric IDs to every interactive element. The LLM clicks `[15]`, not a CSS selector.
- **Stealth Playwright** — Patches `navigator.webdriver`, viewport signatures, input timing, and CDP artifacts before any page loads.
- **Session Resume** — Tasks auto-save on interrupt. Pick up exactly where you left off.
- **Smart Deduplication** — URL + hash checking. Never downloads the same file twice.
- **Stuck Detection** — Loop detection with automatic strategy switching and source failover.
- **Cross-Session Memory** — SQLite-backed. Remembers what worked per domain.
- **Multi-Provider** — Ollama (local), OpenAI, Anthropic, Google, xAI.

---

## Installation

```bash
pip install blackreach
```

**With specific providers:**
```bash
pip install "blackreach[openai]"
pip install "blackreach[anthropic]"
pip install "blackreach[all]"
```

**From source:**
```bash
git clone https://github.com/Null-Phnix/Blackreach
cd Blackreach
pip install -e .
```

**Install the browser (required):**
```bash
playwright install chromium
```

---

## Quick start

First run walks you through setup:
```bash
blackreach
```

Then:
```bash
# Run a task
blackreach run "find and download papers about attention mechanisms from arxiv"

# Headless
blackreach run --headless "download landscape wallpapers from unsplash"

# Specific provider/model
blackreach run -p anthropic -m claude-3-5-sonnet "download the pytorch README"

# Resume interrupted session
blackreach sessions
blackreach run --resume 42
```

---

## Commands

| Command | Description |
|---------|-------------|
| `blackreach` | Interactive mode |
| `blackreach run "goal"` | Run agent with goal |
| `blackreach run --resume ID` | Resume paused session |
| `blackreach sessions` | List resumable sessions |
| `blackreach config` | Configure settings and API keys |
| `blackreach models` | List available models |
| `blackreach stats` | Show performance metrics |
| `blackreach doctor` | Check system requirements |
| `blackreach health` | Check content source availability |
| `blackreach downloads` | Show download history |

**Interactive slash commands:**

| Command | Description |
|---------|-------------|
| `/model` `/m` | Switch model mid-session |
| `/provider` `/p` | Switch provider |
| `/plan "goal"` | Preview a plan without running |
| `/resume ID` | Resume a session |
| `/sessions` | List resumable sessions |
| `/status` `/s` | Show current config |
| `/quit` `/q` | Exit |

---

## Supported providers

| Provider | Type | Models |
|----------|------|--------|
| **Ollama** | Local | qwen2.5:7b, llama3.2:3b, mistral:7b |
| **Anthropic** | Cloud | claude-sonnet-4-6, claude-haiku-4-5 |
| **OpenAI** | Cloud | gpt-4o, gpt-4o-mini |
| **Google** | Cloud | gemini-2.5-pro, gemini-2.5-flash |
| **xAI** | Cloud | grok-2, grok-2-mini |

**Running fully local with Ollama:**
```bash
# Install Ollama: https://ollama.ai
ollama pull qwen2.5:7b
ollama serve
blackreach  # select Ollama on first run
```

---

## Configuration

Config file: `~/.blackreach/config.yaml`

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
export XAI_API_KEY="xai-..."
```

Or use `blackreach config` for interactive setup.

---

## Architecture

```
blackreach/
├── agent.py          # ReAct loop coordinator
├── browser.py        # Playwright control + stealth patches
├── dom_walker.py     # Live DOM extraction, [N] ID assignment
├── llm.py            # Multi-provider LLM integration
├── memory.py         # Session memory + SQLite persistence
├── detection.py      # CAPTCHA, login, paywall detection
├── stuck_detector.py # Loop detection and recovery
├── error_recovery.py # Error categorization and recovery
├── resilience.py     # Retry logic, circuit breaker
├── knowledge.py      # Content source knowledge base
├── config.py         # Configuration management
├── logging.py        # Structured session logging
├── ui.py             # Rich terminal UI
└── cli.py            # CLI entry point
```

---

## Why 2,904 tests

Every test came from a real failure. Rate limits returning 200 OK. Tables rendered by JavaScript two seconds after page load. Session tokens expiring mid-task. CAPTCHAs on page 3 but not pages 1 or 2. Login walls that only trigger from non-residential IPs.

2,904 tests means 2,904 things the world tried and got caught. When it runs at 3am downloading data, it needs to fail loud. Not silent.

---

## Troubleshooting

```bash
blackreach doctor    # check system requirements
```

**Browser not found:** `playwright install chromium`

**Bot detection (403/418 errors):**
- Run without `--headless`
- Try a different browser: `blackreach run -b firefox "goal"`
- Some sites require residential IPs regardless of stealth settings

**Session resume fails:** `blackreach sessions` to check if session still exists

---

## License

MIT. See [LICENSE](LICENSE).

---

Built by [phnix](https://phnix.dev). Issues and PRs welcome.
