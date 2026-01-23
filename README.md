# Blackreach

**Autonomous Browser Agent** - Give it a goal, watch it browse.

Blackreach is a CLI tool that uses AI to autonomously browse the web and accomplish tasks. It can navigate websites, search for content, download files (PDFs, images, datasets, etc.), and more.

```bash
blackreach run "find and download papers about machine learning from arxiv"
```

## Features

- **General-Purpose**: Download any content type - papers, images, datasets, ebooks, etc.
- **ReAct Pattern**: Observe → Think → Act loop for intelligent browsing
- **Session Resume**: Pause and resume interrupted sessions
- **Smart Deduplication**: Never download the same file twice (URL + hash checking)
- **Memory System**: Remembers successful patterns across sessions
- **Multi-Provider**: Ollama, OpenAI, Anthropic, Google, xAI
- **Stealth Mode**: Evades basic bot detection
- **Pagination Support**: Automatically detects and navigates multi-page results

## Installation

### Quick Install (pip)

```bash
pip install blackreach
```

### Install with Cloud Providers

```bash
# With OpenAI support
pip install "blackreach[openai]"

# With Anthropic support
pip install "blackreach[anthropic]"

# With all providers
pip install "blackreach[all]"
```

### From Source

```bash
git clone https://github.com/phnix/blackreach
cd blackreach
pip install -e .
```

### Post-Install: Browser Setup

Blackreach uses Playwright for browser automation. Install the browser:

```bash
playwright install chromium
```

## Quick Start

### First Run

```bash
blackreach
```

On first run, Blackreach will walk you through setup:
1. Install browser (if needed)
2. Choose AI provider (Ollama, OpenAI, etc.)
3. Configure API key (for cloud providers)

### Basic Usage

```bash
# Interactive mode
blackreach

# Run with a specific goal
blackreach run "search wikipedia for artificial intelligence"

# Run headless (no browser window)
blackreach run --headless "download papers about transformers from arxiv"

# Resume an interrupted session
blackreach run --resume 42
```

## Commands

| Command | Description |
|---------|-------------|
| `blackreach` | Interactive mode |
| `blackreach run "goal"` | Run agent with a goal |
| `blackreach run --resume ID` | Resume a paused session |
| `blackreach sessions` | List resumable sessions |
| `blackreach config` | Configure settings and API keys |
| `blackreach models` | List available models |
| `blackreach status` | Show current configuration |
| `blackreach setup` | Run setup wizard |
| `blackreach doctor` | Check system requirements |

### Interactive Commands

In interactive mode, use these slash commands:

| Command | Short | Description |
|---------|-------|-------------|
| `/help` | `/h` | Show help |
| `/model` | `/m` | Switch model |
| `/provider` | `/p` | Switch provider |
| `/status` | `/s` | Show status |
| `/sessions` | | List resumable sessions |
| `/resume ID` | | Resume a session |
| `/logs` | `/l` | View recent logs |
| `/clear` | `/cls` | Clear screen |
| `/quit` | `/q` | Exit |

## Supported AI Providers

| Provider | Type | Models |
|----------|------|--------|
| **Ollama** | Local | qwen2.5:7b, llama3.2:3b, mistral:7b |
| **xAI** | Cloud | grok-2, grok-2-mini |
| **OpenAI** | Cloud | gpt-4o, gpt-4o-mini |
| **Anthropic** | Cloud | claude-3.5-sonnet, claude-3-opus |
| **Google** | Cloud | gemini-2.5-pro, gemini-2.5-flash |

### Using Ollama (Local, Free, Private)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull qwen2.5:7b`
3. Start Ollama: `ollama serve`
4. Use Blackreach: `blackreach`

### Using Cloud Providers

1. Get API key from your provider
2. Configure: `blackreach config` → Set API key
3. Switch provider: `blackreach config` → Set default provider

## Configuration

Config file: `~/.blackreach/config.yaml`

### Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
export XAI_API_KEY="xai-..."
```

## Examples

### Research Papers

```bash
blackreach run "go to arxiv.org, search for 'attention mechanism', download 3 papers"
```

### Images and Media

```bash
blackreach run "find and download landscape wallpapers from unsplash"
```

### Datasets

```bash
blackreach run "download CSV files about climate data from kaggle"
```

### Documentation

```bash
blackreach run "go to github.com/pytorch/pytorch and download the README"
```

### Ebooks

```bash
blackreach run "find and download 'pride and prejudice' from project gutenberg"
```

## Session Resume

Sessions are automatically saved when interrupted (Ctrl+C):

```bash
# Start a task
blackreach run "download 10 papers from arxiv"
# Press Ctrl+C to pause

# Later, resume where you left off
blackreach sessions  # See available sessions
blackreach run --resume 42  # Resume session #42
```

## Architecture

```
blackreach/
├── agent.py       # ReAct loop coordinator
├── browser.py     # Playwright browser control (stealth, downloads)
├── observer.py    # HTML parsing, link detection, pagination
├── llm.py         # Multi-provider LLM integration
├── memory.py      # Session memory + SQLite persistence
├── detection.py   # CAPTCHA, login, paywall detection
├── resilience.py  # Retry logic, circuit breaker
├── exceptions.py  # Error hierarchy
├── config.py      # Configuration management
├── logging.py     # Structured session logging
└── cli.py         # Command-line interface
```

## Troubleshooting

### Check System Status

```bash
blackreach doctor
```

### Common Issues

**Browser not found:**
```bash
playwright install chromium
```

**Ollama not running:**
```bash
ollama serve
```

**Bot detection (418/403 errors):**
- Some sites block headless browsers
- Try running without `--headless`
- Use different search engines (Google/Wikipedia work better than DuckDuckGo)

**Session resume fails:**
```bash
blackreach sessions  # Check if session exists
```

## Memory and Learning

Blackreach maintains two types of memory:

1. **Session Memory** (RAM): Current session state
2. **Persistent Memory** (SQLite): Cross-session learning

The persistent memory tracks:
- All downloads (prevents re-downloading)
- Site patterns that worked
- Common failures to avoid

View stats:
```bash
blackreach status
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.
