"""
StarSearch-backed drop-in replacement for blackreach/browser.py.

Complete implementation of Blackreach's Hand interface backed by StarSearch.
Covers navigation, interaction, downloads, smart actions, proxy rotation,
and the execute() command dispatcher.

INSTALL: Copy this file to blackreach/browser.py (or symlink).
No other Blackreach files need modification.
"""
from __future__ import annotations
import hashlib
import logging
import os
import re
import threading
import time
import random
import urllib.request
import urllib.error
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse, unquote

from starsearch import StarSearch
from starsearch.session import StarSearchSession
from starsearch.exceptions import (
    StarSearchError,
    StarSearchElementNotFound,
    StarSearchTimeoutError,
)

logger = logging.getLogger(__name__)

# Navigation timeouts (milliseconds)
GOTO_TIMEOUT_MS = 30_000
LOAD_STATE_TIMEOUT_MS = 10_000
ELEMENT_WAIT_TIMEOUT_MS = 3_000
DOWNLOAD_TIMEOUT_MS = 60_000

# Content readiness
MIN_LINKS_FOR_READY = 3
MIN_TEXT_LENGTH_FOR_READY = 200

# Challenge handling
MAX_CHALLENGE_WAIT_S = 30

# Filename sanitization
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_PATH_TRAVERSAL = re.compile(r'(?:^|[\\/])\.\.(?:[\\/]|$)')

_download_lock = threading.Lock()


def _sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = _PATH_TRAVERSAL.sub('', filename)
    filename = _UNSAFE_FILENAME_CHARS.sub('_', filename)
    filename = filename.strip('. ')
    if not filename:
        filename = 'downloaded_file'
    return filename


def _reserve_unique_path(download_dir: Path, base_path: Path) -> Path:
    with _download_lock:
        save_path = base_path
        counter = 1
        while save_path.exists():
            stem = base_path.stem
            save_path = download_dir / f"{stem}_{counter}{base_path.suffix}"
            counter += 1
        save_path.touch()
    return save_path


