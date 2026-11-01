"""SSRF guard regressions for direct HTTP fetches."""

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

    def test_public_and_unresolvable_hosts_stay_allowed(self):
        assert _is_ssrf_safe("https://example.com/page") is True
        assert _is_ssrf_safe("https://nonexistent-host-12345.invalid/") is True

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

    def test_live_redirect_cannot_reach_loopback(self, monkeypatch, local_server):
        """A public-looking URL that 302s to an allowed-bypass address must not be read."""
        secret_port = local_server

        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://[::ffff:127.0.0.1]:{secret_port}/secret")
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

    def test_redirect_to_public_host_is_allowed(self):
        handler = _GuardedRedirectHandler()
        request = urllib.request.Request("https://example.com/pixel.png")
        redirected = handler.redirect_request(
            request, None, 302, "Found", {}, "https://example.com/file.png"
        )
        assert redirected.full_url == "https://example.com/file.png"
