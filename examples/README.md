# Blackreach Examples

These standalone scripts demonstrate how to use Blackreach programmatically. Each example is self-contained and can be run directly with Python.

---

## Prerequisites

1. Install Blackreach with dev extras (or standard install):

   ```bash
   pip install -e ".[dev]"
   # or
   pip install blackreach
   ```

2. Install the Playwright browser:

   ```bash
   playwright install chromium
   ```

3. Configure an LLM provider. Blackreach defaults to **Ollama** (local, free). To use a cloud provider, set the appropriate environment variable:

   ```bash
   export OPENAI_API_KEY="sk-..."
   export ANTHROPIC_API_KEY="sk-ant-..."
   export XAI_API_KEY="..."
   export GOOGLE_API_KEY="..."
   ```

   Or run `blackreach config` to configure interactively.

---

## Examples

| File | What It Demonstrates |
|------|---------------------|
| `01_web_research.py` | Research a topic across multiple sources and return a summary |
| `02_download_paper.py` | Find and download an academic paper from arXiv |
| `03_github_readme.py` | Fetch specific content from a GitHub repository page |
| `04_multi_provider.py` | Configure and switch between LLM providers |
| `05_session_resume.py` | Save a session, then resume it from where it left off |
| `06_custom_callbacks.py` | Hook into agent events to build a custom progress tracker |

---

## Running an Example

```bash
# Default: uses Ollama (must be running locally)
python examples/01_web_research.py

# Use a specific provider via environment variable
OPENAI_API_KEY=sk-... python examples/01_web_research.py

# Run headless (no browser window)
# Set headless=True in the AgentConfig inside the script
```

---

## What to Expect

- A browser window will open (unless `headless=True`)
- You will see the agent's steps printed to stdout
- Some goals take many steps (up to `max_steps`)
- Network-dependent goals may fail if the target site is unreachable

---

## Notes

- All examples use `max_steps=20` to keep runtimes short for demonstration purposes
- For production use, increase `max_steps` based on task complexity
- Downloads are saved to a `./downloads/` directory relative to where the script is run
- Session state is saved to `./memory.db`
