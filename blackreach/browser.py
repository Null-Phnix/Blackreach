"""
The Hand - Browser Controller using Playwright

Controls the browser: click, type, scroll, navigate, screenshot, download.
Now with stealth and resilience features.
"""

from playwright.sync_api import sync_playwright, Browser, Page, Playwright, BrowserContext, Route, Download, Error as PlaywrightError
from typing import Optional, List, Union, Callable, Dict, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse, unquote
import urllib.request
import urllib.error
import time
import random
import hashlib
import threading

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
from blackreach.detection import SiteDetector, get_site_characteristics, SiteType
from blackreach.cloudflare_bypass import CloudflareBypasser, CloudflareBypassConfig, UNDETECTED_AVAILABLE

# Use playwright-stealth for better Cloudflare bypass
try:
    from playwright_stealth import stealth_sync
    PLAYWRIGHT_STEALTH_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_STEALTH_AVAILABLE = False

# === Browser Constants ===

# Navigation timeouts (milliseconds)
GOTO_TIMEOUT_MS = 30_000
LOAD_STATE_TIMEOUT_MS = 10_000
ELEMENT_WAIT_TIMEOUT_MS = 3_000
DOWNLOAD_TIMEOUT_MS = 60_000

# Content readiness thresholds
MIN_LINKS_FOR_READY = 3
MIN_TEXT_LENGTH_FOR_READY = 200

# Challenge handling
MAX_CHALLENGE_WAIT_S = 30
CHALLENGE_MOUSE_INTERVAL_S = 3
CHALLENGE_CLICK_AFTER_S = 10

# Human-like delays (seconds)
HUMAN_CLICK_PRE_DELAY = (0.1, 0.3)
HUMAN_CLICK_POST_DELAY = (0.2, 0.5)

# Precompiled regex for filename sanitization (P0-SEC fix)
import re
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_PATH_TRAVERSAL = re.compile(r'(?:^|[\\/])\.\.(?:[\\/]|$)')


def _sanitize_filename(filename: str) -> str:
    r"""
    Sanitize a filename to prevent path traversal and injection attacks.

    Security fixes:
    1. Removes path traversal patterns (../, ..\, etc.)
    2. Removes unsafe characters for all platforms
    3. Uses only the basename (no directory components)
    4. Falls back to safe default if filename becomes empty

    Args:
        filename: The potentially unsafe filename

    Returns:
        A sanitized filename safe for use on all platforms
    """
    import os
    # Get only the base filename (removes any path components)
    filename = os.path.basename(filename)

    # Remove path traversal patterns that might remain
    filename = _PATH_TRAVERSAL.sub('', filename)

    # Remove characters that are unsafe on Windows/Linux/Mac
    filename = _UNSAFE_FILENAME_CHARS.sub('_', filename)

    # Remove leading/trailing dots and spaces (Windows issue)
    filename = filename.strip('. ')

    # Fall back to safe default if filename became empty
    if not filename:
        filename = 'downloaded_file'

    return filename


_download_lock = threading.Lock()


def _reserve_unique_path(download_dir: Path, base_path: Path) -> Path:
    """Atomically reserve a unique filename, avoiding TOCTOU races.

    Holds a lock while checking existence and creating a placeholder file,
    so two threads won't pick the same name.
    """
    with _download_lock:
        save_path = base_path
        counter = 1
        while save_path.exists():
            stem = base_path.stem
            save_path = download_dir / f"{stem}_{counter}{base_path.suffix}"
            counter += 1
        save_path.touch()  # Reserve the name
    return save_path


