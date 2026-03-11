# Blackreach Quick Start Guide

Get up and running in under 5 minutes.

## 1. Install

```bash
pip install blackreach
playwright install chromium
```

## 2. Start Ollama (Free, Local AI)

```bash
# Install from https://ollama.ai, then:
ollama pull qwen2.5:7b
ollama serve
```

## 3. Run Blackreach

```bash
blackreach
```

First run will walk you through setup. Just press Enter to accept defaults.

## 4. Try It

In the interactive prompt, type a goal:

```
> search wikipedia for black holes
```

Watch it browse automatically!

## Example Goals

### Search and Navigate
```
search wikipedia for machine learning
go to github and find trending python repos
```

### Download Files
```
download papers about transformers from arxiv
find and download the pytorch README from github
download the first PDF from gutenberg.org about sherlock holmes
```

### Multi-step Tasks
```
go to arxiv, search for "large language models", download 3 papers
```

## Commands

| Key | Command |
|-----|---------|
| `/h` | Help |
| `/m` | Switch model |
| `/p` | Switch provider |
| `/s` | Status |
| `/q` | Quit |

## Tips

1. **Be specific**: "download 3 papers about GPT from arxiv" > "get some AI papers"
2. **Start simple**: Test with Wikipedia or Google first
3. **Use headless for speed**: `blackreach run --headless "your goal"`
4. **Resume interrupted tasks**: `blackreach run --resume ID`

## Troubleshooting

```bash
blackreach doctor  # Check system status
```

**Ollama issues?** Make sure `ollama serve` is running.

**Browser issues?** Run `playwright install chromium`.

## Next Steps

- Read the full [README](README.md)
- Explore `blackreach config` for more options
- Check `blackreach status` to see memory stats
