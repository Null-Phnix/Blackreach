# Run 2 Findings - January 22, 2026

## Session Overview

**Goal:** Test download functionality and verify agent reliability

---

## Issue 1: Download Timeout for Inline Content

**Problem:** Playwright's `expect_download()` times out for files the browser displays inline (images, etc.) rather than downloading.

**Solution:** Added HTTP fallback in `browser.py`:
```python
def download_link(self, href: str, timeout: int = 60000) -> dict:
    try:
        return self.download_file(url=href, timeout=timeout)
    except Exception as e:
        if "Timeout" in str(e):
            return self._fetch_file_directly(href)  # Use urllib
        raise
```

---

## Issue 2: Inconsistent LLM Output Format

**Problem:** Small models (llama3.2:3b) output various JSON formats:
- `{"action": "type", "args": {...}}` (expected)
- `{"action": {"type": "click", ...}}` (nested)
- `{"done": true, "reason": "..."}` (boolean)
- `{"status": "done", ...}` (status field)

**Solution:** Made JSON parsing extremely flexible to handle all formats:
```python
# Handle various formats
if isinstance(action_val, dict):
    action = action_val.get("type", action_val.get("action", ""))
if data.get("done") == True or data.get("status") == "done":
    action = "done"
```

---

## Issue 3: Model Not Recognizing Goal Completion

**Problem:** Agent kept trying to download/navigate after goal was achieved.

**Solution:** Updated prompt with explicit completion rules:
```
CRITICAL RULES:
1. If "Downloads completed" is 1 or more, output done (goal achieved)
2. If page title contains goal topic, output done
```

---

## Issue 4: Prompt Too Verbose

**Problem:** Long prompts with elements list caused:
- Slow LLM responses
- Model echoing back prompt structure
- Inconsistent outputs

**Solution:** Minimal prompt (removed elements, shortened examples):
```
Goal: {goal}
Page: {title}
URL: {url}
Downloads completed: {download_count}

Actions:
- type: {"action":"type","args":{"selector":"input","text":"query"}}
- navigate: {"action":"navigate","args":{"url":"https://..."}}
...

CRITICAL RULES:
1. If "Downloads completed" is 1 or more, output done
2. If page title contains goal topic, output done
3. Output only ONE JSON object
```

---

## Key Finding: Model Size Matters

| Model | Reliability | Speed |
|-------|-------------|-------|
| llama3.2:3b | ~40% (inconsistent JSON) | Fast |
| qwen2.5:7b | ~95% (consistent JSON) | Medium |

**Recommendation:** Use qwen2.5:7b or larger for production.

---

## Test Results (Run 2)

| Test | Result | Steps |
|------|--------|-------|
| Wikipedia search "cats" | SUCCESS | 2 |
| Wikipedia search "python" | SUCCESS | 2 |
| Download w3c_home.png | SUCCESS | 2 |

---

## Files Modified

| File | Change |
|------|--------|
| browser.py | Added HTTP fallback for inline downloads |
| agent.py | Flexible JSON parsing for various formats |
| prompts/react.txt | Minimal prompt with explicit rules |

---

## Next Steps (Run 3)

1. Test more complex multi-step goals
2. Add better error messages
3. Consider adding retry logic for failed actions
