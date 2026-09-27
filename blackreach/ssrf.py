"""SSRF checks for direct HTTP fetches.

The browser backends call this before urllib reads a URL. Hostnames such as
``0`` and IPv4-mapped loopback (``::ffff:127.0.0.1``) are not spelled like
localhost, but connecting to them still reaches this machine.
"""

import ipaddress
import socket
import urllib.parse
import urllib.request


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True when connecting to ``ip`` can reach a non-public network.

    IPv4-mapped IPv6 addresses are classified by the embedded IPv4 address.
    ``is_reserved`` is true for every mapped address, including public ones,
    so it must not be applied to the IPv6 form itself.
    """
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _ip_is_blocked(mapped)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


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
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            raise ValueError("URL has no hostname")

        # Block localhost variants before DNS so the message stays stable.
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise ValueError("SSRF blocked: localhost access not allowed")

        try:
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            # Can't resolve — allow; the request itself will fail.
            return True

        for _family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if _ip_is_blocked(ip):
                raise ValueError(f"SSRF blocked: {hostname} resolves to non-public IP {ip}")

        return True

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"SSRF validation failed: {exc}") from exc


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-check each redirect target. urllib follows redirects by default."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        _is_ssrf_safe(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def urlopen_guarded(request: urllib.request.Request, timeout: float):
    """Open ``request`` after checking the URL and every redirect hop."""
    _is_ssrf_safe(request.full_url)
    opener = urllib.request.build_opener(_GuardedRedirectHandler)
    return opener.open(request, timeout=timeout)
