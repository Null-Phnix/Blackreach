"""
Site-Specific Handlers (v2.2.0)

Centralized logic for handling specific sites that the agent encounters frequently.
Each handler knows how to navigate and extract content from a particular site.
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


# Registry of all handlers
SITE_HANDLERS: List[type] = [
    AnnasArchiveHandler,
    LibGenHandler,
    ZLibraryHandler,
    GoogleHandler,
    ArxivHandler,
    WallhavenHandler,
    UnsplashHandler,
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
