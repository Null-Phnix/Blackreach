"""
Site-Specific Handlers (v4.0.0-beta.2)

Centralized logic for handling specific sites that the agent encounters frequently.
Each handler knows how to navigate and extract content from a particular site.

Supported Sites:
- Book/Document: Anna's Archive, LibGen, Z-Library, arXiv
- Search Engines: Google, DuckDuckGo
- Images: Wallhaven, Unsplash, Pexels, Pixabay
- Code/Tech: GitHub, Stack Overflow, Hugging Face
- Information: Wikipedia, Reddit, YouTube
- Shopping: Amazon
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from abc import ABC, abstractmethod
from urllib.parse import urlparse
import re
import time


@dataclass
class SiteAction:
    """Represents an action to take on a specific site."""
    action_type: str  # click, wait, scroll, navigate
    target: str       # selector, url, or direction
    description: str
    wait_after: float = 0.5
    optional: bool = False  # If True, failure is OK


@dataclass
class HandlerResult:
    """Result from a site handler."""
    success: bool
    message: str
    actions_taken: List[SiteAction] = field(default_factory=list)
    download_url: Optional[str] = None
    next_step: Optional[str] = None  # Hint for next action
    data: Dict[str, Any] = field(default_factory=dict)


class SiteHandler(ABC):
    """Base class for site-specific handlers."""

    # Domains this handler applies to
    domains: List[str] = []

    # URL patterns for more specific matching
    url_patterns: List[re.Pattern] = []

    @classmethod
    def matches(cls, url: str) -> bool:
        """Check if this handler matches the given URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check domain list
        for d in cls.domains:
            if d in domain:
                return True

        # Check URL patterns
        for pattern in cls.url_patterns:
            if pattern.search(url):
                return True

        return False

    @abstractmethod
    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get the sequence of actions needed to download from this site."""
        pass

    @abstractmethod
    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Get the sequence of actions to search on this site."""
        pass

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Get navigation hints specific to this site."""
        return ""

    def validate_download_url(self, url: str) -> bool:
        """Check if a URL is a valid download link for this site."""
        return True


class AnnasArchiveHandler(SiteHandler):
    """Handler for Anna's Archive (annas-archive.org, annas-archive.se, etc.)."""

    domains = ["annas-archive", "anna's archive"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for Anna's Archive."""
        actions = []

        # Check if we're on a book detail page
        if "/md5/" in url:
            # Need to expand Downloads section first
            actions.append(SiteAction(
                action_type="click",
                target='button:has-text("Downloads")',
                description="Expand downloads section",
                wait_after=1.0
            ))

            # Then click a download link
            actions.append(SiteAction(
                action_type="click",
                target='a[href*="/slow_download"]',
                description="Click slow download link",
                optional=True
            ))

            # Alternative: fast download
            actions.append(SiteAction(
                action_type="click",
                target='a[href*="/fast_download"]',
                description="Click fast download link",
                optional=True
            ))

        # On download page itself
        elif "/slow_download/" in url or "/fast_download/" in url:
            # Direct download link should be visible
            actions.append(SiteAction(
                action_type="click",
                target='a:has-text("Download")',
                description="Click final download button"
            ))

        return actions

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Anna's Archive."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for Anna's Archive."""
        hints = []

        if "/md5/" in url:
            hints.append("ANNA'S ARCHIVE BOOK PAGE: Click 'Downloads' button to expand download options, then click 'Slow download' or 'Fast download'.")
        elif "/slow_download/" in url:
            hints.append("ANNA'S ARCHIVE DOWNLOAD PAGE: Wait for timer or click the download button when ready.")
        elif "search" in url.lower() or "q=" in url.lower():
            hints.append("ANNA'S ARCHIVE SEARCH: Click on a book title to view details and download options.")

        return " ".join(hints)

    def validate_download_url(self, url: str) -> bool:
        """Validate Anna's Archive download URLs."""
        return "/slow_download/" in url or "/fast_download/" in url


class LibGenHandler(SiteHandler):
    """Handler for Library Genesis (libgen.is, libgen.rs, library.lol, etc.)."""

    domains = ["libgen", "library.lol", "libgen.is", "libgen.rs", "libgen.li"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for LibGen."""
        actions = []

        # On book detail page
        if "book/index.php" in url or "/fiction/" in url or "get.php" in url:
            # Try GET button first
            actions.append(SiteAction(
                action_type="click",
                target='a:has-text("GET")',
                description="Click GET download button",
                optional=True
            ))

            # Alternative: Libgen.li mirror
            actions.append(SiteAction(
                action_type="click",
                target='a:has-text("Libgen.li")',
                description="Click Libgen.li mirror",
                optional=True
            ))

            # Alternative: Cloudflare
            actions.append(SiteAction(
                action_type="click",
                target='a:has-text("Cloudflare")',
                description="Click Cloudflare mirror",
                optional=True
            ))

            # Alternative: IPFS
            actions.append(SiteAction(
                action_type="click",
                target='a:has-text("IPFS")',
                description="Click IPFS mirror",
                optional=True
            ))

        # On library.lol download page
        elif "library.lol" in url:
            actions.append(SiteAction(
                action_type="click",
                target='a:has-text("GET")',
                description="Click GET button",
                optional=True
            ))

            actions.append(SiteAction(
                action_type="click",
                target='a[href*="cloudflare"]',
                description="Click Cloudflare link",
                optional=True
            ))

        return actions

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on LibGen."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="req"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='input[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for LibGen."""
        if "search.php" in url.lower():
            return "LIBGEN SEARCH RESULTS: Click on a book title to go to its download page."
        elif "book/index.php" in url or "/fiction/" in url:
            return "LIBGEN BOOK PAGE: Look for 'GET' button or mirror links like 'Libgen.li', 'Cloudflare', or 'IPFS'."
        elif "library.lol" in url:
            return "LIBRARY.LOL: This is a download mirror - look for 'GET' or 'Cloudflare' download links."
        return ""


class ZLibraryHandler(SiteHandler):
    """Handler for Z-Library variants."""

    domains = ["z-lib", "zlibrary", "singlelogin.re", "z-library"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for Z-Library."""
        return [
            SiteAction(
                action_type="click",
                target='a.dlButton, button:has-text("Download")',
                description="Click download button",
                wait_after=2.0
            ),
            SiteAction(
                action_type="click",
                target='a:has-text("Download")',
                description="Click download link",
                optional=True
            )
        ]

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Z-Library."""
        return [
            SiteAction(
                action_type="type",
                target='input#searchFieldx, input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"], input[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]


class GoogleHandler(SiteHandler):
    """Handler for Google Search."""

    domains = ["google.com", "www.google"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Google doesn't have direct downloads - just navigation."""
        return []

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Google."""
        return [
            SiteAction(
                action_type="type",
                target='textarea[name="q"], input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.3
            ),
            SiteAction(
                action_type="click",
                target='input[name="btnK"], button[type="submit"]',
                description="Submit search",
                wait_after=1.5
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for Google."""
        if "search?" in url or "q=" in url:
            return "GOOGLE RESULTS: Click on a result link to visit that page. Avoid ads (marked 'Ad' or 'Sponsored')."
        return "GOOGLE: Type your search query in the search box."


class ArxivHandler(SiteHandler):
    """Handler for arXiv.org."""

    domains = ["arxiv.org"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for arXiv."""
        if "/abs/" in url:
            return [
                SiteAction(
                    action_type="click",
                    target='a:has-text("PDF")',
                    description="Click PDF download link",
                    wait_after=2.0
                )
            ]
        elif "/pdf/" in url:
            return [
                SiteAction(
                    action_type="download",
                    target=url,
                    description="Download PDF directly"
                )
            ]
        return []

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on arXiv."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="query"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]


class WallhavenHandler(SiteHandler):
    """Handler for Wallhaven wallpaper site."""

    domains = ["wallhaven.cc"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for Wallhaven."""
        return [
            SiteAction(
                action_type="click",
                target='a:has-text("Download")',
                description="Click download button",
                optional=True
            ),
            SiteAction(
                action_type="click",
                target='img#wallpaper',
                description="Click wallpaper image for full size",
                optional=True
            )
        ]

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Wallhaven."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]


class UnsplashHandler(SiteHandler):
    """Handler for Unsplash image site."""

    domains = ["unsplash.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for Unsplash."""
        return [
            SiteAction(
                action_type="click",
                target='a:has-text("Download free")',
                description="Click download button",
                wait_after=1.0
            ),
            SiteAction(
                action_type="click",
                target='button:has-text("Download")',
                description="Click download in modal",
                optional=True
            )
        ]

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Unsplash."""
        return [
            SiteAction(
                action_type="type",
                target='input[type="search"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]


class GitHubHandler(SiteHandler):
    """Handler for GitHub repositories and releases."""

    domains = ["github.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for GitHub releases."""
        actions = []

        if "/releases" in url:
            # On releases page, look for download assets
            actions.append(SiteAction(
                action_type="click",
                target='a[href*="/releases/download/"]',
                description="Click release download link",
                optional=True
            ))
            # Or expand assets section
            actions.append(SiteAction(
                action_type="click",
                target='summary:has-text("Assets")',
                description="Expand assets section",
                optional=True
            ))

        return actions

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on GitHub."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for GitHub."""
        if "/releases" in url:
            return "GITHUB RELEASES: Click on a release asset to download, or expand 'Assets' to see all files."
        elif "/blob/" in url:
            return "GITHUB FILE VIEW: Click 'Raw' to view raw file, or 'Download' button if available."
        elif "/tree/" in url or url.endswith((".com", ".com/")):
            return "GITHUB REPO: Navigate to 'Releases' for downloadable files, or browse the file tree."
        return "GITHUB: Use the search bar or navigate to a repository."


class WikipediaHandler(SiteHandler):
    """Handler for Wikipedia."""

    domains = ["wikipedia.org", "en.wikipedia", "en.m.wikipedia"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Wikipedia doesn't have traditional downloads."""
        return []

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Wikipedia."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="search"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for Wikipedia."""
        if "/wiki/" in url:
            return "WIKIPEDIA ARTICLE: Scroll to find information, click section links in Contents, or use internal links."
        return "WIKIPEDIA: Type in the search box to find articles."


class DuckDuckGoHandler(SiteHandler):
    """Handler for DuckDuckGo search engine."""

    domains = ["duckduckgo.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """DuckDuckGo doesn't have downloads."""
        return []

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on DuckDuckGo."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for DuckDuckGo."""
        if "q=" in url:
            return "DUCKDUCKGO RESULTS: Click on a result link to visit that page. Results are not tracked."
        return "DUCKDUCKGO: Type your search query in the search box."


class RedditHandler(SiteHandler):
    """Handler for Reddit."""

    domains = ["reddit.com", "old.reddit.com", "www.reddit.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Reddit has media but complex download patterns."""
        actions = []

        # For image posts
        actions.append(SiteAction(
            action_type="click",
            target='a[href*="i.redd.it"], a[href*="i.imgur"]',
            description="Click image link",
            optional=True
        ))

        return actions

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Reddit."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for Reddit."""
        if "/comments/" in url:
            return "REDDIT POST: Scroll through comments, click links shared by users, or view media attachments."
        elif "/r/" in url:
            return "REDDIT SUBREDDIT: Browse posts, click titles to view full post and comments."
        return "REDDIT: Use search or navigate to a subreddit (r/subreddit)."


class YouTubeHandler(SiteHandler):
    """Handler for YouTube (navigation only - no downloads)."""

    domains = ["youtube.com", "youtu.be", "www.youtube.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """YouTube doesn't allow direct downloads."""
        return []

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on YouTube."""
        return [
            SiteAction(
                action_type="type",
                target='input#search, input[name="search_query"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button#search-icon-legacy',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for YouTube."""
        if "/watch" in url:
            return "YOUTUBE VIDEO: View video info, read description, check comments. Cannot download directly."
        elif "/results" in url:
            return "YOUTUBE SEARCH: Click on a video thumbnail or title to watch it."
        return "YOUTUBE: Use search bar to find videos."


class StackOverflowHandler(SiteHandler):
    """Handler for Stack Overflow and Stack Exchange sites."""

    domains = ["stackoverflow.com", "stackexchange.com", "superuser.com", "serverfault.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Stack Overflow doesn't have downloads."""
        return []

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Stack Overflow."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for Stack Overflow."""
        if "/questions/" in url:
            return "STACKOVERFLOW QUESTION: Read answers (sorted by votes), check accepted answer (green checkmark)."
        return "STACKOVERFLOW: Search for programming questions or browse by tags."


class PexelsHandler(SiteHandler):
    """Handler for Pexels free stock photos."""

    domains = ["pexels.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for Pexels."""
        return [
            SiteAction(
                action_type="click",
                target='button:has-text("Free Download")',
                description="Click free download button",
                wait_after=1.0
            ),
            SiteAction(
                action_type="click",
                target='a[download]',
                description="Click download link",
                optional=True
            )
        ]

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Pexels."""
        return [
            SiteAction(
                action_type="type",
                target='input[type="search"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]


class PixabayHandler(SiteHandler):
    """Handler for Pixabay free images."""

    domains = ["pixabay.com"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for Pixabay."""
        return [
            SiteAction(
                action_type="click",
                target='button:has-text("Download")',
                description="Click download button",
                wait_after=1.0
            ),
            SiteAction(
                action_type="click",
                target='a:has-text("Download")',
                description="Click download link in modal",
                optional=True
            )
        ]

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Pixabay."""
        return [
            SiteAction(
                action_type="type",
                target='input[name="q"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]


class AmazonHandler(SiteHandler):
    """Handler for Amazon (product search, no downloads)."""

    domains = ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Amazon doesn't have direct file downloads."""
        return []

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Amazon."""
        return [
            SiteAction(
                action_type="type",
                target='input#twotabsearchtextbox, input[name="field-keywords"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='input#nav-search-submit-button',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for Amazon."""
        if "/dp/" in url or "/product/" in url:
            return "AMAZON PRODUCT: View product details, price, reviews. Check 'Buy Now' or 'Add to Cart'."
        elif "/s?" in url:
            return "AMAZON SEARCH: Click on product titles or images to view details. Check ratings and prices."
        return "AMAZON: Use search bar to find products."


class HuggingFaceHandler(SiteHandler):
    """Handler for Hugging Face model hub."""

    domains = ["huggingface.co"]

    def get_download_actions(self, html: str, url: str) -> List[SiteAction]:
        """Get download sequence for Hugging Face models."""
        return [
            SiteAction(
                action_type="click",
                target='a:has-text("Files and versions")',
                description="Go to files tab",
                optional=True,
                wait_after=1.0
            ),
            SiteAction(
                action_type="click",
                target='a[download]',
                description="Click download link",
                optional=True
            )
        ]

    def get_search_actions(self, query: str) -> List[SiteAction]:
        """Search on Hugging Face."""
        return [
            SiteAction(
                action_type="type",
                target='input[placeholder*="Search"]',
                description=f"Type search query: {query}",
                wait_after=0.5
            ),
            SiteAction(
                action_type="click",
                target='button[type="submit"]',
                description="Submit search",
                wait_after=2.0
            )
        ]

    def get_navigation_hints(self, html: str, url: str, goal: str) -> str:
        """Navigation hints for Hugging Face."""
        if "/models/" in url or url.endswith("/models"):
            return "HUGGINGFACE MODELS: Browse models, filter by task type, click to view model details."
        return "HUGGINGFACE: Search for AI models, datasets, or spaces."


# Registry of all handlers
SITE_HANDLERS: List[type] = [
    AnnasArchiveHandler,
    LibGenHandler,
    ZLibraryHandler,
    GoogleHandler,
    ArxivHandler,
    WallhavenHandler,
    UnsplashHandler,
    GitHubHandler,
    WikipediaHandler,
    DuckDuckGoHandler,
    RedditHandler,
    YouTubeHandler,
    StackOverflowHandler,
    PexelsHandler,
    PixabayHandler,
    AmazonHandler,
    HuggingFaceHandler,
]


def get_handler_for_url(url: str) -> Optional[SiteHandler]:
    """Get the appropriate handler for a URL."""
    for handler_class in SITE_HANDLERS:
        if handler_class.matches(url):
            return handler_class()
    return None


def get_site_hints(url: str, html: str, goal: str) -> str:
    """Get navigation hints for the current site."""
    handler = get_handler_for_url(url)
    if handler:
        return handler.get_navigation_hints(html, url, goal)
    return ""


def get_download_sequence(url: str, html: str) -> List[SiteAction]:
    """Get the download action sequence for a site."""
    handler = get_handler_for_url(url)
    if handler:
        return handler.get_download_actions(html, url)
    return []


def get_search_sequence(url: str, query: str) -> List[SiteAction]:
    """Get the search action sequence for a site."""
    handler = get_handler_for_url(url)
    if handler:
        return handler.get_search_actions(query)
    return []


class SiteHandlerExecutor:
    """Executes site handler action sequences."""

    def __init__(self, hand, pause_between_actions: float = 0.5):
        self.hand = hand
        self.pause = pause_between_actions

    def execute_actions(self, actions: List[SiteAction]) -> HandlerResult:
        """Execute a sequence of site-specific actions."""
        results = []
        last_error = None

        for action in actions:
            try:
                if action.action_type == "click":
                    try:
                        loc = self.hand.page.locator(action.target)
                        if loc.count() > 0 and loc.first.is_visible():
                            loc.first.click()
                            results.append(action)
                            time.sleep(action.wait_after)
                        elif not action.optional:
                            last_error = f"Element not found: {action.target}"
                    except Exception as e:
                        if not action.optional:
                            last_error = str(e)

                elif action.action_type == "type":
                    self.hand.type(action.target, action.description.split(": ")[-1])
                    results.append(action)
                    time.sleep(action.wait_after)

                elif action.action_type == "scroll":
                    direction = "down" if "down" in action.target.lower() else "up"
                    self.hand.scroll(direction, 500)
                    results.append(action)
                    time.sleep(action.wait_after)

                elif action.action_type == "wait":
                    time.sleep(float(action.target))
                    results.append(action)

                elif action.action_type == "navigate":
                    self.hand.goto(action.target)
                    results.append(action)
                    time.sleep(action.wait_after)

            except Exception as e:
                if not action.optional:
                    last_error = str(e)
                    break

        success = len(results) > 0 and last_error is None
        return HandlerResult(
            success=success,
            message=last_error or f"Executed {len(results)} actions",
            actions_taken=results
        )
