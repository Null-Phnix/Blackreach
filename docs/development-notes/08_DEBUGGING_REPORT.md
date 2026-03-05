# Blackreach Debugging Report - January 22, 2026

## Overview

This report documents all errors encountered during stress testing of Blackreach, the fixes applied, and remaining known issues. The goal was to verify Blackreach works as a general-purpose autonomous web agent across multiple site types.

**Testing Environment:**
- Model: qwen2.5:7b via Ollama
- GPU: RTX 4060 (CUDA enabled after reinstall)
- Browser: Playwright headless mode
- OS: Linux (CachyOS)

---

## Error 1: LLM Outputs Action Array Instead of Single Action

### Symptom
Agent kept navigating to the same URL repeatedly, ignoring paper links on ArXiv.

### Root Cause
The LLM was outputting a planned sequence of actions:
```json
{
  "actions": [
    {"action": "navigate", "args": {"url": "https://arxiv.org/search/..."}},
    {"action": "click", "args": {"text": "[arXiv:2601.15284]"}},
    {"action": "download", "args": {"url": "https://arxiv.org/pdf/2601.15284.pdf"}}
  ]
}
```

The agent's JSON parser extracted the first action from the array, which was always "navigate to the search page" - the page we were already on.

### Fix Applied
**File:** `blackreach/agent.py` (lines 421-426)

Added Format 0 handling to extract the first action from an array:
```python
# Format 0: {"actions": [{...}, {...}]} - array of actions, take first one
actions_array = data.get("actions")
if isinstance(actions_array, list) and len(actions_array) > 0:
    first_action = actions_array[0]
    if isinstance(first_action, dict):
        data = first_action  # Use first action as the data to parse
```

### Additional Fix
**File:** `prompts/react.txt`

Rewrote the prompt to emphasize single action output:
```
WHAT TO DO NEXT (pick ONE):
...
Output ONLY ONE JSON object (not an array):
```

### Status: FIXED

---

## Error 2: Click Text Includes Formatting Brackets

### Symptom
Click actions failed silently. Agent would output `{"action": "click", "args": {"text": "[arXiv:2601.15284]"}}` but the click never happened.

### Root Cause
The element formatting in `_format_elements()` wrapped link text in brackets:
```python
detail_links.append(f"  - DETAIL PAGE: [{text}] -> {href}")
```

The LLM saw `[arXiv:2601.15284]` and used it verbatim, but the actual page text is `arXiv:2601.15284` (no brackets).

Playwright's `get_by_text("[arXiv:2601.15284]")` couldn't find a match.

### Fix Applied
**File:** `blackreach/agent.py` (lines 573-575)

Strip brackets and quotes from click text before matching:
```python
if action == "click":
    selector = args.get("selector", "")
    text = args.get("text", "")

    # Clean text - strip brackets and quotes that may come from formatting
    if text:
        text = text.strip('[]"\'')
```

Also changed formatting to use quotes instead of brackets:
```python
detail_links.append(f"  - DETAIL PAGE: \"{text}\" -> {href}")
```

### Status: FIXED

---

## Error 3: Relative URLs Not Resolved

### Symptom
Navigate and download actions failed with relative URLs like `/pdf/2601.15284` or `/courses/...`.

### Root Cause
The LLM output relative URLs (which is correct based on what it saw in the elements), but the agent tried to use them directly without resolving to absolute URLs.

For navigate:
```python
self.hand.goto("/pdf/2601.15284")  # Fails - not a valid URL
```

For download:
```python
self.hand.download_link("/pdf/2601.15284")  # Fails
```

### Fix Applied
**File:** `blackreach/agent.py`

Added URL resolution for navigate action (lines 665-668):
```python
elif action == "navigate":
    url = args.get("url", "")
    current_url = self.hand.get_url()

    # Resolve relative URLs to absolute
    if url and not url.startswith(('http://', 'https://')):
        from urllib.parse import urljoin
        url = urljoin(current_url, url)
```

Added URL resolution for download action (lines 689-693):
```python
elif action == "download":
    url = args.get("url", "")

    # Resolve relative URLs to absolute
    if url and not url.startswith(('http://', 'https://')):
        from urllib.parse import urljoin
        base_url = self.hand.get_url()
        url = urljoin(base_url, url)
        print(f"  -> Resolved URL: {url[:70]}")
```

### Status: FIXED

---

## Error 4: Author Links Drown Out Paper Links

### Symptom
On ArXiv search results, agent couldn't see paper links. It kept trying to navigate to the search URL instead of clicking on papers.

