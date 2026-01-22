"""
The Hand - Browser Controller using Playwright

Controls the browser: click, type, scroll, navigate, screenshot, download.
Now with stealth and resilience features.
"""

from playwright.sync_api import sync_playwright, Browser, Page, Playwright, BrowserContext, Route, Download
from typing import Optional, List, Union, Callable
from pathlib import Path
import time
import random
import hashlib

from blackreach.stealth import Stealth, StealthConfig
from blackreach.resilience import (
    SmartSelector, PopupHandler, WaitConditions,
    retry_with_backoff, RetryConfig
)


class Hand:
    """
    The Hand that controls the browser.

    Features:
    - Stealth mode for bot detection evasion
    - Human-like interactions (mouse movement, typing)
    - Smart selectors with fallbacks
    - Automatic popup/cookie handling
    - Retry logic with exponential backoff
    """

    def __init__(
        self,
        headless: bool = False,
        stealth_config: Optional[StealthConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        download_dir: Optional[Path] = None
    ):
        self.headless = headless
        self.stealth = Stealth(stealth_config or StealthConfig())
        self.retry_config = retry_config or RetryConfig()
        self.download_dir = download_dir or Path("./downloads")

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # Helpers (initialized after wake)
        self._selector: Optional[SmartSelector] = None
        self._popups: Optional[PopupHandler] = None
        self._waits: Optional[WaitConditions] = None

        # State tracking
        self._mouse_pos = (0, 0)

        # Download tracking
        self._pending_downloads: List[Download] = []
        self._download_callback: Optional[Callable] = None

    def wake(self) -> None:
        """Start the browser with stealth configuration."""
        self._playwright = sync_playwright().start()

        # Ensure download directory exists
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Browser launch args for stealth
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        # Get proxy if configured
        proxy = self.stealth.get_next_proxy()
        proxy_config = {"server": proxy} if proxy else None

        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
            downloads_path=str(self.download_dir)  # Set download path at browser level
        )

        # Create context with randomized fingerprint
        viewport = self.stealth.get_random_viewport() if self.stealth.config.randomize_viewport else {"width": 1280, "height": 800}
        user_agent = self.stealth.get_random_user_agent() if self.stealth.config.randomize_user_agent else None

        context_options = {
            "viewport": viewport,
            "proxy": proxy_config,
            "accept_downloads": True,  # Enable downloads
        }
        if user_agent:
            context_options["user_agent"] = user_agent

        self._context = self._browser.new_context(**context_options)
        self._page = self._context.new_page()

        # Set up download handler
        self._page.on("download", self._handle_download)

        # Set up resource blocking
        self._setup_resource_blocking()

        # Inject stealth scripts
        self._inject_stealth_scripts()

        # Initialize helpers
        self._selector = SmartSelector(self._page)
        self._popups = PopupHandler(self._page)
        self._waits = WaitConditions(self._page)

    def _setup_resource_blocking(self) -> None:
        """Block unnecessary resources for performance."""
        blocked_types = self.stealth.get_resource_types_to_block()

        def handle_route(route: Route):
            if route.request.resource_type in blocked_types:
                route.abort()
            elif self.stealth.should_block_url(route.request.url):
                route.abort()
            else:
                route.continue_()

        if blocked_types or self.stealth.config.block_tracking:
            self._page.route("**/*", handle_route)

    def _inject_stealth_scripts(self) -> None:
        """Inject JavaScript to hide automation and spoof fingerprints."""
        # Combine all stealth scripts into single injection (faster startup)
        scripts = self.stealth.get_all_stealth_scripts()
        if scripts:
            combined = "\n".join(scripts)
            self._page.add_init_script(combined)
    
    def sleep(self) -> None:
        """Close the browser."""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Hand is not awake. Call wake() first.")
        return self._page

    @property
    def selector(self) -> SmartSelector:
        """Get smart selector helper."""
        if not self._selector:
            raise RuntimeError("Hand is not awake. Call wake() first.")
        return self._selector

    @property
    def popups(self) -> PopupHandler:
        """Get popup handler."""
        if not self._popups:
            raise RuntimeError("Hand is not awake. Call wake() first.")
        return self._popups

    @property
    def waits(self) -> WaitConditions:
        """Get wait conditions helper."""
        if not self._waits:
            raise RuntimeError("Hand is not awake. Call wake() first.")
        return self._waits

    def _human_delay(self, min_s: float = None, max_s: float = None) -> None:
        """Add human-like random delay."""
        delay = self.stealth.random_delay(min_s, max_s)
        time.sleep(delay)

    def _move_mouse_human(self, x: float, y: float) -> None:
        """Move mouse in human-like curved path."""
        if not self.stealth.config.human_mouse:
            self.page.mouse.move(x, y)
            return

        path = self.stealth.generate_bezier_path(self._mouse_pos, (x, y))
        for px, py in path:
            self.page.mouse.move(px, py)
            time.sleep(random.uniform(0.005, 0.02))

        self._mouse_pos = (x, y)

    # === Navigation ===

    @retry_with_backoff()
    def goto(self, url: str, handle_popups: bool = True) -> dict:
        """Navigate to a URL with retry logic."""
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Wait for JavaScript to render dynamic elements
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # Don't fail if network doesn't go idle

        self._human_delay(0.5, 1.5)

        if handle_popups:
            self._popups.handle_all()
            # Try again after a moment (popups may appear after JS runs)
            self._human_delay(0.3, 0.5)
            self._popups.handle_all()

        return {"action": "goto", "url": url, "title": self.page.title()}

    def back(self) -> dict:
        """Go back in history."""
        self.page.go_back()
        self._human_delay(0.3, 0.8)
        return {"action": "back", "title": self.page.title()}

    def forward(self) -> dict:
        """Go forward in history."""
        self.page.go_forward()
        self._human_delay(0.3, 0.8)
        return {"action": "forward", "title": self.page.title()}

    def refresh(self) -> dict:
        """Refresh the page."""
        self.page.reload()
        self._human_delay(0.5, 1.0)
        return {"action": "refresh", "title": self.page.title()}

    # === Interaction ===

    def click(self, selector: Union[str, List[str]], human: bool = None) -> dict:
        """Click on an element."""
        human = human if human is not None else self.stealth.config.human_mouse

        # Get locator
        if isinstance(selector, list):
            locator = self._selector.find(selector) if self._selector else None
            if not locator:
                # Fallback: try each selector
                for sel in selector:
                    try:
                        loc = self.page.locator(sel)
                        if loc.count() > 0:
                            locator = loc.first
                            break
                    except Exception:
                        continue
        else:
            locator = self.page.locator(selector).first

        if not locator:
            raise ValueError(f"Element not found: {selector}")

        # Simple human delay before click
        if human:
            self._human_delay(0.1, 0.3)

        locator.click()

        if human:
            self._human_delay(0.2, 0.5)
        else:
            time.sleep(0.3)

        return {"action": "click", "selector": str(selector)}

    def type(self, selector: str, text: str, human: bool = None, clear: bool = True) -> dict:
        """Type text into an element with fallback selectors."""
        human = human if human is not None else self.stealth.config.human_mouse

        # Build list of selectors to try (primary + fallbacks for search inputs)
        selectors_to_try = [selector]

        # If this looks like a search input, add common fallbacks
        if any(x in selector.lower() for x in ['search', 'query', 'q', 'input']):
            selectors_to_try.extend([
                'input[type="search"]',
                'input[name="q"]',
                'input[name="search"]',
                'input[aria-label*="Search"]',
                'input[placeholder*="Search"]',
                'textarea[name="q"]',
                '[role="searchbox"]',
                '[role="combobox"]',
                '.search-input',
                '#search',
            ])

        locator = None
        used_selector = selector

        # Try each selector until one works
        for sel in selectors_to_try:
            try:
                loc = self.page.locator(sel).first
                loc.wait_for(state="visible", timeout=3000)
                if loc.is_visible():
                    locator = loc
                    used_selector = sel
                    break
            except Exception:
                continue

        if locator is None:
            raise ValueError(f"Could not find visible element with selector: {selector}")

        # Now type into the found element
        try:
            if human:
                # Click to focus
                locator.click()
                self._human_delay(0.05, 0.15)

                # Clear existing content if requested
                if clear:
                    self.page.keyboard.press("Control+a")
                    self.page.keyboard.press("Backspace")
                    self._human_delay(0.05, 0.1)

                # Type character by character
                for char in text:
                    self.page.keyboard.type(char)
                    time.sleep(self.stealth.typing_delay())
            else:
                if clear:
                    locator.fill(text)
                else:
                    locator.click()
                    self.page.keyboard.type(text)
        except Exception as e:
            # Last resort: try using fill() directly
            try:
                locator.fill(text)
            except Exception:
                raise e

        return {"action": "type", "selector": used_selector, "text": text}

    def press(self, key: str) -> dict:
        """Press a key (e.g., 'Enter', 'Escape')."""
        self._human_delay(0.1, 0.2)
        self.page.keyboard.press(key)
        self._human_delay(0.2, 0.5)
        return {"action": "press", "key": key}

    def scroll(self, direction: str = "down", amount: int = 500, human: bool = None) -> dict:
        """Scroll the page."""
        human = human if human is not None else self.stealth.config.human_mouse
        delta = amount if direction == "down" else -amount

        if human:
            # Scroll in smaller chunks
            remaining = abs(delta)
            sign = 1 if delta > 0 else -1
            while remaining > 0:
                chunk = min(remaining, random.randint(80, 150))
                self.page.mouse.wheel(0, chunk * sign)
                remaining -= chunk
                time.sleep(random.uniform(0.03, 0.08))
        else:
            self.page.mouse.wheel(0, delta)

        return {"action": "scroll", "direction": direction, "amount": amount}

    def hover(self, selector: str) -> dict:
        """Hover over an element."""
        self.page.locator(selector).first.hover()
        return {"action": "hover", "selector": selector}
    
    # === Reading ===

    def get_html(self, wait_for_load: bool = True, retries: int = 3) -> str:
        """Get the current page HTML with retry logic for dynamic pages."""
        if wait_for_load:
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except:
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                except:
                    pass  # Continue anyway

        # Retry logic for pages that are still navigating
        for attempt in range(retries):
            try:
                return self.page.content()
            except Exception as e:
                if "navigating" in str(e).lower() and attempt < retries - 1:
                    time.sleep(1)  # Wait a bit and retry
                else:
                    raise

    def get_url(self) -> str:
        """Get the current URL."""
        return self.page.url

    def get_title(self, retries: int = 3) -> str:
        """Get the current page title with retry for navigation."""
        for attempt in range(retries):
            try:
                return self.page.title()
            except Exception as e:
                if "navigation" in str(e).lower() or "destroyed" in str(e).lower():
                    if attempt < retries - 1:
                        time.sleep(1)
                        try:
                            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                        except:
                            pass
                    else:
                        return self.page.url  # Fallback to URL
                else:
                    raise
        return ""

    def wait_for_navigation(self, timeout: float = 10000) -> None:
        """Wait for page to finish navigating."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except:
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass

    def screenshot(self, path: str = "screenshot.png", full_page: bool = False) -> dict:
        """Take a screenshot."""
        self.page.screenshot(path=path, full_page=full_page)
        return {"action": "screenshot", "path": path}

    # === Downloads ===

    def _handle_download(self, download: Download) -> None:
        """Internal handler for download events."""
        self._pending_downloads.append(download)
        if self._download_callback:
            self._download_callback(download)

    def set_download_callback(self, callback: Callable[[Download], None]) -> None:
        """Set a callback for download events."""
        self._download_callback = callback

    def download_file(self, selector: str = None, url: str = None, timeout: int = 60000) -> dict:
        """
        Download a file by clicking a link or navigating to a URL.

        Args:
            selector: CSS selector for download link/button
            url: Direct URL to download
            timeout: Max time to wait for download (ms)

        Returns:
            Dict with download info: path, filename, size, hash
        """
        self._pending_downloads.clear()

        if url:
            # Direct download via navigation
            # Note: page.goto() will throw "Download is starting" for direct file URLs
            # We catch this and wait for the download
            with self.page.expect_download(timeout=timeout) as download_info:
                try:
                    self.page.goto(url, wait_until="commit", timeout=timeout)
                except Exception as e:
                    # "Download is starting" error is expected for direct file URLs
                    if "Download is starting" not in str(e):
                        raise
            download = download_info.value
        elif selector:
            # Download by clicking
            with self.page.expect_download(timeout=timeout) as download_info:
                self.page.locator(selector).first.click()
            download = download_info.value
        else:
            raise ValueError("Must provide either selector or url")

        # Save to download directory
        suggested_name = download.suggested_filename
        save_path = self.download_dir / suggested_name

        # Handle duplicate filenames
        counter = 1
        while save_path.exists():
            stem = save_path.stem.rsplit('_', 1)[0] if '_' in save_path.stem else save_path.stem
            save_path = self.download_dir / f"{stem}_{counter}{save_path.suffix}"
            counter += 1

        download.save_as(str(save_path))

        # Compute file hash and size
        file_hash = self._compute_hash(save_path)
        file_size = save_path.stat().st_size

        return {
            "action": "download",
            "filename": save_path.name,
            "path": str(save_path),
            "size": file_size,
            "hash": file_hash,
            "url": download.url
        }

    def download_link(self, href: str, timeout: int = 60000) -> dict:
        """
        Download a file from a direct link URL.

        This handles both regular file URLs and blob URLs.
        """
        return self.download_file(url=href, timeout=timeout)

    def click_and_download(self, selector: str, timeout: int = 60000) -> dict:
        """
        Click an element and wait for download to start.

        Useful for download buttons that don't have direct URLs.
        """
        return self.download_file(selector=selector, timeout=timeout)

    def get_pending_downloads(self) -> List[Download]:
        """Get list of pending/recent downloads."""
        return self._pending_downloads.copy()

    def wait_for_download(self, timeout: int = 60000) -> Optional[dict]:
        """
        Wait for any download to complete.

        Returns download info or None if timeout.
        """
        try:
            with self.page.expect_download(timeout=timeout) as download_info:
                pass  # Just wait
            download = download_info.value

            save_path = self.download_dir / download.suggested_filename
            download.save_as(str(save_path))

            return {
                "filename": save_path.name,
                "path": str(save_path),
                "size": save_path.stat().st_size,
                "hash": self._compute_hash(save_path),
                "url": download.url
            }
        except Exception:
            return None

    def _compute_hash(self, path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # === Smart Actions ===

    def smart_click(self, text: str, tag: str = "*") -> dict:
        """Click element by its visible text."""
        locator = self.selector.find_by_text(text, tag)
        if not locator:
            raise ValueError(f"No element found with text: {text}")
        locator.click()
        self._human_delay()
        return {"action": "smart_click", "text": text}

    def smart_type(self, text: str, into: str = None, placeholder: str = None, label: str = None) -> dict:
        """Type into input found by various attributes."""
        locator = self.selector.find_input(name=into, placeholder=placeholder, label=label)
        if not locator:
            raise ValueError(f"No input found matching criteria")
        locator.fill(text)
        return {"action": "smart_type", "text": text}

    def wait_and_click(self, selector: str, timeout: float = 10000) -> dict:
        """Wait for element then click."""
        self.waits.wait_for_element(selector, timeout=timeout)
        return self.click(selector)

    def dismiss_popups(self) -> dict:
        """Dismiss any visible popups/cookie banners."""
        result = self.popups.handle_all()
        return {"action": "dismiss_popups", **result}

    # === Execution ===

    def execute(self, command: dict) -> dict:
        """Execute a command dict from the Brain."""
        action = command.get("action")
        human = command.get("human", True)

        if action == "goto":
            return self.goto(command["url"])
        elif action == "click":
            return self.click(command["selector"], human=human)
        elif action == "type":
            return self.type(command["selector"], command["text"], human=human)
        elif action == "press":
            return self.press(command["key"])
        elif action == "scroll":
            return self.scroll(command.get("direction", "down"), command.get("amount", 500), human=human)
        elif action == "back":
            return self.back()
        elif action == "forward":
            return self.forward()
        elif action == "refresh":
            return self.refresh()
        elif action == "hover":
            return self.hover(command["selector"])
        elif action == "screenshot":
            return self.screenshot(command.get("path", "screenshot.png"))
        elif action == "wait":
            time.sleep(command.get("seconds", 1))
            return {"action": "wait", "seconds": command.get("seconds", 1)}
        elif action == "smart_click":
            return self.smart_click(command["text"], command.get("tag", "*"))
        elif action == "smart_type":
            return self.smart_type(command["text"], command.get("into"), command.get("placeholder"), command.get("label"))
        elif action == "dismiss_popups":
            return self.dismiss_popups()
        elif action == "wait_and_click":
            return self.wait_and_click(command["selector"], command.get("timeout", 10000))
        else:
            raise ValueError(f"Unknown action: {action}")

