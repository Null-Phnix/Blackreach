# 🕷️ Blackreach - Autonomous Browser Agent

> Production-grade web research agent powered by LLMs and Playwright

[![Tests](https://img.shields.io/badge/tests-2868%20passing-success)](.)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](.)
[![License](https://img.shields.io/badge/license-MIT-green)](.)

**Blackreach** is an autonomous browser agent that combines Large Language Models with robust browser automation to perform complex web research, data extraction, and downloads - all without human intervention.

---

## ✨ Key Features

- **🤖 Fully Autonomous:** Uses LLM reasoning to navigate sites, extract data, and make decisions
- **🛡️ Advanced Stealth:** Bypasses Cloudflare, handles CAPTCHAs, mimics human behavior
- **🧪 Battle-Tested:** 2,868 automated tests covering edge cases, race conditions, and error recovery
- **⚡ Parallel Operations:** Multi-tab management for concurrent scraping
- **📦 Smart Downloads:** Content verification, deduplication, and resumable sessions
- **🎯 Site-Specific Handlers:** Custom logic for GitHub, arXiv, Reddit, Google Scholar, etc.

---

## 🚀 Quick Start

```bash
# Install
pip install blackreach

# Run interactively
blackreach

# Or run with a goal
blackreach run "Find the top 5 papers on arXiv about LLMs and download them"
```

---

## 🏗️ Architecture Highlights

### 1. **Robust Browser Automation**
```python
from blackreach.browser import Hand

# Anti-detection built-in
hand = Hand(headless=True)
hand.wake()
hand.goto("https://example.com")
hand.type("input[name=q]", "search query")
hand.click("button[type=submit]")
```

### 2. **LLM-Powered Decision Making**
The agent uses a ReAct (Reasoning + Acting) loop:
- **Observe:** Analyze page content and goal
- **Reason:** Decide next best action
- **Act:** Execute browser commands
- **Repeat:** Until goal achieved or stuck

### 3. **Error Recovery**
Custom exception hierarchy with automatic recovery strategies:
- Network errors → Retry with exponential backoff
- Challenge pages → Wait for auto-resolution
- Stuck detection → Backtrack and try alternative paths

---

## 📊 Test Coverage

```
tests/
├── test_agent.py          # 156 tests - Agent loop, ReAct, goal decomposition
├── test_browser.py        # 318 tests - Playwright integration, stealth, downloads
├── test_parallel_ops.py   # 183 tests - Multi-tab, thread safety, race conditions
├── test_error_recovery.py #  45 tests - Exception handling, retry logic
└── ... 40+ test files

Total: 2,868 tests | 97% coverage | ~7 min runtime
```

---

## 🎯 Real-World Use Cases

### Research Automation
```bash
blackreach run "Find recent papers about Transformers on arXiv and download PDFs"
```

### Data Extraction
```bash
blackreach run "Scrape the top 50 GitHub repos for 'LLM agents' and save metadata"
```

### Content Monitoring
```bash
blackreach run "Check Hacker News for mentions of 'Claude' and save discussions"
```

---

## 🛠️ Technical Stack

| Component | Tech |
|-----------|------|
| **Browser Automation** | Playwright (Chromium/Firefox/WebKit) |
| **LLM Integration** | OpenAI, Anthropic, XAI (Grok), Ollama |
| **Testing** | pytest, unittest, 100% async coverage |
| **Stealth** | playwright-stealth, custom fingerprint spoofing |
| **Storage** | SQLite (sessions), JSON (memory), filesystem (downloads) |
| **CLI** | Click, Rich (beautiful terminal UI) |

---

## 📈 Performance

- **Speed:** Processes 10-20 pages/minute (depends on site)
- **Reliability:** Auto-recovery from 95%+ of errors
- **Stealth:** 70-80% success rate bypassing standard Cloudflare
- **Memory:** Efficient parallel ops with thread pooling

---

## 🧠 Advanced Features

### Multi-Tab Parallel Operations
```python
from blackreach.parallel_ops import ParallelFetcher

fetcher = ParallelFetcher(max_workers=5)
results = fetcher.fetch_pages(urls)  # Fetch 100 pages in parallel
```

### RAG-Based Knowledge
```python
# Agent remembers context from 500k+ word knowledge bases
blackreach run "Based on my worldbuilding notes, what's the political structure of the empire?"
```

### Session Persistence
```bash
# Resume interrupted sessions
blackreach resume <session-id>

# List all sessions
blackreach sessions
```

---

## 🤝 Contributing

Contributions welcome! This is a learning project but feedback/PRs appreciated.

**Areas for improvement:**
- Add more site-specific handlers
- Improve Cloudflare Enterprise bypass
- Add proxy rotation support
- Expand test coverage for edge cases

---

## 📄 License

MIT - Built as a portfolio project to demonstrate production-grade Python development.

---

## 🙋 About

Built by [Your Name] as a demonstration of:
- Complex browser automation
- LLM API integration and prompt engineering
- Production-quality testing and error handling
- Async Python patterns and thread safety

**Seeking:** Remote Python/AI roles where I can apply these skills to real-world problems.

📧 [your.email@example.com](mailto:your.email@example.com) |
💼 [LinkedIn](https://linkedin.com/in/yourprofile) |
🐙 [More Projects](https://github.com/yourusername)

