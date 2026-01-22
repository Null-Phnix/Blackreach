# Memory Integration
## Connecting Persistent Memory to the Agent

---

## What Changed

We integrated the memory system from `memory.py` into `agent.py`. Now the agent:
- Remembers downloads across sessions (won't re-download)
- Learns which selectors work on which sites
- Tracks failures for future learning
- Records every session with stats

---

## Before vs After

### Before (Phase 1)
```python
class Agent:
    def __init__(self):
        self.memory = AgentMemory()  # Dies when program ends
```

### After (Phase 2)
```python
class Agent:
    def __init__(self):
        self.session_memory = SessionMemory()    # RAM - this run only
        self.persistent_memory = PersistentMemory()  # SQLite - forever
        self.session_id = None  # Track in database
```

---

## The Integration Pattern

### 1. Helper Methods

We added helper methods that write to BOTH memories:

```python
def _record_visit(self, url: str, title: str = ""):
    """Record to both memories."""
    self.session_memory.add_visit(url)           # RAM
    self.persistent_memory.add_visit(url, ...)   # SQLite

def _record_download(self, filename: str, url: str = ""):
    """Record to both memories."""
    self.session_memory.add_download(filename, url)
    self.persistent_memory.add_download(...)

def _record_failure(self, url: str, action: str, error: str):
    """Record to both memories."""
    self.session_memory.add_failure(error)
    self.persistent_memory.add_failure(...)
```

**Why both?**
- Session memory = fast, for current run context
- Persistent memory = permanent, for learning across runs

### 2. Session Lifecycle

Every run is now tracked:

```python
def run(self, goal):
    # START session
    self.session_id = self.persistent_memory.start_session(goal)

    try:
        # ... do the work ...
    finally:
        # END session with stats
        self.persistent_memory.end_session(
            self.session_id,
            steps=len(self.session_memory.actions_taken),
            downloads=len(self.session_memory.downloaded_files),
            success=success
        )
```

### 3. Duplicate Detection

Before downloading, check if we already have it:

```python
elif action == "download":
    url = args.get("url", "")

    # Check persistent memory
    if self.persistent_memory.has_downloaded(url=url):
        print(f"  SKIP: Already downloaded")
        return {"skipped": True}

    # Actually download...
```

### 4. Learning Patterns

When a selector works, remember it:

```python
def _act(self, thought, observation):
    try:
        result = self._execute_action(action, args)

        # Success! Remember this selector
        if selector:
            self.persistent_memory.record_pattern(
                domain=domain,
                pattern_type="selector",
                pattern_data=selector,
                success=True
            )
    except Exception as e:
        # Failure! Remember that too
        self.persistent_memory.record_pattern(..., success=False)
```

### 5. Using Learned Patterns

When thinking, consider what worked before:

```python
def _think(self, goal, observation):
    domain = self._get_domain()

    # Get patterns that worked on this site
    patterns = self.persistent_memory.get_best_patterns(domain, "selector")

    if patterns:
        prompt += f"\nPreviously successful selectors: {patterns[:3]}"
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Agent.run()                             │
├─────────────────────────────────────────────────────────────────┤
│  1. Start session in SQLite                                     │
│  2. Loop: observe → think → act                                 │
│  3. End session with stats                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   _observe   │    │    _think    │    │    _act      │
│              │    │              │    │              │
│ Records      │    │ Gets learned │    │ Records      │
│ visits       │    │ patterns     │    │ patterns     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     ┌────────────────┐      ┌────────────────┐
     │ SessionMemory  │      │PersistentMemory│
     │ (RAM)          │      │ (SQLite)       │
     │                │      │                │
     │ - visited_urls │      │ - downloads    │
     │ - downloaded   │      │ - visits       │
     │ - actions      │      │ - patterns     │
     │ - failures     │      │ - failures     │
     └────────────────┘      │ - sessions     │
                             └────────────────┘
```

---

## What Happens Over Time

### Run 1: First time on arxiv.org
```
Session #1 started
  Tried selector "input[name=q]" - FAILED
  Tried selector "input.search" - FAILED
  Tried selector "#search-input" - SUCCESS!
Session #1 ended

Database:
  site_patterns: {"arxiv.org", "selector", "#search-input", success=1, fail=0}
```

### Run 2: Back to arxiv.org
```
Session #2 started
  _think() says: "Previously successful selectors: ['#search-input']"
  Agent tries #search-input FIRST - SUCCESS!
Session #2 ended

Database:
  site_patterns: {"arxiv.org", "selector", "#search-input", success=2, fail=0}
```

### Run 10: Agent is now an expert
```
Session #10 started
  Memory: 47 downloads, 180 visits from 9 sessions
  Knows best selectors for arxiv.org, wikipedia.org, github.com
  Skips files it already downloaded
Session #10 ended
```

---

## The AgentConfig Change

Added `memory_db` to config:

```python
@dataclass
class AgentConfig:
    max_steps: int = 50
    headless: bool = False
    download_dir: Path = Path("./downloads")
    start_url: str = "https://www.google.com"
    memory_db: Path = Path("./memory.db")  # NEW
```

Now you can specify where to store the memory:

```python
config = AgentConfig(memory_db=Path("./data/agent_memory.db"))
```

---

## Testing the Integration

```python
from blackreach.agent import Agent, AgentConfig
from blackreach.llm import LLMConfig

# Create agent
agent = Agent(
    llm_config=LLMConfig(provider="ollama", model="qwen2.5:7b"),
    agent_config=AgentConfig()
)

# Run it
agent.run("go to wikipedia and search for cats")

# Check memory
stats = agent.persistent_memory.get_stats()
print(stats)
# {
#     "total_downloads": 0,
#     "total_visits": 5,
#     "total_sessions": 1,
#     "total_failures": 0,
#     "known_domains": 2
# }

# Check what patterns were learned
patterns = agent.persistent_memory.get_best_patterns("wikipedia.org", "selector")
print(patterns)  # ['input[name="search"]', ...]
```

---

## Files Modified

| File | Changes |
|------|---------|
| `blackreach/agent.py` | Added dual memory, helper methods, pattern learning |
| `blackreach/memory.py` | (Already created in previous step) |

---

## Next Steps

The memory integration is complete. Now we need:
1. **Download handling** - Actually download files, compute hashes
2. **Better element detection** - Smarter selectors, fuzzy matching

→ See `04_DOWNLOAD_HANDLING.md` for proper file downloads
