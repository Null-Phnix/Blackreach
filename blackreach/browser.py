"""
Blackreach Browser Backend — Auto-selecting loader.

Tries StarSearch first (stealth daemon with behavioral humanization).
Falls back to Playwright if StarSearch is not installed or daemon isn't running.

No StarSearch code is shipped with Blackreach — it's an optional dependency.
"""
import logging

logger = logging.getLogger(__name__)

_backend = None

try:
    from starsearch import StarSearch as _StarSearchCheck
    # Verify daemon is actually running by creating a session and navigating
    _ss = _StarSearchCheck()
    _test_session = _ss.new_session(human_level=0)
    _test_session.evaluate("document.title")
    _test_session.close()
    _ss.close()
    del _ss, _test_session, _StarSearchCheck

    from blackreach.extras.browser_starsearch import (
        Hand, ProxyConfig, ProxyType, ProxyRotator,
        BrowserNotReadyError, ElementNotFoundError, DownloadError,
        InvalidActionArgsError, UnknownActionError,
    )
    _backend = "starsearch"
    logger.info("Using StarSearch browser backend (stealth daemon)")

except Exception:
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
