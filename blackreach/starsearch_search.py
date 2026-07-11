"""
Keyless web search via the StarSearch anti-detect browser daemon -> Bing.

No API keys, no paid services. StarSearch drives a real Chromium with
anti-detection, so it gets clean Bing SERPs where plain-HTTP scrapers get
CAPTCHA'd (DDG hard-blocks this box's IP; Bing does not).

Talks the daemon's Unix-socket JSON-lines protocol directly (stdlib only) so
this has no dependency on the StarSearch Python client. Returns [] on any
failure so callers can fall back to another backend.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import socket
import time
import urllib.parse
from pathlib import Path
from typing import List, Dict

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_SOCK_POINTER = Path.home() / ".starsearch" / "daemon.sock_path"
_PROTOCOL = "1.0"


def _socket_path() -> str | None:
    env = os.environ.get("STARSEARCH_SOCKET")
    if env:
        return env
    try:
        p = _SOCK_POINTER.read_text().strip()
    except OSError:
        return None
    return p if p and Path(p).exists() else None


class _Daemon:
    """Minimal client for one request/response session over the Unix socket."""

    def __init__(self, timeout: float = 90.0):
        path = _socket_path()
        if not path:
            raise ConnectionError("StarSearch daemon socket not found (daemon not running?)")
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.settimeout(timeout)
        self.s.connect(path)
        self.f = self.s.makefile("rwb")
        h = self._send({"starsearch": _PROTOCOL, "client_version": "blackreach"})
        if not h.get("compatible", False):
            raise ConnectionError(f"StarSearch handshake incompatible: {h}")

    def _send(self, obj: dict) -> dict:
        self.f.write((json.dumps(obj) + "\n").encode())
        self.f.flush()
        return json.loads(self.f.readline().decode())

    def get_html(self, url: str, human_level: int = 1, timeout_s: int = 45) -> str:
        r = self._send({"v": 1, "cmd": "new_session", "sid": None,
                        "opts": {"human_level": human_level}})
        sid = r.get("sid")
        if not r.get("ok") or not sid:
            raise RuntimeError(f"new_session failed: {r.get('error')}")
        try:
            self._send({"v": 1, "cmd": "navigate", "sid": sid, "url": url, "timeout_s": timeout_s})
            gc = self._send({"v": 1, "cmd": "get_content", "sid": sid})
            c = gc.get("result") or gc.get("content") or ""
            return c if isinstance(c, str) else (c.get("html") or c.get("text") or "")
        finally:
            self._send({"v": 1, "cmd": "close_session", "sid": sid})

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def _decode_bing_url(href: str) -> str:
    """Bing wraps results in /ck/a redirects with the target base64 in u=a1<b64>."""
    if "bing.com/ck/a" not in href:
        return href
    u = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("u", [""])[0]
    if u.startswith("a1"):
        b = u[2:] + "=" * (-len(u[2:]) % 4)
        try:
            return base64.urlsafe_b64decode(b).decode("utf-8", "ignore")
        except Exception:
            return href
    return href


def _parse_bing(html: str, limit: int) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, str]] = []
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        cap = li.select_one(".b_caption p") or li.select_one("p")
        out.append({
            "title": a.get_text(" ", strip=True),
            "url": _decode_bing_url(a["href"]),
            "description": cap.get_text(" ", strip=True) if cap else "",
        })
        if len(out) >= limit:
            break
    return out


def search(query: str, limit: int = 10, retries: int = 3) -> List[Dict[str, str]]:
    """Search Bing via StarSearch. Returns [{title,url,description}], or [] on failure.

    Retries transient failures (CapacityExceeded under load, a crashed session,
    a dropped connection) with backoff before giving up so the caller falls back.
    """
    url = "https://www.bing.com/search?q=" + urllib.parse.quote_plus(query)
    for attempt in range(retries):
        d = None
        try:
            d = _Daemon()
            return _parse_bing(d.get_html(url), limit)
        except Exception as e:
            if attempt == retries - 1:
                logger.warning("StarSearch->Bing search failed (%s): %s", type(e).__name__, e)
                return []
            time.sleep(0.4 * (attempt + 1))
        finally:
            if d:
                d.close()
    return []


def demo() -> None:
    """Self-check: requires the StarSearch daemon running. Proves a keyless search."""
    res = search("python programming language", limit=5)
    for i, r in enumerate(res, 1):
        print(f"{i}. {r['title'][:70]}\n   {r['url'][:90]}")
    assert len(res) >= 3, "expected >=3 results from StarSearch->Bing"
    assert all(r["url"].startswith("http") and "bing.com/ck" not in r["url"] for r in res), \
        "URLs should be decoded (not Bing redirects)"
    print(f"\nPASS: {len(res)} keyless results via StarSearch->Bing")


if __name__ == "__main__":
    demo()
