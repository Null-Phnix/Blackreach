# Search and Type Actions

This document explains how Blackreach handles typing into search boxes and submitting searches.

---

## What This Does (ELI5)

When you want to search for something on a website, you need to:
1. Find the search box
2. Click on it to focus
3. Type your search query
4. Press Enter (or click the search button)

The agent needs to do all of this automatically. This document explains how.

---

## The Problem

### Before the Fix

The agent could type text but couldn't submit the search:

```
Step 1: Type "cats" into search box
Step 2: ???  (How to press Enter?)
Step 3: LLM confused, tries typing "\n" or navigating directly
```

The action prompt only had:
```json
{"action": "type", "args": {"selector": "input", "text": "cats"}}
```

No way to press Enter after typing.

### After the Fix

Now there are two ways to submit:

**Option 1: Type with submit**
```json
{"action": "type", "args": {"selector": "input", "text": "cats", "submit": true}}
```
This types "cats" AND presses Enter.

**Option 2: Separate press action**
```json
{"action": "type", "args": {"selector": "input", "text": "cats"}}
{"action": "press", "args": {"key": "Enter"}}
```

---

## How It Works

### The Type Action (agent.py)

```python
elif action == "type":
    selector = args.get("selector", "input")
    text = args.get("text", "")
    submit = args.get("submit", False)  # NEW: Submit option

    # Type the text
    self.hand.type(selector, text)

    # If submit=true, press Enter after typing
    if submit:
        self.hand.page.keyboard.press("Enter")
        time.sleep(0.5)  # Wait for page response

    return {"action": "type", "selector": selector, "text": text, "submit": submit}
```

### The Press Action (agent.py)

```python
elif action == "press":
    key = args.get("key", "Enter")
    self.hand.page.keyboard.press(key)
    return {"action": "press", "key": key}
```

### The Prompts (act.txt)

```
1. TYPE and SEARCH (use submit:true to press Enter after typing):
{"action": "type", "args": {"selector": "input", "text": "cats", "submit": true}}

2. TYPE without submitting (just fill the field):
{"action": "type", "args": {"selector": "input", "text": "your text"}}

3. PRESS a key (Enter, Tab, Escape, etc.):
{"action": "press", "args": {"key": "Enter"}}
```

---

## Finding Search Inputs

Websites use many different selectors for search boxes:

| Selector | Website Examples |
|----------|------------------|
| `input[name="q"]` | Google, DuckDuckGo |
| `input[type="search"]` | Many modern sites |
| `[role="searchbox"]` | Accessible sites |
| `#search` | Various |
| `.search-input` | Various |

### Fallback System (browser.py)

```python
def type(self, selector: str, text: str, ...):
    selectors_to_try = [selector]

    # If this looks like a search input, add fallbacks
    if any(x in selector.lower() for x in ['search', 'query', 'q', 'input']):
        selectors_to_try.extend([
            'input[type="search"]',
            'input[name="q"]',
            'input[name="search"]',
            'input[aria-label*="Search"]',
            'input[placeholder*="Search"]',
            '[role="searchbox"]',
            '[role="combobox"]',
        ])

    # Try each selector until one works
    for sel in selectors_to_try:
        try:
            loc = self.page.locator(sel).first
            if loc.is_visible():
                # Found it!
                return loc
        except:
            continue
```

---

## The Complete Flow

Here's what happens when the agent searches for something:

### Step 1: Observe
```
OBSERVE: This is Google's homepage. There's a search box.
```

### Step 2: Think
```
THINK: I need to search for "cats". I'll type with submit:true.
```

### Step 3: Act
```
ACT: {"action": "type", "args": {"selector": "input", "text": "cats", "submit": true}}
```

### What Happens Inside:

```python
# 1. Find the search box
selectors_to_try = ["input", "input[name='q']", ...]
for sel in selectors_to_try:
    if page.locator(sel).is_visible():
        locator = page.locator(sel)
        break

# 2. Click to focus
locator.click()

# 3. Type character by character (human-like)
for char in "cats":
    keyboard.type(char)
    sleep(random(0.05, 0.15))  # Human typing speed

# 4. Press Enter (because submit=true)
keyboard.press("Enter")

# 5. Wait for page to load
sleep(0.5)
```

### Result:
```
Step 4: OBSERVE: Search results page showing results for "cats"
```

---

## Edge Cases

### Autocomplete Dropdowns

Some sites show autocomplete suggestions. The agent might see:
```
OBSERVE: Typing "cat" shows suggestions: "cats", "cat videos", "cat food"
```

If needed, the agent can:
1. Click a suggestion: `{"action": "click", "args": {"text": "cats"}}`
2. Or press Enter to submit current text: `{"action": "press", "args": {"key": "Enter"}}`

### Search Buttons

Some sites don't respond to Enter. They need a button click:
```json
{"action": "click", "args": {"text": "Search"}}
```

### Multiple Search Boxes

If a page has multiple inputs:
```json
{"action": "type", "args": {"selector": "#main-search", "text": "cats", "submit": true}}
```

Use a more specific selector to target the right one.

---

## Testing

### Test Case 1: Google Search

```python
agent_config = AgentConfig(start_url="https://www.google.com")
agent.run("search for python programming")

# Expected:
# Step 1: OBSERVE Google homepage
# Step 2: TYPE "python programming" with submit:true
# Step 3: OBSERVE Search results
# Step 4: DONE
```

**Result:** SUCCESS in 2 steps

### Test Case 2: Wikipedia Search

```python
agent_config = AgentConfig(start_url="https://www.wikipedia.org")
agent.run("search for artificial intelligence")

# Expected:
# Step 1: TYPE "artificial intelligence" with submit:true
# Step 2: OBSERVE AI article
# Step 3: DONE
```

**Result:** SUCCESS in 2 steps

---

## Key Concepts

1. **submit:true** - One parameter that types AND presses Enter
2. **Fallback selectors** - Try multiple selectors for search inputs
3. **Human-like typing** - Character by character with random delays
4. **Press action** - For when you need to press a specific key

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Enter doesn't submit | Use click on search button |
| Can't find search box | Check selector, use fallbacks |
| Autocomplete interferes | Press Escape first, then type |
| Page doesn't load after Enter | Increase wait time |

---

## Code Locations

| What | Where |
|------|-------|
| Type action handler | agent.py:472-485 |
| Press action handler | agent.py:486-488 |
| Fallback selectors | browser.py:281-297 |
| Action prompt | prompts/act.txt |
| Think prompt | prompts/think.txt |