def _is_ssrf_safe(url: str) -> bool:
    import socket
    import ipaddress

    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("URL has no hostname")

    if hostname.lower() in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
        raise ValueError(f"SSRF blocked: localhost access not allowed")

    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return True

    private_ranges = [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('127.0.0.0/8'),
        ipaddress.ip_network('169.254.0.0/16'),
        ipaddress.ip_network('fc00::/7'),
        ipaddress.ip_network('fe80::/10'),
        ipaddress.ip_network('::1/128'),
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
            continue

    return True


# ── Exceptions (match Blackreach's) ──

class BrowserNotReadyError(Exception):
    pass

class ElementNotFoundError(Exception):
    def __init__(self, selector: str = "", text: str = ""):
        self.selector = selector
        self.text = text
        super().__init__(f"Element not found: {selector or text}")

class DownloadError(Exception):
    def __init__(self, url: str, reason: str = "", status_code: int = 0):
        self.url = url
        self.reason = reason
        self.status_code = status_code
        super().__init__(f"Download failed: {url} ({reason})")

class InvalidActionArgsError(Exception):
    def __init__(self, action: str, message: str):
        super().__init__(f"Invalid args for {action}: {message}")

class UnknownActionError(Exception):
    def __init__(self, action: str):
        super().__init__(f"Unknown action: {action}")


# ── Proxy ──

class ProxyType(Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"
    SOCKS4 = "socks4"


@dataclass
class ProxyConfig:
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    bypass: Optional[List[str]] = None

    def to_playwright_proxy(self) -> Dict[str, Any]:
        scheme = self.proxy_type.value
        if scheme == "https":
            scheme = "http"
        server = f"{scheme}://{self.host}:{self.port}"
        result = {"server": server}
        if self.username and self.password:
            result["username"] = self.username
            result["password"] = self.password
        if self.bypass:
            result["bypass"] = ",".join(self.bypass)
        return result

    @classmethod
    def from_url(cls, url: str) -> "ProxyConfig":
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        proxy_type_map = {
            "http": ProxyType.HTTP, "https": ProxyType.HTTPS,
            "socks5": ProxyType.SOCKS5, "socks4": ProxyType.SOCKS4,
            "socks": ProxyType.SOCKS5,
        }
        return cls(
            host=parsed.hostname or "localhost",
            port=parsed.port or (1080 if "socks" in scheme else 8080),
            proxy_type=proxy_type_map.get(scheme, ProxyType.HTTP),
            username=parsed.username,
            password=parsed.password,
        )

    def __str__(self) -> str:
        auth = f"{self.username}:***@" if self.username else ""
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"


class ProxyRotator:
    def __init__(self, proxies: Optional[List[Union[str, ProxyConfig]]] = None):
        self._proxies: List[ProxyConfig] = []
        self._current_index = 0
        self._health: Dict[str, Dict[str, Any]] = {}
        self._domain_sticky: Dict[str, str] = {}
        if proxies:
            for proxy in proxies:
                self.add_proxy(proxy)

    def add_proxy(self, proxy: Union[str, ProxyConfig]):
        if isinstance(proxy, str):
            proxy = ProxyConfig.from_url(proxy)
        self._proxies.append(proxy)
        self._health[str(proxy)] = {
            "successes": 0, "failures": 0,
            "last_used": None, "avg_response_time": 0, "enabled": True,
        }

    def remove_proxy(self, proxy: Union[str, ProxyConfig]):
        proxy_str = str(proxy) if isinstance(proxy, ProxyConfig) else proxy
        self._proxies = [p for p in self._proxies if str(p) != proxy_str]
        self._health.pop(proxy_str, None)

    def get_next(self, domain: Optional[str] = None) -> Optional[ProxyConfig]:
        if not self._proxies:
            return None
        if domain and domain in self._domain_sticky:
            sticky_str = self._domain_sticky[domain]
            for proxy in self._proxies:
                if str(proxy) == sticky_str and self._health[sticky_str]["enabled"]:
                    return proxy
        enabled = [p for p in self._proxies if self._health[str(p)]["enabled"]]
        if not enabled:
            for proxy_str in self._health:
                self._health[proxy_str]["enabled"] = True
            enabled = self._proxies
        if not enabled:
            return None
        self._current_index = self._current_index % len(enabled)
        proxy = enabled[self._current_index]
        self._current_index += 1
        if domain:
            self._domain_sticky[domain] = str(proxy)
        self._health[str(proxy)]["last_used"] = time.time()
        return proxy

    def report_success(self, proxy: Union[str, ProxyConfig], response_time: float = 0):
        proxy_str = str(proxy) if isinstance(proxy, ProxyConfig) else proxy
        if proxy_str in self._health:
            h = self._health[proxy_str]
            h["successes"] += 1
            total = h["successes"] + h["failures"]
            h["avg_response_time"] = (h["avg_response_time"] * (total - 1) + response_time) / total

    def report_failure(self, proxy: Union[str, ProxyConfig], disable_threshold: int = 5):
        proxy_str = str(proxy) if isinstance(proxy, ProxyConfig) else proxy
        if proxy_str in self._health:
            h = self._health[proxy_str]
            h["failures"] += 1
            rate = h["failures"] / (h["successes"] + h["failures"])
            if h["failures"] >= disable_threshold and rate > 0.5:
                h["enabled"] = False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_proxies": len(self._proxies),
            "enabled": sum(1 for h in self._health.values() if h["enabled"]),
            "proxies": {str(p): self._health.get(str(p), {}) for p in self._proxies},
        }

    def clear_sticky_sessions(self):
        self._domain_sticky.clear()

    def __len__(self) -> int:
        return len(self._proxies)


# ── Hand ──

class Hand:
    """
    StarSearch-backed Hand class. Complete drop-in for Blackreach's Playwright Hand.
    All stealth, fingerprinting, and behavioral humanization handled by StarSearch daemon.
    """

    def __init__(
        self,
        headless: bool = False,
        stealth_config=None,  # accepted but ignored — StarSearch handles stealth
        retry_config=None,
        download_dir: Optional[Path] = None,
        browser_type: str = "chromium",
        proxy: Optional[Union[str, ProxyConfig]] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
        **kwargs,
    ):
        self._browser = StarSearch()
        self._session: Optional[StarSearchSession] = None
        self.download_dir = download_dir or Path("./downloads")
        self.headless = headless

        # Proxy
        self._proxy: Optional[ProxyConfig] = None
        self._proxy_rotator = proxy_rotator
        self._current_proxy: Optional[ProxyConfig] = None
        if proxy:
            self._proxy = ProxyConfig.from_url(proxy) if isinstance(proxy, str) else proxy

        # State
        self._mouse_pos = (0, 0)
        self._wake_count = 0
        self._consecutive_errors = 0
        self._download_callback: Optional[Callable] = None

    # ── lifecycle ──

    @property
    def is_awake(self) -> bool:
        return self._session is not None

    def is_healthy(self) -> bool:
        if not self.is_awake:
            return False
        try:
            self._session.evaluate("document.title")
            self._consecutive_errors = 0
            return True
        except StarSearchError:
            self._consecutive_errors += 1
            return False

    def ensure_awake(self) -> bool:
        if self.is_awake and self.is_healthy():
            return True
        if self._session is not None:
            try:
                self.sleep()
            except Exception as e:
                logger.warning("Failed to close unhealthy session: %s", e)
        try:
            self.wake()
            return True
        except Exception as e:
            logger.error("Failed to wake: %s", e)
            return False

    def restart(self) -> bool:
        current_url = None
        if self.is_awake:
            try:
                current_url = self.get_url()
            except Exception:
                pass
        try:
            self.sleep()
        except Exception as e:
            logger.warning("Failed to close during restart: %s", e)
        try:
            self.wake()
            if current_url and current_url != "about:blank":
                try:
                    self.goto(current_url, wait_for_content=False)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error("Failed to wake during restart: %s", e)
            return False

    def wake(self) -> None:
        if self._session is not None:
            return
        self.download_dir.mkdir(parents=True, exist_ok=True)
        proxy_url = None
        if self._proxy:
            self._current_proxy = self._proxy
            proxy_url = f"{self._proxy.proxy_type.value}://{self._proxy.host}:{self._proxy.port}"
        elif self._proxy_rotator and len(self._proxy_rotator) > 0:
            p = self._proxy_rotator.get_next()
            if p:
                self._current_proxy = p
                proxy_url = f"{p.proxy_type.value}://{p.host}:{p.port}"
        self._session = self._browser.new_session(
            proxy=proxy_url,
            locale="en-US",
            human_level=2,
        )
        self._wake_count += 1

    def sleep(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
        self._current_proxy = None

    def close(self) -> None:
        self.sleep()
        if self._browser:
            self._browser.close()

    def __enter__(self) -> "Hand":
        self.wake()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ── proxy ──

    def set_proxy(self, proxy: Union[str, ProxyConfig, None]):
        if proxy is None:
            self._proxy = None
        elif isinstance(proxy, str):
            self._proxy = ProxyConfig.from_url(proxy)
        else:
            self._proxy = proxy

    def get_current_proxy(self) -> Optional[ProxyConfig]:
        return self._current_proxy

    def report_proxy_result(self, success: bool, response_time: float = 0):
        if self._proxy_rotator and self._current_proxy:
            if success:
                self._proxy_rotator.report_success(self._current_proxy, response_time)
            else:
                self._proxy_rotator.report_failure(self._current_proxy)

    # ── navigation ──

    def goto(self, url: str, handle_popups: bool = True, wait_for_content: bool = True, **kwargs) -> dict:
        self._ensure_session()
        self._session.navigate(url, timeout=GOTO_TIMEOUT_MS // 1000)
        if wait_for_content:
            self._wait_for_dynamic_content()
        if handle_popups:
            self._try_dismiss_popups()
        return {"action": "goto", "url": url}

    def get_url(self) -> str:
        self._ensure_session()
        return self._session.evaluate("window.location.href") or ""

    def get_title(self, retries: int = 3) -> str:
        self._ensure_session()
        for attempt in range(retries):
            try:
                return self._session.evaluate("document.title") or ""
            except StarSearchError:
                if attempt < retries - 1:
                    time.sleep(1)
        return self.get_url()

    def back(self) -> dict:
        self._ensure_session()
        self._session.go_back()
        return {"action": "back"}

    def forward(self) -> dict:
        self._ensure_session()
        self._session.go_forward()
        return {"action": "forward"}

    def refresh(self) -> dict:
        self._ensure_session()
        self._session.evaluate("window.location.reload()")
        return {"action": "refresh"}

    # ── interaction ──

    def click(self, selector: Union[str, List[str]], human: bool = None, **kwargs) -> dict:
        self._ensure_session()
        selectors = selector if isinstance(selector, list) else [selector]
        used = None
        for sel in selectors:
            try:
                self._session.click(sel, human=human if human is not None else True)
                used = sel
                break
            except StarSearchElementNotFound:
                continue
        if used is None:
            raise ElementNotFoundError(selector=str(selectors[0]))
        return {"action": "click", "selector": used}

    def type(self, selector: str, text: str, human: bool = None, clear: bool = True, **kwargs) -> dict:
        self._ensure_session()
        escaped_text = text.replace("'", "\\'").replace("\n", "\\n")
        # Focus and clear the element via JS first (works with data-br-id selectors)
        if clear:
            self._session.evaluate(f"""
            (() => {{
                const el = document.querySelector('{selector}');
                if (el) {{ el.focus(); el.value = ''; }}
            }})()
            """)
        # Try StarSearch native type first (better humanization)
        try:
            self._session.type(selector, text, human=human if human is not None else True)
        except (StarSearchError, StarSearchElementNotFound):
            # Fallback: set value via JS and dispatch events
            self._session.evaluate(f"""
            (() => {{
                const el = document.querySelector('{selector}');
                if (el) {{
                    el.focus();
                    el.value = '{escaped_text}';
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            }})()
            """)
        return {"action": "type", "selector": selector, "text": text}

    def press(self, key: str) -> dict:
        self._ensure_session()
        self._session.evaluate(f"""
        (() => {{
            const el = document.activeElement || document;
            const opts = {{key: '{key}', code: '{key}', bubbles: true, cancelable: true}};
            el.dispatchEvent(new KeyboardEvent('keydown', opts));
            el.dispatchEvent(new KeyboardEvent('keypress', opts));
            el.dispatchEvent(new KeyboardEvent('keyup', opts));
            if ('{key}' === 'Enter') {{
                const form = el.closest('form');
                if (form) {{
                    try {{ form.requestSubmit(); }} catch(e) {{ form.submit(); }}
                }}
            }}
        }})()
        """)
        time.sleep(random.uniform(0.05, 0.15))
        return {"action": "press", "key": key}

    def scroll(self, direction: str = "down", amount: int = 500, human: bool = None, **kwargs) -> dict:
        self._ensure_session()
        self._session.scroll(direction, amount)
        return {"action": "scroll", "direction": direction, "amount": amount}

    def hover(self, selector: str) -> dict:
        self._ensure_session()
        self._session.hover(selector)
        return {"action": "hover", "selector": selector}

    # ── content ──

    def get_html(self, wait_for_load: bool = True, retries: int = 3, ensure_content: bool = False) -> str:
        self._ensure_session()
        if wait_for_load:
            self._wait_for_dynamic_content(timeout=LOAD_STATE_TIMEOUT_MS)
        for attempt in range(retries):
            try:
                html = self._session.get_content().html
                if ensure_content and html and '<a ' not in html.lower() and attempt < retries - 1:
                    time.sleep(2)
                    continue
                return html
            except StarSearchError:
                if attempt < retries - 1:
                    time.sleep(1)
                else:
                    raise
        return ""

    def get_url(self) -> str:
        self._ensure_session()
        return self._session.evaluate("window.location.href") or ""

    def wait_for_navigation(self, timeout: float = 10000) -> None:
        self._ensure_session()
        self._session.wait_for_navigation(timeout=int(timeout) // 1000)

    def screenshot(self, path: str = "screenshot.png", full_page: bool = False) -> dict:
        self._ensure_session()
        import base64
        data = self._session.screenshot()
        if path and data:
            img_bytes = base64.b64decode(data) if isinstance(data, str) else data
            with open(path, "wb") as f:
                f.write(img_bytes)
        return {"action": "screenshot", "path": path}

    def force_render(self) -> bool:
        self._ensure_session()
        try:
            self._session.evaluate(
                "window.scrollTo(0, 1); window.scrollTo(0, 0);"
            )
            time.sleep(0.5)
            return True
        except StarSearchError:
            return False

    # ── downloads ──

    def set_download_callback(self, callback: Callable) -> None:
        self._download_callback = callback

    def download_file(self, selector: str = None, url: str = None, timeout: int = DOWNLOAD_TIMEOUT_MS) -> dict:
        if not selector and not url:
            raise InvalidActionArgsError("download", "Must provide either selector or url")
        if url:
            return self._fetch_file_directly(url)
        # Click-triggered download — click then check for file via JS
        self._ensure_session()
        self._session.click(selector)
        time.sleep(2)
        return {"action": "download", "selector": selector, "note": "click-triggered"}

    def download_link(self, href: str, timeout: int = DOWNLOAD_TIMEOUT_MS) -> dict:
        return self._fetch_file_directly(href)

    def _fetch_file_directly(self, url: str) -> dict:
        _is_ssrf_safe(url)
        parsed = urlparse(url)
        raw_filename = unquote(parsed.path.split('/')[-1]) or 'downloaded_file'
        filename = _sanitize_filename(raw_filename)
        base_path = self.download_dir / filename
        save_path = _reserve_unique_path(self.download_dir, base_path)

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                content_type = response.headers.get('Content-Type', '')
                data = response.read()

            if not save_path.suffix:
                ext_map = {'pdf': '.pdf', 'zip': '.zip', 'jpeg': '.jpg', 'jpg': '.jpg', 'png': '.png', 'html': '.html'}
                for key, ext in ext_map.items():
                    if key in content_type:
                        save_path = _reserve_unique_path(self.download_dir, save_path.with_suffix(ext))
                        break

            with open(save_path, 'wb') as f:
                f.write(data)
        except urllib.error.HTTPError as e:
            save_path.unlink(missing_ok=True)
            raise DownloadError(url, reason=e.reason, status_code=e.code)
        except (urllib.error.URLError, OSError) as e:
            save_path.unlink(missing_ok=True)
            raise DownloadError(url, reason=str(e))

        return {
            "action": "download",
            "filename": save_path.name,
            "path": str(save_path),
            "size": save_path.stat().st_size,
            "hash": self._compute_hash(save_path),
            "url": url,
        }

    def click_and_download(self, selector: str, timeout: int = DOWNLOAD_TIMEOUT_MS) -> dict:
        return self.download_file(selector=selector, timeout=timeout)

    def get_pending_downloads(self) -> list:
        return []

    def wait_for_download(self, timeout: int = DOWNLOAD_TIMEOUT_MS) -> Optional[dict]:
        return None

    def _compute_hash(self, path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ── smart actions ──

    def smart_click(self, text: str, tag: str = "*") -> dict:
        self._ensure_session()
        # Use XPath text matching via JS
        script = f"""
        (() => {{
            const xpath = "//{tag}[contains(normalize-space(.), '{text}')]";
            const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            const el = result.singleNodeValue;
            if (el) {{ el.click(); return true; }}
            return false;
        }})()
        """
        found = self._session.evaluate(script)
        if not found:
            raise ElementNotFoundError(text=text)
        return {"action": "smart_click", "text": text}

    def smart_type(self, text: str, into: str = None, placeholder: str = None, label: str = None) -> dict:
        self._ensure_session()
        # Build selector from available attributes
        if into:
            selector = f"input[name='{into}'], textarea[name='{into}']"
        elif placeholder:
            selector = f"input[placeholder*='{placeholder}'], textarea[placeholder*='{placeholder}']"
        elif label:
            script = f"""
            (() => {{
                const labels = document.querySelectorAll('label');
                for (const l of labels) {{
                    if (l.textContent.includes('{label}')) {{
                        const input = l.querySelector('input, textarea') || document.getElementById(l.htmlFor);
                        if (input) {{ input.value = '{text}'; input.dispatchEvent(new Event('input', {{bubbles: true}})); return true; }}
                    }}
                }}
                return false;
            }})()
            """
            found = self._session.evaluate(script)
            if not found:
                raise ElementNotFoundError(text=label)
            return {"action": "smart_type", "text": text}
        else:
            raise InvalidActionArgsError("smart_type", "Need into, placeholder, or label")

        self._session.type(selector, text)
        return {"action": "smart_type", "text": text}

    def wait_and_click(self, selector: str, timeout: float = 10000) -> dict:
        self._ensure_session()
        self._session.wait_for_selector(selector, timeout=int(timeout) // 1000)
        return self.click(selector)

    def dismiss_popups(self) -> dict:
        return self._try_dismiss_popups()

    # ── cookies ──

    def get_cookies(self) -> list:
        self._ensure_session()
        return self._session.get_cookies()

    def set_cookies(self, cookies: list) -> None:
        self._ensure_session()
        self._session.set_cookies(cookies)

    # ── execute dispatcher ──

    def execute(self, command: dict) -> dict:
        action = command.get("action")
        human = command.get("human", True)

        dispatch = {
            "goto": lambda: self.goto(command["url"]),
            "click": lambda: self.click(command["selector"], human=human),
            "type": lambda: self.type(command["selector"], command["text"], human=human),
            "press": lambda: self.press(command["key"]),
            "scroll": lambda: self.scroll(command.get("direction", "down"), command.get("amount", 500), human=human),
            "back": lambda: self.back(),
            "forward": lambda: self.forward(),
            "refresh": lambda: self.refresh(),
            "hover": lambda: self.hover(command["selector"]),
            "screenshot": lambda: self.screenshot(command.get("path", "screenshot.png")),
            "wait": lambda: (time.sleep(command.get("seconds", 1)), {"action": "wait", "seconds": command.get("seconds", 1)})[1],
            "smart_click": lambda: self.smart_click(command["text"], command.get("tag", "*")),
            "smart_type": lambda: self.smart_type(command["text"], command.get("into"), command.get("placeholder"), command.get("label")),
            "dismiss_popups": lambda: self.dismiss_popups(),
            "wait_and_click": lambda: self.wait_and_click(command["selector"], command.get("timeout", 10000)),
        }

        handler = dispatch.get(action)
        if handler is None:
            raise UnknownActionError(action)
        return handler()

    # ── internal helpers ──

    def _ensure_session(self) -> None:
        if self._session is None:
            self.wake()

    def _wait_for_dynamic_content(self, timeout: int = LOAD_STATE_TIMEOUT_MS) -> bool:
        """Wait for page to have meaningful content."""
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            try:
                result = self._session.evaluate("""
                (() => {
                    const links = document.querySelectorAll('a').length;
                    const text = document.body ? document.body.innerText.length : 0;
                    return {links, text};
                })()
                """)
                if result and result.get("links", 0) >= MIN_LINKS_FOR_READY and result.get("text", 0) >= MIN_TEXT_LENGTH_FOR_READY:
                    return True
            except StarSearchError:
                pass
            time.sleep(0.5)
        return False

    def _try_dismiss_popups(self) -> dict:
        """Try to dismiss common popups and cookie banners."""
        dismissed = 0
        try:
            result = self._session.evaluate("""
            (() => {
                let count = 0;
                const selectors = [
                    '[class*="cookie"] button', '[class*="consent"] button',
                    '[id*="cookie"] button', '[id*="consent"] button',
                    'button[class*="accept"]', 'button[class*="agree"]',
                    'button[class*="close"]', '[class*="modal"] button[class*="close"]',
                    '[class*="popup"] button[class*="close"]',
                    '[aria-label="Close"]', '[aria-label="close"]',
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        if (el.offsetParent !== null) {
                            el.click();
                            count++;
                        }
                    }
                }
                return count;
            })()
            """)
            dismissed = result or 0
        except StarSearchError:
            pass
        return {"action": "dismiss_popups", "dismissed": dismissed}

    # ── properties for compatibility ──

    @property
    def page(self):
        """Return a compatibility shim that exposes evaluate() and keyboard
        so existing code (dom_walker, agent action dispatch) keeps working."""
        return _PageShim(self._session)

    @property
    def selector(self):
        raise NotImplementedError("SmartSelector not available with StarSearch. Use smart_click/smart_type instead.")

    @property
    def popups(self):
        raise NotImplementedError("PopupHandler not available with StarSearch. Use dismiss_popups() instead.")

    @property
    def waits(self):
        raise NotImplementedError("WaitConditions not available with StarSearch. Use wait_and_click() instead.")


class _KeyboardShim:
    """Minimal keyboard interface matching Playwright's page.keyboard."""

    def __init__(self, session):
        self._session = session

    def press(self, key: str):
        # Dispatch key events on the currently focused element (not document)
        # For Enter: also trigger form submission if the element is in a form
        self._session.evaluate(f"""
        (() => {{
            const el = document.activeElement || document;
            const opts = {{key: '{key}', code: '{key}', bubbles: true, cancelable: true}};
            el.dispatchEvent(new KeyboardEvent('keydown', opts));
            el.dispatchEvent(new KeyboardEvent('keypress', opts));
            el.dispatchEvent(new KeyboardEvent('keyup', opts));
            if ('{key}' === 'Enter') {{
                // Try to submit the form the element belongs to
                const form = el.closest('form');
                if (form) {{
                    // requestSubmit respects validation, submit() bypasses it
                    try {{ form.requestSubmit(); }} catch(e) {{ form.submit(); }}
                }}
            }}
        }})()
        """)
        time.sleep(random.uniform(0.05, 0.15))


class _LocatorShim:
    """Minimal locator matching Playwright's page.locator()."""

    def __init__(self, session, selector: str):
        self._session = session
        self._selector = selector

    @property
    def first(self):
        return self

    def count(self) -> int:
        try:
            result = self._session.evaluate(
                f"document.querySelectorAll('{self._selector}').length"
            )
            return int(result) if result else 0
        except Exception:
            return 0

    def click(self, **kwargs):
        # Try StarSearch native click first (better humanization, mouse events)
        try:
            self._session.click(self._selector)
        except (StarSearchError, StarSearchElementNotFound, Exception):
            # Fallback: JS click with scrollIntoView (works for data-br-id selectors)
            clicked = self._session.evaluate(
                f"(() => {{ const el = document.querySelector('{self._selector}'); "
                f"if (el) {{ el.scrollIntoView({{block:'center'}}); el.click(); return true; }} return false; }})()"
            )
            if not clicked:
                raise ElementNotFoundError(selector=self._selector)

    def fill(self, value: str, **kwargs):
        # Use JS to clear and set value, then dispatch input event
        escaped_value = value.replace("'", "\\'").replace("\n", "\\n")
        self._session.evaluate(
            f"(() => {{ const el = document.querySelector('{self._selector}'); "
            f"if (el) {{ el.focus(); el.value = ''; el.value = '{escaped_value}'; "
            f"el.dispatchEvent(new Event('input', {{bubbles:true}})); "
            f"el.dispatchEvent(new Event('change', {{bubbles:true}})); }} }})()"
        )

    def is_visible(self) -> bool:
        try:
            result = self._session.evaluate(
                f"!!document.querySelector('{self._selector}') && "
                f"document.querySelector('{self._selector}').offsetParent !== null"
            )
            return bool(result)
        except Exception:
            return False


class _GetByTextShim:
    """Minimal shim for page.get_by_text()."""

    def __init__(self, session, text: str, exact: bool = False):
        self._session = session
        self._text = text
        self._exact = exact

    @property
    def first(self):
        return self

    def click(self, **kwargs):
        escaped = self._text.replace("'", "\\'")
        script = f"""
        (() => {{
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {{
                if (walker.currentNode.textContent.includes('{escaped}')) {{
                    walker.currentNode.parentElement.click();
                    return true;
                }}
            }}
            return false;
        }})()
        """
        self._session.evaluate(script)


class _PageShim:
    """Thin compatibility layer so code using hand.page.evaluate(),
    hand.page.keyboard.press(), hand.page.locator(), and
    hand.page.get_by_text() keeps working with StarSearch."""

    def __init__(self, session):
        self._session = session
        self.keyboard = _KeyboardShim(session)

    @property
    def url(self) -> str:
        try:
            return self._session.evaluate("window.location.href") or ""
        except Exception:
            return ""

    def evaluate(self, expression, arg=None):
        if arg is not None:
            import json
            arg_json = json.dumps(arg)
            # Playwright evaluate: if expression is a function like (arg) => {...},
            # it calls the function with the arg. We replicate this by wrapping
            # the function expression as an IIFE with the arg injected.
            stripped = expression.strip()
            if stripped.startswith("(") or stripped.startswith("function"):
                expression = f"({stripped})({arg_json})"
            else:
                expression = f"((__arg) => {{ {stripped} }})({arg_json})"
        return self._session.evaluate(expression)

    def locator(self, selector: str):
        return _LocatorShim(self._session, selector)

    def get_by_text(self, text: str, exact: bool = False):
        return _GetByTextShim(self._session, text, exact)


# Alias for backwards compatibility
Browser = Hand
