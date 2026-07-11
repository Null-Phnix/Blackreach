"""Deterministic browser-backend loader.

``BLACKREACH_BROWSER_BACKEND`` accepts ``auto`` (default), ``starsearch``, or
``playwright``. Auto selection checks installation and daemon socket presence;
it never creates a browser session at import time.
"""
import importlib.util
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _choose_backend(requested: str, starsearch_available: bool) -> str:
    """Return the requested backend without silently weakening explicit policy."""
    if requested == "starsearch":
        return "starsearch"
    if requested == "auto" and starsearch_available:
        return "starsearch"
    return "playwright"

def _starsearch_available() -> bool:
    if importlib.util.find_spec("starsearch") is None:
        return False
    socket_path = os.environ.get("STARSEARCH_SOCKET")
    if not socket_path:
        pointer = Path.home() / ".starsearch" / "daemon.sock_path"
        try:
            socket_path = pointer.read_text().strip()
        except OSError:
            return False
    return bool(socket_path and Path(socket_path).is_socket())


_requested_backend = os.environ.get("BLACKREACH_BROWSER_BACKEND", "auto").strip().lower()
if _requested_backend not in {"auto", "starsearch", "playwright"}:
    logger.warning(
        "Unknown BLACKREACH_BROWSER_BACKEND=%r; using auto", _requested_backend
    )
    _requested_backend = "auto"

_backend = _choose_backend(_requested_backend, _starsearch_available())

try:
    if _backend != "starsearch":
        raise ImportError("Playwright explicitly selected")
    from blackreach.extras.browser_starsearch import (
        Hand, ProxyConfig, ProxyType, ProxyRotator,
        BrowserNotReadyError, ElementNotFoundError, DownloadError,
        InvalidActionArgsError, UnknownActionError,
    )
    _backend = "starsearch"
    logger.info("Using StarSearch browser backend (stealth daemon)")

except (ImportError, ModuleNotFoundError) as exc:
    if _requested_backend == "starsearch":
        raise RuntimeError(
            "BLACKREACH_BROWSER_BACKEND=starsearch but the StarSearch backend "
            "could not be loaded; refusing silent Playwright fallback"
        ) from exc
    from blackreach.browser_playwright import (
        Hand, ProxyConfig, ProxyType, ProxyRotator,
    )
    _backend = "playwright"
    logger.info("Using Playwright browser backend")


def get_backend() -> str:
    """Return which backend is active: 'starsearch' or 'playwright'."""
    return _backend


# Re-export helpers from whichever backend is active
try:
    if _backend == "starsearch":
        from blackreach.extras.browser_starsearch import _is_ssrf_safe
    else:
        from blackreach.browser_playwright import _is_ssrf_safe
except ImportError:
    def _is_ssrf_safe(url: str) -> bool:
        return True

# _sanitize_filename is always from the Playwright backend (shared utility)
from blackreach.browser_playwright import _sanitize_filename, _reserve_unique_path


# Backwards compatibility
Browser = Hand

__all__ = [
    "Hand", "Browser", "ProxyConfig", "ProxyType", "ProxyRotator",
    "get_backend", "_is_ssrf_safe", "_sanitize_filename",
]
