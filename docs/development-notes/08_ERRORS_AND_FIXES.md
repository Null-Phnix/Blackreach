# Errors and Fixes

This document catalogs every error encountered during Blackreach development and how each was fixed. Use this as a debugging reference.

---

## Table of Contents

1. [Browser Automation Errors](#browser-automation-errors)
2. [LLM Integration Errors](#llm-integration-errors)
3. [Action Execution Errors](#action-execution-errors)
4. [Bot Detection Issues](#bot-detection-issues)
5. [Performance Issues](#performance-issues)

---

## Browser Automation Errors

### Error: Null Locator Dereference

**Symptom:**
```
Error: Cannot read property 'is_visible' of undefined
```

**Code that caused it:**
```python
loc = self.hand.page.locator(selector).first
if loc.is_visible():  # Crashes if no elements match!
    loc.click()
```

**Why it happens:**
Playwright's `.first` property doesn't throw an error when no elements match - it returns a "null locator" that crashes when you try to use it.

**Fix:**
```python
loc = self.hand.page.locator(selector)
if loc.count() > 0 and loc.first.is_visible():
    loc.first.click()
```

**Lesson:** Always check `count() > 0` before accessing `.first` on a Playwright locator.

---

### Error: Bare Except Catches Everything

**Symptom:**
Ctrl+C doesn't stop the program, or errors are silently swallowed.

**Code that caused it:**
```python
except:
    continue
```

**Why it happens:**
`except:` without a specific exception type catches EVERYTHING, including:
- `KeyboardInterrupt` (Ctrl+C)
- `SystemExit` (sys.exit())
- `GeneratorExit`

**Fix:**
```python
except Exception:
    continue
```

**Lesson:** Always catch `Exception` specifically, never use bare `except:`.

---

### Error: Element Not Found Timeout

**Symptom:**
```
TimeoutError: waiting for selector "input[name=q]" failed: timeout 30000ms exceeded
```

**Why it happens:**
The element doesn't exist, hasn't loaded yet, or has a different selector.

**Fix:**
Add fallback selectors for common elements like search inputs:

```python
selectors_to_try = [selector]
if any(x in selector.lower() for x in ['search', 'query', 'q', 'input']):
    selectors_to_try.extend([
        'input[type="search"]',
        'input[name="q"]',
        '[role="searchbox"]',
        # ... more fallbacks
    ])

for sel in selectors_to_try:
    try:
        loc = self.page.locator(sel).first
        if loc.is_visible():
            return loc
    except Exception:
        continue
```

**Lesson:** Don't rely on a single selector. Use fallback patterns for common UI elements.

---

## LLM Integration Errors

### Error: JSON Parse Failed

**Symptom:**
```
JSONDecodeError: Expecting ',' delimiter: line 1 column 45
```

**Why it happens:**
The LLM outputs text before/after JSON, or outputs invalid JSON.

**LLM output example:**
```
I'll click the search button.
{"action": "click", "args": {"text": "Search"}}
Great!
```

**Fix:**
Use regex to find JSON within the response:

```python
import re
json_match = re.search(r'\{[\s\S]*\}', response_text)
if json_match:
    data = json.loads(json_match.group())
```

**Lesson:** Never assume LLM output is clean JSON. Extract it with regex.

---

### Error: Action Format Inconsistency

**Symptom:**
Agent says "done" but doesn't complete.

**Why it happens:**
The LLM outputs either:
- `{"action": "done", "args": {"reason": "..."}}`
- `{"done": true, "reason": "..."}`

The parser only handled one format.

**Fix:**
Handle both formats:

```python
action = data.get("action")
done = data.get("done", False)
reason = data.get("reason")

# Handle action: "done" format
if action == "done":
    done = True
    reason = reason or data.get("args", {}).get("reason", "Goal complete")
```

**Lesson:** LLMs are inconsistent. Handle multiple valid output formats.

---

### Error: Missing Action Type

**Symptom:**
Agent couldn't press Enter after typing in search box.

**Why it happens:**
The prompt listed actions but didn't include a "press" action for keyboard keys.

**Original prompts:**
```
type() - Type text
click() - Click element
... (no press/submit action)
```

**Fix:**
1. Added `submit: true` parameter to type action
2. Added `press` action for keyboard input

```python
# In agent.py
if submit:
    self.hand.page.keyboard.press("Enter")

elif action == "press":
    key = args.get("key", "Enter")
    self.hand.page.keyboard.press(key)
```

**Lesson:** Audit your action space. If you can't do something obvious (like press Enter), add it.

---

## Action Execution Errors

### Error: Click Failed - Generic Selector

**Symptom:**
```
Timeout waiting for selector "a"
```

**Why it happens:**
The LLM outputs `{"action": "click", "args": {"selector": "a"}}` which is too generic - there are hundreds of `<a>` elements on most pages.

**Fix:**
1. Require `text` field for clicking
2. Add fallback selectors for image galleries and search results

```python
# If we have text, try text-based clicking first
if text:
    self.hand.page.get_by_text(text, exact=False).first.click()
    return

# If selector is too generic, try specific fallbacks
if selector in ['a', 'button', 'div']:
    result_selectors = [
        'a:has(img)',      # Image links
        '.result a',       # Search results
        'article a',       # Article links
    ]
    for sel in result_selectors:
        try:
            # ... try selector
        except:
            continue
```

**Lesson:** Never trust generic selectors like "a" or "button". Use text-based clicking when possible.

---

### Error: Success Reported When Not Successful

**Symptom:**
Agent hit max steps (30) but CLI showed "Success".

**Why it happens:**
Completion logic was:
```python
success = result.get('steps_taken', 0) > 0  # Always true!
```

**Fix:**
```python
success = result.get('success', False)
```

And added `success` field to agent return dict:
```python
result = {
    "goal": goal,
    "success": success,  # True only if agent said "done"
    # ...
}
```

**Lesson:** Don't infer success from activity. Track explicit success state.

---

## Bot Detection Issues

### Error: HTTP 418 "I'm a Teapot"

**Symptom:**
DuckDuckGo returns 418 error page instead of search results.

**Why it happens:**
DuckDuckGo's bot detection identified the headless browser despite stealth mode.

**Tried:**
- Stealth scripts (hide webdriver, fake plugins)
- Human-like delays
- Random user agents and viewports

**Result:**
Still detected. DuckDuckGo's detection is sophisticated.

**Fix:**
Changed default start URL to Google, which is more tolerant:
```python
start_url: str = "https://www.google.com"
```

**Alternative approaches:**
1. Use a less aggressive site (Wikipedia, Google)
2. Use a real browser window (headless=False)
3. Add captcha solving service
4. Use proxy rotation

**Lesson:** Some sites can't be automated reliably. Have fallbacks.

---

## Performance Issues

### Error: DOM Parsed Twice Per Step

**Symptom:**
Each step takes 5-10 seconds, even on simple pages.

**Why it happens:**
```python
def _observe(self):
    html = self.hand.get_html()  # Parse #1
    parsed = self.eyes.see(html)

def _act(self):
    html = self.hand.get_html()  # Parse #2 (same page!)
    parsed = self.eyes.see(html)
```

**Fix:**
Cache parsed results between observe and act:

```python
# In __init__
self._page_cache = {"elements": None, "url": None}

# In _observe
self._page_cache["elements"] = self._format_elements(parsed)

# In _act
elements = self._page_cache.get("elements")  # Reuse!
```

**Result:** 2-3 seconds saved per step.

**Lesson:** Cache expensive operations when data doesn't change.

---

### Error: Multiple Stealth Script Injections

**Symptom:**
Browser startup takes 3-5 extra seconds.

**Why it happens:**
```python
for script in stealth.get_all_stealth_scripts():  # 10+ scripts
    page.add_init_script(script)  # Separate IPC call each time
```

**Fix:**
Combine scripts before injection:
```python
scripts = stealth.get_all_stealth_scripts()
combined = "\n".join(scripts)
page.add_init_script(combined)  # Single IPC call
```

**Lesson:** Batch operations when possible.

---

## Summary Table

| Error | Category | File | Fix |
|-------|----------|------|-----|
| Null locator crash | Browser | agent.py:439 | Check count() > 0 |
| Bare except | Python | browser.py:252 | Use `except Exception:` |
| Element timeout | Browser | browser.py | Fallback selectors |
| JSON parse fail | LLM | llm.py | Regex extraction |
| Action format mismatch | LLM | llm.py | Handle both formats |
| Missing press action | Actions | agent.py | Add press/submit |
| Generic selector fail | Actions | agent.py | Text-based clicking |
| False success | Logic | cli.py | Check actual success |
| Bot detection 418 | Stealth | agent.py | Use different site |
| Double DOM parse | Performance | agent.py | Add caching |
| Multiple injections | Performance | browser.py | Combine scripts |

---

## Debugging Tips

1. **Always read error messages fully** - they usually tell you exactly what's wrong

2. **Add logging** - When something fails silently, add `print()` statements or proper logging

3. **Test incrementally** - Don't write 100 lines then test. Test every 10-20 lines.

4. **Check the data** - Print what the LLM actually returns, what the page HTML looks like

5. **Isolate the problem** - Create a minimal test case that reproduces the issue

6. **Check the docs** - Playwright, Ollama, etc. have great documentation
