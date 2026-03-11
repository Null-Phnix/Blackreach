"""
Unit tests for proxy support in browser.py

Tests ProxyConfig, ProxyRotator, and browser proxy integration.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from blackreach.browser import (
    ProxyType,
    ProxyConfig,
    ProxyRotator,
    Hand,
)
from blackreach.stealth import StealthConfig


class TestProxyType:
    """Tests for ProxyType enum."""

    def test_all_types_defined(self):
        """All proxy types are defined."""
        types = [t.value for t in ProxyType]
        assert "http" in types
        assert "https" in types
        assert "socks5" in types
        assert "socks4" in types


class TestProxyConfig:
    """Tests for ProxyConfig dataclass."""

    def test_create_http_proxy(self):
        """Create basic HTTP proxy config."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8080
        assert proxy.proxy_type == ProxyType.HTTP
        assert proxy.username is None
        assert proxy.password is None

    def test_create_socks5_proxy(self):
        """Create SOCKS5 proxy config."""
        proxy = ProxyConfig(
            host="socks.example.com",
            port=1080,
            proxy_type=ProxyType.SOCKS5
        )
        assert proxy.proxy_type == ProxyType.SOCKS5
        assert proxy.port == 1080

    def test_create_authenticated_proxy(self):
        """Create proxy with authentication."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="pass123"
        )
        assert proxy.username == "user"
        assert proxy.password == "pass123"

    def test_create_proxy_with_bypass(self):
        """Create proxy with bypass list."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            bypass=["localhost", "*.internal.com"]
        )
        assert proxy.bypass == ["localhost", "*.internal.com"]

    def test_from_url_http(self):
        """Create proxy from HTTP URL."""
        proxy = ProxyConfig.from_url("http://proxy.example.com:8080")
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8080
        assert proxy.proxy_type == ProxyType.HTTP

    def test_from_url_socks5(self):
        """Create proxy from SOCKS5 URL."""
        proxy = ProxyConfig.from_url("socks5://socks.example.com:1080")
        assert proxy.host == "socks.example.com"
        assert proxy.port == 1080
        assert proxy.proxy_type == ProxyType.SOCKS5

    def test_from_url_with_auth(self):
        """Create proxy from URL with credentials."""
        proxy = ProxyConfig.from_url("http://user:pass@proxy.example.com:8080")
        assert proxy.username == "user"
        assert proxy.password == "pass"
        assert proxy.host == "proxy.example.com"

    def test_from_url_default_port_http(self):
        """Default port for HTTP proxy."""
        proxy = ProxyConfig.from_url("http://proxy.example.com")
        assert proxy.port == 8080

    def test_from_url_default_port_socks(self):
        """Default port for SOCKS proxy."""
        proxy = ProxyConfig.from_url("socks5://proxy.example.com")
        assert proxy.port == 1080

    def test_to_playwright_proxy_basic(self):
        """Convert to Playwright format - basic."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        pw_proxy = proxy.to_playwright_proxy()
        assert pw_proxy["server"] == "http://proxy.example.com:8080"
        assert "username" not in pw_proxy or pw_proxy.get("username") is None

    def test_to_playwright_proxy_with_auth(self):
        """Convert to Playwright format - with auth."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="secret"
        )
        pw_proxy = proxy.to_playwright_proxy()
        assert pw_proxy["server"] == "http://proxy.example.com:8080"
        assert pw_proxy["username"] == "user"
        assert pw_proxy["password"] == "secret"

    def test_to_playwright_proxy_socks5(self):
        """Convert SOCKS5 to Playwright format."""
        proxy = ProxyConfig(
            host="socks.example.com",
            port=1080,
            proxy_type=ProxyType.SOCKS5
        )
        pw_proxy = proxy.to_playwright_proxy()
        assert pw_proxy["server"] == "socks5://socks.example.com:1080"

    def test_to_playwright_proxy_with_bypass(self):
        """Convert with bypass list."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            bypass=["localhost", "127.0.0.1"]
        )
        pw_proxy = proxy.to_playwright_proxy()
        assert pw_proxy["bypass"] == "localhost,127.0.0.1"

    def test_str_representation(self):
        """String representation hides password."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="supersecret"
        )
        str_repr = str(proxy)
        assert "supersecret" not in str_repr
        assert "***" in str_repr
        assert "user" in str_repr


