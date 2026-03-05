# Blackreach Architecture Deep Dive
## Understanding Every File

---

## Overview

```
blackreach/
├── agent.py      ← THE BRAIN (coordinates everything)
├── browser.py    ← THE HANDS (controls the browser)
├── observer.py   ← THE EYES (parses HTML)
├── llm.py        ← THE MIND (talks to AI models)
├── stealth.py    ← THE DISGUISE (avoids detection)
├── resilience.py ← THE IMMUNE SYSTEM (handles errors)
└── __init__.py   ← Package definition
```

---

## 1. agent.py — The Brain

**Purpose:** Coordinates the entire ReAct loop.

### Key Classes

```python
@dataclass
class AgentConfig:
    max_steps: int = 50          # Stop after this many actions
    headless: bool = False       # True = invisible browser
    download_dir: Path           # Where to save files
    start_url: str               # Where to begin (default: google.com)
```

```python
@dataclass
class AgentMemory:
    downloaded_files: List[str]  # Files we've downloaded
    visited_urls: List[str]      # Pages we've been to
    actions_taken: List[Dict]    # History of what we did
    failures: List[str]          # Errors we encountered
```

```python
class Agent:
    def __init__(self, llm_config, agent_config):
        self.llm = LLM(llm_config)      # The AI brain
        self.hand = None                 # Browser (created in run())
        self.eyes = Eyes()               # HTML parser
        self.memory = AgentMemory()      # Session state
        self.prompts = self._load_prompts()  # Load prompt templates
```

### The Main Loop

```python
def run(self, goal: str):
    # 1. Start browser
    self.hand = Hand(headless=self.config.headless)
    self.hand.wake()

    # 2. Go to start URL
    self.hand.goto(self.config.start_url)

    # 3. ReAct loop
    for step in range(1, self.config.max_steps + 1):
        result = self._step(goal, step)
        if result.get("done"):
            break

    # 4. Cleanup
    self.hand.sleep()
    return results
```

### One Step of the Loop

```python
def _step(self, goal, step_num):
    # OBSERVE
    observation = self._observe()

    # THINK
    thought = self._think(goal, observation)

    # ACT
    result = self._act(thought, observation)

    return result
```

**Why this matters:** The agent is just a coordinator. It doesn't know how to parse HTML (that's `observer.py`), it doesn't know how to click buttons (that's `browser.py`), it doesn't know how to talk to AI (that's `llm.py`). It just orchestrates them.

---

## 2. browser.py — The Hands

**Purpose:** Control the browser. Click, type, scroll, navigate.

### Key Class

```python
class Hand:
    def __init__(self, headless=False, stealth_config=None):
        self.headless = headless
        self.stealth = Stealth(stealth_config)
        self._page = None  # The browser tab
```

### Core Methods

```python
def wake(self):
    """Start the browser."""
    self._playwright = sync_playwright().start()
    self._browser = self._playwright.chromium.launch(headless=self.headless)
    self._page = self._browser.new_page()

def sleep(self):
    """Close the browser."""
    self._browser.close()
    self._playwright.stop()

def goto(self, url: str):
    """Navigate to a URL."""
    self.page.goto(url, wait_until="domcontentloaded")

def click(self, selector: str):
    """Click an element."""
    self.page.locator(selector).first.click()

def type(self, selector: str, text: str):
    """Type into an input."""
    self.page.locator(selector).first.fill(text)

def scroll(self, direction="down", amount=500):
    """Scroll the page."""
    delta = amount if direction == "down" else -amount
    self.page.mouse.wheel(0, delta)
```

**Why this matters:** This is the interface between Python code and the actual browser. Playwright does the heavy lifting, but `Hand` wraps it in a clean API.

---

## 3. observer.py — The Eyes

**Purpose:** Parse raw HTML into structured data the LLM can understand.

### The Problem

Raw HTML is messy:
```html
<div class="nav"><a href="/home">Home</a><a href="/about">About</a></div>
<script>trackUser();</script>
<main><h1>Welcome</h1><p>Hello world</p></main>
```

### The Solution

```python
class Eyes:
    def see(self, html: str) -> dict:
        soup = BeautifulSoup(html, 'lxml')

        # Remove junk
        for tag in soup.find_all(['script', 'style', 'nav']):
            tag.decompose()

        # Extract useful stuff
        return {
            "text": self._get_text(soup),      # Main content
            "links": self._get_links(soup),    # Clickable links
            "inputs": self._get_inputs(soup),  # Form fields
            "buttons": self._get_buttons(soup) # Buttons
        }
```