### Root Cause
ArXiv search results have ~250 author links that appeared before the 50 paper links in the element list. The `_format_elements()` function was returning links in DOM order, so the first 50 links were all author links.

The LLM only saw:
```
Links:
  - "John Smith" -> /search/?searchtype=author&query=Smith
  - "Jane Doe" -> /search/?searchtype=author&query=Doe
  ... (50 author links)
```

It never saw the actual paper links (`/abs/...`).

### Fix Applied
**File:** `blackreach/agent.py` (lines 804-831)

Implemented link prioritization:
```python
# Separate and prioritize links
download_links = []
detail_links = []
other_links = []

for link in all_links:
    href = link.get("href", "")
    href_lower = href.lower()
    text = link.get("text", "")[:40]

    # Check for downloadable files
    is_download = ...

    if is_download:
        download_links.append(f"  - DOWNLOAD: \"{text}\" -> {href}")
    elif any(p in href_lower for p in ['/abs/', '/paper/', '/article/', '/item/', '/w/', '/full/']):
        detail_links.append(f"  - DETAIL PAGE: \"{text}\" -> {href}")
    elif 'author' not in href_lower and 'search' not in href_lower:
        other_links.append(f"  - \"{text}\" -> {href[:70]}")

# Combine with priority: downloads first, then detail pages, then others
prioritized = download_links[:10] + detail_links[:10] + other_links[:5]
```

Now the LLM sees:
```
Links:
  - DETAIL PAGE: "arXiv:2601.15284" -> https://arxiv.org/abs/2601.15284
  - DETAIL PAGE: "arXiv:2601.15250" -> https://arxiv.org/abs/2601.15250
  ...
```

### Status: FIXED

---

## Error 5: PDF Links Not Detected on Paper Pages

### Symptom
On ArXiv paper pages (`/abs/...`), the agent couldn't find PDF download links.

### Root Cause
ArXiv PDF links use the path `/pdf/2601.15284` (no `.pdf` extension in URL). The download detection only looked for file extensions:
```python
download_exts = ['.pdf', '.zip', '.tar', ...]
```

### Fix Applied
**File:** `blackreach/agent.py` (lines 817-820)

Added path-based download detection:
```python
download_exts = ['.pdf', '.zip', '.tar', '.gz', '.csv', '.json', '.xlsx', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.mp3', '.mp4', '.doc', '.docx', '.txt', '.md']
download_paths = ['/pdf/', '/download/', '/file/', 'upload.wikimedia.org']
is_download = any(ext in href_lower for ext in download_exts) or any(p in href_lower for p in download_paths)
```

### Status: FIXED

---

## Error 6: Size Filter Rejects Valid Data Files

### Symptom
CSV file downloads (89KB) were rejected as "thumbnails" and deleted.

### Root Cause
The 200KB minimum file size filter was designed to reject image thumbnails, but it was applied to ALL files:
```python
MIN_FULL_IMAGE_SIZE = 200000  # 200KB
if result["size"] < MIN_FULL_IMAGE_SIZE:
    print(f"  WARNING: Small file ({result['size']} bytes) - likely thumbnail")
    Path(result["path"]).unlink()  # Delete the file!
```

Valid CSV files (which are often small) were being deleted.

### Fix Applied
**File:** `blackreach/agent.py` (lines 718-727)

Only apply size filter to image files:
```python
# Check if file is too small (likely a thumbnail) - only for images
filename_lower = result["filename"].lower()
is_image = any(filename_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'])
MIN_FULL_IMAGE_SIZE = 200000  # 200KB

if is_image and result["size"] < MIN_FULL_IMAGE_SIZE:
    print(f"  WARNING: Small image ({result['size']} bytes) - likely thumbnail")
    Path(result["path"]).unlink()
    return {"action": "download", "skipped": True, "reason": "thumbnail (too small)"}
```

### Status: FIXED

---

## Error 7: "Already Visited" Only Tracked Wallhaven Pages

### Symptom
Agent kept navigating to the same ArXiv paper page repeatedly, even though it had already visited it.

### Root Cause
The "ALREADY VISITED" context only tracked wallhaven-specific URLs:
```python
visited_detail_pages = [u for u in self.session_memory.visited_urls if '/w/' in u]
```

ArXiv pages (`/abs/...`) were never tracked.

### Fix Applied
**File:** `blackreach/agent.py` (lines 365-372)

Generalized detail page detection:
```python
# Detect detail pages by common URL patterns
detail_patterns = ['/w/', '/abs/', '/paper/', '/article/', '/item/', '/full/', '/pdf/']
visited_detail_pages = [
    u for u in self.session_memory.visited_urls
    if any(p in u for p in detail_patterns)
]
if visited_detail_pages:
    extra_context += f"\nALREADY VISITED (pick a DIFFERENT link): {visited_detail_pages[-5:]}"
```

