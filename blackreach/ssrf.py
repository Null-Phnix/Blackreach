"""SSRF checks for direct HTTP fetches.

The browser backends call this before urllib reads a URL. Hostnames such as
``0`` and IPv4-mapped loopback (``::ffff:127.0.0.1``) are not spelled like
localhost, but connecting to them still reaches this machine.
"""

import ipaddress
import socket
import urllib.parse
import urllib.request


_NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True unless ``ip`` is a globally routable unicast address.

    IPv4-mapped and NAT64 IPv6 addresses are classified by the embedded IPv4
    address.
    Older Pythons classify the ``::ffff:0:0/96`` block as a whole, which would
    wrongly block public addresses written in mapped form.
    """
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _ip_is_blocked(mapped)
    if ip.version == 6 and ip in _NAT64_WELL_KNOWN:
        # 64:ff9b::/96 counts as global, but a NAT64 gateway forwards it to
        # the IPv4 address in the low 32 bits, so judge that address instead.
        return _ip_is_blocked(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    # ``is_global`` is False for every special-purpose range, including the
    # ones ``is_private`` misses: CGNAT 100.64.0.0/10 (Tailscale assigns
    # tailnet addresses from it), benchmarking, documentation and NAT64.
    # Multicast is listed separately because some global multicast passes it.
    return not ip.is_global or ip.is_multicast


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
