# Blackreach Memory System
## How the Agent Remembers

---

## The Problem

Without memory, the agent:
- Re-downloads files it already has
- Repeats mistakes that failed before
- Forgets which sites work well
- Starts from scratch every run

---

## The Solution: Two Types of Memory

### 1. SessionMemory (RAM)
- **Lifetime:** Dies when program ends
- **Speed:** Instant (just Python variables)
- **Use case:** "What did I do 5 steps ago?"

### 2. PersistentMemory (SQLite)
- **Lifetime:** Survives forever (stored on disk)
- **Speed:** Fast enough (SQLite is lightweight)
- **Use case:** "Did I download this file last week?"

---

## Why SQLite?

SQLite is:
- **Built into Python** - No install needed (`import sqlite3`)
- **Single file** - Your entire memory is one `.db` file
- **Fast** - Handles millions of records easily
- **Queryable** - Use SQL to search and analyze

```python
# That's it. One file contains all your data.
memory.db  # ~1MB for thousands of records
```

---

## The Database Schema

### Table: `downloads`

Tracks every file ever downloaded.

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER | Unique identifier |
| filename | TEXT | "paper.pdf" |
| url | TEXT | Where we got it |
| source_site | TEXT | "arxiv.org" |
| goal | TEXT | What we were trying to do |
| file_hash | TEXT | Content fingerprint (detect duplicates) |
| file_size | INTEGER | Bytes |
| downloaded_at | TIMESTAMP | When |

**Why file_hash?** The same file might have different URLs. By hashing the content, we can detect duplicates even if the URL changed.

### Table: `visits`

Tracks every page visited.

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER | Unique identifier |
| url | TEXT | The page URL |
| title | TEXT | Page title |
| goal | TEXT | What we were doing |
| success | BOOLEAN | Did we achieve something? |
| visited_at | TIMESTAMP | When |

### Table: `site_patterns`

Learns what works on each site.

| Column | Type | Purpose |
|--------|------|---------|
| domain | TEXT | "arxiv.org" |
| pattern_type | TEXT | "search_selector", "download_link" |
| pattern_data | TEXT | "input#search", "a.pdf-link" |
| success_count | INTEGER | How many times it worked |
| fail_count | INTEGER | How many times it failed |

**Example:** If `input#search` works 10 times on arxiv.org, we'll try it first next time.

### Table: `failures`

Tracks errors for learning.

| Column | Type | Purpose |
|--------|------|---------|
| url | TEXT | Where it failed |
| action | TEXT | What we tried ("click", "type") |
| error_message | TEXT | What went wrong |
| goal | TEXT | What we were doing |

### Table: `sessions`

Tracks each run of the agent.

| Column | Type | Purpose |
|--------|------|---------|
| goal | TEXT | What we tried to do |
| start_time | TIMESTAMP | When we started |
| end_time | TIMESTAMP | When we finished |
| steps_taken | INTEGER | How many actions |
| downloads_count | INTEGER | Files downloaded |
| success | BOOLEAN | Did we succeed? |

---

## Code Walkthrough

### Creating the Memory

```python
from blackreach.memory import PersistentMemory

# Creates memory.db in current directory
memory = PersistentMemory()

# Or specify a path
memory = PersistentMemory(db_path=Path("./data/agent_memory.db"))
```

### Recording Downloads

```python
# Basic
memory.add_download("paper.pdf", url="https://arxiv.org/pdf/123.pdf")

# With more info
memory.add_download(
    filename="transformers_survey.pdf",
    url="https://arxiv.org/pdf/2023.12345.pdf",
    source_site="arxiv.org",
    goal="download transformer papers",
    file_hash="abc123...",  # SHA256 of file content
    file_size=1024000
)
```

### Checking for Duplicates

```python
# Before downloading, check if we already have it
if memory.has_downloaded(url="https://arxiv.org/pdf/123.pdf"):
    print("Already have this file!")
else:
    # Download it
    ...
```

### Learning Site Patterns

```python
# We tried clicking "a.pdf-link" and it worked
memory.record_pattern(
    domain="arxiv.org",
    pattern_type="download_selector",
    pattern_data="a.pdf-link",
    success=True
)

# Next time on arxiv.org, get selectors that worked before
best_selectors = memory.get_best_patterns("arxiv.org", "download_selector")
# Returns: ["a.pdf-link", "a.download", ...]
```

### Getting Stats

```python
stats = memory.get_stats()
print(stats)
# {
#     "total_downloads": 150,
#     "total_visits": 423,
#     "total_sessions": 12,
#     "total_failures": 37,
#     "known_domains": 8,
#     "db_path": "./memory.db"
# }
```

---

## How Memory Grows Over Time

### Day 1: First Run
```
memory.db:
├── downloads: 5 files
├── visits: 20 pages
├── site_patterns: 3 patterns
└── failures: 2 errors
```

### Week 1: After 10 Runs
```
memory.db:
├── downloads: 47 files
├── visits: 180 pages
├── site_patterns: 25 patterns (learning what works!)
└── failures: 15 errors
```

### Month 1: After 50 Runs
```
memory.db:
├── downloads: 200+ files (knows not to re-download)
├── visits: 800+ pages (knows site structures)
├── site_patterns: 100+ patterns (expert at common sites)
└── failures: 50 errors (knows what to avoid)
```

The agent gets **smarter over time** because it remembers what worked.

---

## Integration with Agent

In `agent.py`, we'll add:

```python
class Agent:
    def __init__(self, ...):
        self.session_memory = SessionMemory()  # Short-term (RAM)
        self.persistent_memory = PersistentMemory()  # Long-term (SQLite)
        self.session_id = None  # Track current session

    def run(self, goal: str):
        # Start a session
        self.session_id = self.persistent_memory.start_session(goal)

        try:
            # ... do the work ...
            pass
        finally:
            # End the session with stats
            self.persistent_memory.end_session(
                self.session_id,
                steps=len(self.session_memory.actions_taken),
                downloads=len(self.session_memory.downloaded_files),
                success=True
            )
```

---

## Querying the Database Directly

You can inspect the memory with any SQLite tool:

```bash
# Command line
sqlite3 memory.db

# In the SQLite prompt
sqlite> SELECT * FROM downloads ORDER BY downloaded_at DESC LIMIT 10;
sqlite> SELECT domain, COUNT(*) FROM site_patterns GROUP BY domain;
sqlite> .quit
```

Or use a GUI like **DB Browser for SQLite**.

---

## Next Steps

The memory system is built. Now we need to:
1. Integrate it into `agent.py`
2. Use it for duplicate detection
3. Use learned patterns for smarter selectors

→ See `03_DOWNLOAD_HANDLING.md` for proper file downloads
