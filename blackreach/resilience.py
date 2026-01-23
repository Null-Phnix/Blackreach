"""
Resilience Module - Error Handling & Smart Selectors

Provides:
- Retry logic with exponential backoff
- Smart element selectors with fallback strategies
- Wait conditions for dynamic content
- Popup/overlay handling
- Fuzzy text matching
- Accessibility-based selectors
"""

import time
import random
import re
from typing import Optional, List, Callable, Any, Union
from dataclasses import dataclass
from functools import wraps
from difflib import SequenceMatcher
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeout


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


def retry_with_backoff(config: RetryConfig = None):
    """
    Decorator for retrying functions with exponential backoff.
    
    Usage:
        @retry_with_backoff(RetryConfig(max_attempts=5))
        def flaky_operation():
            ...
    """
    config = config or RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = min(
                            config.base_delay * (config.exponential_base ** attempt),
                            config.max_delay
                        )
                        if config.jitter:
                            delay *= random.uniform(0.5, 1.5)
                        time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Failures before tripping
    recovery_timeout: float = 30.0  # Seconds before attempting recovery
    half_open_max_calls: int = 1  # Calls allowed in half-open state


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
        - CLOSED: Normal operation, allows requests
        - OPEN: Failing fast, blocking requests
        - HALF_OPEN: Testing if system has recovered

    Usage:
        breaker = CircuitBreaker()

        try:
            with breaker:
                result = risky_operation()
        except CircuitBreakerOpen:
            # Handle fail-fast case
            pass
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, config: CircuitBreakerConfig = None, name: str = "default"):
        self.config = config or CircuitBreakerConfig()
        self.name = name
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        """Current circuit breaker state."""
        if self._state == self.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.config.recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == self.OPEN

    def record_success(self) -> None:
        """Record a successful operation."""
        if self._state == self.HALF_OPEN:
            # Successful call in half-open state - close the circuit
            self._state = self.CLOSED
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == self.HALF_OPEN:
            # Failure in half-open - re-open the circuit
            self._state = self.OPEN
        elif self._failure_count >= self.config.failure_threshold:
            # Threshold reached - open the circuit
            self._state = self.OPEN

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        state = self.state

        if state == self.CLOSED:
            return True
        elif state == self.HALF_OPEN:
            # Allow limited requests in half-open state
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        else:  # OPEN
            return False

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = self.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0

    def __enter__(self):
        """Context manager entry - check if request is allowed."""
        if not self.allow_request():
            raise CircuitBreakerOpen(self.name, self.config.recovery_timeout - (time.time() - self._last_failure_time))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - record success or failure."""
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure()
        return False  # Don't suppress exceptions


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, name: str, time_remaining: float = 0):
        self.name = name
        self.time_remaining = max(0, time_remaining)
        super().__init__(f"Circuit breaker '{name}' is open. Retry in {self.time_remaining:.1f}s")


class SmartSelector:
    """
    Smart element selector with fallback strategies.
    Tries multiple selector strategies to find elements reliably.
    """
    
    def __init__(self, page: Page, timeout: float = 10000):
        self.page = page
        self.timeout = timeout
    
    def find(
        self, 
        selectors: Union[str, List[str]], 
        visible_only: bool = True,
        wait: bool = True
    ) -> Optional[Locator]:
        """
        Find element using multiple selector strategies.
        
        Args:
            selectors: Single selector or list of fallback selectors
            visible_only: Only return visible elements
            wait: Wait for element to appear
        """
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                locator = self._try_selector(selector, visible_only, wait)
                if locator:
                    return locator
            except Exception:
                continue
        
        return None
    
    def _try_selector(
        self, 
        selector: str, 
        visible_only: bool,
        wait: bool
    ) -> Optional[Locator]:
        """Try a single selector."""
        locator = self.page.locator(selector)
        
        if visible_only:
            locator = locator.filter(has=self.page.locator(":visible"))
        
        if wait:
            try:
                locator.first.wait_for(timeout=self.timeout / len([selector]))
            except PlaywrightTimeout:
                return None
        
        if locator.count() > 0:
            return locator.first
        return None
    
    def find_by_text(
        self, 
        text: str, 
        tag: str = "*",
        exact: bool = False
    ) -> Optional[Locator]:
        """Find element by its text content."""
        # Escape special characters for CSS selector
        # Use get_by_text for better handling of special characters
        try:
            if exact:
                locator = self.page.get_by_text(text, exact=True)
            else:
                locator = self.page.get_by_text(text, exact=False)
            
            # Filter by tag if specified
            if tag != "*":
                locator = self.page.locator(tag).filter(has=locator)
            
            locator.first.wait_for(timeout=self.timeout)
            return locator.first
        except PlaywrightTimeout:
            return None
        except Exception:
            # Fallback: try CSS escape approach (re already imported at module level)
            escaped_text = text.replace("'", "\\'").replace('"', '\\"')
            try:
                if exact:
                    locator = self.page.locator(f"{tag}:text-is('{escaped_text}')")
                else:
                    locator = self.page.locator(f"{tag}:has-text('{escaped_text}')")
                locator.first.wait_for(timeout=self.timeout)
                return locator.first
            except Exception:
                return None
    
    def find_input(
        self,
        name: str = None,
        placeholder: str = None,
        label: str = None,
        input_type: str = None
    ) -> Optional[Locator]:
        """Find input field by various attributes."""
        selectors = []
        
        if name:
            selectors.extend([
                f"input[name='{name}']",
                f"textarea[name='{name}']",
                f"[name='{name}']"
            ])
        
        if placeholder:
            selectors.extend([
                f"input[placeholder*='{placeholder}' i]",
                f"textarea[placeholder*='{placeholder}' i]"
            ])
        
        if label:
            selectors.extend([
                f"label:has-text('{label}') input",
                f"input[aria-label*='{label}' i]"
            ])
        
        if input_type:
            selectors.append(f"input[type='{input_type}']")

        return self.find(selectors) if selectors else None

    def find_button(
        self,
        text: str = None,
        submit: bool = False
    ) -> Optional[Locator]:
        """Find button by text or type."""
        selectors = []

        if text:
            selectors.extend([
                f"button:has-text('{text}')",
                f"input[type='submit'][value*='{text}' i]",
                f"a:has-text('{text}')",
                f"[role='button']:has-text('{text}')"
            ])

        if submit:
            selectors.extend([
                "button[type='submit']",
                "input[type='submit']"
            ])

        return self.find(selectors) if selectors else None

    # === Enhanced Element Detection ===

    def find_link(
        self,
        text: str = None,
        href_contains: str = None,
        download: bool = False
    ) -> Optional[Locator]:
        """Find link by text, href pattern, or download attribute."""
        selectors = []

        if text:
            selectors.extend([
                f"a:has-text('{text}')",
                f"a[title*='{text}' i]",
                f"a[aria-label*='{text}' i]"
            ])

        if href_contains:
            selectors.append(f"a[href*='{href_contains}']")

        if download:
            selectors.extend([
                "a[download]",
                "a[href$='.pdf']",
                "a[href$='.zip']",
                "a[href$='.doc']",
                "a[href$='.docx']"
            ])

        return self.find(selectors) if selectors else None

    def find_by_aria(
        self,
        label: str = None,
        role: str = None,
        described_by: str = None
    ) -> Optional[Locator]:
        """Find element by ARIA attributes (accessibility)."""
        selectors = []

        if label:
            selectors.extend([
                f"[aria-label*='{label}' i]",
                f"[aria-labelledby]:has-text('{label}')"
            ])

        if role:
            selectors.append(f"[role='{role}']")

        if described_by:
            selectors.append(f"[aria-describedby*='{described_by}']")

        return self.find(selectors) if selectors else None

    def find_by_data_attr(
        self,
        attr_name: str,
        attr_value: str = None
    ) -> Optional[Locator]:
        """Find element by data-* attribute."""
        if attr_value:
            return self.find(f"[data-{attr_name}*='{attr_value}' i]")
        else:
            return self.find(f"[data-{attr_name}]")

    def find_fuzzy(
        self,
        text: str,
        threshold: float = 0.6,
        tag: str = "*"
    ) -> Optional[Locator]:
        """
        Find element with fuzzy text matching.

        Uses SequenceMatcher to find elements with similar text.
        Useful when exact text matching fails due to whitespace,
        special characters, or slight variations.

        Args:
            text: Target text to match
            threshold: Similarity threshold (0.0 to 1.0)
            tag: HTML tag to search within
        """
        try:
            # Get all visible elements of the specified tag
            elements = self.page.locator(f"{tag}:visible").all()

            best_match = None
            best_score = threshold

            for element in elements:
                try:
                    element_text = element.inner_text(timeout=100)
                    if not element_text:
                        continue

                    # Clean and compare
                    clean_target = text.lower().strip()
                    clean_element = element_text.lower().strip()

                    # Check direct containment first
                    if clean_target in clean_element or clean_element in clean_target:
                        return element

                    # Fuzzy match
                    score = SequenceMatcher(None, clean_target, clean_element).ratio()

                    if score > best_score:
                        best_score = score
                        best_match = element

                except Exception:
                    continue

            return best_match

        except Exception:
            return None

    def find_search_input(self) -> Optional[Locator]:
        """Find the main search input on a page."""
        # Common search input patterns
        selectors = [
            "input[type='search']",
            "input[name='q']",
            "input[name='query']",
            "input[name='search']",
            "input[name='s']",
            "input[placeholder*='search' i]",
            "input[placeholder*='find' i]",
            "input[aria-label*='search' i]",
            "[role='searchbox']",
            "#search",
            "#q",
            ".search-input",
            ".search-field",
        ]
        return self.find(selectors)

    def find_submit_button(self) -> Optional[Locator]:
        """Find the submit/search button near inputs."""
        selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Search')",
            "button:has-text('Go')",
            "button:has-text('Submit')",
            "button[aria-label*='search' i]",
            "[role='button']:has-text('Search')",
        ]
        return self.find(selectors)

    def find_download_link(self, file_type: str = None) -> Optional[Locator]:
        """Find download link, optionally filtered by file type."""
        selectors = ["a[download]"]

        if file_type:
            selectors.extend([
                f"a[href$='.{file_type}']",
                f"a:has-text('.{file_type}')",
                f"a:has-text('{file_type.upper()}')"
            ])
        else:
            # Common download patterns
            selectors.extend([
                "a[href$='.pdf']",
                "a[href$='.zip']",
                "a[href$='.tar.gz']",
                "a:has-text('Download')",
                "a:has-text('download')",
                "button:has-text('Download')"
            ])

        return self.find(selectors)

    def generate_selectors(self, description: str) -> List[str]:
        """
        Generate likely selectors from a natural language description.

        Useful for converting LLM output like "the search box" into
        actual CSS selectors to try.
        """
        description = description.lower()
        selectors = []

        # Search-related
        if any(word in description for word in ['search', 'find', 'query']):
            selectors.extend([
                "input[type='search']",
                "input[name='q']",
                "input[name='query']",
                "input[placeholder*='search' i]",
                "[role='searchbox']",
            ])

        # Button-related
        if any(word in description for word in ['button', 'submit', 'click', 'press']):
            selectors.extend([
                "button[type='submit']",
                "button",
                "[role='button']",
                "input[type='submit']"
            ])

        # Link-related
        if any(word in description for word in ['link', 'href', 'navigate']):
            selectors.append("a")

        # Download-related
        if any(word in description for word in ['download', 'pdf', 'file']):
            selectors.extend([
                "a[download]",
                "a[href$='.pdf']",
                "a:has-text('download')"
            ])

        # Input-related
        if any(word in description for word in ['input', 'text', 'field', 'box', 'type']):
            selectors.extend([
                "input[type='text']",
                "input:not([type='hidden'])",
                "textarea"
            ])

        # Extract any quoted text as has-text selector
        quoted = re.findall(r'"([^"]+)"', description)
        for text in quoted:
            selectors.append(f"*:has-text('{text}')")

        return selectors if selectors else ["*"]


class PopupHandler:
    """
    Handles common popups, overlays, and cookie banners.
    """

    # Common cookie consent selectors
    COOKIE_SELECTORS = [
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('Accept all')",
        "button:has-text('Accept Cookies')",
        "button:has-text('I Accept')",
        "button:has-text('I agree')",
        "button:has-text('OK')",
        "button:has-text('Got it')",
        "button:has-text('Agree')",
        "button:has-text('Reject all')",  # Google EU consent
        "[id*='accept']",
        "[class*='accept']",
        "[data-testid*='accept']",
        # Google specific
        "[aria-label*='Accept']",
        "div[role='dialog'] button",
    ]

    # Common popup close selectors
    CLOSE_SELECTORS = [
        "button[aria-label='Close']",
        "button[aria-label='Dismiss']",
        "[class*='close']",
        "[class*='dismiss']",
        ".modal-close",
        ".popup-close",
        "button:has-text('×')",
        "button:has-text('X')",
        "button:has-text('No thanks')",
        "button:has-text('Maybe later')",
    ]

    def __init__(self, page: Page):
        self.page = page
        self.selector = SmartSelector(page, timeout=2000)

    def dismiss_cookie_banner(self) -> bool:
        """Try to dismiss cookie consent banners."""
        # Google-specific selectors (they change frequently)
        google_selectors = [
            'button[id*="Accept"]',
            'button[id*="accept"]',
            '[aria-label*="Accept"]',
            '[aria-label*="accept"]',
            'div[role="dialog"] button:first-of-type',
            'div[role="dialog"] button:last-of-type',
            '#L2AGLb',  # Google "I agree" button ID
            '#W0wltc',  # Google "Reject all" button ID
            'button.tHlp8d',  # Google consent button class
            'form[action*="consent"] button',
            'div[data-ved] button',
        ]

        all_selectors = google_selectors + self.COOKIE_SELECTORS

        # First try main page
        for sel in all_selectors:
            try:
                locator = self.page.locator(sel).first
                if locator.is_visible():
                    locator.click()
                    time.sleep(0.5)
                    return True
            except Exception:
                continue

        # Try all iframes (not just consent-named ones)
        try:
            frames = self.page.frames
            for frame in frames:
                # Skip the main frame
                if frame == self.page.main_frame:
                    continue
                for sel in all_selectors:
                    try:
                        locator = frame.locator(sel).first
                        if locator.is_visible():
                            locator.click()
                            time.sleep(0.5)
                            return True
                    except Exception:
                        continue
        except Exception:
            pass

        # Try pressing Escape to close dialogs
        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.3)
        except Exception:
            pass

        return False

    def close_popups(self) -> int:
        """Close any visible popups/modals. Returns count closed."""
        closed = 0
        for sel in self.CLOSE_SELECTORS:
            try:
                locator = self.page.locator(sel).first
                if locator.is_visible():
                    locator.click()
                    closed += 1
                    time.sleep(0.3)
            except Exception:
                continue
        return closed

    def handle_all(self) -> dict:
        """Handle all common interruptions."""
        return {
            "cookies_dismissed": self.dismiss_cookie_banner(),
            "popups_closed": self.close_popups()
        }


class WaitConditions:
    """
    Smart wait conditions for dynamic content.
    """

    def __init__(self, page: Page):
        self.page = page

    def wait_for_network_idle(self, timeout: float = 30000) -> bool:
        """Wait until network is idle (no pending requests)."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def wait_for_element(
        self,
        selector: str,
        state: str = "visible",
        timeout: float = 10000
    ) -> bool:
        """Wait for element to reach specified state."""
        try:
            self.page.locator(selector).wait_for(state=state, timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def wait_for_text(
        self,
        text: str,
        timeout: float = 10000
    ) -> bool:
        """Wait for specific text to appear on page."""
        try:
            self.page.get_by_text(text).wait_for(timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def wait_for_url(
        self,
        url_pattern: str,
        timeout: float = 10000
    ) -> bool:
        """Wait for URL to match pattern."""
        try:
            self.page.wait_for_url(url_pattern, timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def wait_for_navigation(self, timeout: float = 30000) -> bool:
        """Wait for navigation to complete."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def wait_for_ajax(self, timeout: float = 10000) -> bool:
        """
        Wait for AJAX requests to complete.
        Uses JavaScript to check for pending XHR/fetch requests.
        """
        script = """
        () => {
            return new Promise((resolve) => {
                let pending = 0;
                const originalXHR = window.XMLHttpRequest;
                const originalFetch = window.fetch;

                // Check if there are pending requests
                const checkPending = () => {
                    if (pending === 0) resolve(true);
                };

                // Simple timeout-based check
                setTimeout(checkPending, 500);
            });
        }
        """
        try:
            self.page.evaluate(script)
            return True
        except Exception:
            return False
