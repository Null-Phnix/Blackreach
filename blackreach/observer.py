"""
The Eyes - HTML Parser using BeautifulSoup

Cleans raw HTML into simple, readable text for the Brain.
Optimized for performance and LLM consumption.
"""

from bs4 import BeautifulSoup, Tag, SoupStrainer
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from functools import lru_cache
import re
import hashlib


@dataclass
class EyesConfig:
    """Configuration for the Eyes parser."""
    max_text_length: int = 8000
    max_links: int = 50
    max_inputs: int = 20
    max_buttons: int = 20

    # Content prioritization
    prioritize_main_content: bool = True
    extract_headings: bool = True
    extract_lists: bool = True
    extract_tables: bool = False  # Tables can be verbose

    # Performance
    use_cache: bool = True
    cache_size: int = 100


class Eyes:
    """
    The Eyes that parse and clean HTML for the Brain.

    Features:
    - Optimized parsing with SoupStrainer
    - Content prioritization (main content first)
    - Semantic extraction (headings, lists, structured data)
    - Result caching for repeated parsing
    - Multiple output formats for different use cases
    """

    # Tags to completely remove
    REMOVE_TAGS = {
        'script', 'style', 'noscript', 'svg', 'path', 'meta',
        'link', 'head', 'iframe', 'frame', 'object', 'embed',
        'applet', 'audio', 'video', 'source', 'track', 'canvas'
    }

    # Tags that typically contain main content
    MAIN_CONTENT_TAGS = {'main', 'article', 'section', 'div[role="main"]'}

    # Semantic content containers (in priority order)
    CONTENT_PRIORITY = ['main', 'article', '[role="main"]', '.content', '#content', '.main', '#main']

    # Navigation/footer areas to deprioritize
    NOISE_SELECTORS = [
        'nav', 'header', 'footer', 'aside', '.sidebar', '.navigation',
        '.menu', '.breadcrumb', '.pagination', '.advertisement', '.ad',
        '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]'
    ]

    def __init__(self, config: Optional[EyesConfig] = None):
        self.config = config or EyesConfig()
        self._cache: Dict[str, dict] = {}

    def _get_cache_key(self, html: str) -> str:
        """Generate cache key from HTML content."""
        return hashlib.md5(html.encode()[:10000]).hexdigest()

    def see(self, html: str, use_cache: bool = None) -> dict:
        """
        Parse HTML and return a structured view for the Brain.

        Returns:
            dict with:
                - text: Cleaned readable text (prioritized)
                - headings: Page structure via headings
                - links: Clickable links
                - inputs: Form inputs
                - buttons: Clickable buttons
                - forms: Form structures
        """
        use_cache = use_cache if use_cache is not None else self.config.use_cache

        if use_cache:
            cache_key = self._get_cache_key(html)
            if cache_key in self._cache:
                return self._cache[cache_key]

        soup = BeautifulSoup(html, 'lxml')

        # Remove unwanted tags
        for tag in soup.find_all(self.REMOVE_TAGS):
            tag.decompose()

        # Extract structured elements FIRST (before text extraction modifies soup)
        headings = self._extract_headings(soup) if self.config.extract_headings else []
        links = self._extract_links(soup)
        inputs = self._extract_inputs(soup)
        buttons = self._extract_buttons(soup)
        forms = self._extract_forms(soup)
        lists = self._extract_lists(soup) if self.config.extract_lists else []

        # Extract text LAST (may modify soup for prioritization)
        main_text = self._extract_prioritized_text(soup)

        result = {
            "text": main_text[:self.config.max_text_length],
            "headings": headings,
            "links": links[:self.config.max_links],
            "inputs": inputs[:self.config.max_inputs],
            "buttons": buttons[:self.config.max_buttons],
            "forms": forms,
            "lists": lists[:10],
        }

        if use_cache and len(self._cache) < self.config.cache_size:
            self._cache[cache_key] = result

        return result

    def see_simple(self, html: str) -> str:
        """Compact text representation for quick overview."""
        result = self.see(html)

        lines = []
        lines.append("=== PAGE CONTENT ===")
        lines.append(result["text"][:2000])

        if result["inputs"]:
            lines.append("\n=== INPUT FIELDS ===")
            for inp in result["inputs"][:10]:
                selector = inp.get("selector", "input")
                placeholder = inp.get("placeholder", "")
                inp_type = inp.get("type", "text")
                lines.append(f"  [{selector}] ({inp_type}) {placeholder}")

        if result["buttons"]:
            lines.append("\n=== BUTTONS ===")
            for btn in result["buttons"][:10]:
                lines.append(f"  [{btn['selector']}] {btn['text']}")

        if result["links"]:
            lines.append("\n=== LINKS ===")
            for link in result["links"][:15]:
                lines.append(f"  [{link['text'][:50]}] -> {link['href'][:80]}")

        return "\n".join(lines)

    def see_for_llm(self, html: str, max_tokens: int = 4000) -> str:
        """
        Optimized output format for LLM consumption.
        Prioritizes actionable information and structure.
        """
        result = self.see(html)

        lines = []
        char_limit = max_tokens * 4  # Rough chars-to-tokens ratio

        # Page structure via headings
        if result["headings"]:
            lines.append("## Page Structure")
            for h in result["headings"][:10]:
                indent = "  " * (h["level"] - 1)
                lines.append(f"{indent}- {h['text']}")

        # Actionable elements first
        if result["forms"]:
            lines.append("\n## Forms")
            for form in result["forms"][:3]:
                lines.append(f"Form: {form.get('action', 'submit')}")
                for field in form.get("fields", [])[:5]:
                    lines.append(f"  - {field['selector']}: {field.get('placeholder', field.get('type', 'input'))}")

        if result["inputs"] and not result["forms"]:
            lines.append("\n## Input Fields")
            for inp in result["inputs"][:8]:
                lines.append(f"  - {inp['selector']}: {inp.get('placeholder', inp.get('type', ''))}")

        if result["buttons"]:
            lines.append("\n## Buttons")
            for btn in result["buttons"][:8]:
                lines.append(f"  - [{btn['selector']}] {btn['text']}")

        # Key links
        if result["links"]:
            lines.append("\n## Key Links")
            # Filter out noise links
            key_links = [l for l in result["links"] if len(l["text"]) > 3 and not l["href"].startswith("#")][:10]
            for link in key_links:
                lines.append(f"  - [{link['text'][:40]}] {link['href'][:60]}")

        # Main content (remaining space)
        current_len = sum(len(l) for l in lines)
        remaining = char_limit - current_len
        if remaining > 500:
            lines.append("\n## Page Content")
            lines.append(result["text"][:remaining - 100])

        return "\n".join(lines)

    def _extract_prioritized_text(self, soup: BeautifulSoup) -> str:
        """
        Extract text with priority given to main content areas.
        Deprioritizes navigation, headers, footers.
        """
        if not self.config.prioritize_main_content:
            return self._clean_text(soup.get_text())

        # Try to find main content area
        main_content = None
        for selector in self.CONTENT_PRIORITY:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if main_content:
            # Main content first
            main_text = self._clean_text(main_content.get_text())

            # Then get other text (limited)
            main_content.decompose()  # Remove from soup
            other_text = self._clean_text(soup.get_text())[:1000]

            return f"{main_text}\n\n---\n{other_text}" if other_text else main_text

        # Fallback: remove noise areas and get remaining text
        for selector in self.NOISE_SELECTORS:
            for el in soup.select(selector):
                el.decompose()

        return self._clean_text(soup.get_text())

    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract page structure via headings."""
        headings = []
        for i in range(1, 7):
            for h in soup.find_all(f'h{i}'):
                text = h.get_text(strip=True)
                if text and len(text) > 1:
                    headings.append({
                        "level": i,
                        "text": text[:100],
                        "selector": self._get_selector(h)
                    })
        return headings

    def _extract_links(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract links with relevance scoring."""
        links = []
        seen_hrefs: Set[str] = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)

            # Skip duplicates, empty, and anchor-only links
            if not text or href in seen_hrefs or href == "#":
                continue

            seen_hrefs.add(href)

            # Calculate relevance score
            score = len(text)  # Longer text = more likely important
            if a.find_parent(['nav', 'header', 'footer']):
                score -= 50  # Deprioritize nav links
            if 'btn' in str(a.get('class', [])).lower():
                score += 20  # Boost button-like links

            links.append({
                "text": text[:100],
                "href": href,
                "selector": self._get_selector(a),
                "score": score
            })

        # Sort by relevance
        links.sort(key=lambda x: x.get("score", 0), reverse=True)
        return links

    def _extract_inputs(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract form inputs with context."""
        inputs = []
        for inp in soup.find_all(['input', 'textarea', 'select']):
            input_type = inp.get('type', 'text')
            if input_type in ('hidden',):
                continue

            # Try to find associated label
            label = None
            if inp.get('id'):
                label_el = soup.find('label', {'for': inp['id']})
                if label_el:
                    label = label_el.get_text(strip=True)

            # Check for aria-label
            if not label:
                label = inp.get('aria-label', '')

            inputs.append({
                "type": input_type,
                "id": inp.get('id'),
                "name": inp.get('name'),
                "placeholder": inp.get('placeholder', ''),
                "label": label,
                "required": inp.has_attr('required'),
                "selector": self._get_selector(inp)
            })
        return inputs

    def _extract_buttons(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract all clickable buttons."""
        buttons = []
        seen_text: Set[str] = set()

        # Standard buttons
        for btn in soup.find_all(['button', 'input']):
            if btn.name == 'input' and btn.get('type') not in ('submit', 'button'):
                continue
            text = btn.get_text(strip=True) or btn.get('value', '')
            if text and text not in seen_text:
                seen_text.add(text)
                buttons.append({
                    "text": text[:50],
                    "type": btn.get('type', 'button'),
                    "selector": self._get_selector(btn)
                })

        # Role="button" elements
        for btn in soup.find_all(attrs={"role": "button"}):
            text = btn.get_text(strip=True)
            if text and text not in seen_text:
                seen_text.add(text)
                buttons.append({
                    "text": text[:50],
                    "type": "role-button",
                    "selector": self._get_selector(btn)
                })

        return buttons

    def _extract_forms(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract form structures."""
        forms = []
        for form in soup.find_all('form'):
            fields = []
            for inp in form.find_all(['input', 'textarea', 'select']):
                if inp.get('type') == 'hidden':
                    continue
                fields.append({
                    "type": inp.get('type', 'text'),
                    "name": inp.get('name'),
                    "placeholder": inp.get('placeholder', ''),
                    "selector": self._get_selector(inp)
                })

            forms.append({
                "action": form.get('action', ''),
                "method": form.get('method', 'get').upper(),
                "id": form.get('id'),
                "fields": fields,
                "selector": self._get_selector(form)
            })
        return forms

    def _extract_lists(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract list content (useful for navigation, options)."""
        lists = []
        for ul in soup.find_all(['ul', 'ol']):
            items = [li.get_text(strip=True)[:50] for li in ul.find_all('li', recursive=False)][:10]
            if items:
                lists.append({
                    "type": ul.name,
                    "items": items,
                    "selector": self._get_selector(ul)
                })
        return lists

    def _get_selector(self, tag: Tag) -> str:
        """Generate a robust CSS selector for an element."""
        # Priority 1: ID
        if tag.get('id'):
            return f"#{tag['id']}"

        # Priority 2: Name attribute
        if tag.get('name'):
            return f"[name='{tag['name']}']"

        # Priority 3: data-testid (common in modern apps)
        if tag.get('data-testid'):
            return f"[data-testid='{tag['data-testid']}']"

        # Priority 4: aria-label
        if tag.get('aria-label'):
            return f"[aria-label='{tag['aria-label'][:30]}']"

        # Priority 5: Class combination
        if tag.get('class'):
            classes = '.'.join(tag['class'][:2])
            return f"{tag.name}.{classes}"

        # Fallback: text content
        text = tag.get_text(strip=True)[:20]
        if text:
            # Escape quotes in text
            text = text.replace("'", "\\'")
            return f"{tag.name}:has-text('{text}')"

        return tag.name

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def clear_cache(self) -> None:
        """Clear the parsing cache."""
        self._cache.clear()