Also added tracking of downloaded files:
```python
downloaded = self.session_memory.downloaded_files
if downloaded:
    filenames = [Path(f).name for f in downloaded[-5:]]
    extra_context += f"\nALREADY DOWNLOADED: {filenames}"
```

### Status: FIXED (but LLM still sometimes ignores the hint)

---

## Error 8: HTTP Fetch Returns 403 Forbidden

### Symptom
Wikimedia image downloads failed with "HTTP Error 403: Forbidden".

### Root Cause
The `_fetch_file_directly()` method used `urllib.request.urlretrieve()` which doesn't send a User-Agent header. Wikimedia blocks requests without a proper User-Agent.

### Fix Applied
**File:** `blackreach/browser.py` (lines 551-559)

Added User-Agent header to HTTP requests:
```python
# Download the file with User-Agent to avoid 403 errors
try:
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        with open(save_path, 'wb') as f:
            f.write(response.read())
except urllib.error.HTTPError as e:
    raise ValueError(f"HTTP error downloading {url}: {e.code} {e.reason}")
```

### Status: FIXED

---

## Error 9: Wiki File Pages Classified as Downloads

### Symptom
On Wikimedia, links like `/wiki/File:Python-logo.png` were classified as DOWNLOAD links, but they're actually wiki pages (not direct file downloads).

### Root Cause
The download detection looked for `.png` in the URL:
```python
if any(ext in href_lower for ext in ['.png', '.jpg', ...]):
    download_links.append(...)
```

The URL `/wiki/File:Python-logo.png` contains `.png` but it's a wiki page, not a direct download.

### Fix Applied
**File:** `blackreach/agent.py` (lines 817-821)

Exclude wiki pages from download classification:
```python
# Exclude wiki pages (e.g. /wiki/File:something.png is a wiki page, not a direct download)
is_wiki_page = '/wiki/' in href_lower
is_download = (not is_wiki_page) and (any(ext in href_lower for ext in download_exts) or any(p in href_lower for p in download_paths))
```

### Status: FIXED

---

## Remaining Known Issues

### Issue A: LLM Picks Same Link Repeatedly - FIXED

**Symptom:** Even with "ALREADY VISITED" context, the LLM sometimes picks the same link over and over.

**Root Cause:** The 7B model doesn't always follow instructions. It sees the first link and picks it without reading the context.

**Final Fix Applied (Session 2):**
Removed already-visited/downloaded URLs from the element list entirely before sending to LLM:

**File:** `blackreach/agent.py` (lines 329-338)
```python
# Build list of URLs to exclude (already visited detail pages + downloaded URLs)
detail_patterns = ['/w/', '/abs/', '/paper/', '/article/', '/item/', '/full/', '/pdf/']
exclude_urls = [
    u for u in self.session_memory.visited_urls
    if any(p in u for p in detail_patterns)
]
# Also exclude URLs we've already downloaded from
exclude_urls.extend(self.session_memory.downloaded_urls)

elements = self._format_elements(parsed, exclude_urls=exclude_urls)
```

**File:** `blackreach/agent.py` (`_format_elements` method)
```python
def is_excluded(url: str) -> bool:
    if not url or not exclude_urls:
        return False
    url_lower = url.lower()
    url_id = extract_id(url_lower)  # Extract paper ID for academic URLs

    for excluded in exclude_urls:
        excluded_lower = excluded.lower()
        if url_lower == excluded_lower or excluded_lower in url_lower or url_lower in excluded_lower:
            return True
        # Check if paper IDs match (e.g., /abs/XXXX matches /pdf/XXXX)
        if url_id and url_id == extract_id(excluded_lower):
            return True
    return False
```

Also added ArXiv paper ID extraction to handle `/abs/` vs `/pdf/` URL variants:
```python
def extract_id(url: str) -> str:
    """Extract paper ID from academic URLs (e.g., arxiv.org/abs/2305.14496v2 -> 2305.14496)"""
    import re
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url.lower())
    if arxiv_match:
        return f"arxiv:{arxiv_match.group(1)}"
    return ""
```

**Status:** FIXED - Now the LLM never sees already-visited links, eliminating the need to trust it to follow instructions.

---

### Issue B: Wikimedia Complex Page Structure

**Symptom:** Cannot download images from Wikimedia Commons pages.

