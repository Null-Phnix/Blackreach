"""
The Eyes - HTML Parser using BeautifulSoup

Cleans raw HTML into simple, readable text for the Brain.
Optimized for performance and LLM consumption.
"""

from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import logging
import re
import hashlib

logger = logging.getLogger(__name__)


# Precompiled regex patterns for performance
RE_WHITESPACE = re.compile(r'\s+')
RE_PAGE_NUMBER = re.compile(r'^\d+$')
RE_ACTIVE_CURRENT = re.compile(r'active|current')


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
        """Generate cache key from HTML content.

        Uses blake2b (faster than MD5) with 16-byte digest for cache keys.
        Only uses first 10KB of HTML for performance.
        """
        return hashlib.blake2b(html.encode()[:10000], digest_size=16).hexdigest()

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

        # P0-PERF: Use lxml for ~10x faster parsing performance
        # lxml handles malformed HTML well and is much faster than html.parser
        # Falls back to html.parser if lxml is not installed
        try:
            soup = BeautifulSoup(html, 'lxml')
        except Exception as e:
            logger.debug("lxml parser unavailable, falling back to html.parser: %s", e)
            soup = BeautifulSoup(html, 'html.parser')

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
        images = self._extract_images(soup)

        # Extract text LAST (may modify soup for prioritization)
        main_text = self._extract_prioritized_text(soup)

        # Extract pagination for multi-page navigation
        pagination = self._extract_pagination(soup)

        result = {
            "text": main_text[:self.config.max_text_length],
            "headings": headings,
            "links": links[:self.config.max_links],
            "inputs": inputs[:self.config.max_inputs],
            "buttons": buttons[:self.config.max_buttons],
            "forms": forms,
            "lists": lists[:10],
            "images": images[:30],
            "pagination": pagination,
        }

        if use_cache and len(self._cache) < self.config.cache_size:
            self._cache[cache_key] = result

        return result

    def debug_html(self, html: str) -> dict:
        """
        Debug helper to understand what's in the HTML.
        Returns statistics about the HTML structure.
        """
        # P0-PERF: Use lxml for faster parsing
        try:
            soup = BeautifulSoup(html, 'lxml')
        except Exception as e:
            logger.debug("lxml parser unavailable in debug_html, falling back to html.parser: %s", e)
            soup = BeautifulSoup(html, 'html.parser')

        # Count raw elements before any filtering
        raw_links = len(soup.find_all('a', href=True))
        raw_buttons = len(soup.find_all(['button', 'input']))
        raw_inputs = len(soup.find_all(['input', 'textarea', 'select']))
        raw_divs = len(soup.find_all('div'))
        raw_text = len(soup.get_text(strip=True))

        # Check for common SPA indicators
        has_react = 'react' in html.lower() or 'data-reactroot' in html
        has_vue = 'vue' in html.lower() or 'data-v-' in html
        has_angular = 'ng-' in html or 'angular' in html.lower()
        has_empty_root = bool(soup.find('div', id='root') and not soup.find('div', id='root').get_text(strip=True))
        has_empty_app = bool(soup.find('div', id='app') and not soup.find('div', id='app').get_text(strip=True))

        # Check for challenge/interstitial indicators
        has_challenge = any(phrase in html.lower() for phrase in [
            'ddos-guard', 'cloudflare', 'checking your browser', 'please wait'
        ])

        return {
            "html_length": len(html),
            "text_length": raw_text,
            "raw_links": raw_links,
            "raw_buttons": raw_buttons,
            "raw_inputs": raw_inputs,
            "raw_divs": raw_divs,
            "is_spa": has_react or has_vue or has_angular,
            "spa_framework": "React" if has_react else ("Vue" if has_vue else ("Angular" if has_angular else None)),
            "empty_root": has_empty_root or has_empty_app,
            "is_challenge_page": has_challenge,
            "has_meaningful_content": raw_text > 200 and (raw_links > 3 or raw_inputs > 0)
        }

    def see_simple(self, html: str) -> str:
        """Get a compact text representation of the page for quick overview.

        Args:
            html: Raw HTML content of the page

        Returns:
            Formatted string with page content, input fields, buttons, and links
        """
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
        """Get optimized output format for LLM consumption.

        Prioritizes actionable information and structure for efficient
        LLM processing. Limits output to stay within token budgets.

        Args:
            html: Raw HTML content of the page
            max_tokens: Approximate maximum tokens for output (default 4000)

        Returns:
            Formatted string optimized for LLM context windows
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

    # Common downloadable file extensions
    DOWNLOAD_EXTENSIONS = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # Documents
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',  # Archives
        '.csv', '.json', '.xml', '.txt', '.md',  # Data files
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico',  # Images
        '.mp3', '.mp4', '.avi', '.mkv', '.mov', '.wav', '.flac',  # Media
        '.epub', '.mobi', '.azw',  # Ebooks
        '.apk', '.exe', '.dmg', '.deb', '.rpm',  # Software
    }

    # URL patterns that indicate downloadable content
    DOWNLOAD_PATH_PATTERNS = [
        '/pdf/', '/download/', '/file/', '/files/', '/downloads/',
        '/attachment/', '/attachments/', '/asset/', '/assets/',
        '/media/', '/uploads/', '/static/', '/content/',
        'download=', 'file=', 'get=',
        # Anna's Archive patterns
        '/slow_download', '/fast_download',
        # LibGen patterns
        'get.php', 'download.php', '/get/', '/ads.php',
        # General ebook site patterns
        '/libro/', '/book/', '/ebook/',
    ]

    # URL patterns that indicate detail/content pages (worth visiting)
    DETAIL_PAGE_PATTERNS = [
        '/abs/', '/paper/', '/article/', '/item/', '/view/',
        '/full/', '/detail/', '/record/', '/entry/',
        '/wiki/', '/page/', '/post/', '/blog/',
        '/product/', '/show/', '/display/',
    ]

    def _extract_links(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract links with smart relevance scoring for any content type."""
        links = []
        seen_hrefs: Set[str] = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            href_lower = href.lower()

            # Skip duplicates, empty, and anchor-only links
            if not text or href in seen_hrefs or href == "#":
                continue

            seen_hrefs.add(href)

            # Calculate relevance score based on content type
            score = 0
            link_type = "other"

            # Check if it's a direct download link
            is_download = (
                any(href_lower.endswith(ext) for ext in self.DOWNLOAD_EXTENSIONS) or
                any(pattern in href_lower for pattern in self.DOWNLOAD_PATH_PATTERNS)
            )

            # Check if it's a detail page (likely contains downloadable content)
            is_detail = any(pattern in href_lower for pattern in self.DETAIL_PAGE_PATTERNS)

            if is_download:
                score = 100  # Highest priority - direct downloads
                link_type = "download"
            elif is_detail:
                score = 75  # High priority - pages with content
                link_type = "detail"
            else:
                # Base score from text length (longer = more descriptive)
                score = min(len(text), 50)

            # Boost button-like links
            classes = str(a.get('class', [])).lower()
            if 'btn' in classes or 'button' in classes or 'download' in classes:
                score += 25

            # Boost links with relevant text
            text_lower = text.lower()
            if any(word in text_lower for word in ['download', 'pdf', 'view', 'full', 'open', 'get']):
                score += 15

            # Extra boost for Anna's Archive specific patterns
            if any(word in text_lower for word in ['slow download', 'fast download', 'partner server']):
                score += 30  # High priority - these are actual download links

            # Boost LibGen patterns
            if any(word in text_lower for word in ['libgen', 'library.lol', 'cloudflare', 'ipfs']):
                score += 20

            # Deprioritize navigation links
            if a.find_parent(['nav', 'header', 'footer']):
                score -= 40

            # Deprioritize common noise links
            if any(noise in href_lower for noise in [
                'login', 'signin', 'signup', 'register', 'cart', 'checkout',
                'account', 'profile', 'settings', 'help', 'faq', 'about',
                'contact', 'privacy', 'terms', 'cookie', 'javascript:',
                'mailto:', 'tel:', '#', 'share', 'tweet', 'facebook'
            ]):
                score -= 50

            links.append({
                "text": text[:100],
                "href": href,
                "selector": self._get_selector(a),
                "score": score,
                "type": link_type
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

    def _extract_pagination(self, soup: BeautifulSoup) -> Dict:
        """Extract pagination info for multi-page navigation."""
        pagination = {
            "has_pagination": False,
            "current_page": None,
            "next_page": None,
            "prev_page": None,
            "total_pages": None,
            "page_links": []
        }

        # Look for pagination containers
        pag_selectors = [
            '.pagination', '.pager', '.pages', '[class*="pagina"]',
            'nav[aria-label*="page"]', '[role="navigation"]',
            '.page-numbers', '.page-links'
        ]

        pag_container = None
        for selector in pag_selectors:
            pag_container = soup.select_one(selector)
            if pag_container:
                break

        # Also check for common pagination patterns in the page
        if not pag_container:
            # Look for links with page numbers
            for a in soup.find_all('a', href=True):
                href = a.get('href', '').lower()
                text = a.get_text(strip=True)
                if 'page=' in href or 'p=' in href or RE_PAGE_NUMBER.match(text):
                    pag_container = a.find_parent(['div', 'nav', 'ul'])
                    if pag_container:
                        break

        if not pag_container:
            return pagination

        pagination["has_pagination"] = True

        # Find all pagination links
        for a in pag_container.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            classes = str(a.get('class', [])).lower()

            # Detect current page
            if 'active' in classes or 'current' in classes or a.find_parent(class_=RE_ACTIVE_CURRENT):
                try:
                    pagination["current_page"] = int(text)
                except ValueError:
                    pass

            # Detect next page
            if any(w in text.lower() for w in ['next', '»', '>', 'следующая']) or 'next' in classes:
                pagination["next_page"] = href

            # Detect previous page
            if any(w in text.lower() for w in ['prev', 'previous', '«', '<', 'назад']) or 'prev' in classes:
                pagination["prev_page"] = href

            # Collect numbered page links
            if RE_PAGE_NUMBER.match(text):
                pagination["page_links"].append({
                    "page": int(text),
                    "href": href
                })

        # Sort page links and determine total
        if pagination["page_links"]:
            pagination["page_links"].sort(key=lambda x: x["page"])
            pagination["total_pages"] = max(p["page"] for p in pagination["page_links"])

        return pagination

    def _extract_images(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract images with their URLs and context."""
        images = []
        seen_srcs: Set[str] = set()

        for img in soup.find_all('img'):
            # Get image source - check src, data-src, data-original, srcset
            src = (img.get('src') or img.get('data-src') or
                   img.get('data-original') or img.get('data-lazy-src') or '')

            # Skip small images, icons, tracking pixels
            if not src or src in seen_srcs:
                continue
            if any(x in src.lower() for x in ['icon', 'logo', 'avatar', 'pixel', 'tracking', 'ads', 'btn', 'button']):
                continue

            seen_srcs.add(src)

            # Get alt text and title
            alt = img.get('alt', '')
            title = img.get('title', '')

            # Find associated link - check parent, then sibling, then container
            link_href = ''

            # 1. Check if image is inside a link
            parent_link = img.find_parent('a')
            if parent_link and parent_link.get('href'):
                link_href = parent_link.get('href', '')

            # 2. Check container (figure, div, li) for links (wallhaven pattern)
            if not link_href:
                container = img.find_parent(['figure', 'div', 'li', 'article'])
                if container:
                    # Find the first link in the same container
                    sibling_link = container.find('a', href=True)
                    if sibling_link:
                        link_href = sibling_link.get('href', '')

            # Look for data attributes with full-size URLs (common in galleries)
            full_src = (img.get('data-full') or img.get('data-wallpaper') or
                        img.get('data-large') or img.get('data-original-src') or
                        img.get('data-zoom') or '')

            images.append({
                "src": src,
                "full_src": full_src,
                "alt": alt[:100],
                "title": title[:100],
                "link": link_href,
                "selector": self._get_selector(img)
            })

        # Sort by likely importance (images with links first, then with alt text)
        images.sort(key=lambda x: (bool(x['link']), bool(x['alt']), len(x['src'])), reverse=True)
        return images

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
        text = RE_WHITESPACE.sub(' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def clear_cache(self) -> None:
        """Clear the parsing cache."""
        self._cache.clear()