def _is_ssrf_safe(url: str) -> bool:
    """
    Validate URL is safe from SSRF attacks by checking against private IP ranges.

    This prevents the browser/fetch from being used to access internal services.

    Args:
        url: URL to validate

    Returns:
        True if URL is safe to fetch, False if it targets private/internal networks

    Raises:
        ValueError: If URL is invalid or targets internal network
    """
    import socket
    import ipaddress
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            raise ValueError("URL has no hostname")

        # Block localhost variants
        if hostname.lower() in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            raise ValueError(f"SSRF blocked: localhost access not allowed")

        # Resolve hostname to IP address(es)
        try:
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            # Can't resolve - might be a DNS rebinding attempt, but allow for now
            # as it will fail at the actual request time
            return True

        # Check each resolved IP against private ranges
        private_ranges = [
            ipaddress.ip_network('10.0.0.0/8'),       # Class A private
            ipaddress.ip_network('172.16.0.0/12'),    # Class B private
            ipaddress.ip_network('192.168.0.0/16'),   # Class C private
            ipaddress.ip_network('127.0.0.0/8'),      # Loopback
            ipaddress.ip_network('169.254.0.0/16'),   # Link-local
            ipaddress.ip_network('fc00::/7'),         # IPv6 unique local
            ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
            ipaddress.ip_network('::1/128'),          # IPv6 loopback
        ]

        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                for private_range in private_ranges:
                    if ip in private_range:
                        raise ValueError(f"SSRF blocked: {hostname} resolves to private IP {ip}")
            except ValueError as e:
                if "SSRF blocked" in str(e):
                    raise
                continue  # Invalid IP string, skip

        return True

    except ValueError:
        raise
    except Exception as e:
        # On any parsing error, block as a safety measure
        raise ValueError(f"SSRF validation failed: {e}")


