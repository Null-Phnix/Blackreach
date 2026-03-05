# Download Handling
## How the Agent Downloads Files

---

## The Problem

Web downloads are tricky because:
1. **Duplicates** - Same file might be linked from different URLs
2. **No direct links** - Some sites use JavaScript buttons, not `<a href>`
3. **Naming conflicts** - Multiple files might have the same name
4. **Bot detection** - Downloads can trigger CAPTCHAs

---

## The Solution

We added download handling to `browser.py` and integrated it with the memory system to prevent duplicates.

---

## How It Works

### 1. Browser Level (`browser.py`)

The Hand class now handles downloads:

```python
class Hand:
    def __init__(self, ..., download_dir: Path = None):
        self.download_dir = download_dir or Path("./downloads")
        self._pending_downloads = []
```

On wake, we enable downloads:

```python
def wake(self):
    # Ensure download directory exists
    self.download_dir.mkdir(parents=True, exist_ok=True)

    # Enable downloads in browser
    self._browser = self._playwright.chromium.launch(
        downloads_path=str(self.download_dir)
    )

    # Enable in context
    self._context = self._browser.new_context(
        accept_downloads=True
    )

    # Listen for download events
    self._page.on("download", self._handle_download)
```

### 2. Download Methods

**Direct URL download:**
```python
def download_link(self, href: str) -> dict:
    """Download from a direct URL."""
    with self.page.expect_download() as download_info:
        self.page.goto(href)
    download = download_info.value

    # Save and compute hash
    save_path = self.download_dir / download.suggested_filename
    download.save_as(str(save_path))

    return {
        "filename": save_path.name,
        "path": str(save_path),
        "size": save_path.stat().st_size,
        "hash": self._compute_hash(save_path)
    }
```

**Click-triggered download:**
```python
def click_and_download(self, selector: str) -> dict:
    """Click a button/link and wait for download."""
    with self.page.expect_download() as download_info:
        self.page.locator(selector).first.click()
    download = download_info.value
    # ... save and return info
```

### 3. File Hashing

We compute SHA256 hashes to detect duplicates:

```python
def _compute_hash(self, path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
```

**Why hash?** The same PDF might be served from:
- `https://site-a.com/paper.pdf`
- `https://site-b.com/mirror/paper.pdf`
- `https://cdn.site-a.com/v2/paper.pdf`

Different URLs, same content. The hash catches this.

---

## Agent Integration

### In `_execute_action`

```python
elif action == "download":
    url = args.get("url", "")
    selector = args.get("selector", "")

    # Check 1: Have we downloaded this URL before?
    if url and self.persistent_memory.has_downloaded(url=url):
        print("  SKIP: Already downloaded from this URL")
        return {"skipped": True}

    # Actually download
    if url:
        result = self.hand.download_link(url)
    elif selector:
        result = self.hand.click_and_download(selector)

    # Check 2: Have we downloaded this content before?
    if self.persistent_memory.has_downloaded(file_hash=result["hash"]):
        Path(result["path"]).unlink()  # Delete duplicate
        print("  SKIP: Duplicate content")
        return {"skipped": True}

    # Record the download
    self.persistent_memory.add_download(
        filename=result["filename"],
        url=result["url"],
        file_hash=result["hash"],
        file_size=result["size"]
    )
```

---

## Duplicate Detection Flow

```
                    ┌─────────────────┐
                    │ Download Request│
                    │ url or selector │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Check: URL in   │
                    │ downloads table?│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │ YES          │              │ NO
              ▼              │              ▼
      ┌───────────┐          │      ┌───────────────┐
      │   SKIP    │          │      │ Actually      │
      │(same URL) │          │      │ download file │
      └───────────┘          │      └───────┬───────┘
                             │              │
                             │              ▼
                             │      ┌───────────────┐
                             │      │ Compute hash  │
                             │      │ of new file   │
                             │      └───────┬───────┘
                             │              │
                             │              ▼
                             │      ┌───────────────┐
                             │      │ Check: hash   │
                             │      │ in downloads? │
                             │      └───────┬───────┘
                             │              │
                             │   ┌──────────┼──────────┐
                             │   │ YES      │          │ NO
                             │   ▼          │          ▼
                             │ ┌───────────┐│  ┌───────────────┐
                             │ │ Delete    ││  │ Keep file     │
                             │ │ duplicate ││  │ Record in DB  │
                             │ │ SKIP      ││  │ SUCCESS       │
                             │ └───────────┘│  └───────────────┘
                             │              │
                             └──────────────┘
```

---

## Handling Filename Conflicts

If a file with the same name already exists:

```python
save_path = self.download_dir / suggested_name

counter = 1
while save_path.exists():
    # paper.pdf → paper_1.pdf → paper_2.pdf
    stem = save_path.stem.rsplit('_', 1)[0]
    save_path = self.download_dir / f"{stem}_{counter}{save_path.suffix}"
    counter += 1
```

---

## Download Actions for LLM

The LLM can now output:

```json
{"action": "download", "args": {"url": "https://example.com/paper.pdf"}}
```

Or for click-triggered downloads:

```json
{"action": "download", "args": {"selector": "a.download-btn"}}
```

---

## What Gets Stored

### In `downloads` table:

| Column | Example |
|--------|---------|
| filename | `transformers_survey.pdf` |
| url | `https://arxiv.org/pdf/2023.12345.pdf` |
| source_site | `arxiv.org` |
| file_hash | `a3f2b1c4d5e6...` (SHA256) |
| file_size | `1024000` |
| downloaded_at | `2024-01-22 10:30:00` |

---

## Example Session

```
Session #5 started
Memory: 47 downloads, 180 visits from 4 sessions

[Step 1] OBSERVE: ArXiv search results page...
[Step 2] THINK: I should download the first paper...
[Step 3] ACT: download
  Downloaded: attention_is_all_you_need.pdf (2.1 MB)

[Step 4] ACT: download
  SKIP: Already downloaded (same URL)

[Step 5] ACT: download
  SKIP: Duplicate content (same hash)

Session #5 ended
Downloads this session: 1 (skipped 2 duplicates)
```

---

## Files Modified

| File | Changes |
|------|---------|
| `blackreach/browser.py` | Added download methods, hash computation |
| `blackreach/agent.py` | Integrated download with memory system |

---

## Next Steps

Download handling is complete. Now we need:
1. **Better element detection** - Smart selectors, fuzzy matching

→ See `05_ELEMENT_DETECTION.md` for smarter selectors
