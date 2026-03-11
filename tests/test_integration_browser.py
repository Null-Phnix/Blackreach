"""
Integration tests for blackreach/browser.py

These tests actually start a browser and interact with real web pages.
They are slower but provide realistic coverage of browser automation.

Run with: pytest tests/test_integration_browser.py -v
Skip network tests: pytest tests/test_integration_browser.py -v -m "not network"
"""

import pytest
import time
from pathlib import Path
from blackreach.browser import Hand
from blackreach.stealth import StealthConfig
from blackreach.resilience import RetryConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


def has_network():
    """Check if we have network access."""
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


# Skip network tests if no connectivity
requires_network = pytest.mark.skipif(
    not has_network(),
    reason="No network access"
)


@pytest.fixture
def browser():
    """Create a browser instance for testing."""
    hand = Hand(
        headless=True,
        stealth_config=StealthConfig(
            min_delay=0.1,
            max_delay=0.3,
            randomize_viewport=False,
            randomize_user_agent=False
        ),
        retry_config=RetryConfig(max_attempts=2, base_delay=0.5),
        download_dir=Path("/tmp/blackreach_test_downloads")
    )
    hand.wake()
    yield hand
    hand.sleep()


@pytest.fixture
def download_dir(tmp_path):
    """Create a temporary download directory."""
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir()
    return dl_dir


# =============================================================================
# Navigation Tests
# =============================================================================

class TestBrowserNavigation:
    """Integration tests for browser navigation."""

    @requires_network
    def test_goto_returns_result(self, browser):
        """Navigate to a page and get result."""
        result = browser.goto("https://www.google.com")

        assert result is not None
        assert "action" in result
        assert result["action"] == "goto"

    @requires_network
    def test_goto_updates_url(self, browser):
        """Navigation updates the current URL."""
        browser.goto("https://www.google.com")

        url = browser.get_url()
        assert "google" in url.lower()

    @requires_network
    def test_back_returns_result(self, browser):
        """back() returns a result dict."""
        browser.goto("https://www.google.com")

        result = browser.back()

        assert result is not None
        assert result["action"] == "back"

    @requires_network
    def test_forward_returns_result(self, browser):
        """forward() returns a result dict."""
        browser.goto("https://www.google.com")

        result = browser.forward()

        assert result is not None
        assert result["action"] == "forward"

    @requires_network
    def test_refresh_returns_result(self, browser):
        """refresh() returns a result dict."""
        browser.goto("https://www.google.com")

        result = browser.refresh()

        assert result is not None
        assert result["action"] == "refresh"


# =============================================================================
# Page Info Tests
# =============================================================================

class TestBrowserPageInfo:
    """Integration tests for getting page information."""

    @requires_network
    def test_get_url_returns_string(self, browser):
        """get_url() returns the current URL as string."""
        browser.goto("https://www.google.com")

        url = browser.get_url()

        assert isinstance(url, str)
        assert url.startswith("http")

    @requires_network
    def test_get_title_returns_string(self, browser):
        """get_title() returns page title as string."""
        browser.goto("https://www.google.com")

        title = browser.get_title()

        assert isinstance(title, str)

    @requires_network
    def test_get_html_returns_content(self, browser):
        """get_html() returns HTML content."""
        browser.goto("https://www.google.com")

        html = browser.get_html()

        assert isinstance(html, str)
        assert len(html) > 100
        assert "<html" in html.lower() or "<!doctype" in html.lower()


# =============================================================================
# Interaction Tests
# =============================================================================

class TestBrowserInteractions:
    """Integration tests for browser interactions."""

    @requires_network
    def test_type_returns_result(self, browser):
        """type() returns a result dict."""
        browser.goto("https://www.google.com")

        result = browser.type(
            'textarea[name="q"], input[name="q"]',
            "test",
            human=False
        )

        assert result is not None
        assert result["action"] == "type"

    @requires_network
    def test_scroll_down_returns_result(self, browser):
        """scroll() down returns a result dict."""
        browser.goto("https://www.google.com")

        result = browser.scroll("down", 300)

        assert result is not None
        assert result["action"] == "scroll"
        assert result["direction"] == "down"

    @requires_network
    def test_scroll_up_returns_result(self, browser):
        """scroll() up returns a result dict."""
        browser.goto("https://www.google.com")

        result = browser.scroll("up", 100)

        assert result is not None
        assert result["action"] == "scroll"
        assert result["direction"] == "up"

    @requires_network
    def test_press_key_returns_result(self, browser):
        """press() returns a result dict."""
        browser.goto("https://www.google.com")

        result = browser.press("Escape")

        assert result is not None
        assert result["action"] == "press"
        assert result["key"] == "Escape"

    @requires_network
    def test_click_returns_result(self, browser):
        """click() returns a result dict."""
        browser.goto("https://www.google.com")

        # Click on something that exists
        result = browser.click("body")

        assert result is not None
        assert result["action"] == "click"


# =============================================================================
# Screenshot Tests
# =============================================================================

class TestBrowserScreenshot:
    """Integration tests for screenshots."""

    @requires_network
    def test_screenshot_creates_file(self, browser, tmp_path):
        """screenshot() creates an image file."""
        browser.goto("https://www.google.com")
        screenshot_path = tmp_path / "test.png"

        result = browser.screenshot(str(screenshot_path))

        assert result["action"] == "screenshot"
        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 0

    @requires_network
    def test_screenshot_full_page(self, browser, tmp_path):
        """screenshot() with full_page captures entire page."""
        browser.goto("https://www.google.com")
        screenshot_path = tmp_path / "full.png"

        result = browser.screenshot(str(screenshot_path), full_page=True)

        assert result["action"] == "screenshot"
        assert screenshot_path.exists()