Output:
```python
{
    "text": "Welcome\nHello world",
    "links": [{"text": "Home", "href": "/home"}, {"text": "About", "href": "/about"}],
    "inputs": [{"name": "search", "placeholder": "Search..."}],
    "buttons": [{"text": "Submit"}]
}
```

**Why this matters:** LLMs can't process raw HTML efficiently. We need to give them a clean summary of what's on the page.

---

## 4. llm.py — The Mind

**Purpose:** Communicate with AI models (Ollama, OpenAI, Anthropic, Google).

### Key Classes

```python
@dataclass
class LLMConfig:
    provider: str = "ollama"       # Which service to use
    model: str = "qwen2.5:7b"      # Which model
    temperature: float = 0.7       # Creativity (0=deterministic, 1=random)
    max_tokens: int = 1024         # Max response length
```

```python
class LLM:
    def generate(self, system_prompt: str, user_message: str) -> str:
        """Send a message to the LLM and get a response."""
        if self._provider_type == "ollama":
            return self._call_ollama(system_prompt, user_message)
        elif self._provider_type == "openai":
            return self._call_openai(system_prompt, user_message)
        # ... etc
```

### Parsing Actions

The LLM returns text. We need to extract the action:

```python
def parse_action(self, response_text: str) -> LLMResponse:
    # Find JSON in the response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    data = json.loads(json_match.group())

    return LLMResponse(
        thought=data.get("thought", ""),
        action=data.get("action"),
        args=data.get("args", {}),
        done=data.get("done", False)
    )
```

**Why this matters:** The LLM is the "intelligence" of the agent. Without it, we'd need to hardcode every decision.

---

## 5. stealth.py — The Disguise

**Purpose:** Make the browser look like a real human, not a bot.

### Why Needed?

Websites detect bots by checking:
- Is `navigator.webdriver` set? (Automation flag)
- Is the viewport size exactly 800x600? (Default bot size)
- Does the mouse move in straight lines? (Bots don't curve)

### Key Features

```python
class Stealth:
    def get_random_viewport(self):
        """Return a realistic screen size."""
        return random.choice([
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
        ])

    def get_random_user_agent(self):
        """Return a realistic browser identifier."""
        return random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120...",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/...",
        ])

    def generate_bezier_path(self, start, end):
        """Generate curved mouse movement path."""
        # Humans don't move mice in straight lines
        ...
```

**Why this matters:** Without stealth, many websites will block you or show CAPTCHAs.

---

## 6. resilience.py — The Immune System

**Purpose:** Handle errors gracefully. Retry failed actions.

### Key Features

```python
@retry_with_backoff(max_retries=3, initial_delay=1.0)
def some_flaky_function():
    """This will retry up to 3 times if it fails."""
    ...
```

```python
class SmartSelector:
    """Try multiple selectors until one works."""
    def find(self, selectors: List[str]):
        for selector in selectors:
            try:
                element = self.page.locator(selector).first
                if element.count() > 0:
                    return element
            except:
                continue
        return None
```

```python
class PopupHandler:
    """Automatically close cookie banners, popups, etc."""
    def handle_all(self):
        for pattern in ["Accept", "Got it", "Close", "×"]:
            try:
                self.page.click(f"text={pattern}", timeout=1000)
            except:
                pass
```

**Why this matters:** The web is messy. Elements load slowly, popups appear, selectors change. Resilience makes the agent robust.

---

## How They Connect

```
┌─────────────────────────────────────────────────────────────┐
│                        agent.py                              │
│                    (The Coordinator)                         │
│                                                              │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│    │ _observe │    │  _think  │    │   _act   │            │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘            │
└─────────┼───────────────┼───────────────┼───────────────────┘
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │observer.py│   │  llm.py  │    │browser.py│
    │ (parse)  │    │ (think)  │    │(execute) │
    └────┬─────┘    └──────────┘    └────┬─────┘
         │                               │
         │         ┌──────────┐          │
         │         │stealth.py│◄─────────┤
         │         │resilience│          │
         │         └──────────┘          │
         │                               │
         ▼                               ▼
    [HTML from page]              [Browser actions]
```

---

## Next Doc

→ `02_MEMORY_SYSTEM.md` - Building persistent memory with SQLite
