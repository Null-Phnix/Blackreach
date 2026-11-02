"""Hostname matching that respects label boundaries.

Plain substring checks such as ``"google.com" in url`` are wrong in both
directions: they match ``notgoogle.com`` and ``evil.io/?ref=google.com``.
These helpers compare against the parsed hostname instead.

Pattern forms:

* ``"github.com"`` (contains a dot): the host is that domain or a subdomain
  of it (``github.com``, ``api.github.com``), never ``notgithub.com`` or
  ``github.com.evil.io``.
* ``"libgen"`` (no dot): the host has a label equal to it. This is for sites
  that hop between TLDs (``libgen.is``, ``libgen.rs``, ``annas-archive.org``).
"""

from __future__ import annotations

from typing import Iterable, Optional
from urllib.parse import urlparse


def hostname_of(url_or_host: str) -> str:
    """Return the lowercase hostname of a URL, or of a bare host[:port]."""
    if not url_or_host:
        return ""
    value = url_or_host.strip()
    if "://" not in value:
        value = "//" + value
    try:
        host = urlparse(value).hostname or ""
    except ValueError:
        return ""
    return host.rstrip(".").lower()


def host_matches(url_or_host: str, pattern: str) -> bool:
    """True if the URL's host matches ``pattern`` (see module docstring)."""
    host = hostname_of(url_or_host)
    pattern = pattern.strip().lower().rstrip(".")
    if not host or not pattern:
        return False
    if "." in pattern:
        return host == pattern or host.endswith("." + pattern)
    return pattern in host.split(".")


def best_host_match(url_or_host: str, patterns: Iterable[str]) -> Optional[str]:
    """Return the most specific (longest) pattern that matches, or None."""
    matches = [p for p in patterns if host_matches(url_or_host, p)]
    return max(matches, key=len) if matches else None