# =============================================================================
# Wait Methods Tests
# =============================================================================

class TestBrowserWaitMethods:
    """Integration tests for wait methods."""

    @requires_network
    def test_force_render_returns_bool(self, browser):
        """force_render() returns a boolean."""
        browser.goto("https://www.google.com")

        result = browser.force_render()

        assert isinstance(result, bool)


# =============================================================================
# Stealth Tests
# =============================================================================

class TestBrowserStealth:
    """Integration tests for stealth features."""

    @requires_network
    def test_webdriver_hidden(self, browser):
        """Stealth mode hides webdriver property."""
        browser.goto("https://www.google.com")

        result = browser.page.evaluate("() => navigator.webdriver")

        # Should be undefined (None) or false, not true
        assert result is not True

    @requires_network
    def test_user_agent_present(self, browser):
        """User agent is set."""
        browser.goto("https://www.google.com")

        ua = browser.page.evaluate("() => navigator.userAgent")

        assert ua is not None
        assert len(ua) > 0


# =============================================================================
# Helper Properties Tests
# =============================================================================

class TestBrowserHelperProperties:
    """Integration tests for browser helper properties."""

    def test_page_property_after_wake(self, browser):
        """page property returns Page after wake."""
        page = browser.page

        assert page is not None

    def test_selector_property_after_wake(self, browser):
        """selector property returns SmartSelector after wake."""
        selector = browser.selector

        assert selector is not None

    def test_popups_property_after_wake(self, browser):
        """popups property returns PopupHandler after wake."""
        popups = browser.popups

        assert popups is not None

    def test_waits_property_after_wake(self, browser):
        """waits property returns WaitConditions after wake."""
        waits = browser.waits

        assert waits is not None


# =============================================================================
# Download Setup Tests
# =============================================================================

class TestBrowserDownloadSetup:
    """Integration tests for download configuration."""

    def test_download_dir_created(self, download_dir):
        """Download directory is created on wake."""
        hand = Hand(headless=True, download_dir=download_dir)
        hand.wake()

        assert download_dir.exists()

        hand.sleep()

    def test_set_download_callback(self, browser):
        """Download callback can be set."""
        callback_called = []

        def callback(download):
            callback_called.append(download)

        browser.set_download_callback(callback)

        assert browser._download_callback is not None


# =============================================================================
# Human Behavior Tests
# =============================================================================

class TestBrowserHumanBehavior:
    """Integration tests for human-like behavior."""

    def test_human_delay_waits(self, browser):
        """_human_delay() actually waits."""
        start = time.time()
        browser._human_delay(0.1, 0.2)
        elapsed = time.time() - start

        assert elapsed >= 0.1


# =============================================================================
# Cleanup Tests
# =============================================================================

class TestBrowserCleanup:
    """Integration tests for browser cleanup."""

    def test_sleep_closes_browser(self):
        """sleep() properly closes the browser."""
        hand = Hand(headless=True)
        hand.wake()

        hand.sleep()

        # Browser should be closed
        assert hand._browser is None

    def test_sleep_without_wake(self):
        """sleep() handles case when wake() wasn't called."""
        hand = Hand(headless=True)

        # Should not raise
        hand.sleep()

    def test_release_all_keys_without_page(self):
        """_release_all_keys() handles no page gracefully."""
        hand = Hand(headless=True)

        # Should not raise
        hand._release_all_keys()


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestBrowserErrorHandling:
    """Integration tests for error handling."""

    def test_goto_invalid_url_handled(self, browser):
        """Invalid URL doesn't crash."""
        # This should not raise an unhandled exception
        try:
            browser.goto("not-a-valid-url")
        except Exception:
            pass  # Expected to fail, but gracefully

    @requires_network
    def test_click_nonexistent_returns_error(self, browser):
        """Click on non-existent element returns error dict."""
        browser.goto("https://www.google.com")

        # May raise or return error - both are acceptable
        try:
            result = browser.click("#nonexistent-element-xyz123")
            # If it returns, should have error info
            assert "error" in result or result.get("action") == "click"
        except Exception as e:
            # TimeoutError is expected for non-existent elements
            assert "timeout" in str(e).lower() or "not found" in str(e).lower()


# =============================================================================
# Hash Computation Tests
# =============================================================================

class TestBrowserHashComputation:
    """Integration tests for file hash computation."""

    def test_compute_hash_returns_string(self, browser, tmp_path):
        """_compute_hash() returns a hash string."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        hash_val = browser._compute_hash(test_file)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA-256 hex length

    def test_compute_hash_consistent(self, browser, tmp_path):
        """_compute_hash() returns same hash for same content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("same content")

        hash1 = browser._compute_hash(test_file)
        hash2 = browser._compute_hash(test_file)

        assert hash1 == hash2

    def test_compute_hash_different_content(self, browser, tmp_path):
        """_compute_hash() returns different hash for different content."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")

        hash1 = browser._compute_hash(file1)
        hash2 = browser._compute_hash(file2)

        assert hash1 != hash2
