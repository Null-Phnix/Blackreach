# Blackreach

**Autonomous Browser Agent** - Give it a goal, watch it browse.

Blackreach is a CLI tool that uses AI to autonomously browse the web and accomplish tasks. It can navigate websites, fill forms, download files, and more.

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
2. Choose AI provider (Ollama, Groq, OpenAI, etc.)
3. Configure API key (for cloud providers)

### Basic Usage

```bash
# Interactive mode
blackreach

# Run with a specific goal
blackreach run "go to wikipedia and search for artificial intelligence"

# Run headless (no browser window)
blackreach run --headless "download the first PDF from arxiv about transformers"
```

## Commands

| Command | Description |
|---------|-------------|
| `blackreach` | Interactive mode |
| `blackreach run "goal"` | Run agent with a goal |
| `blackreach config` | Configure settings and API keys |
| `blackreach models` | List available models |
| `blackreach status` | Show current configuration |
| `blackreach setup` | Run setup wizard |
| `blackreach doctor` | Check system requirements |

## Supported AI Providers

| Provider | Type | Models |
|----------|------|--------|
| **Ollama** | Local | qwen2.5, llama3.2, mistral, etc. |
| **Groq** | Cloud (free tier) | llama-3.1-70b, mixtral |
| **OpenAI** | Cloud | gpt-4o, gpt-4o-mini |
| **Anthropic** | Cloud | claude-3.5-sonnet, claude-3-opus |
| **Google** | Cloud | gemini-1.5-pro, gemini-1.5-flash |

### Using Ollama (Local, Free, Private)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull qwen2.5:7b`
3. Start Ollama: `ollama serve`
4. Use Blackreach: `blackreach`

### Using Groq (Fast, Free Tier)

1. Get API key: https://console.groq.com/keys
2. Configure: `blackreach config` → Set API key
3. Switch provider: `blackreach config` → Set default provider to "groq"

## Configuration

Config file location: `~/.blackreach/config.yaml`

### Environment Variables

You can also set API keys via environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
export GROQ_API_KEY="gsk_..."
```

## Examples

### Search and Navigate

```bash
blackreach run "go to github.com and search for python web frameworks"
```

### Download Files

```bash
blackreach run "go to arxiv.org, search for 'attention is all you need', and download the PDF"
```

### Fill Forms

```bash
blackreach run "go to example.com/contact and fill out the contact form with test data"
```

## Features

- **ReAct Pattern**: Observe → Think → Act loop for intelligent browsing
- **Memory System**: Remembers successful patterns across sessions
- **Download Handling**: Automatic deduplication via file hashing
- **Stealth Mode**: Evades basic bot detection
- **Multi-Provider**: Switch between local and cloud AI easily

## Architecture

```
blackreach/
├── agent.py      # ReAct loop coordinator
├── browser.py    # Playwright browser control
├── observer.py   # HTML parsing and element detection
├── llm.py        # Multi-provider LLM integration
├── memory.py     # Session and persistent memory
├── config.py     # Configuration management
└── cli.py        # Command-line interface
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

**Permission denied:**
```bash
pip install --user blackreach
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.
