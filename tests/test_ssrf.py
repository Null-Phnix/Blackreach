"""SSRF guard regressions for direct HTTP fetches."""

import socket
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from blackreach.ssrf import _GuardedRedirectHandler, _is_ssrf_safe, urlopen_guarded


class _SecretHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"SECRET-LOCAL-DATA"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def _dual_stack_loopback_available() -> bool:
    """True when this host can connect to ``::ffff:127.0.0.1`` (needs IPv6)."""
    if not socket.has_ipv6:
        return False
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.settimeout(1)
            probe.connect(("::ffff:127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        listener.close()


needs_dual_stack = pytest.mark.skipif(
    not _dual_stack_loopback_available(),
    reason="host has no IPv6 support, so ::ffff:127.0.0.1 cannot be reached",
)


@pytest.fixture
def local_server():
    server = HTTPServer(("127.0.0.1", 0), _SecretHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()


class TestNonPublicAddresses:
    def test_decimal_zero_host_is_blocked(self):
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://0/secret")

    def test_unspecified_addresses_are_blocked(self):
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://0.0.0.0/secret")
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://[::]/secret")

    def test_ipv4_mapped_loopback_and_metadata_are_blocked(self):
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://[::ffff:127.0.0.1]/secret")
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://[::ffff:169.254.169.254]/latest/meta-data/")

    def test_ipv4_mapped_public_address_is_allowed(self):
        assert _is_ssrf_safe("http://[::ffff:8.8.8.8]/") is True

    def test_cgnat_and_tailscale_addresses_are_blocked(self):
        """``is_private`` is False for 100.64.0.0/10, which Tailscale uses."""
        for url in (
            "http://100.64.0.1/",
            "http://100.100.100.100/",  # Tailscale MagicDNS resolver
            "http://[::ffff:100.101.102.103]/",
            "http://[fd7a:115c:a1e0::1]/",  # Tailscale IPv6 range
        ):
            with pytest.raises(ValueError, match="SSRF"):
                _is_ssrf_safe(url)

    def test_hostname_resolving_to_tailnet_is_blocked(self, monkeypatch):
        def fake_getaddrinfo(host, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.88.1.2", 0))]

        monkeypatch.setattr("blackreach.ssrf.socket.getaddrinfo", fake_getaddrinfo)
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://scriptorium.example.ts.net/git/")

    def test_nat64_is_judged_by_embedded_ipv4(self):
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://[64:ff9b::7f00:1]/")
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://[64:ff9b::a9fe:a9fe]/")  # 169.254.169.254
        assert _is_ssrf_safe("http://[64:ff9b::808:808]/") is True  # 8.8.8.8

    def test_other_special_purpose_ranges_are_blocked(self):
        for url in (
            "http://198.18.0.1/",  # benchmarking
            "http://192.0.2.1/",  # documentation
            "http://224.0.0.1/",  # multicast
            "http://[ff0e::1]/",
        ):
            with pytest.raises(ValueError, match="SSRF"):
                _is_ssrf_safe(url)

    def test_public_and_unresolvable_hosts_stay_allowed(self, monkeypatch):
        def fake_getaddrinfo(host, *args, **kwargs):
            if host == "example.com":
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 0))]
            raise socket.gaierror(socket.EAI_NONAME, "not found")

        monkeypatch.setattr("blackreach.ssrf.socket.getaddrinfo", fake_getaddrinfo)
        assert _is_ssrf_safe("https://example.com/page") is True
        assert _is_ssrf_safe("https://nonexistent-host-12345.invalid/") is True

    @needs_dual_stack
    def test_guarded_open_cannot_read_loopback_via_bypass(self, local_server):
        port = local_server
        bypasses = [
            f"http://0:{port}/secret",
            f"http://[::ffff:127.0.0.1]:{port}/secret",
        ]
        for url in bypasses:
            with urllib.request.urlopen(url, timeout=3) as response:
                assert response.read() == b"SECRET-LOCAL-DATA"
            request = urllib.request.Request(url)
            with pytest.raises(ValueError, match="SSRF"):
                urlopen_guarded(request, timeout=3)


class TestRedirects:
    def test_redirect_to_loopback_bypass_is_blocked(self):
        handler = _GuardedRedirectHandler()
        request = urllib.request.Request("https://example.com/pixel.png")
        with pytest.raises(ValueError, match="SSRF"):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://[::ffff:127.0.0.1]/secret"
            )

    @pytest.mark.parametrize(
        "secret_host",
        [
            "127.0.0.1",
            pytest.param("[::ffff:127.0.0.1]", marks=needs_dual_stack),
        ],
    )
    def test_live_redirect_cannot_reach_loopback(self, monkeypatch, local_server, secret_host):
        """A public-looking URL that 302s to loopback must not be read."""
        secret_port = local_server

        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://{secret_host}:{secret_port}/secret")
                self.end_headers()

            def log_message(self, fmt, *args):
                return

        redirector = HTTPServer(("127.0.0.1", 0), Redirect)
        redirect_thread = threading.Thread(target=redirector.serve_forever, daemon=True)
        redirect_thread.start()
        redirect_port = redirector.server_address[1]
        start = f"http://127.0.0.1:{redirect_port}/pixel.png"
        try:
            with urllib.request.urlopen(start, timeout=3) as response:
                assert response.read() == b"SECRET-LOCAL-DATA"

            real_check = _is_ssrf_safe

            def allow_redirector_only(url: str) -> bool:
                if url == start:
                    return True
                return real_check(url)

            monkeypatch.setattr("blackreach.ssrf._is_ssrf_safe", allow_redirector_only)
            with pytest.raises(ValueError, match="SSRF"):
                urlopen_guarded(urllib.request.Request(start), timeout=3)
        finally:
            redirector.shutdown()

    def test_redirect_to_public_host_is_allowed(self, monkeypatch):
        monkeypatch.setattr(
            "blackreach.ssrf.socket.getaddrinfo",
            lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 0))],
        )
        handler = _GuardedRedirectHandler()
        request = urllib.request.Request("https://example.com/pixel.png")
        redirected = handler.redirect_request(
            request, None, 302, "Found", {}, "https://example.com/file.png"
        )
        assert redirected.full_url == "https://example.com/file.png"