class ProxyType(Enum):
    """Supported proxy types."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"
    SOCKS4 = "socks4"


@dataclass
class ProxyConfig:
    """Configuration for proxy connection.

    Supports HTTP, HTTPS, SOCKS4, and SOCKS5 proxies.

    Examples:
        # HTTP proxy
        ProxyConfig(host="proxy.example.com", port=8080)

        # SOCKS5 proxy with auth
        ProxyConfig(
            host="socks.example.com",
            port=1080,
            proxy_type=ProxyType.SOCKS5,
            username="user",
            password="pass"
        )

        # From URL string
        ProxyConfig.from_url("socks5://user:pass@proxy.example.com:1080")
    """
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    bypass: Optional[List[str]] = None  # Domains to bypass proxy

    def to_playwright_proxy(self) -> Dict[str, Any]:
        """Convert to Playwright proxy configuration format."""
        # Build proxy URL
        scheme = self.proxy_type.value
        if scheme == "https":
            scheme = "http"  # Playwright uses http for HTTPS proxies

        if self.username and self.password:
            server = f"{scheme}://{self.host}:{self.port}"
            return {
                "server": server,
                "username": self.username,
                "password": self.password,
                "bypass": ",".join(self.bypass) if self.bypass else None
            }
        else:
            server = f"{scheme}://{self.host}:{self.port}"
            result = {"server": server}
            if self.bypass:
                result["bypass"] = ",".join(self.bypass)
            return result

    @classmethod
    def from_url(cls, url: str) -> "ProxyConfig":
        """
        Create ProxyConfig from a proxy URL string.

        Supported formats:
            - http://host:port
            - http://user:pass@host:port
            - socks5://host:port
            - socks5://user:pass@host:port
        """
        parsed = urlparse(url)

        # Determine proxy type
        scheme = parsed.scheme.lower()
        proxy_type_map = {
            "http": ProxyType.HTTP,
            "https": ProxyType.HTTPS,
            "socks5": ProxyType.SOCKS5,
            "socks4": ProxyType.SOCKS4,
            "socks": ProxyType.SOCKS5,  # Default socks to socks5
        }
        proxy_type = proxy_type_map.get(scheme, ProxyType.HTTP)

        # Extract host and port
        host = parsed.hostname or "localhost"
        port = parsed.port or (1080 if "socks" in scheme else 8080)

        return cls(
            host=host,
            port=port,
            proxy_type=proxy_type,
            username=parsed.username,
            password=parsed.password
        )

    def __str__(self) -> str:
        """String representation (without password)."""
        auth = f"{self.username}:***@" if self.username else ""
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"


class ProxyRotator:
    """
    Manages a pool of proxies with rotation and health tracking.

    Features:
    - Round-robin rotation
    - Health checking and automatic removal of bad proxies
    - Sticky sessions (same proxy for a domain)
    - Weighted selection based on performance
    """

    def __init__(self, proxies: Optional[List[Union[str, ProxyConfig]]] = None):
        self._proxies: List[ProxyConfig] = []
        self._current_index = 0
        self._health: Dict[str, Dict[str, Any]] = {}  # proxy_str -> health info
        self._domain_sticky: Dict[str, str] = {}  # domain -> proxy_str

        if proxies:
            for proxy in proxies:
                self.add_proxy(proxy)

    def add_proxy(self, proxy: Union[str, ProxyConfig]):
        """Add a proxy to the pool."""
        if isinstance(proxy, str):
            proxy = ProxyConfig.from_url(proxy)
        self._proxies.append(proxy)
        self._health[str(proxy)] = {
            "successes": 0,
            "failures": 0,
            "last_used": None,
            "avg_response_time": 0,
            "enabled": True
        }

    def remove_proxy(self, proxy: Union[str, ProxyConfig]):
        """Remove a proxy from the pool."""
        proxy_str = str(proxy) if isinstance(proxy, ProxyConfig) else proxy
        self._proxies = [p for p in self._proxies if str(p) != proxy_str]
        self._health.pop(proxy_str, None)

    def get_next(self, domain: Optional[str] = None) -> Optional[ProxyConfig]:
        """
        Get the next proxy in rotation.

        Args:
            domain: If provided, uses sticky session for this domain
        """
        if not self._proxies:
            return None

        # Check for sticky session
        if domain and domain in self._domain_sticky:
            sticky_str = self._domain_sticky[domain]
            for proxy in self._proxies:
                if str(proxy) == sticky_str and self._health[sticky_str]["enabled"]:
                    return proxy

        # Get enabled proxies
        enabled = [p for p in self._proxies if self._health[str(p)]["enabled"]]
        if not enabled:
            # Re-enable all if none available
            for proxy_str in self._health:
                self._health[proxy_str]["enabled"] = True
            enabled = self._proxies

        if not enabled:
            return None

        # Round-robin selection
        self._current_index = self._current_index % len(enabled)
        proxy = enabled[self._current_index]
        self._current_index += 1

        # Update sticky session
        if domain:
            self._domain_sticky[domain] = str(proxy)

        self._health[str(proxy)]["last_used"] = time.time()
        return proxy

    def report_success(self, proxy: Union[str, ProxyConfig], response_time: float = 0):
        """Report a successful request through a proxy."""
        proxy_str = str(proxy) if isinstance(proxy, ProxyConfig) else proxy
        if proxy_str in self._health:
            health = self._health[proxy_str]
            health["successes"] += 1
            # Update rolling average response time
            total = health["successes"] + health["failures"]
            health["avg_response_time"] = (
                (health["avg_response_time"] * (total - 1) + response_time) / total
            )

    def report_failure(self, proxy: Union[str, ProxyConfig], disable_threshold: int = 5):
        """
        Report a failed request through a proxy.

        Args:
            proxy: The proxy that failed
            disable_threshold: Number of consecutive failures before disabling
        """
        proxy_str = str(proxy) if isinstance(proxy, ProxyConfig) else proxy
        if proxy_str in self._health:
            health = self._health[proxy_str]
            health["failures"] += 1

            # Disable if too many consecutive failures
            recent_failure_rate = health["failures"] / (health["successes"] + health["failures"])
            if health["failures"] >= disable_threshold and recent_failure_rate > 0.5:
                health["enabled"] = False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all proxies."""
        return {
            "total_proxies": len(self._proxies),
            "enabled": sum(1 for h in self._health.values() if h["enabled"]),
            "proxies": {
                str(p): self._health.get(str(p), {})
                for p in self._proxies
            }
        }

    def clear_sticky_sessions(self):
        """Clear all domain sticky sessions."""
        self._domain_sticky.clear()

    def __len__(self) -> int:
        return len(self._proxies)


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
        browser_type: str = "chromium",  # chromium, firefox, or webkit
        proxy: Optional[Union[str, ProxyConfig]] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
    ):
        """
        Initialize the Hand browser controller.

        Args:
            headless: Run browser in headless mode
            stealth_config: Configuration for stealth/anti-detection features
            retry_config: Configuration for retry behavior
            download_dir: Directory for downloaded files
            browser_type: Browser engine to use (chromium, firefox, webkit)
            proxy: Single proxy to use (URL string or ProxyConfig)
            proxy_rotator: ProxyRotator for proxy pool rotation
        """
        self.headless = headless
        self.browser_type = browser_type.lower()
        self.stealth = Stealth(stealth_config or StealthConfig())
        self.retry_config = retry_config or RetryConfig()
        self.download_dir = download_dir or Path("./downloads")

        # Proxy configuration
        self._proxy: Optional[ProxyConfig] = None
        self._proxy_rotator = proxy_rotator

        if proxy:
            if isinstance(proxy, str):
                self._proxy = ProxyConfig.from_url(proxy)
            else:
                self._proxy = proxy

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # Helpers (initialized after wake)
        self._selector: Optional[SmartSelector] = None
        self._popups: Optional[PopupHandler] = None
        self._waits: Optional[WaitConditions] = None
        self._detector = SiteDetector()  # Reuse for performance
        self._cf_bypasser = CloudflareBypasser()  # Cloudflare bypass helper

        # State tracking
        self._mouse_pos = (0, 0)
        self._current_proxy: Optional[ProxyConfig] = None  # Currently active proxy

        # Download tracking
        self._pending_downloads: List[Download] = []
        self._download_callback: Optional[Callable] = None

        # Health tracking
        self._wake_count = 0
        self._last_health_check = 0.0
        self._consecutive_errors = 0

    @property
    def is_awake(self) -> bool:
        """Check if browser is initialized and running."""
        return (
            self._playwright is not None and
            self._browser is not None and
            self._page is not None
        )

    def is_healthy(self) -> bool:
        """
        Check if browser is healthy and responsive.

        Returns True if browser can execute basic operations.
        """
        if not self.is_awake:
            return False

        try:
            # Try to get basic page info - if this fails, browser is unhealthy
            _ = self._page.url
            _ = self._page.title()
            self._consecutive_errors = 0
            return True
        except PlaywrightError:
            self._consecutive_errors += 1
            return False

    def ensure_awake(self) -> bool:
        """
        Ensure browser is awake, starting it if necessary.

        Returns True if browser is now awake, False if wake failed.
        """
        if self.is_awake and self.is_healthy():
            return True

        # If browser exists but is unhealthy, try to restart
        if self._playwright is not None:
            try:
                self.sleep()
            except Exception:
                pass  # Best-effort cleanup

        try:
            self.wake()
            return True
        except Exception:
            return False

    def restart(self) -> bool:
        """
        Restart the browser completely.

        Useful when browser becomes unresponsive or gets stuck.
        Returns True if restart successful.
        """
        current_url = None

        # Try to save current URL for navigation after restart
        if self.is_awake:
            try:
                current_url = self._page.url
            except Exception:
                pass  # Best-effort cleanup

        # Close existing browser
        try:
            self.sleep()
        except Exception:
            pass  # Best-effort cleanup

        # Start fresh browser
        try:
            self.wake()

            # Navigate back to saved URL if we had one
            if current_url and current_url != "about:blank":
                try:
                    self.goto(current_url, wait_for_content=False)
                except Exception:
                    pass  # Best-effort cleanup

            return True
        except Exception:
            return False

    def wake(self) -> None:
        """Start the browser with stealth configuration."""
        self._playwright = sync_playwright().start()

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

        # Get proxy configuration (priority: rotator > direct proxy > stealth config)
        proxy_config = self._get_proxy_config()

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
            # Security: Only ignore HTTPS errors when explicitly configured via StealthConfig
            # Default is False - SSL verification is enabled by default
            "ignore_https_errors": self.stealth.config.ignore_https_errors,
        }
        if user_agent:
            context_options["user_agent"] = user_agent

        self._context = self._browser.new_context(**context_options)
        self._page = self._context.new_page()

        self._page.on("download", self._handle_download)
        self._setup_resource_blocking()
        self._inject_stealth_scripts()

        self._selector = SmartSelector(self._page)
        self._popups = PopupHandler(self._page)
        self._waits = WaitConditions(self._page)

    def _get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """
        Get proxy configuration for browser context.

        Priority:
        1. Proxy rotator (if configured)
        2. Direct proxy (if configured)
        3. Stealth config proxy (legacy)

        Returns Playwright proxy dict or None.
        """
        # Try proxy rotator first
        if self._proxy_rotator:
            proxy = self._proxy_rotator.get_next()
            if proxy:
                self._current_proxy = proxy
                return proxy.to_playwright_proxy()

        # Try direct proxy config
        if self._proxy:
            self._current_proxy = self._proxy
            return self._proxy.to_playwright_proxy()

        # Fall back to stealth config (legacy support)
        proxy_str = self.stealth.get_next_proxy()
        if proxy_str:
            self._current_proxy = ProxyConfig.from_url(proxy_str)
            return {"server": proxy_str}

        return None

    def set_proxy(self, proxy: Union[str, ProxyConfig, None]):
        """
        Set or update the proxy for future sessions.

        Note: This only affects new wake() calls. To change proxy
        on an active session, call sleep() then wake() again.
        """
        if proxy is None:
            self._proxy = None
        elif isinstance(proxy, str):
            self._proxy = ProxyConfig.from_url(proxy)
        else:
            self._proxy = proxy

    def get_current_proxy(self) -> Optional[ProxyConfig]:
        """Get the currently active proxy configuration."""
        return self._current_proxy

    def report_proxy_result(self, success: bool, response_time: float = 0):
        """
        Report proxy request result for health tracking.

        Args:
            success: Whether the request succeeded
            response_time: Request response time in seconds
        """
        if self._proxy_rotator and self._current_proxy:
            if success:
                self._proxy_rotator.report_success(self._current_proxy, response_time)
            else:
                self._proxy_rotator.report_failure(self._current_proxy)

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
        # Use playwright-stealth if available (better for Cloudflare/Indeed)
        if PLAYWRIGHT_STEALTH_AVAILABLE:
            stealth_sync(self._page)

        # Also apply our custom stealth scripts for extra protection
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
                    pass  # Best-effort cleanup
        except Exception:
            pass  # Best-effort cleanup

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

    # P1-ARCH: Context manager support for proper resource cleanup
    def __enter__(self) -> "Hand":
        """Enter context - wake the browser."""
        self.wake()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context - ensure browser is properly closed."""
        self.sleep()
        return False  # Don't suppress exceptions

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

        Uses adaptive timeouts based on site characteristics - static sites like
        Wikipedia get much shorter timeouts than SPAs.

        Args:
            url: URL to navigate to
            handle_popups: Whether to automatically dismiss popups
            wait_for_content: Whether to wait for dynamic content to load

        Returns:
            Dict with action, url, title, content_found, and http_status
        """
        # Get site characteristics for adaptive timeouts
        site_chars = get_site_characteristics(url)

        # Navigate and wait for initial DOM
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)

        # Track HTTP status for error detection
        http_status = response.status if response else None
        if http_status and http_status >= 400:
            # Log HTTP errors but don't fail - page may still have useful content
            print(f"  [HTTP {http_status}: {url[:50]}...]")

        # Wait for full page load - use adaptive timeout
        load_timeout = min(site_chars.network_idle_timeout, 10000)
        try:
            self.page.wait_for_load_state("load", timeout=load_timeout)
        except PlaywrightError:
            pass  # Continue - page may still be usable

        # Wait for network to settle - shorter for static sites
        try:
            self.page.wait_for_load_state("networkidle", timeout=site_chars.network_idle_timeout)
        except PlaywrightError:
            pass  # Don't fail if network doesn't go idle

        # FAST PATH: For known static sites, do a quick content check and exit early
        if site_chars.site_type in (SiteType.STATIC, SiteType.SEARCH_ENGINE):
            quick_ready = self._quick_content_ready_check(
                min_links=site_chars.min_links_for_ready,
                min_text=site_chars.min_text_length_for_ready
            )
            if quick_ready:
                self._human_delay(0.3, 0.6)
                if handle_popups:
                    self._popups.handle_all()
                return {
                    "action": "goto",
                    "url": url,
                    "title": self.page.title(),
                    "content_found": True,
                    "http_status": http_status,
                    "site_type": site_chars.site_type.value
                }

        # Check for and wait through challenge pages (DDoS-Guard, Cloudflare, etc.)
        # Skip for known safe sites
        if site_chars.site_type == SiteType.UNKNOWN:
            self._wait_for_challenge_resolution(max_wait=15)  # Reduced from 30

        # Wait for dynamic content if enabled
        content_found = False
        if wait_for_content and not site_chars.skip_dynamic_content_wait:
            content_found = self._wait_for_dynamic_content(
                timeout=site_chars.content_wait_timeout,
                skip_framework=site_chars.skip_framework_detection
            )

            # Only do scroll recovery for unknown/SPA sites, with shorter waits
            if not content_found and site_chars.site_type in (SiteType.SPA, SiteType.UNKNOWN):
                self.scroll("down", 300)
                time.sleep(1)
                content_found = self._wait_for_dynamic_content(timeout=3000, skip_framework=True)
        elif site_chars.skip_dynamic_content_wait:
            # For static sites, just verify basic content is present
            content_found = self._quick_content_ready_check(min_links=1, min_text=100)

        self._human_delay(0.3, 0.6)

        if handle_popups:
            self._popups.handle_all()
            self._human_delay(0.1, 0.2)

        return {
            "action": "goto",
            "url": url,
            "title": self.page.title(),
            "content_found": content_found,
            "http_status": http_status,
            "site_type": site_chars.site_type.value
        }

    def _quick_content_ready_check(self, min_links: int = MIN_LINKS_FOR_READY, min_text: int = MIN_TEXT_LENGTH_FOR_READY) -> bool:
        """
        Quick check if page has enough content to be considered ready.

        This is a fast-path for static sites that don't need full dynamic
        content waiting. Returns True if the page appears to have loaded.

        Args:
            min_links: Minimum number of links to consider page ready
            min_text: Minimum text length to consider page ready

        Returns:
            True if page appears ready, False otherwise
        """
        try:
            result = self.page.evaluate(f"""
                () => {{
                    const links = document.querySelectorAll('a[href]').length;
                    const text = (document.body?.innerText || '').length;
                    const title = document.title || '';
                    const hasMainContent = document.querySelector('main, article, #content, .content, #mw-content-text');
                    return {{
                        links: links,
                        textLength: text,
                        hasTitle: title.length > 0,
                        hasMainContent: !!hasMainContent,
                        ready: (links >= {min_links} || text >= {min_text}) && title.length > 0
                    }};
                }}
            """)
            return result.get('ready', False)
        except PlaywrightError:
            return False

    def _wait_for_challenge_resolution(self, max_wait: int = MAX_CHALLENGE_WAIT_S) -> bool:
        """
        Wait for challenge/interstitial pages to resolve.

        DDoS-Guard, Cloudflare and similar services often show an interstitial
        page that auto-resolves after a few seconds. This method detects and
        waits for such pages, with human-like interaction to help solve challenges.

        Returns True if a challenge was detected and resolved, False otherwise.
        """
        # Check if this is specifically Cloudflare using advanced detection
        if self._cf_bypasser.is_challenge_page(self.page):
            print("  [Cloudflare challenge detected - using advanced bypass...]")
            return self._cf_bypasser.wait_for_challenge_resolution(self.page)

        # Fall back to generic challenge detection for other services
        for attempt in range(max_wait):
            html = self.page.content()
            result = self._detector.detect_challenge(html)

            if not result.detected:
                return attempt > 0  # Return True if we waited at all

            # Challenge detected - wait and check again
            if attempt == 0:
                print(f"  [Challenge detected: {result.details or 'unknown'} - waiting...]")

            # Human-like interaction to help solve challenge
            if attempt % CHALLENGE_MOUSE_INTERVAL_S == 0:  # Every 3 seconds
                try:
                    # Move mouse randomly (some challenges check for mouse activity)
                    viewport = self.page.viewport_size
                    if viewport:
                        x = random.randint(100, viewport['width'] - 100)
                        y = random.randint(100, viewport['height'] - 100)
                        self.page.mouse.move(x, y)
                except PlaywrightError:
                    pass

            if attempt == 5:  # After 5 seconds, try scrolling
                try:
                    self.page.mouse.wheel(0, 100)
                except PlaywrightError:
                    pass

            if attempt == CHALLENGE_CLICK_AFTER_S:  # After 10 seconds, try clicking in center
                try:
                    viewport = self.page.viewport_size
                    if viewport:
                        self.page.mouse.click(viewport['width'] // 2, viewport['height'] // 2)
                except PlaywrightError:
                    pass

            time.sleep(1)

            # Check if page URL changed (redirect after challenge)
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=2000)
            except PlaywrightError:
                pass

        # If we're still on a challenge page after max_wait, log it
        print(f"  [Challenge did not resolve after {max_wait}s]")
        return True

    def _wait_for_dynamic_content(self, timeout: int = LOAD_STATE_TIMEOUT_MS, skip_framework: bool = False) -> bool:
        """
        Wait for JavaScript-rendered content to appear.

        Uses multiple strategies with verification:
        1. Wait for network idle (shortened)
        2. Wait for framework hydration (React, Vue, Angular) - optional
        3. Early exit if content already appears ready
        4. Wait for loading indicators to disappear
        5. VERIFY actual content exists (links, buttons, text)

        Args:
            timeout: Maximum time to wait in milliseconds
            skip_framework: Skip framework detection for known static sites

        Returns True if content was found, False otherwise.
        """
        start_time = time.time()
        max_time = timeout / 1000  # Convert to seconds

        # EARLY EXIT CHECK: If content is already ready, return immediately
        # This is the key optimization for static sites
        if self._quick_content_ready_check(min_links=5, min_text=300):
            return True

        # Strategy 1: Brief wait for network to settle (reduced timeout)
        network_timeout = min(timeout, 5000)  # Max 5s for network idle
        try:
            self.page.wait_for_load_state("networkidle", timeout=network_timeout)
        except PlaywrightError:
            pass

        # Early exit check after network settles
        if self._quick_content_ready_check(min_links=MIN_LINKS_FOR_READY, min_text=MIN_TEXT_LENGTH_FOR_READY):
            return True

        # Strategy 2: Wait for framework hydration (only for SPAs)
        if not skip_framework:
            try:
                self.page.evaluate("""
                    () => {
                        return new Promise((resolve) => {
                            // Check if React has finished hydrating
                            if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__ || document.querySelector('[data-reactroot]')) {
                                setTimeout(resolve, 300);
                                return;
                            }
                            // Check for Vue
                            if (window.__VUE__ || document.querySelector('[data-v-]')) {
                                setTimeout(resolve, 300);
                                return;
                            }
                            // Check for Angular
                            if (window.ng || document.querySelector('[ng-version]')) {
                                setTimeout(resolve, 300);
                                return;
                            }
                            // Check for Next.js
                            if (window.__NEXT_DATA__ || document.querySelector('#__next')) {
                                setTimeout(resolve, 400);
                                return;
                            }
                            // No framework detected, resolve immediately
                            resolve();
                        });
                    }
                """)
            except PlaywrightError:
                pass

        # Strategy 3: Wait for document.readyState === 'complete' (brief)
        try:
            self.page.wait_for_function(
                "() => document.readyState === 'complete'",
                timeout=2000
            )
        except PlaywrightError:
            pass

        # Check again - many pages are ready by now
        if self._quick_content_ready_check(min_links=MIN_LINKS_FOR_READY, min_text=MIN_TEXT_LENGTH_FOR_READY):
            return True

        # Strategy 4: Wait for loading indicators to disappear (shortened)
        spinner_selectors = [
            '.loading', '.spinner', '.loader', '[aria-busy="true"]',
            '.skeleton', '.loading-overlay'
        ]
        for selector in spinner_selectors:
            if time.time() - start_time > max_time:
                break
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.wait_for(state="hidden", timeout=2000)
            except PlaywrightError:
                pass

        # Strategy 5: Final content verification loop (reduced iterations)
        for attempt in range(3):  # Reduced from 8
            if time.time() - start_time > max_time:
                break

            try:
                content_check = self.page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a[href]');
                        const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
                        const inputs = document.querySelectorAll('input, textarea, select');
                        const textLength = document.body?.innerText?.length || 0;

                        const hasPlaceholder = document.querySelector('.loading, .skeleton, [aria-busy="true"]');
                        const hasEmptyRoot = document.querySelector('#root:empty, #app:empty, #__next:empty');

                        const visibleLinks = Array.from(links).filter(el => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        }).length;

                        return {
                            visibleLinks: visibleLinks,
                            buttons: buttons.length,
                            inputs: inputs.length,
                            textLength: textLength,
                            hasPlaceholder: !!hasPlaceholder,
                            hasEmptyRoot: !!hasEmptyRoot,
                            hasContent: (visibleLinks > 3 || buttons.length > 0 || inputs.length > 0 || textLength > 500) && !hasEmptyRoot
                        };
                    }
                """)

                if content_check.get('hasContent', False) and not content_check.get('hasPlaceholder', True):
                    return True

                # Wait briefly before retry
                time.sleep(0.5)

            except PlaywrightError:
                time.sleep(0.3)

        # Final verification - accept any page with minimal content
        try:
            return self.page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href]').length;
                    const text = document.body?.innerText?.length || 0;
                    return links > 0 || text > 100;
                }
            """)
        except PlaywrightError:
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
        except PlaywrightError:
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
        except PlaywrightError:
            pass

        # Trigger mouse move (some sites wait for user activity)
        try:
            self.page.mouse.move(100, 100)
            self.page.mouse.move(200, 200)
        except PlaywrightError:
            pass

        # Click on body to trigger focus events
        try:
            self.page.evaluate("document.body.click()")
        except PlaywrightError:
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
                    except PlaywrightError:
                        continue
        else:
            locator = self.page.locator(selector).first

        if not locator:
            raise ElementNotFoundError(selector=str(selector))

        # Simple human delay before click
        if human:
            self._human_delay(*HUMAN_CLICK_PRE_DELAY)

        locator.click()

        if human:
            self._human_delay(*HUMAN_CLICK_POST_DELAY)
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
                loc.wait_for(state="visible", timeout=ELEMENT_WAIT_TIMEOUT_MS)
                if loc.is_visible():
                    locator = loc
                    used_selector = sel
                    break
            except PlaywrightError:
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
                    except PlaywrightError:
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
        except PlaywrightError as e:
            # Last resort: try using fill() directly
            try:
                locator.fill(text)
            except PlaywrightError:
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
                self.page.wait_for_load_state("networkidle", timeout=LOAD_STATE_TIMEOUT_MS)
            except PlaywrightError:
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                except PlaywrightError:
                    pass  # Continue anyway - page may be usable

        # If ensure_content is True, wait for actual content to appear
        if ensure_content:
            self._wait_for_dynamic_content(timeout=LOAD_STATE_TIMEOUT_MS)

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
            except PlaywrightError as e:
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
            except PlaywrightError as e:
                if "navigation" in str(e).lower() or "destroyed" in str(e).lower():
                    if attempt < retries - 1:
                        time.sleep(1)
                        try:
                            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                        except PlaywrightError:
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
        except PlaywrightError:
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except PlaywrightError:
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

    def download_file(self, selector: str = None, url: str = None, timeout: int = DOWNLOAD_TIMEOUT_MS) -> dict:
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
                except PlaywrightError as e:
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

        # Save to download directory (P0-SEC: sanitize filename to prevent path traversal)
        suggested_name = _sanitize_filename(download.suggested_filename)
        base_path = self.download_dir / suggested_name
        save_path = _reserve_unique_path(self.download_dir, base_path)

        download.save_as(str(save_path))

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

    def download_link(self, href: str, timeout: int = DOWNLOAD_TIMEOUT_MS) -> dict:
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
        except (PlaywrightError, OSError) as e:
            if "Timeout" in str(e) or "download" in str(e).lower():
                # Browser displays file inline - use HTTP fetch instead
                return self._fetch_file_directly(href)
            raise

    def _fetch_file_directly(self, url: str) -> dict:
        """
        Download a file using direct HTTP fetch (for inline content like images).

        Security: Validates URL against SSRF attacks before fetching.
        """
        # P0-SEC: Validate URL is not targeting internal networks (SSRF protection)
        _is_ssrf_safe(url)  # Raises ValueError if unsafe

        # Get filename from URL (P0-SEC: sanitize to prevent path traversal)
        parsed = urlparse(url)
        raw_filename = unquote(parsed.path.split('/')[-1]) or 'downloaded_file'
        filename = _sanitize_filename(raw_filename)

        # Add extension if missing based on content type
        base_path = self.download_dir / filename
        save_path = _reserve_unique_path(self.download_dir, base_path)

        # Download the file with User-Agent to avoid 403 errors
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': self.stealth.get_random_user_agent()
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(save_path, 'wb') as f:
                    f.write(response.read())
        except urllib.error.HTTPError as e:
            save_path.unlink(missing_ok=True)
            raise DownloadError(url, reason=e.reason, status_code=e.code)
        except (urllib.error.URLError, OSError) as e:
            save_path.unlink(missing_ok=True)
            raise DownloadError(url, reason=str(e))

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

    def click_and_download(self, selector: str, timeout: int = DOWNLOAD_TIMEOUT_MS) -> dict:
        """
        Click an element and wait for download to start.

        Useful for download buttons that don't have direct URLs.
        """
        return self.download_file(selector=selector, timeout=timeout)

    def get_pending_downloads(self) -> List[Download]:
        """Get list of pending/recent downloads."""
        return self._pending_downloads.copy()

    def wait_for_download(self, timeout: int = DOWNLOAD_TIMEOUT_MS) -> Optional[dict]:
        """
        Wait for any download to complete.

        Returns download info or None if timeout.
        """
        try:
            with self.page.expect_download(timeout=timeout) as download_info:
                pass  # Just wait
            download = download_info.value

            # P0-SEC: sanitize filename to prevent path traversal
            safe_filename = _sanitize_filename(download.suggested_filename)
            save_path = self.download_dir / safe_filename
            download.save_as(str(save_path))

            return {
                "filename": save_path.name,
                "path": str(save_path),
                "size": save_path.stat().st_size,
                "hash": self._compute_hash(save_path),
                "url": download.url
            }
        except (PlaywrightError, OSError):
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

