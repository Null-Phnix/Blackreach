"""
TLS-scraping fallback for Blackreach — activated when StarSearch/Playwright gets blocked.
Uses curl_cffi to impersonate Chrome's TLS fingerprint, bypassing PerimeterX, Cloudflare, Akamai.

ponytail: NOT wired into the fallback chain yet, and `curl_cffi` is not installed.
Import-safe (guarded below); fetch() raises a clear error until the dep is added and a
caller is added in blackreach/browser.py. Wire-up + `pip install curl_cffi` is a Phase-2 item.
"""
import re
import logging

try:
    from curl_cffi import requests as cffi_requests
    _HAVE_CURL_CFFI = True
except ImportError:  # dep not installed — module stays importable but inert
    cffi_requests = None
    _HAVE_CURL_CFFI = False

logger = logging.getLogger(__name__)

IMPERSONATE = "chrome124"
BLOCK_MARKERS = [
    'just a moment', 'captcha', 'verify you', 'access denied',
    'blocked', 'are you a robot', 'attention required',
    'enable javascript', 'please turn javascript', 'security check',
    'ddos protection', 'checking your browser', 'press & hold',
]


def fetch(url: str, timeout: int = 15) -> dict:
    """
    Fetch a URL via TLS impersonation. Returns dict with html, title, status.
    Use this when StarSearch/Playwright returns blocked/challenge pages.
    """
    if not _HAVE_CURL_CFFI:
        raise RuntimeError("tls_fallback requires curl_cffi (not installed); see module docstring")
    try:
        r = cffi_requests.get(url, impersonate=IMPERSONATE, timeout=timeout)
        html = r.text
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        
        combined = (title + html[:2000]).lower()
        blocked = any(m in combined for m in BLOCK_MARKERS)
        
        return {
            "url": str(r.url),
            "status": r.status_code,
            "title": title,
            "html": html,
            "text": re.sub(r'<[^>]+>', ' ', html)[:5000],
            "blocked": blocked,
        }
    except Exception as e:
        logger.error(f"TLS fetch failed for {url}: {e}")
        return {"url": url, "status": 0, "title": "", "html": "", "text": "", "blocked": True, "error": str(e)}


def is_blocked(html_or_title: str) -> bool:
    """Check if a page response indicates a bot block."""
    return any(m in html_or_title.lower() for m in BLOCK_MARKERS)


# Make importable from Blackreach
__all__ = ["fetch", "is_blocked", "IMPERSONATE"]