**Root Cause:** Wikimedia pages have a complex structure where:
1. The main image is shown as an `<img>` tag with a thumbnail URL
2. The full-size download links are in a separate section
3. Links to "File:" wiki pages look like downloads but aren't

The element extraction doesn't properly identify the actual download URL (`upload.wikimedia.org/...`).

**Attempted Fixes:**
- Added `upload.wikimedia.org` to download path detection
- Excluded `/wiki/` pages from download classification
- Added User-Agent to HTTP fetch

**Status:** NOT FIXED - Would need site-specific parsing logic for Wikimedia.

---

### Issue C: Browser Download Timeout for Inline Files - FIXED

**Symptom:** Some downloads timeout because the browser displays the file inline instead of triggering a download event.

**Root Cause:** Playwright's `expect_download()` waits for a download event, but some files (images, PDFs) are displayed inline by the browser.

**Final Fix Applied (Session 2):**
Detect inline file types upfront and use HTTP fetch directly instead of waiting for timeout:

**File:** `blackreach/browser.py` (lines 513-540)
```python
def download_link(self, href: str, timeout: int = 60000) -> dict:
    href_lower = href.lower()

    # Files that are typically displayed inline by browsers - use HTTP fetch directly
    inline_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp']
    is_inline_file = any(href_lower.endswith(ext) or f'{ext}?' in href_lower for ext in inline_extensions)

    # Also check for image hosting patterns
    is_image_host = any(h in href_lower for h in ['upload.wikimedia.org', 'i.imgur.com', 'pbs.twimg.com'])

    if is_inline_file or is_image_host:
        # Use HTTP fetch directly for images (faster, no timeout)
        return self._fetch_file_directly(href)

    # For other files, try browser download first with shorter timeout
    try:
        return self.download_file(url=href, timeout=min(timeout, 30000))  # Max 30s
    except Exception as e:
        if "Timeout" in str(e) or "download" in str(e).lower():
            return self._fetch_file_directly(href)
        raise
```

**Status:** FIXED - Inline files are now downloaded instantly via HTTP instead of waiting for browser timeout.

---

### Issue D: Model Latency on CPU

**Symptom:** Each LLM call takes 5-10 seconds on GPU, would be 15-20+ seconds on CPU.

**Root Cause:** Ollama was running on CPU due to missing CUDA libraries. User reinstalled Ollama to fix.

**Status:** FIXED (requires proper Ollama installation with CUDA)

---

## Summary of All Fixes

| Error | File | Lines | Status |
|-------|------|-------|--------|
| Action array parsing | agent.py | 421-426 | FIXED |
| Click text brackets | agent.py | 573-575 | FIXED |
| Relative URL (navigate) | agent.py | 665-668 | FIXED |
| Relative URL (download) | agent.py | 689-693 | FIXED |
| Link prioritization | agent.py | 804-831 | FIXED |
| PDF path detection | agent.py | 817-820 | FIXED |
| Size filter scope | agent.py | 718-727 | FIXED |
| Visited page tracking | agent.py | 365-372 | FIXED |
| HTTP User-Agent | browser.py | 551-559 | FIXED |
| Wiki page exclusion | agent.py | 817-821 | FIXED |
| Repeated link selection | agent.py | 329-338, _format_elements | FIXED (Session 2) |
| Inline file timeout | browser.py | 513-540 | FIXED (Session 2) |
| ArXiv ID matching | agent.py | _format_elements | FIXED (Session 2) |
| Wikimedia structure | - | - | NOT FIXED |

## Lessons Learned

1. **The LLM only knows what you show it.** If elements aren't formatted well, the LLM makes bad decisions.

2. **Small models need simple prompts.** The 7B model struggled with complex instructions. Single action output works better than multi-step planning.

3. **Normalize everything.** URLs, text, selectors - clean them before use.

4. **Domain-specific rules hurt generalization.** The wallhaven-specific `/w/` tracking broke ArXiv. Use general patterns.

5. **Test with diverse sites.** ArXiv, GitHub, Gutenberg, and Wikimedia all have different structures. What works on one may break on another.

6. **Fewer LLM calls = better.** Reducing from 3 calls to 1 call per step improved both speed and consistency.

7. **Don't trust the LLM to follow instructions - remove the options.** Instead of telling the LLM "don't pick already-visited links", filter them out before the LLM sees them. This is more reliable than prompt engineering.

8. **Handle edge cases proactively, not reactively.** Detecting inline file types upfront and using the right download method is faster and more reliable than waiting for timeouts and falling back.

9. **Academic sites have aliased URLs.** ArXiv `/abs/XXXX` and `/pdf/XXXX` point to the same paper. Need ID extraction to detect duplicates across URL variants.
