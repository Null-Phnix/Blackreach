# Blackreach Foundations
## What You Need to Know Before Reading the Code

---

## What is Blackreach?

Blackreach is an **autonomous browser agent**. You give it a goal in plain English, and it:
1. Opens a browser
2. Figures out where to go
3. Navigates, clicks, types, downloads
4. Reports back when done

```bash
blackreach "download the top 5 papers on transformers from arxiv"
# Agent opens browser, goes to arxiv, searches, downloads PDFs
```

---

## Why Does This Exist?

You built Ghost Hand to collect mythology texts. But Ghost Hand was **hardcoded for mythology** — it knew about sacred-texts.com, gutenberg.org, and had prompts like "find Norse mythology PDFs."

Blackreach is Ghost Hand **generalized**. Same core tech, but it can do *anything*:
- Download research papers
- Scrape recipes
- Find free courses
- Collect any data from the web

---

## The Core Concept: ReAct

Blackreach uses the **ReAct pattern** (Reasoning + Acting). This is how most modern AI agents work.

```
┌─────────────┐
│   OBSERVE   │  ← "What do I see on this page?"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    THINK    │  ← "What should I do next to reach my goal?"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     ACT     │  ← "Execute: click this button / type this text"
└──────┬──────┘
       │
       └──────→ (repeat until goal achieved)
```

Each step:
1. **OBSERVE**: Parse the webpage, extract text, links, buttons, inputs
2. **THINK**: Ask the LLM "given what I see, what should I do next?"
3. **ACT**: Execute the action (click, type, navigate, etc.)

---

## The Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Browser Control | **Playwright** | Automates Chrome/Firefox |
| HTML Parsing | **BeautifulSoup** | Extracts text/links from pages |
| LLM | **Ollama** (local) | The "brain" that decides actions |
| Stealth | Custom scripts | Avoids bot detection |

### Why Playwright?

Playwright is a browser automation library. It can:
- Open browsers (headless or visible)
- Click buttons, fill forms
- Wait for pages to load
- Take screenshots
- Download files

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://google.com")
    page.fill("input[name=q]", "cats")
    page.click("input[type=submit]")
```

### Why Ollama?

Ollama runs LLMs locally on your machine. No API costs, no rate limits, no censorship.

```python
import ollama

response = ollama.chat(
    model="qwen2.5:7b",
    messages=[{"role": "user", "content": "What is 2+2?"}]
)
print(response["message"]["content"])  # "4"
```

---

## File Structure Explained

```
Blackreach/
├── blackreach/              # The Python package
│   ├── __init__.py          # Makes it importable
│   ├── agent.py             # THE MAIN FILE - ReAct loop lives here
│   ├── browser.py           # Playwright wrapper (click, type, scroll)
│   ├── observer.py          # HTML → structured data
│   ├── llm.py               # Talk to Ollama/OpenAI/etc
│   ├── stealth.py           # Anti-bot-detection
│   └── resilience.py        # Error handling, retries
│
├── prompts/                 # Text templates for the LLM
│   ├── observe.txt          # "Describe what you see"
│   ├── think.txt            # "What should I do next?"
│   └── act.txt              # "Output a JSON action"
│
├── learning/                # YOU ARE HERE - docs explaining everything
├── downloads/               # Where downloaded files go
├── blackreach.py            # Entry point (runs cli.py)
└── requirements.txt         # Python dependencies
```

---

## How Data Flows

```
User: "go to wikipedia and search for cats"
                    │
                    ▼
┌─────────────────────────────────────────┐
│              cli.py                      │
│  Parses command line args               │
│  Creates Agent with config              │
└─────────────────────┬───────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│              agent.py                    │
│  agent.run(goal) starts the loop        │
└─────────────────────┬───────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌────────┐   ┌────────┐   ┌────────┐
   │OBSERVE │   │ THINK  │   │  ACT   │
   └───┬────┘   └───┬────┘   └───┬────┘
       │            │            │
       ▼            ▼            ▼
  observer.py    llm.py      browser.py
  (parse HTML)   (ask LLM)   (execute)
```

---

## Key Concepts You'll See in Code

### 1. Selectors
A **selector** tells Playwright which element to interact with.

```python
# By CSS selector
page.click("button.submit")        # Click button with class "submit"
page.fill("#search", "cats")       # Fill input with id "search"

# By text content
page.click("text=Sign In")         # Click element containing "Sign In"
```

### 2. Locators
Playwright's modern way to find elements:

```python
locator = page.locator("button.submit")
locator.click()  # Waits for element, then clicks
```

### 3. JSON Actions
The LLM outputs actions as JSON:

```json
{"action": "type", "args": {"selector": "input", "text": "cats"}}
{"action": "click", "args": {"text": "Search"}}
{"action": "navigate", "args": {"url": "https://wikipedia.org"}}
{"action": "done", "args": {"reason": "Found what I needed"}}
```

### 4. Session Memory
The agent tracks what it's done:

```python
memory.downloaded_files  # ["paper1.pdf", "paper2.pdf"]
memory.visited_urls      # ["https://arxiv.org", "https://arxiv.org/search"]
memory.actions_taken     # [{"action": "click", ...}, ...]
memory.failures          # ["Timeout waiting for element"]
```

---

## The Prompts (How We Talk to the LLM)

### observe.txt
Asks the LLM to describe the page:
```
Page Title: {title}
URL: {url}
Visible Elements: {elements}
Describe what you see in 2-3 sentences.
```

### think.txt
Asks the LLM what to do next:
```
GOAL: {goal}
OBSERVATION: {observation}
What should you do next? Think step by step.
```

### act.txt
Asks the LLM to output a JSON action:
```
AVAILABLE ACTIONS:
- type: {"action": "type", "args": {"selector": "input", "text": "query"}}
- click: {"action": "click", "args": {"selector": "button"}}
...
Output ONLY valid JSON:
```

---

## What We Built in Phase 1

✅ Basic ReAct loop (observe/think/act)
✅ Browser control (navigate, click, type, scroll)
✅ Multi-provider LLM support (Ollama, OpenAI, Anthropic, Google)
✅ Session memory (tracks visits, actions, failures)
✅ CLI interface

**Test result:** Agent successfully navigated from Google to Wikipedia when asked.

---

## What We're Building in Phase 2

- [ ] Better element detection (smarter selectors)
- [ ] Persistent memory (SQLite - remember across sessions)
- [ ] Proper download handling
- [ ] Recovery from failures
- [ ] Planner for complex multi-step goals

---

## Next Doc

→ `01_ARCHITECTURE.md` - Deep dive into each file
