"""
Bulk HTTP Fetcher — fast parallel page fetching for lightweight/static sites.

When BrowserRouter says a URL is lightweight, there's no reason to spin up
a whole browser. Just fire httpx requests with sensible headers and parse
the HTML with BeautifulSoup. For list pages, we can blast through dozens
of URLs in parallel using ThreadPoolExecutor.

Use this for:
  - Search result pages
  - Wikipedia articles
  - ArXiv abstracts
  - Static documentation
  - API endpoints
  - Any site where adaptive_browser.scan_url() returns mode=LIGHTWEIGHT
"""

import concurrent.futures
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union


try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


@dataclass
class FetchResult:
    url: str
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    html: str = ""
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    content_type: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    def soup(self) -> "BeautifulSoup":
        """Parse HTML lazily with BeautifulSoup."""
        if not BS4_AVAILABLE:
            raise RuntimeError("beautifulsoup4 is required for soup()")
        return BeautifulSoup(self.html, "html.parser")

    def text_content(self) -> str:
        """Extract visible text (fast, no JS execution)."""
        if not BS4_AVAILABLE or not self.html:
            return self.html
        soup = self.soup()
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()
        return soup.get_text(separator="\n", strip=True)

    def extract_links(self, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """Extract all <a href> links with text."""
        if not BS4_AVAILABLE or not self.html:
            return []
        soup = self.soup()
        from urllib.parse import urljoin
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if base_url and href.startswith("/"):
                href = urljoin(base_url, href)
            links.append({
                "url": href,
                "text": a.get_text(strip=True),
                "title": a.get("title", ""),
            })
        return links

    def extract_tables(self, max_rows: int = 1000) -> List[List[List[str]]]:
        """Extract all HTML tables as lists of lists."""
        if not BS4_AVAILABLE or not self.html:
            return []
        soup = self.soup()
        tables = []
        for table in soup.find_all("table")[:20]:  # cap at 20 tables
            rows = []
            for tr in table.find_all("tr")[:max_rows]:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return tables

    def extract_title(self) -> str:
        """Get page title."""
        if not BS4_AVAILABLE or not self.html:
            m = re.search(r"<\s*title[^>]*>(.*?)<\\/\s*title\s*>", self.html, re.I | re.S)
            return m.group(1).strip() if m else ""
        return self.soup().title.get_text(strip=True) if self.soup().title else ""


class BulkFetcher:
    """
    Parallel HTTP fetcher for bulk scraping of lightweight sites.

    Example:
        fetcher = BulkFetcher(workers=8)
        results = fetcher.fetch_many(["https://en.wikipedia.org/wiki/X",
                                      "https://en.wikipedia.org/wiki/Y"])
    """

    def __init__(
        self,
        workers: int = 8,
        timeout: float = 15.0,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 1,
        retry_delay: float = 1.0,
        respect_robots: bool = True,
    ):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for BulkFetcher. pip install httpx")
        self.workers = workers
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.respect_robots = respect_robots
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/133.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }
        self._disallowed: Dict[str, Set[str]] = {}  # domain -> {paths}
        self._client: Optional[httpx.Client] = None

    def __enter__(self):
        self._client = httpx.Client(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
            http2=False,         # HTTP/2 triggers bot detection more often
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def fetch(self, url: str, retries: int = 0) -> FetchResult:
        """Fetch a single URL synchronously."""
        if self._client is None:
            with self._client() as client:
                return self._do_fetch(client, url, retries)
        return self._do_fetch(self._client, url, retries)

    def fetch_many(self, urls: List[str], progress_cb: Optional[Callable[[int, int], None]] = None) -> List[FetchResult]:
        """Fetch multiple URLs in parallel with ThreadPoolExecutor."""
        if not urls:
            return []

        results: List[FetchResult] = []
        total = len(urls)
        done = 0

        with self if self._client else self.__enter__():
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.workers, total)) as ex:
                futures = {ex.submit(self._do_fetch, self._client, url, 0): url for url in urls}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    results.append(result)
                    done += 1
                    if progress_cb:
                        progress_cb(done, total)

        # Return in original order — this is what callers usually expect
        url_to_result = {r.url: r for r in results}
        return [url_to_result.get(u, FetchResult(url=u, status=0, error="missing")) for u in urls]

    def fetch_generator(self, urls: List[str]) -> FetchResult:
        """Yield results as they come in (for streaming progress)."""
        with self if self._client else self.__enter__():
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.workers, len(urls))) as ex:
                futures = {ex.submit(self._do_fetch, self._client, url, 0): url for url in urls}
                for future in concurrent.futures.as_completed(futures):
                    yield future.result()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_fetch(self, client: httpx.Client, url: str, retries: int) -> FetchResult:
        start = time.perf_counter()
        try:
            resp = client.get(url)
            elapsed = (time.perf_counter() - start) * 1000

            return FetchResult(
                url=url,
                status=resp.status_code,
                headers=dict(resp.headers),
                html=resp.text,
                elapsed_ms=elapsed,
                content_type=resp.headers.get("content-type", ""),
            )
        except Exception as e:
            if retries < self.max_retries:
                time.sleep(self.retry_delay)
                return self._do_fetch(client, url, retries + 1)
            elapsed = (time.perf_counter() - start) * 1000
            return FetchResult(
                url=url, status=0, error=str(e), elapsed_ms=elapsed
            )
