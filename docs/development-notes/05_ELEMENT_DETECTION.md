# Element Detection
## How the Agent Finds Things on Pages

---

## The Problem

Finding elements on web pages is hard because:
1. **Different sites, different selectors** - Google uses `input[name=q]`, DuckDuckGo uses `input[name=q]`, Bing uses `input[name=q]`... wait they're all the same. But YouTube uses `input#search`!
2. **Dynamic content** - Elements might not exist yet when we look
3. **Fuzzy text** - User says "click Search" but button says "  Search  " (extra spaces)
4. **Accessibility** - Some elements are only reachable via ARIA attributes

---

## The Solution: SmartSelector

The `SmartSelector` class in `resilience.py` provides multiple ways to find elements:

```python
class SmartSelector:
    def __init__(self, page: Page, timeout: float = 10000):
        self.page = page
        self.timeout = timeout
```

---

## Finding Strategies

### 1. Fallback Selectors

Try multiple selectors until one works:

```python
def find(self, selectors: List[str]) -> Optional[Locator]:
    """Try each selector until one finds an element."""
    for selector in selectors:
        try:
            locator = self.page.locator(selector).first
            if locator.count() > 0:
                return locator
        except:
            continue
    return None

# Usage
element = selector.find([
    "input#search",           # Try ID first
    "input[name='q']",        # Then name attribute
    "input[type='search']",   # Then type
    "[role='searchbox']"      # Then ARIA role
])
```

### 2. Find by Text

```python
def find_by_text(self, text: str, tag: str = "*") -> Optional[Locator]:
    """Find element by its visible text."""
    return self.page.get_by_text(text).first

# Usage
button = selector.find_by_text("Download PDF")
```

### 3. Find Input Fields

```python
def find_input(
    self,
    name: str = None,
    placeholder: str = None,
    label: str = None
) -> Optional[Locator]:
    """Find input by various attributes."""

# Usage
search_box = selector.find_input(placeholder="Search...")
email_field = selector.find_input(label="Email Address")
```

### 4. Find Buttons

```python
def find_button(self, text: str = None, submit: bool = False):
    """Find button by text or type."""

# Usage
login_btn = selector.find_button(text="Log In")
submit_btn = selector.find_button(submit=True)
```

---

## New Enhanced Methods

### 5. Find Links

```python
def find_link(
    self,
    text: str = None,
    href_contains: str = None,
    download: bool = False
) -> Optional[Locator]:
    """Find link by text, href pattern, or download attribute."""

# Examples
pdf_link = selector.find_link(href_contains=".pdf")
download_link = selector.find_link(download=True)
arxiv_link = selector.find_link(text="arXiv")
```

### 6. Find by ARIA (Accessibility)

```python
def find_by_aria(
    self,
    label: str = None,
    role: str = None
) -> Optional[Locator]:
    """Find element by accessibility attributes."""

# Examples
search_box = selector.find_by_aria(role="searchbox")
menu = selector.find_by_aria(role="menu")
close_btn = selector.find_by_aria(label="Close dialog")
```

### 7. Fuzzy Text Matching

```python
def find_fuzzy(
    self,
    text: str,
    threshold: float = 0.6
) -> Optional[Locator]:
    """Find element with similar text (not exact match)."""

# If page has "  Download PDF  " but you search for "Download PDF"
element = selector.find_fuzzy("Download PDF", threshold=0.8)
```

**How it works:**
```python
from difflib import SequenceMatcher

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

similarity("Download PDF", "  Download PDF  ")  # 0.85
similarity("Download PDF", "Download the PDF")  # 0.76
similarity("Download PDF", "Get PDF File")      # 0.45
```

### 8. Common Element Shortcuts

```python
# Find the main search input
search_box = selector.find_search_input()

# Find submit/search button
submit = selector.find_submit_button()

# Find download link
download = selector.find_download_link(file_type="pdf")
```

### 9. Natural Language to Selectors

