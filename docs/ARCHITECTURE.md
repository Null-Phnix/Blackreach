# Project Blackreach

> General-purpose autonomous browser agent. No configs. No restrictions. Just a goal.

**Lineage:** Evolved from Ghost Hand (mythology scraper) into a universal web agent.

---

## Vision

```bash
blackreach "download the top 20 state space model papers with code from 2024"
```

```bash
blackreach "find and save all free courses on transformer architecture"
```

```bash
blackreach "scrape every recipe from this cooking blog into markdown"
```

One command. Agent figures out where to go, how to navigate, what to download.

---

## Core Principles

1. **No hardcoded sites** — Agent discovers where to go based on the goal
2. **No config files** — Goal is the only input
3. **Local models** — Untethered, no API refusals
4. **Resilient** — Recovers from failures, adapts strategy
5. **Memory** — Remembers what it's done across sessions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         GOAL                                │
│        "download papers on state space models"              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      PLANNER                                │
│                                                             │
│  • Breaks goal into subtasks                                │
│  • Suggests starting points (arxiv? google scholar?)        │
│  • Can use smarter model (planning isn't "doing")           │
│                                                             │
│  Output: ["search arxiv for SSM papers",                    │
│           "check paperswithcode for implementations",       │
│           "look for github repos"]                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    REACT LOOP                               │
│                   (local model)                             │
│                                                             │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│    │ OBSERVE  │ →  │  THINK   │ →  │   ACT    │            │
│    └────┬─────┘    └──────────┘    └────┬─────┘            │
│         │                               │                   │
│         └───────────────────────────────┘                   │
│                     (repeat)                                │
│                                                             │
│  OBSERVE: What's on the page? What elements exist?          │
│  THINK: What should I do next? Why?                         │
│  ACT: click(), type(), scroll(), download(), navigate()     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      MEMORY                                 │
│                                                             │
│  SessionMemory:                                             │
│    • downloaded_urls: set                                   │
│    • visited_pages: set                                     │
│    • successful_actions: list                               │
│    • failed_actions: list                                   │
│                                                             │
│  PersistentMemory (SQLite):                                 │
│    • All downloads ever (dedup across sessions)             │
│    • Site navigation patterns that worked                   │
│    • Common failure modes and recoveries                    │
└─────────────────────────────────────────────────────────────┘
```

---

## ReAct Loop Detail

Each iteration is three focused prompts:

### 1. OBSERVE
```
You are looking at: {page_title}
URL: {current_url}

Visible elements:
{element_list}

Page content summary:
{text_summary}

Describe what you see in 2-3 sentences.
```

### 2. THINK
```
GOAL: {user_goal}
OBSERVATION: {observation}
HISTORY: {last_5_actions}
MEMORY: Downloaded {n} files. Visited {m} pages. Last failure: {failure}

What should you do next to make progress toward the goal?
Respond in 1-2 sentences explaining your reasoning.
```

### 3. ACT
```
You decided: {thought}

Available actions:
- click(selector) — Click an element
- type(selector, text) — Type into input
- scroll(direction) — Scroll up/down
- navigate(url) — Go to URL
- download(url) — Download a file
- extract(selector) — Save text content
- screenshot() — Save current view
- back() — Go back
- done(reason) — Task complete

Output your action as JSON:
{"action": "click", "selector": "a.download-btn", "reason": "Download PDF link found"}
```

---

## File Structure

```
Blackreach/
├── blackreach/
│   ├── __init__.py
│   ├── cli.py              # Entry point
│   ├── agent.py            # Main agent loop
│   ├── planner.py          # Goal → subtasks
│   ├── observer.py         # Page analysis
│   ├── thinker.py          # Reasoning step
│   ├── actor.py            # Action execution
│   ├── memory.py           # Session + persistent memory
│   ├── browser.py          # Playwright wrapper
│   └── llm.py              # Ollama integration
│
├── prompts/
│   ├── observe.txt
│   ├── think.txt
│   ├── act.txt
│   └── plan.txt
│
├── downloads/              # Default download location
├── memory.db               # SQLite persistent memory
├── config.yaml             # Optional overrides (model, timeouts)
├── requirements.txt
└── README.md
```

---

## Models

### Recommended Local Models (via Ollama)

| Model | VRAM | Reasoning | Speed |
|-------|------|-----------|-------|
| qwen2.5:32b-instruct | ~20GB | Great | Medium |
| qwen2.5:14b-instruct | ~10GB | Good | Fast |
| deepseek-v3:70b-q4 | ~40GB | Excellent | Slow |
| llama3.3:70b-q4 | ~40GB | Good | Medium |
| mistral-small:22b | ~14GB | Good | Fast |

### Hybrid Option
- **Planner:** Claude API (planning isn't restricted)
- **Executor:** Local model (unrestricted)

---

## Actions Reference

| Action | Description | Example |
|--------|-------------|---------|
| `click(selector)` | Click element | `click("a.download")` |
| `type(selector, text)` | Type in input | `type("#search", "SSM papers")` |
| `scroll(dir, amount)` | Scroll page | `scroll("down", 500)` |
| `navigate(url)` | Go to URL | `navigate("https://arxiv.org")` |
| `download(url)` | Download file | `download("paper.pdf")` |
| `extract(selector)` | Save text | `extract("article.content")` |
| `back()` | Browser back | `back()` |
| `wait(seconds)` | Pause | `wait(2)` |
| `done(reason)` | Complete task | `done("Downloaded 20 papers")` |

---

## Recovery Strategies

When things go wrong:

### CAPTCHA Detected
```
1. Screenshot for human review
2. Wait and retry
3. Try different site
```

### Login Wall
```
1. Check if content accessible elsewhere
2. Navigate around (direct PDF links often work)
3. Mark site as requiring auth, move on
```

### Rate Limited
```
1. Exponential backoff
2. Switch to different source
3. Resume later from memory
```

### Element Not Found
```
1. Re-observe page (maybe it loaded late)
2. Try alternative selectors
3. Scroll to reveal hidden content
```

---

## Example Run

```bash
$ blackreach "download 5 papers about mamba state space models"

🎯 Goal: download 5 papers about mamba state space models

📋 Planning...
   Subtasks:
   1. Search arxiv for "mamba state space model"
   2. Download top results with PDF links
   3. Check paperswithcode for implementations

🌐 Starting browser...

[Step 1] OBSERVE: Google homepage loaded
[Step 1] THINK: Need to go to arxiv.org to find academic papers
[Step 1] ACT: navigate("https://arxiv.org")

[Step 2] OBSERVE: Arxiv homepage with search box
[Step 2] THINK: Should search for mamba state space papers
[Step 2] ACT: type("#search-query", "mamba state space model")

[Step 3] OBSERVE: Search results showing 47 papers
[Step 3] THINK: First result looks relevant, has PDF link
[Step 3] ACT: click("a.pdf-link")

[Step 4] OBSERVE: PDF loading
[Step 4] THINK: Download this PDF
[Step 4] ACT: download("https://arxiv.org/pdf/2312.00752.pdf")
         ✓ Downloaded: mamba_architecture.pdf (1/5)

... continues ...

[Step 18] THINK: Have 5 papers now, goal complete
[Step 18] ACT: done("Downloaded 5 mamba SSM papers")

✅ Complete!
📥 Downloaded 5 files to ./downloads/
💾 Memory saved
```

---

## Migration from Ghost Hand

What to keep:
- Playwright browser setup
- Download handling
- Basic agent loop structure

What to change:
- Remove mythology-specific code
- Remove hardcoded site strategies
- Add ReAct prompt structure
- Add planner step
- Improve memory/recovery
- Switch to local model by default

---

## Development Phases

### Phase 1: Core Loop (Week 1)
- [ ] Basic ReAct loop working
- [ ] Single goal → completion
- [ ] Local model integration
- [ ] Simple memory (session only)

### Phase 2: Intelligence (Week 2)
- [ ] Planner for complex goals
- [ ] Better observation (element detection)
- [ ] Recovery strategies
- [ ] Persistent memory

### Phase 3: Polish (Week 3)
- [ ] CLI with nice output
- [ ] Config file support
- [ ] Multiple concurrent tasks
- [ ] Progress saving/resuming

---

## Why "Blackreach"?

From Elder Scrolls — a massive underground realm hidden beneath Skyrim.

A place that exists below the surface, where you can find things that aren't supposed to be found.

Fitting.