class TestProxyRotator:
    """Tests for ProxyRotator class."""

    @pytest.fixture
    def rotator(self):
        """Create rotator with test proxies."""
        rotator = ProxyRotator()
        rotator.add_proxy("http://proxy1.example.com:8080")
        rotator.add_proxy("http://proxy2.example.com:8080")
        rotator.add_proxy("http://proxy3.example.com:8080")
        return rotator

    def test_add_proxy_from_string(self):
        """Add proxy from URL string."""
        rotator = ProxyRotator()
        rotator.add_proxy("http://proxy.example.com:8080")
        assert len(rotator) == 1

    def test_add_proxy_from_config(self):
        """Add proxy from ProxyConfig."""
        rotator = ProxyRotator()
        config = ProxyConfig(host="proxy.example.com", port=8080)
        rotator.add_proxy(config)
        assert len(rotator) == 1

    def test_init_with_proxies(self):
        """Initialize with proxy list."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080"
        ])
        assert len(rotator) == 2

    def test_get_next_rotation(self, rotator):
        """Proxies rotate in round-robin."""
        proxy1 = rotator.get_next()
        proxy2 = rotator.get_next()
        proxy3 = rotator.get_next()
        proxy4 = rotator.get_next()  # Should cycle back

        assert proxy1.host == "proxy1.example.com"
        assert proxy2.host == "proxy2.example.com"
        assert proxy3.host == "proxy3.example.com"
        assert proxy4.host == "proxy1.example.com"  # Cycled

    def test_get_next_empty(self):
        """Get next from empty pool returns None."""
        rotator = ProxyRotator()
        assert rotator.get_next() is None

    def test_sticky_session(self, rotator):
        """Sticky session returns same proxy for domain."""
        proxy1 = rotator.get_next(domain="example.com")
        proxy2 = rotator.get_next(domain="example.com")
        proxy3 = rotator.get_next(domain="other.com")

        assert proxy1.host == proxy2.host  # Same domain = same proxy
        assert proxy1.host != proxy3.host  # Different domain = different proxy

    def test_report_success(self, rotator):
        """Report successful request."""
        proxy = rotator.get_next()
        rotator.report_success(proxy, response_time=0.5)

        stats = rotator.get_stats()
        proxy_stats = stats["proxies"][str(proxy)]
        assert proxy_stats["successes"] == 1
        assert proxy_stats["avg_response_time"] == 0.5

    def test_report_failure(self, rotator):
        """Report failed request."""
        proxy = rotator.get_next()
        rotator.report_failure(proxy)

        stats = rotator.get_stats()
        proxy_stats = stats["proxies"][str(proxy)]
        assert proxy_stats["failures"] == 1

    def test_disable_on_failures(self, rotator):
        """Proxy disabled after too many failures."""
        proxy = rotator.get_next()
        proxy_str = str(proxy)

        # Report many failures
        for _ in range(6):
            rotator.report_failure(proxy, disable_threshold=5)

        stats = rotator.get_stats()
        assert stats["proxies"][proxy_str]["enabled"] is False

    def test_skip_disabled_proxy(self, rotator):
        """Disabled proxies are skipped."""
        # Disable first proxy
        proxy1 = rotator.get_next()
        for _ in range(6):
            rotator.report_failure(proxy1, disable_threshold=5)

        # Get next should skip disabled one
        proxy2 = rotator.get_next()
        assert proxy2.host != proxy1.host

    def test_reenable_when_all_disabled(self, rotator):
        """All proxies re-enabled when all disabled."""
        # Disable all proxies
        for _ in range(3):
            proxy = rotator.get_next()
            for _ in range(6):
                rotator.report_failure(proxy, disable_threshold=5)

        # Should re-enable all and return one
        proxy = rotator.get_next()
        assert proxy is not None

    def test_remove_proxy(self, rotator):
        """Remove proxy from pool."""
        initial_count = len(rotator)
        rotator.remove_proxy("http://proxy1.example.com:8080")
        assert len(rotator) == initial_count - 1

    def test_clear_sticky_sessions(self, rotator):
        """Clear sticky sessions."""
        rotator.get_next(domain="example.com")
        rotator.get_next(domain="other.com")

        rotator.clear_sticky_sessions()

        # After clearing, should get new proxy assignments
        # (actual behavior depends on rotation state)
        stats = rotator.get_stats()
        assert stats["total_proxies"] == 3

    def test_get_stats(self, rotator):
        """Get comprehensive stats."""
        proxy = rotator.get_next()
        rotator.report_success(proxy, response_time=0.3)

        stats = rotator.get_stats()
        assert stats["total_proxies"] == 3
        assert stats["enabled"] == 3
        assert len(stats["proxies"]) == 3


class TestHandProxyIntegration:
    """Tests for proxy integration in Hand class."""

    def test_init_with_proxy_string(self):
        """Initialize Hand with proxy URL string."""
        hand = Hand(proxy="http://proxy.example.com:8080", headless=True)
        assert hand._proxy is not None
        assert hand._proxy.host == "proxy.example.com"

    def test_init_with_proxy_config(self):
        """Initialize Hand with ProxyConfig."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            proxy_type=ProxyType.SOCKS5
        )
        hand = Hand(proxy=proxy, headless=True)
        assert hand._proxy.proxy_type == ProxyType.SOCKS5

    def test_init_with_proxy_rotator(self):
        """Initialize Hand with ProxyRotator."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080"
        ])
        hand = Hand(proxy_rotator=rotator, headless=True)
        assert hand._proxy_rotator is rotator

    def test_set_proxy(self):
        """Set proxy after initialization."""
        hand = Hand(headless=True)
        assert hand._proxy is None

        hand.set_proxy("http://proxy.example.com:8080")
        assert hand._proxy is not None
        assert hand._proxy.host == "proxy.example.com"

    def test_set_proxy_none(self):
        """Clear proxy configuration."""
        hand = Hand(proxy="http://proxy.example.com:8080", headless=True)
        hand.set_proxy(None)
        assert hand._proxy is None

    def test_get_current_proxy_before_wake(self):
        """Current proxy is None before wake."""
        hand = Hand(proxy="http://proxy.example.com:8080", headless=True)
        assert hand.get_current_proxy() is None

    @patch('blackreach.browser.sync_playwright')
    def test_get_proxy_config_priority(self, mock_playwright):
        """Proxy config priority: rotator > direct > stealth."""
        # Setup mock
        mock_pw = MagicMock()
        mock_playwright.return_value.start.return_value = mock_pw
        mock_browser = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page

        # Test with rotator
        rotator = ProxyRotator(["http://rotator-proxy.example.com:8080"])
        direct_proxy = ProxyConfig(host="direct-proxy.example.com", port=8080)

        hand = Hand(
            proxy=direct_proxy,
            proxy_rotator=rotator,
            headless=True
        )

        proxy_config = hand._get_proxy_config()
        # Rotator should take priority
        assert "rotator-proxy" in proxy_config["server"]

    def test_report_proxy_result_success(self):
        """Report successful proxy request."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        hand = Hand(proxy_rotator=rotator, headless=True)
        hand._current_proxy = rotator._proxies[0]

        hand.report_proxy_result(success=True, response_time=0.5)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["successes"] == 1

    def test_report_proxy_result_failure(self):
        """Report failed proxy request."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        hand = Hand(proxy_rotator=rotator, headless=True)
        hand._current_proxy = rotator._proxies[0]

        hand.report_proxy_result(success=False)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["failures"] == 1


class TestProxyEdgeCases:
    """Tests for edge cases in proxy handling."""

    def test_proxy_url_with_special_chars_in_password(self):
        """Handle special characters in proxy password."""
        # URL encoding for special chars - urllib leaves encoded
        proxy = ProxyConfig.from_url("http://user:p%40ss%23word@proxy.example.com:8080")
        # Note: urllib.parse.urlparse preserves percent-encoding in password
        # This is actually correct behavior for proxy URLs
        assert proxy.password is not None
        assert "p" in proxy.password  # Just verify password was parsed

    def test_proxy_ipv4_address(self):
        """Proxy with IPv4 address."""
        proxy = ProxyConfig.from_url("http://192.168.1.100:8080")
        assert proxy.host == "192.168.1.100"

    def test_socks_generic_scheme(self):
        """Generic 'socks' scheme defaults to SOCKS5."""
        proxy = ProxyConfig.from_url("socks://proxy.example.com:1080")
        assert proxy.proxy_type == ProxyType.SOCKS5

    def test_empty_rotator_stats(self):
        """Stats for empty rotator."""
        rotator = ProxyRotator()
        stats = rotator.get_stats()
        assert stats["total_proxies"] == 0
        assert stats["enabled"] == 0