```python
def generate_selectors(self, description: str) -> List[str]:
    """Convert description to CSS selectors."""

# "the search box" →
selectors = selector.generate_selectors("the search box")
# ["input[type='search']", "input[name='q']", "[role='searchbox']", ...]

# "click the Download button" →
selectors = selector.generate_selectors("click the Download button")
# ["button:has-text('Download')", "a:has-text('download')", ...]
```

---

## How the Agent Uses These

### In `_act()`:

```python
def _act(self, thought, observation):
    # LLM outputs: {"action": "click", "args": {"selector": "search button"}}

    selector_text = args.get("selector", "")

    # First try it directly
    try:
        locator = self.page.locator(selector_text).first
        if locator.count() > 0:
            locator.click()
            return {"action": "click", "success": True}
    except:
        pass

    # Fallback: generate selectors from description
    selectors = self.hand.selector.generate_selectors(selector_text)
    locator = self.hand.selector.find(selectors)

    if locator:
        locator.click()
        return {"action": "click", "success": True}

    raise ValueError(f"Could not find element: {selector_text}")
```

---

## Selector Priority

When finding elements, we try selectors in this order:

1. **ID** - `#search` (most reliable)
2. **Name** - `[name='q']` (very reliable)
3. **Data attributes** - `[data-testid='search']` (reliable)
4. **ARIA** - `[aria-label='Search']` (accessible)
5. **Class** - `.search-input` (less reliable, can change)
6. **Text** - `:has-text('Search')` (depends on language)
7. **Position** - `nth-child(1)` (fragile, avoid)

---

## Common Selector Patterns

### Search Inputs
```css
input[type='search']
input[name='q']
input[name='query']
input[name='search']
input[placeholder*='search' i]
[role='searchbox']
```

### Submit Buttons
```css
button[type='submit']
input[type='submit']
button:has-text('Search')
button:has-text('Submit')
button:has-text('Go')
```

### Download Links
```css
a[download]
a[href$='.pdf']
a[href$='.zip']
a:has-text('Download')
```

### Close Buttons
```css
button[aria-label='Close']
button:has-text('×')
.close
.dismiss
```

---

## Handling Failures

When a selector fails, we:

1. **Record the failure** in persistent memory
2. **Try alternative selectors** using fallback list
3. **Use fuzzy matching** if exact match fails
4. **Report to LLM** so it can try a different approach

```python
# In agent._act():
try:
    result = self._execute_action(action, args)

    # Success! Remember this selector
    self.persistent_memory.record_pattern(
        domain=domain,
        pattern_type="selector",
        pattern_data=selector,
        success=True
    )
except Exception as e:
    # Failure! Remember to avoid this
    self.persistent_memory.record_pattern(
        domain=domain,
        pattern_type="selector",
        pattern_data=selector,
        success=False
    )
```

---

## Files Modified

| File | Changes |
|------|---------|
| `blackreach/resilience.py` | Added fuzzy matching, ARIA selectors, link finding, natural language conversion |

---

## Example: Finding a Search Box

```python
# The LLM says: "type 'transformers' into the search box"

# 1. Try common search selectors
selectors = [
    "input[type='search']",
    "input[name='q']",
    "input[placeholder*='search' i]",
    "[role='searchbox']"
]

element = smart_selector.find(selectors)

# 2. If none found, try ARIA
if not element:
    element = smart_selector.find_by_aria(label="search")

# 3. If still not found, try fuzzy text
if not element:
    element = smart_selector.find_fuzzy("search")

# 4. If STILL not found, generate selectors from context
if not element:
    selectors = smart_selector.generate_selectors("search box input field")
    element = smart_selector.find(selectors)
```

---

## Next Steps

Element detection is enhanced. Phase 2 is complete!

Phase 2 Summary:
- ✅ Persistent memory (SQLite)
- ✅ Memory integration
- ✅ Download handling
- ✅ Better element detection

→ See `06_TESTING.md` for testing the complete system
