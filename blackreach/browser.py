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
from blackreach.exceptions import (
    BrowserNotReadyError,
    ElementNotFoundError,
    DownloadError,
    InvalidActionArgsError,
    UnknownActionError,
)
from blackreach.detection import SiteDetector


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
        download_dir: Optional[Path] = None,
        browser_type: str = "chromium"  # chromium, firefox, or webkit
    ):
        self.headless = headless
        self.browser_type = browser_type.lower()
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
        self._detector = SiteDetector()  # Reuse for performance

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

        # Browser launch args for stealth - comprehensive anti-detection
        launch_args = [
            # Core anti-automation flags
            "--disable-blink-features=AutomationControlled",
            "--disable-automation",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            # Hide headless indicators
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--disable-ipc-flooding-protection",
            # Make it look like a real browser
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--disable-features=IsolateOrigins,site-per-process,TranslateUI",
            "--disable-site-isolation-trials",
            # GPU and rendering (helps avoid detection)
            "--enable-webgl",
            "--enable-webgl2-compute-context",
            "--enable-accelerated-2d-canvas",
            "--ignore-gpu-blocklist",
            # Misc
            "--lang=en-US",
            "--disable-extensions",
            "--disable-component-extensions-with-background-pages",
            "--disable-default-apps",
            "--disable-breakpad",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-pings",
        ]

        # Get proxy if configured
        proxy = self.stealth.get_next_proxy()
        proxy_config = {"server": proxy} if proxy else None

        # Select browser type
        if self.browser_type == "firefox":
            # Firefox-specific launch options
            self._browser = self._playwright.firefox.launch(
                headless=self.headless,
                firefox_user_prefs={
                    "dom.webdriver.enabled": False,
                    "useAutomationExtension": False,
                    "privacy.resistFingerprinting": False,  # We handle this ourselves
                },
                downloads_path=str(self.download_dir)
            )
        elif self.browser_type == "webkit":
            self._browser = self._playwright.webkit.launch(
                headless=self.headless,
                downloads_path=str(self.download_dir)
            )
        else:
            # Default to Chromium with full stealth args
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
                downloads_path=str(self.download_dir)
            )

        # Create context with randomized fingerprint
        viewport = self.stealth.get_random_viewport() if self.stealth.config.randomize_viewport else {"width": 1280, "height": 800}
        user_agent = self.stealth.get_random_user_agent() if self.stealth.config.randomize_user_agent else None

        context_options = {
            "viewport": viewport,
            "proxy": proxy_config,
            "accept_downloads": True,  # Enable downloads
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "light",
            "reduced_motion": "no-preference",
            "has_touch": False,
            "is_mobile": False,
            "java_script_enabled": True,
            "bypass_csp": True,  # Helps with some challenges
            "ignore_https_errors": True,
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
    
    def _release_all_keys(self) -> None:
        """Release all modifier keys to prevent stuck keys on the host system."""
        if not self._page:
            return
        try:
            # Release all common modifier keys that might be stuck
            for key in ["Control", "Alt", "Shift", "Meta"]:
                try:
                    self._page.keyboard.up(key)
                except Exception:
                    pass
        except Exception:
            pass  # Page might already be closed

    def sleep(self) -> None:
        """Close the browser safely, releasing any stuck keys."""
        # IMPORTANT: Release all modifier keys before closing
        # This prevents the host keyboard from getting stuck
        self._release_all_keys()

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
            raise BrowserNotReadyError()
        return self._page

    @property
    def selector(self) -> SmartSelector:
        """Get smart selector helper."""
        if not self._selector:
            raise BrowserNotReadyError()
        return self._selector

    @property
    def popups(self) -> PopupHandler:
        """Get popup handler."""
        if not self._popups:
            raise BrowserNotReadyError()
        return self._popups

    @property
    def waits(self) -> WaitConditions:
        """Get wait conditions helper."""
        if not self._waits:
            raise BrowserNotReadyError()
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
    def goto(self, url: str, handle_popups: bool = True, wait_for_content: bool = True) -> dict:
        """Navigate to a URL with retry logic and smart content waiting.

        Args:
            url: URL to navigate to
            handle_popups: Whether to automatically dismiss popups
            wait_for_content: Whether to wait for dynamic content to load

        Returns:
            Dict with action, url, title, content_found, and http_status
        """
        # Navigate and wait for initial DOM
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Track HTTP status for error detection
        http_status = response.status if response else None
        if http_status and http_status >= 400:
            # Log HTTP errors but don't fail - page may still have useful content
            print(f"  [HTTP {http_status}: {url[:50]}...]")

        # Wait for full page load (all resources including images, scripts)
        try:
            self.page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass  # Continue - page may still be usable

        # Wait for network to settle
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass  # Don't fail if network doesn't go idle

        # Check for and wait through challenge pages (DDoS-Guard, Cloudflare, etc.)
        self._wait_for_challenge_resolution()

        # Wait for dynamic content if enabled
        content_found = False
        if wait_for_content:
            content_found = self._wait_for_dynamic_content(timeout=20000)

            # If no content found, try scrolling to trigger lazy loading
            if not content_found:
                self.scroll("down", 300)
                time.sleep(2)
                content_found = self._wait_for_dynamic_content(timeout=8000)

                # Second scroll attempt
                if not content_found:
                    self.scroll("up", 300)
                    time.sleep(1)
                    self.scroll("down", 100)
                    time.sleep(2)
                    content_found = self._wait_for_dynamic_content(timeout=5000)

        self._human_delay(0.5, 1.0)

        if handle_popups:
            self._popups.handle_all()
            self._human_delay(0.2, 0.4)
            self._popups.handle_all()

        return {
            "action": "goto",
            "url": url,
            "title": self.page.title(),
            "content_found": content_found,
            "http_status": http_status
        }

    def _wait_for_challenge_resolution(self, max_wait: int = 30) -> bool:
        """
        Wait for challenge/interstitial pages to resolve.

        DDoS-Guard, Cloudflare and similar services often show an interstitial
        page that auto-resolves after a few seconds. This method detects and
        waits for such pages, with human-like interaction to help solve challenges.

        Returns True if a challenge was detected and resolved, False otherwise.
        """
        import random

        for attempt in range(max_wait):
            html = self.page.content()
            result = self._detector.detect_challenge(html)

            if not result.detected:
                return attempt > 0  # Return True if we waited at all

            # Challenge detected - wait and check again
            if attempt == 0:
                print(f"  [Challenge detected: {result.details or 'unknown'} - waiting...]")

            # Human-like interaction to help solve challenge
            if attempt % 3 == 0:  # Every 3 seconds
                try:
                    # Move mouse randomly (some challenges check for mouse activity)
                    viewport = self.page.viewport_size
                    if viewport:
                        x = random.randint(100, viewport['width'] - 100)
                        y = random.randint(100, viewport['height'] - 100)
                        self.page.mouse.move(x, y)
                except Exception:
                    pass

            if attempt == 5:  # After 5 seconds, try scrolling
                try:
                    self.page.mouse.wheel(0, 100)
                except Exception:
                    pass

            if attempt == 10:  # After 10 seconds, try clicking in center
                try:
                    viewport = self.page.viewport_size
                    if viewport:
                        self.page.mouse.click(viewport['width'] // 2, viewport['height'] // 2)
                except Exception:
                    pass

            time.sleep(1)

            # Check if page URL changed (redirect after challenge)
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=2000)
            except Exception:
                pass

        # If we're still on a challenge page after max_wait, log it
        print(f"  [Challenge did not resolve after {max_wait}s]")
        return True

    def _wait_for_dynamic_content(self, timeout: int = 10000) -> bool:
        """
        Wait for JavaScript-rendered content to appear.

        Uses multiple strategies with verification:
        1. Wait for network idle
        2. Wait for framework hydration (React, Vue, Angular)
        3. Wait for common content containers
        4. Wait for loading indicators to disappear
        5. VERIFY actual content exists (links, buttons, text)
        6. Use JavaScript to check DOM readiness

        Returns True if content was found, False otherwise.
        """
        start_time = time.time()
        max_time = timeout / 1000  # Convert to seconds

        # Strategy 1: Wait for network to settle
        try:
            self.page.wait_for_load_state("networkidle", timeout=min(timeout, 10000))
        except Exception:
            pass

        # Strategy 2: Wait for framework hydration
        try:
            self.page.evaluate("""
                () => {
                    return new Promise((resolve) => {
                        // Check if React has finished hydrating
                        if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__ || document.querySelector('[data-reactroot]')) {
                            // Wait for React to finish rendering
                            setTimeout(resolve, 500);
                            return;
                        }
                        // Check for Vue
                        if (window.__VUE__ || document.querySelector('[data-v-]')) {
                            setTimeout(resolve, 500);
                            return;
                        }
                        // Check for Angular
                        if (window.ng || document.querySelector('[ng-version]')) {
                            setTimeout(resolve, 500);
                            return;
                        }
                        // Check for Next.js
                        if (window.__NEXT_DATA__ || document.querySelector('#__next')) {
                            setTimeout(resolve, 800);
                            return;
                        }
                        // No framework detected, resolve immediately
                        resolve();
                    });
                }
            """)
        except Exception:
            pass

        # Strategy 3: Wait for document.readyState === 'complete'
        try:
            self.page.wait_for_function(
                "() => document.readyState === 'complete'",
                timeout=5000
            )
        except Exception:
            pass

        # Strategy 4: Wait for common content containers to have content
        content_selectors = [
            'main', 'article', '.content', '#content', '#root', '#app',
            '.results', '.items', '.list', '.cards', '.search-results',
            '[role="main"]', '.container', '.page-content', '.main-content',
            'form', 'input[type="search"]', 'input[type="text"]'
        ]

        for selector in content_selectors:
            if time.time() - start_time > max_time:
                break
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    loc.first.wait_for(state="visible", timeout=2000)
                    # Check if container actually has content
                    has_content = self.page.evaluate(f"""
                        () => {{
                            const el = document.querySelector('{selector}');
                            return el && el.innerText && el.innerText.trim().length > 50;
                        }}
                    """)
                    if has_content:
                        break
            except Exception:
                continue

        # Strategy 5: Wait for loading indicators to disappear
        spinner_selectors = [
            '.loading', '.spinner', '.loader', '[class*="loading"]',
            '[class*="spinner"]', '.skeleton', '[aria-busy="true"]',
            '.lds-ring', '.lds-dual-ring', '.progress', '.loading-overlay'
        ]
        for selector in spinner_selectors:
            if time.time() - start_time > max_time:
                break
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.wait_for(state="hidden", timeout=5000)
            except Exception:
                pass

        # Strategy 6: Use JavaScript to verify DOM has meaningful content
        # This is the KEY fix - actually verify content exists
        for attempt in range(8):  # More attempts
            if time.time() - start_time > max_time:
                break

            try:
                # Comprehensive check for page readiness
                content_check = self.page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a[href]');
                        const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
                        const inputs = document.querySelectorAll('input, textarea, select');
                        const images = document.querySelectorAll('img[src]');
                        const textLength = document.body?.innerText?.length || 0;

                        // Check for empty placeholder states
                        const hasPlaceholder = document.querySelector('.loading, .skeleton, [aria-busy="true"]');
                        const hasEmptyRoot = document.querySelector('#root:empty, #app:empty, #__next:empty');

                        // Check for visible content (not hidden or zero-sized)
                        const visibleLinks = Array.from(links).filter(el => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        }).length;

                        return {
                            links: links.length,
                            visibleLinks: visibleLinks,
                            buttons: buttons.length,
                            inputs: inputs.length,
                            images: images.length,
                            textLength: textLength,
                            hasPlaceholder: !!hasPlaceholder,
                            hasEmptyRoot: !!hasEmptyRoot,
                            hasContent: (visibleLinks > 3 || buttons.length > 0 || inputs.length > 0 || textLength > 500) && !hasEmptyRoot
                        };
                    }
                """)

                if content_check.get('hasContent', False) and not content_check.get('hasPlaceholder', True):
                    return True

                # Content not ready yet, wait and retry
                time.sleep(1.5)

            except Exception:
                time.sleep(1)

        # Strategy 7: Final fallback with longer wait for very slow sites
        time.sleep(2)

        # Final verification
        try:
            final_check = self.page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href]');
                    const text = document.body?.innerText?.length || 0;
                    // At this point, accept any page with some links or text
                    return links.length > 0 || text > 100;
                }
            """)
            return final_check
        except Exception:
            return False

    def force_render(self) -> bool:
        """
        Force page to fully render by triggering various browser events.

        Useful for stubborn SPAs that don't render until user interaction.
        Returns True if content was eventually found.
        """
        # Trigger resize event (some sites render on resize)
        try:
            self.page.evaluate("window.dispatchEvent(new Event('resize'))")
        except Exception:
            pass

        # Scroll to trigger lazy loading
        try:
            self.page.evaluate("""
                () => {
                    // Scroll to bottom and back
                    window.scrollTo(0, document.body.scrollHeight);
                    setTimeout(() => window.scrollTo(0, 0), 500);
                }
            """)
            time.sleep(1)
        except Exception:
            pass

        # Trigger mouse move (some sites wait for user activity)
        try:
            self.page.mouse.move(100, 100)
            self.page.mouse.move(200, 200)
        except Exception:
            pass

        # Click on body to trigger focus events
        try:
            self.page.evaluate("document.body.click()")
        except Exception:
            pass

        # Wait a moment for any triggered renders
        time.sleep(2)

        # Check if we now have content
        return self._wait_for_dynamic_content(timeout=5000)

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
            raise ElementNotFoundError(selector=str(selector))

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
            raise ElementNotFoundError(selector=selector)

        # Now type into the found element
        try:
            if human:
                # Click to focus
                locator.click()
                self._human_delay(0.05, 0.15)

                # Clear existing content if requested
                # Use triple-click to select all (safer than Ctrl+A which can leave keys stuck)
                if clear:
                    try:
                        locator.click(click_count=3)  # Triple-click to select all
                        self._human_delay(0.05, 0.1)
                    except Exception:
                        # Fallback: use fill to clear first, then type
                        locator.fill("")
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
        finally:
            # Always release modifier keys after typing operations
            self._release_all_keys()

        return {"action": "type", "selector": used_selector, "text": text}

    def press(self, key: str) -> dict:
        """Press a key (e.g., 'Enter', 'Escape')."""
        self._human_delay(0.1, 0.2)
        try:
            self.page.keyboard.press(key)
        finally:
            # Release any modifier keys that might have gotten stuck
            self._release_all_keys()
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

    def get_html(self, wait_for_load: bool = True, retries: int = 3, ensure_content: bool = False) -> str:
        """
        Get the current page HTML with retry logic for dynamic pages.

        Args:
            wait_for_load: Wait for network to settle before getting HTML
            retries: Number of retries if page is still navigating
            ensure_content: If True, verify page has actual content before returning
        """
        if wait_for_load:
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass  # Continue anyway - page may be usable

        # If ensure_content is True, wait for actual content to appear
        if ensure_content:
            self._wait_for_dynamic_content(timeout=10000)

        # Retry logic for pages that are still navigating
        for attempt in range(retries):
            try:
                html = self.page.content()

                # If ensure_content, verify we have meaningful HTML
                if ensure_content and html:
                    # Quick check: does HTML have any links?
                    if '<a ' not in html.lower() and attempt < retries - 1:
                        time.sleep(2)  # Wait and retry
                        continue

                return html
            except Exception as e:
                if "navigating" in str(e).lower() and attempt < retries - 1:
                    time.sleep(1)  # Wait a bit and retry
                else:
                    raise
        return ""

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
                        except Exception:
                            pass  # Continue anyway - will retry or fallback to URL
                    else:
                        return self.page.url  # Fallback to URL
                else:
                    raise
        return ""

    def wait_for_navigation(self, timeout: float = 10000) -> None:
        """Wait for page to finish navigating."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass  # Navigation may still be usable

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
            raise InvalidActionArgsError("download", "Must provide either selector or url")

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

        This handles both regular file URLs, blob URLs, and inline files (images, etc.)
        Automatically chooses the best download method based on file type.
        """
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
                # Browser displays file inline - use HTTP fetch instead
                return self._fetch_file_directly(href)
            raise

    def _fetch_file_directly(self, url: str) -> dict:
        """
        Download a file using direct HTTP fetch (for inline content like images).
        """
        import urllib.request
        import urllib.error
        from urllib.parse import urlparse, unquote
        import hashlib

        # Get filename from URL
        parsed = urlparse(url)
        filename = unquote(parsed.path.split('/')[-1]) or 'downloaded_file'

        # Add extension if missing based on content type
        save_path = self.download_dir / filename

        # Handle duplicate filenames
        counter = 1
        base_path = save_path
        while save_path.exists():
            stem = base_path.stem
            save_path = self.download_dir / f"{stem}_{counter}{base_path.suffix}"
            counter += 1

        # Download the file with User-Agent to avoid 403 errors
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': self.stealth.get_random_user_agent()
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(save_path, 'wb') as f:
                    f.write(response.read())
        except urllib.error.HTTPError as e:
            raise DownloadError(url, reason=e.reason, status_code=e.code)

        # Compute hash and size
        file_hash = self._compute_hash(save_path)
        file_size = save_path.stat().st_size

        return {
            "action": "download",
            "filename": save_path.name,
            "path": str(save_path),
            "size": file_size,
            "hash": file_hash,
            "url": url
        }

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
            raise ElementNotFoundError(text=text)
        locator.click()
        self._human_delay()
        return {"action": "smart_click", "text": text}

    def smart_type(self, text: str, into: str = None, placeholder: str = None, label: str = None) -> dict:
        """Type into input found by various attributes."""
        locator = self.selector.find_input(name=into, placeholder=placeholder, label=label)
        if not locator:
            raise ElementNotFoundError()
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
            raise UnknownActionError(action)

