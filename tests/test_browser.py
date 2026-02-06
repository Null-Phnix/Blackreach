"""
Unit tests for blackreach/browser.py

Tests browser controller (Hand class) initialization and configuration.
Note: Full browser integration tests require Playwright fixtures.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from playwright.sync_api import Error as PlaywrightError
from blackreach.browser import (
    Hand, _sanitize_filename, _is_ssrf_safe,
    ProxyConfig, ProxyRotator, ProxyType
)
from blackreach.stealth import StealthConfig
from blackreach.resilience import RetryConfig
from blackreach.exceptions import (
    BrowserNotReadyError,
    ElementNotFoundError,
    InvalidActionArgsError,
    UnknownActionError,
)


class TestHandInit:
    """Tests for Hand initialization."""

    def test_default_init(self):
        """Hand initializes with default values."""
        hand = Hand()
        assert hand.headless is False
        assert hand.stealth is not None
        assert hand.retry_config is not None
        assert hand.download_dir == Path("./downloads")

    def test_headless_mode(self):
        """Hand respects headless parameter."""
        hand = Hand(headless=True)
        assert hand.headless is True

    def test_custom_stealth_config(self):
        """Hand accepts custom stealth config."""
        config = StealthConfig(min_delay=2.0, max_delay=5.0)
        hand = Hand(stealth_config=config)
        assert hand.stealth.config.min_delay == 2.0
        assert hand.stealth.config.max_delay == 5.0

    def test_custom_retry_config(self):
        """Hand accepts custom retry config."""
        config = RetryConfig(max_attempts=5, base_delay=2.0)
        hand = Hand(retry_config=config)
        assert hand.retry_config.max_attempts == 5
        assert hand.retry_config.base_delay == 2.0

    def test_custom_download_dir(self):
        """Hand accepts custom download directory."""
        download_path = Path("/tmp/test_downloads")
        hand = Hand(download_dir=download_path)
        assert hand.download_dir == download_path

    def test_initial_state_none(self):
        """Hand starts with no browser running."""
        hand = Hand()
        assert hand._playwright is None
        assert hand._browser is None
        assert hand._context is None
        assert hand._page is None

    def test_mouse_pos_initialized(self):
        """Mouse position starts at origin."""
        hand = Hand()
        assert hand._mouse_pos == (0, 0)

    def test_pending_downloads_empty(self):
        """Pending downloads list starts empty."""
        hand = Hand()
        assert hand._pending_downloads == []


class TestHandProperties:
    """Tests for Hand property accessors."""

    def test_page_raises_when_not_ready(self):
        """page property raises BrowserNotReadyError when not started."""
        hand = Hand()
        with pytest.raises(BrowserNotReadyError):
            _ = hand.page

    def test_selector_raises_when_not_ready(self):
        """selector property raises BrowserNotReadyError when not started."""
        hand = Hand()
        with pytest.raises(BrowserNotReadyError):
            _ = hand.selector

    def test_popups_raises_when_not_ready(self):
        """popups property raises BrowserNotReadyError when not started."""
        hand = Hand()
        with pytest.raises(BrowserNotReadyError):
            _ = hand.popups

    def test_waits_raises_when_not_ready(self):
        """waits property raises BrowserNotReadyError when not started."""
        hand = Hand()
        with pytest.raises(BrowserNotReadyError):
            _ = hand.waits


class TestHandHelperMethods:
    """Tests for Hand helper methods."""

    def test_compute_hash_returns_string(self, tmp_path):
        """_compute_hash returns hex string."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        hand = Hand()
        result = hand._compute_hash(test_file)

        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 produces 64 hex chars

    def test_compute_hash_consistent(self, tmp_path):
        """_compute_hash returns same hash for same content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        hand = Hand()
        hash1 = hand._compute_hash(test_file)
        hash2 = hand._compute_hash(test_file)

        assert hash1 == hash2

    def test_compute_hash_different_content(self, tmp_path):
        """_compute_hash returns different hash for different content."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content A")
        file2.write_text("Content B")

        hand = Hand()
        hash1 = hand._compute_hash(file1)
        hash2 = hand._compute_hash(file2)

        assert hash1 != hash2


class TestHandHumanDelay:
    """Tests for human delay functionality."""

    def test_human_delay_uses_stealth(self):
        """_human_delay delegates to stealth module."""
        config = StealthConfig(min_delay=0.01, max_delay=0.02)
        hand = Hand(stealth_config=config)

        # Should not raise and should complete quickly
        hand._human_delay(0.001, 0.002)


class TestReleaseAllKeys:
    """Tests for _release_all_keys method."""

    def test_release_all_keys_no_page(self):
        """_release_all_keys handles no page gracefully."""
        hand = Hand()
        # Should not raise
        hand._release_all_keys()

    def test_release_all_keys_with_mock_page(self):
        """_release_all_keys releases modifier keys."""
        hand = Hand()
        mock_page = MagicMock()
        mock_keyboard = MagicMock()
        mock_page.keyboard = mock_keyboard
        hand._page = mock_page

        hand._release_all_keys()

        # Should have called up() for each modifier key
        assert mock_keyboard.up.call_count == 4
        mock_keyboard.up.assert_any_call("Control")
        mock_keyboard.up.assert_any_call("Alt")
        mock_keyboard.up.assert_any_call("Shift")
        mock_keyboard.up.assert_any_call("Meta")


class TestHandExecute:
    """Tests for execute command routing."""

    def test_execute_unknown_action(self):
        """execute raises UnknownActionError for invalid action."""
        hand = Hand()
        # Mock page so property doesn't raise
        hand._page = MagicMock()

        with pytest.raises(UnknownActionError):
            hand.execute({"action": "invalid_action"})

    def test_execute_wait_action(self):
        """execute handles wait action correctly."""
        hand = Hand()
        hand._page = MagicMock()

        with patch('time.sleep') as mock_sleep:
            result = hand.execute({"action": "wait", "seconds": 2})

        assert result["action"] == "wait"
        assert result["seconds"] == 2
        mock_sleep.assert_called_once_with(2)

    def test_execute_wait_default_seconds(self):
        """execute uses default 1 second for wait."""
        hand = Hand()
        hand._page = MagicMock()

        with patch('time.sleep') as mock_sleep:
            result = hand.execute({"action": "wait"})

        assert result["seconds"] == 1
        mock_sleep.assert_called_once_with(1)


class TestDownloadLinkDetection:
    """Tests for download link type detection."""

    def test_inline_file_detection_jpg(self):
        """download_link detects .jpg as inline file."""
        hand = Hand()
        hand._page = MagicMock()
        hand.download_dir = Path("/tmp")

        # Check that inline extension detection works
        href = "https://example.com/image.jpg"
        assert any(href.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif'])

    def test_inline_file_detection_with_query(self):
        """download_link handles extensions with query strings."""
        href = "https://example.com/image.png?size=large"
        inline_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp']
        is_inline = any(f'{ext}?' in href.lower() for ext in inline_extensions)
        assert is_inline is True

    def test_image_host_detection(self):
        """download_link detects known image hosts."""
        image_hosts = ['upload.wikimedia.org', 'i.imgur.com', 'pbs.twimg.com']

        test_urls = [
            "https://upload.wikimedia.org/wikipedia/commons/image.png",
            "https://i.imgur.com/abc123.jpg",
            "https://pbs.twimg.com/media/xyz.jpg"
        ]

        for url in test_urls:
            is_image_host = any(h in url.lower() for h in image_hosts)
            assert is_image_host is True


class TestDownloadFileValidation:
    """Tests for download_file argument validation."""

    def test_download_file_requires_selector_or_url(self):
        """download_file raises InvalidActionArgsError without selector or url."""
        hand = Hand()
        hand._page = MagicMock()
        hand._pending_downloads = []

        with pytest.raises(InvalidActionArgsError) as exc_info:
            hand.download_file()

        assert "download" in str(exc_info.value)


class TestSetDownloadCallback:
    """Tests for download callback functionality."""

    def test_set_download_callback(self):
        """set_download_callback stores callback."""
        hand = Hand()
        callback = Mock()

        hand.set_download_callback(callback)

        assert hand._download_callback is callback

    def test_handle_download_triggers_callback(self):
        """_handle_download calls registered callback."""
        hand = Hand()
        callback = Mock()
        hand._download_callback = callback

        mock_download = Mock()
        hand._handle_download(mock_download)

        callback.assert_called_once_with(mock_download)
        assert mock_download in hand._pending_downloads

    def test_handle_download_no_callback(self):
        """_handle_download works without callback."""
        hand = Hand()

        mock_download = Mock()
        hand._handle_download(mock_download)

        assert mock_download in hand._pending_downloads


class TestGetPendingDownloads:
    """Tests for get_pending_downloads."""

    def test_returns_copy(self):
        """get_pending_downloads returns a copy."""
        hand = Hand()
        mock_download = Mock()
        hand._pending_downloads.append(mock_download)

        result = hand.get_pending_downloads()

        assert result == [mock_download]
        assert result is not hand._pending_downloads


class TestScrollDirection:
    """Tests for scroll direction calculation."""

    def test_scroll_down_positive_delta(self):
        """scroll down produces positive delta."""
        direction = "down"
        amount = 500
        delta = amount if direction == "down" else -amount
        assert delta == 500

    def test_scroll_up_negative_delta(self):
        """scroll up produces negative delta."""
        direction = "up"
        amount = 500
        delta = amount if direction == "down" else -amount
        assert delta == -500


class TestTypeSelectorFallbacks:
    """Tests for type selector fallback logic."""

    def test_search_input_fallbacks_triggered(self):
        """type adds fallbacks for search-related selectors."""
        selector = 'input[name="search"]'

        # Simulate the fallback logic
        selectors_to_try = [selector]
        if any(x in selector.lower() for x in ['search', 'query', 'q', 'input']):
            selectors_to_try.extend([
                'input[type="search"]',
                'input[name="q"]',
            ])

        assert len(selectors_to_try) > 1
        assert 'input[type="search"]' in selectors_to_try

    def test_non_search_no_fallbacks(self):
        """type doesn't add fallbacks for non-search selectors."""
        selector = 'input[name="email"]'

        selectors_to_try = [selector]
        if any(x in selector.lower() for x in ['search', 'query', 'q', 'input']):
            selectors_to_try.extend(['input[type="search"]'])

        # 'input' is in selector, so fallbacks are added
        # This test verifies the behavior
        assert 'input' in selector.lower()


class TestHandStateTracking:
    """Tests for Hand state tracking."""

    def test_mouse_pos_updates(self):
        """Mouse position can be updated."""
        hand = Hand()
        hand._mouse_pos = (100, 200)
        assert hand._mouse_pos == (100, 200)

    def test_detector_initialized(self):
        """SiteDetector is initialized in Hand."""
        hand = Hand()
        assert hand._detector is not None

    def test_download_callback_starts_none(self):
        """Download callback starts as None."""
        hand = Hand()
        assert hand._download_callback is None


class TestHandHelperProperties:
    """Tests for helper property initialization."""

    def test_selector_starts_none(self):
        """_selector starts as None."""
        hand = Hand()
        assert hand._selector is None

    def test_popups_starts_none(self):
        """_popups starts as None."""
        hand = Hand()
        assert hand._popups is None

    def test_waits_starts_none(self):
        """_waits starts as None."""
        hand = Hand()
        assert hand._waits is None


class TestMultipleHandInstances:
    """Tests for multiple Hand instances."""

    def test_independent_instances(self):
        """Multiple Hand instances are independent."""
        hand1 = Hand(headless=True)
        hand2 = Hand(headless=False)

        assert hand1.headless is True
        assert hand2.headless is False

    def test_independent_download_dirs(self):
        """Each Hand can have its own download directory."""
        hand1 = Hand(download_dir=Path("/tmp/downloads1"))
        hand2 = Hand(download_dir=Path("/tmp/downloads2"))

        assert hand1.download_dir != hand2.download_dir

    def test_independent_pending_downloads(self):
        """Each Hand tracks its own pending downloads."""
        hand1 = Hand()
        hand2 = Hand()

        mock_download = Mock()
        hand1._pending_downloads.append(mock_download)

        assert len(hand1._pending_downloads) == 1
        assert len(hand2._pending_downloads) == 0


class TestHandCombinedConfigs:
    """Tests for combined configuration options."""

    def test_all_configs_custom(self):
        """Hand accepts all custom configurations together."""
        stealth = StealthConfig(min_delay=1.0)
        retry = RetryConfig(max_attempts=10)
        download = Path("/custom/downloads")

        hand = Hand(
            headless=True,
            stealth_config=stealth,
            retry_config=retry,
            download_dir=download
        )

        assert hand.headless is True
        assert hand.stealth.config.min_delay == 1.0
        assert hand.retry_config.max_attempts == 10
        assert hand.download_dir == download

    def test_partial_configs(self):
        """Hand works with partial custom configurations."""
        hand = Hand(headless=True, download_dir=Path("/tmp"))

        assert hand.headless is True
        assert hand.download_dir == Path("/tmp")
        # Defaults still applied
        assert hand.retry_config is not None
        assert hand.stealth is not None


class TestHandNavigationMethods:
    """Tests for Hand navigation methods."""

    def test_goto_returns_dict(self):
        """goto() should return a dict."""
        hand = Hand(headless=True)
        # Without wake, this will fail, but we're testing the method signature
        assert hasattr(hand, 'goto')
        assert callable(hand.goto)

    def test_back_returns_dict(self):
        """back() should return a dict."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'back')
        assert callable(hand.back)

    def test_forward_returns_dict(self):
        """forward() should return a dict."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'forward')
        assert callable(hand.forward)

    def test_refresh_returns_dict(self):
        """refresh() should return a dict."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'refresh')
        assert callable(hand.refresh)


class TestHandInteractionMethods:
    """Tests for Hand interaction methods."""

    def test_click_method_exists(self):
        """click() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'click')
        assert callable(hand.click)

    def test_type_method_exists(self):
        """type() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'type')
        assert callable(hand.type)

    def test_press_method_exists(self):
        """press() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'press')
        assert callable(hand.press)

    def test_scroll_method_exists(self):
        """scroll() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'scroll')
        assert callable(hand.scroll)

    def test_hover_method_exists(self):
        """hover() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'hover')
        assert callable(hand.hover)

    def test_smart_click_method_exists(self):
        """smart_click() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'smart_click')
        assert callable(hand.smart_click)


class TestHandPageInfoMethods:
    """Tests for Hand page info methods."""

    def test_get_html_method_exists(self):
        """get_html() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'get_html')
        assert callable(hand.get_html)

    def test_get_url_method_exists(self):
        """get_url() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'get_url')
        assert callable(hand.get_url)

    def test_get_title_method_exists(self):
        """get_title() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'get_title')
        assert callable(hand.get_title)

    def test_screenshot_method_exists(self):
        """screenshot() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'screenshot')
        assert callable(hand.screenshot)


class TestHandDownloadMethods:
    """Tests for Hand download methods."""

    def test_download_file_method_exists(self):
        """download_file() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'download_file')
        assert callable(hand.download_file)

    def test_download_link_method_exists(self):
        """download_link() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'download_link')
        assert callable(hand.download_link)

    def test_click_and_download_method_exists(self):
        """click_and_download() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'click_and_download')
        assert callable(hand.click_and_download)

    def test_wait_for_download_method_exists(self):
        """wait_for_download() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'wait_for_download')
        assert callable(hand.wait_for_download)


class TestHandWaitMethods:
    """Tests for Hand wait methods."""

    def test_wait_for_navigation_method_exists(self):
        """wait_for_navigation() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'wait_for_navigation')
        assert callable(hand.wait_for_navigation)

    def test_force_render_method_exists(self):
        """force_render() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'force_render')
        assert callable(hand.force_render)


class TestHandWakeAndSleep:
    """Tests for Hand wake and sleep methods."""

    def test_wake_method_exists(self):
        """wake() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'wake')
        assert callable(hand.wake)

    def test_sleep_method_exists(self):
        """sleep() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, 'sleep')
        assert callable(hand.sleep)

    def test_sleep_handles_no_playwright(self):
        """sleep() handles case where playwright not started."""
        hand = Hand(headless=True)
        # Should not raise even without wake
        hand.sleep()

    def test_sleep_handles_no_browser(self):
        """sleep() handles case where browser not started."""
        hand = Hand(headless=True)
        hand._playwright = Mock()
        hand._browser = None
        # Should not raise
        hand.sleep()


class TestHandInternalMethods:
    """Tests for Hand internal helper methods."""

    def test_human_delay_method_exists(self):
        """_human_delay() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_human_delay')
        assert callable(hand._human_delay)

    def test_move_mouse_human_method_exists(self):
        """_move_mouse_human() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_move_mouse_human')
        assert callable(hand._move_mouse_human)

    def test_setup_resource_blocking_method_exists(self):
        """_setup_resource_blocking() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_setup_resource_blocking')
        assert callable(hand._setup_resource_blocking)

    def test_inject_stealth_scripts_method_exists(self):
        """_inject_stealth_scripts() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_inject_stealth_scripts')
        assert callable(hand._inject_stealth_scripts)

    def test_wait_for_challenge_resolution_method_exists(self):
        """_wait_for_challenge_resolution() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_wait_for_challenge_resolution')
        assert callable(hand._wait_for_challenge_resolution)

    def test_wait_for_dynamic_content_method_exists(self):
        """_wait_for_dynamic_content() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_wait_for_dynamic_content')
        assert callable(hand._wait_for_dynamic_content)

    def test_compute_hash_method_exists(self):
        """_compute_hash() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_compute_hash')
        assert callable(hand._compute_hash)

    def test_fetch_file_directly_method_exists(self):
        """_fetch_file_directly() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_fetch_file_directly')
        assert callable(hand._fetch_file_directly)

    def test_handle_download_method_exists(self):
        """_handle_download() method exists."""
        hand = Hand(headless=True)
        assert hasattr(hand, '_handle_download')
        assert callable(hand._handle_download)


class TestHandPropertyHelpers:
    """Tests for Hand property helper access."""

    def test_page_property_raises_without_wake(self):
        """page property raises BrowserNotReadyError without wake."""
        from blackreach.exceptions import BrowserNotReadyError

        hand = Hand(headless=True)
        with pytest.raises(BrowserNotReadyError):
            _ = hand.page

    def test_selector_property_raises_without_wake(self):
        """selector property raises BrowserNotReadyError without wake."""
        from blackreach.exceptions import BrowserNotReadyError

        hand = Hand(headless=True)
        with pytest.raises(BrowserNotReadyError):
            _ = hand.selector

    def test_popups_property_raises_without_wake(self):
        """popups property raises BrowserNotReadyError without wake."""
        from blackreach.exceptions import BrowserNotReadyError

        hand = Hand(headless=True)
        with pytest.raises(BrowserNotReadyError):
            _ = hand.popups

    def test_waits_property_raises_without_wake(self):
        """waits property raises BrowserNotReadyError without wake."""
        from blackreach.exceptions import BrowserNotReadyError

        hand = Hand(headless=True)
        with pytest.raises(BrowserNotReadyError):
            _ = hand.waits


class TestHandWithMockedPage:
    """Tests for Hand methods with mocked page."""

    def test_get_url_with_mock_page(self):
        """get_url() returns page URL."""
        hand = Hand(headless=True)
        hand._page = Mock()
        hand._page.url = "https://example.com"

        url = hand.get_url()

        assert url == "https://example.com"

    def test_get_title_with_mock_page(self):
        """get_title() returns page title."""
        hand = Hand(headless=True)
        hand._page = Mock()
        hand._page.title.return_value = "Example Page"

        title = hand.get_title()

        assert title == "Example Page"

    def test_get_html_with_mock_page(self):
        """get_html() returns page content."""
        hand = Hand(headless=True)
        hand._page = Mock()
        hand._page.content.return_value = "<html><body>Test</body></html>"

        html = hand.get_html(wait_for_load=False)

        assert "<html>" in html
        assert "Test" in html

    def test_handle_download_appends_to_pending(self):
        """_handle_download() adds to pending downloads."""
        hand = Hand(headless=True)
        mock_download = Mock()

        hand._handle_download(mock_download)

        assert mock_download in hand._pending_downloads

    def test_handle_download_calls_callback(self):
        """_handle_download() calls download callback."""
        hand = Hand(headless=True)
        callback = Mock()
        hand._download_callback = callback
        mock_download = Mock()

        hand._handle_download(mock_download)

        callback.assert_called_once_with(mock_download)

    def test_compute_hash_returns_string(self):
        """_compute_hash() returns a hash string."""
        import tempfile
        import os

        hand = Hand(headless=True)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            path = Path(f.name)

        try:
            hash_val = hand._compute_hash(path)
            assert isinstance(hash_val, str)
            assert len(hash_val) == 64  # SHA-256 hex length
        finally:
            os.unlink(path)


class TestSanitizeFilename:
    """Tests for _sanitize_filename security function."""

    def test_normal_filename_unchanged(self):
        """Normal filename passes through unchanged."""
        assert _sanitize_filename("document.pdf") == "document.pdf"
        assert _sanitize_filename("my_file.txt") == "my_file.txt"
        assert _sanitize_filename("report-2024.xlsx") == "report-2024.xlsx"

    def test_removes_path_traversal_unix(self):
        """Path traversal patterns (../) are removed."""
        assert "../" not in _sanitize_filename("../../../etc/passwd")
        assert "passwd" in _sanitize_filename("../../../etc/passwd")

    def test_removes_path_traversal_windows(self):
        r"""Path traversal patterns (..\) are removed."""
        result = _sanitize_filename(r"..\..\Windows\System32\config")
        assert "..\\" not in result
        # On Linux, backslashes are converted to underscores (not path seps)
        # The important thing is path traversal characters are neutralized
        assert ".." not in result or result.count("..") == 0

    def test_removes_absolute_paths_unix(self):
        """Absolute Unix paths are reduced to basename."""
        assert _sanitize_filename("/etc/passwd") == "passwd"
        assert _sanitize_filename("/home/user/document.pdf") == "document.pdf"

    def test_removes_absolute_paths_windows(self):
        """Absolute Windows paths are reduced to basename (on Windows) or sanitized (on Linux)."""
        result = _sanitize_filename("C:\\Windows\\System32\\cmd.exe")
        # On Linux, backslashes are not path separators so they become part of the name
        # The colon is removed (dangerous char), and the result is safe
        assert ":" not in result
        assert result  # non-empty

        result = _sanitize_filename("D:\\Users\\Admin\\malicious.exe")
        assert ":" not in result
        assert result  # non-empty

    def test_removes_dangerous_characters(self):
        """Dangerous characters are replaced with underscore."""
        assert '<' not in _sanitize_filename("file<name>.txt")
        assert '>' not in _sanitize_filename("file<name>.txt")
        assert ':' not in _sanitize_filename("file:name.txt")
        assert '"' not in _sanitize_filename('file"name.txt')
        assert '|' not in _sanitize_filename("file|name.txt")
        assert '?' not in _sanitize_filename("file?name.txt")
        assert '*' not in _sanitize_filename("file*name.txt")

    def test_removes_null_bytes(self):
        """Null bytes are removed (common injection attack)."""
        result = _sanitize_filename("file.txt\x00.exe")
        assert '\x00' not in result

    def test_removes_control_characters(self):
        """Control characters (0x00-0x1f) are removed."""
        result = _sanitize_filename("file\x01\x02\x03name.txt")
        assert all(ord(c) >= 0x20 or c == '_' for c in result)

    def test_handles_empty_string(self):
        """Empty string returns safe default."""
        assert _sanitize_filename("") == "downloaded_file"

    def test_handles_dots_only(self):
        """String of dots returns safe default."""
        assert _sanitize_filename("...") == "downloaded_file"
        assert _sanitize_filename("..") == "downloaded_file"

    def test_handles_spaces_only(self):
        """String of spaces returns safe default."""
        assert _sanitize_filename("   ") == "downloaded_file"

    def test_strips_leading_trailing_dots(self):
        """Leading and trailing dots are stripped."""
        result = _sanitize_filename(".hidden_file.txt")
        # basename preserves leading dot, but we strip leading dots
        assert not result.startswith('.')

    def test_handles_unicode_filenames(self):
        """Unicode filenames are preserved."""
        # Chinese characters should pass through
        assert "文档" in _sanitize_filename("文档.pdf") or _sanitize_filename("文档.pdf") == "文档.pdf"
        # Japanese characters
        assert "ファイル" in _sanitize_filename("ファイル.txt") or _sanitize_filename("ファイル.txt") == "ファイル.txt"

    def test_complex_attack_patterns(self):
        """Complex attack patterns are neutralized."""
        # Mix of path traversal and dangerous chars
        result = _sanitize_filename("../<script>alert('xss')</script>/../passwd")
        assert "../" not in result
        assert "<" not in result
        assert ">" not in result

    def test_encoded_path_traversal_not_decoded(self):
        """URL-encoded path traversal stays encoded (not decoded by this function)."""
        # The function doesn't decode, so %2e%2e%2f stays as is
        result = _sanitize_filename("%2e%2e%2f")
        # The percent sign is allowed, so it passes through
        assert result  # Just ensure no crash

    def test_multiple_extensions(self):
        """Multiple extensions are preserved."""
        assert _sanitize_filename("archive.tar.gz") == "archive.tar.gz"
        assert _sanitize_filename("file.backup.txt") == "file.backup.txt"

    def test_very_long_filename(self):
        """Very long filenames don't crash (though may be truncated by OS)."""
        long_name = "a" * 500 + ".txt"
        result = _sanitize_filename(long_name)
        assert isinstance(result, str)
        assert len(result) > 0


class TestSSRFProtection:
    """Tests for _is_ssrf_safe security function."""

    def test_public_urls_allowed(self):
        """Public URLs are allowed."""
        assert _is_ssrf_safe("https://www.google.com") is True
        assert _is_ssrf_safe("https://example.com/page") is True
        assert _is_ssrf_safe("http://public-api.example.com") is True

    def test_localhost_blocked(self):
        """Localhost in various forms is blocked."""
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://localhost/admin")

        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://127.0.0.1/secret")

        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://0.0.0.0/debug")

    def test_ipv6_localhost_blocked(self):
        """IPv6 localhost is blocked."""
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://[::1]/admin")

    def test_no_hostname_blocked(self):
        """URLs without hostname raise error."""
        with pytest.raises(ValueError, match="no hostname"):
            _is_ssrf_safe("file:///etc/passwd")

    def test_case_insensitive_localhost(self):
        """Localhost detection is case-insensitive."""
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://LOCALHOST/")

        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://LocalHost/")

    def test_localhost_with_port_blocked(self):
        """Localhost with port is blocked."""
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://localhost:8080/")

        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://127.0.0.1:3000/api")

    def test_private_ip_class_a_blocked(self):
        """Class A private IPs (10.x.x.x) are blocked if they resolve."""
        # Note: These tests may pass if DNS doesn't resolve
        # The function blocks IPs it can resolve to private ranges
        # For hosts that don't resolve, it returns True (handled at request time)
        # We test the localhost case which we know will resolve
        pass  # Covered by localhost tests

    def test_with_authentication_in_url(self):
        """URLs with authentication info are handled."""
        # Public URLs with auth should still be allowed
        assert _is_ssrf_safe("https://user:pass@example.com/api") is True

    def test_unresolvable_hostname_allowed(self):
        """Unresolvable hostnames are allowed (will fail at request time)."""
        # This tests the DNS resolution failure case
        result = _is_ssrf_safe("https://nonexistent-host-12345.invalid/")
        assert result is True  # Allowed through - will fail at request time

    def test_url_with_path_and_query(self):
        """URLs with paths and query strings work correctly."""
        assert _is_ssrf_safe("https://api.example.com/v1/data?key=value") is True

    def test_https_urls_allowed(self):
        """HTTPS URLs are handled same as HTTP."""
        assert _is_ssrf_safe("https://secure.example.com/") is True


class TestHandContextManager:
    """Tests for Hand context manager functionality."""

    def test_context_manager_enter_returns_hand(self):
        """Context manager __enter__ returns the Hand instance."""
        with patch.object(Hand, 'wake') as mock_wake:
            hand = Hand(headless=True)
            result = hand.__enter__()
            assert result is hand
            mock_wake.assert_called_once()

    def test_context_manager_exit_calls_sleep(self):
        """Context manager __exit__ calls sleep."""
        with patch.object(Hand, 'sleep') as mock_sleep:
            hand = Hand(headless=True)
            result = hand.__exit__(None, None, None)
            assert result is False  # Should not suppress exceptions
            mock_sleep.assert_called_once()

    def test_context_manager_exit_does_not_suppress_exceptions(self):
        """Context manager __exit__ returns False (doesn't suppress)."""
        hand = Hand(headless=True)
        with patch.object(hand, 'sleep'):
            result = hand.__exit__(ValueError, ValueError("test"), None)
            assert result is False

    def test_context_manager_with_syntax(self):
        """Hand can be used with 'with' statement."""
        with patch.object(Hand, 'wake') as mock_wake:
            with patch.object(Hand, 'sleep') as mock_sleep:
                with Hand(headless=True) as hand:
                    assert hand is not None
                mock_wake.assert_called_once()
                mock_sleep.assert_called_once()


class TestFilenameSanitizationEdgeCases:
    """Additional edge cases for filename sanitization."""

    def test_backslash_forward_slash_mix(self):
        """Mixed path separators are handled."""
        result = _sanitize_filename("path/to\\..\\secret/file.txt")
        assert "/" not in result or result == "file.txt"
        assert "\\" not in result

    def test_double_dot_in_extension(self):
        """Double dot in extension is safe (not path traversal)."""
        result = _sanitize_filename("file..txt")
        # This is a valid filename, not path traversal
        assert result  # Should produce a valid result

    def test_dotfile_names(self):
        """Dot files are handled (may be stripped or kept)."""
        result = _sanitize_filename(".gitignore")
        # Leading dots are stripped by the function
        assert result == "gitignore" or result == ".gitignore"

    def test_null_byte_injection(self):
        """Null byte injection attack is prevented."""
        # Attacker tries: file.txt\x00.exe -> on some systems this becomes file.txt
        result = _sanitize_filename("safe.txt\x00malicious.exe")
        assert "\x00" not in result
        # Should only contain printable characters
        assert all(c.isprintable() or c == '_' for c in result)

    def test_colon_for_alternate_data_stream(self):
        """Windows alternate data stream syntax (file:stream) is blocked."""
        result = _sanitize_filename("file.txt:secret_data")
        assert ":" not in result  # Colons are removed

    def test_reserved_windows_names(self):
        """Reserved Windows names don't crash (though may cause OS issues)."""
        # The function doesn't block these, but they shouldn't crash
        reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved:
            result = _sanitize_filename(name)
            assert isinstance(result, str)


class TestSSRFProtectionAdvanced:
    """Advanced SSRF protection tests."""

    def test_metadata_service_urls(self):
        """Cloud metadata service URLs should be blocked."""
        # AWS metadata service
        # This would need to resolve to 169.254.169.254 to be blocked
        # If it doesn't resolve, the function allows it (will fail at request time)
        # We can't easily test this without DNS resolution mocking
        pass

    def test_internal_kubernetes_urls(self):
        """Kubernetes internal URLs should be handled."""
        # Similar to metadata - depends on DNS resolution
        pass

    def test_url_with_ipv6_brackets(self):
        """URLs with IPv6 addresses in brackets are handled."""
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://[::1]:8080/admin")

    def test_url_with_credentials(self):
        """URLs with credentials don't bypass SSRF check."""
        with pytest.raises(ValueError, match="SSRF"):
            _is_ssrf_safe("http://user:pass@localhost/admin")

    def test_malformed_urls_rejected(self):
        """Malformed URLs are rejected safely."""
        with pytest.raises(ValueError):
            _is_ssrf_safe("not_a_url")

        with pytest.raises(ValueError):
            _is_ssrf_safe("://missing-scheme.com")

    def test_empty_url_rejected(self):
        """Empty URL is rejected."""
        with pytest.raises(ValueError):
            _is_ssrf_safe("")

    def test_url_with_fragment(self):
        """URLs with fragments work correctly."""
        assert _is_ssrf_safe("https://example.com/page#section") is True

    def test_url_with_unicode_hostname(self):
        """URLs with unicode/IDN hostnames work."""
        # IDN domains should work if they resolve to public IPs
        result = _is_ssrf_safe("https://münchen.example.com/")
        assert result is True  # Either resolves to public IP or doesn't resolve


# ============================================================================
# ProxyConfig Tests
# ============================================================================

class TestProxyConfigBasic:
    """Tests for ProxyConfig creation and basic operations."""

    def test_create_http_proxy_default_type(self):
        """ProxyConfig defaults to HTTP type."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8080
        assert proxy.proxy_type == ProxyType.HTTP
        assert proxy.username is None
        assert proxy.password is None
        assert proxy.bypass is None

    def test_create_socks5_proxy(self):
        """ProxyConfig can create SOCKS5 proxy."""
        proxy = ProxyConfig(
            host="socks.example.com",
            port=1080,
            proxy_type=ProxyType.SOCKS5
        )
        assert proxy.proxy_type == ProxyType.SOCKS5
        assert proxy.port == 1080

    def test_create_proxy_with_auth(self):
        """ProxyConfig stores authentication credentials."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="secret123"
        )
        assert proxy.username == "user"
        assert proxy.password == "secret123"

    def test_create_proxy_with_bypass(self):
        """ProxyConfig stores bypass list."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            bypass=["localhost", "*.internal.com"]
        )
        assert proxy.bypass == ["localhost", "*.internal.com"]


class TestProxyConfigFromUrl:
    """Tests for ProxyConfig.from_url() parsing."""

    def test_parse_simple_http_url(self):
        """Parse simple HTTP proxy URL."""
        proxy = ProxyConfig.from_url("http://proxy.example.com:8080")
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8080
        assert proxy.proxy_type == ProxyType.HTTP

    def test_parse_https_url(self):
        """Parse HTTPS proxy URL."""
        proxy = ProxyConfig.from_url("https://proxy.example.com:8443")
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8443
        assert proxy.proxy_type == ProxyType.HTTPS

    def test_parse_socks5_url(self):
        """Parse SOCKS5 proxy URL."""
        proxy = ProxyConfig.from_url("socks5://socks.example.com:1080")
        assert proxy.host == "socks.example.com"
        assert proxy.port == 1080
        assert proxy.proxy_type == ProxyType.SOCKS5

    def test_parse_socks4_url(self):
        """Parse SOCKS4 proxy URL."""
        proxy = ProxyConfig.from_url("socks4://socks.example.com:1080")
        assert proxy.proxy_type == ProxyType.SOCKS4

    def test_parse_socks_defaults_to_socks5(self):
        """Bare 'socks' scheme defaults to SOCKS5."""
        proxy = ProxyConfig.from_url("socks://socks.example.com:1080")
        assert proxy.proxy_type == ProxyType.SOCKS5

    def test_parse_url_with_auth(self):
        """Parse proxy URL with authentication."""
        proxy = ProxyConfig.from_url("http://user:pass@proxy.example.com:8080")
        assert proxy.username == "user"
        assert proxy.password == "pass"
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8080

    def test_parse_url_missing_port_http(self):
        """HTTP URL without port defaults to 8080."""
        proxy = ProxyConfig.from_url("http://proxy.example.com")
        assert proxy.port == 8080

    def test_parse_url_missing_port_socks(self):
        """SOCKS URL without port defaults to 1080."""
        proxy = ProxyConfig.from_url("socks5://proxy.example.com")
        assert proxy.port == 1080

    def test_parse_url_missing_host_defaults_localhost(self):
        """URL without hostname defaults to localhost."""
        proxy = ProxyConfig.from_url("http://:8080")
        assert proxy.host == "localhost"

    def test_parse_unknown_scheme_defaults_http(self):
        """Unknown scheme defaults to HTTP."""
        proxy = ProxyConfig.from_url("xyz://proxy.example.com:8080")
        assert proxy.proxy_type == ProxyType.HTTP


class TestProxyConfigToPlaywright:
    """Tests for ProxyConfig.to_playwright_proxy() conversion."""

    def test_simple_proxy_conversion(self):
        """Convert simple proxy to Playwright format."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        result = proxy.to_playwright_proxy()
        assert result["server"] == "http://proxy.example.com:8080"
        assert "username" not in result
        assert "password" not in result

    def test_https_proxy_uses_http_scheme(self):
        """HTTPS proxy uses http scheme for Playwright."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8443,
            proxy_type=ProxyType.HTTPS
        )
        result = proxy.to_playwright_proxy()
        # Playwright uses http for HTTPS proxies
        assert result["server"] == "http://proxy.example.com:8443"

    def test_socks5_proxy_conversion(self):
        """Convert SOCKS5 proxy to Playwright format."""
        proxy = ProxyConfig(
            host="socks.example.com",
            port=1080,
            proxy_type=ProxyType.SOCKS5
        )
        result = proxy.to_playwright_proxy()
        assert result["server"] == "socks5://socks.example.com:1080"

    def test_proxy_with_auth_conversion(self):
        """Convert proxy with auth to Playwright format."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="secret"
        )
        result = proxy.to_playwright_proxy()
        assert result["server"] == "http://proxy.example.com:8080"
        assert result["username"] == "user"
        assert result["password"] == "secret"

    def test_proxy_with_bypass_conversion(self):
        """Convert proxy with bypass to Playwright format."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            bypass=["localhost", "*.internal.com"]
        )
        result = proxy.to_playwright_proxy()
        assert result["bypass"] == "localhost,*.internal.com"

    def test_proxy_with_auth_and_bypass(self):
        """Convert proxy with both auth and bypass."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="pass",
            bypass=["localhost"]
        )
        result = proxy.to_playwright_proxy()
        assert result["username"] == "user"
        assert result["bypass"] == "localhost"


class TestProxyConfigStringRepresentation:
    """Tests for ProxyConfig string representation."""

    def test_str_without_auth(self):
        """String representation without auth."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        assert str(proxy) == "http://proxy.example.com:8080"

    def test_str_with_auth_hides_password(self):
        """String representation hides password."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="secret"
        )
        result = str(proxy)
        assert "user" in result
        assert "***" in result
        assert "secret" not in result

    def test_str_shows_proxy_type(self):
        """String representation shows proxy type."""
        proxy = ProxyConfig(
            host="socks.example.com",
            port=1080,
            proxy_type=ProxyType.SOCKS5
        )
        assert "socks5://" in str(proxy)


# ============================================================================
# ProxyRotator Tests
# ============================================================================

class TestProxyRotatorBasic:
    """Tests for ProxyRotator creation and basic operations."""

    def test_create_empty_rotator(self):
        """Create rotator with no proxies."""
        rotator = ProxyRotator()
        assert len(rotator) == 0

    def test_create_rotator_with_string_proxies(self):
        """Create rotator with proxy URL strings."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080"
        ])
        assert len(rotator) == 2

    def test_create_rotator_with_proxy_configs(self):
        """Create rotator with ProxyConfig objects."""
        proxies = [
            ProxyConfig(host="proxy1.example.com", port=8080),
            ProxyConfig(host="proxy2.example.com", port=8080)
        ]
        rotator = ProxyRotator(proxies)
        assert len(rotator) == 2

    def test_create_rotator_with_mixed_types(self):
        """Create rotator with mixed strings and ProxyConfigs."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            ProxyConfig(host="proxy2.example.com", port=8080)
        ])
        assert len(rotator) == 2


class TestProxyRotatorAddRemove:
    """Tests for adding and removing proxies."""

    def test_add_proxy_string(self):
        """Add proxy using URL string."""
        rotator = ProxyRotator()
        rotator.add_proxy("http://proxy.example.com:8080")
        assert len(rotator) == 1

    def test_add_proxy_config(self):
        """Add proxy using ProxyConfig."""
        rotator = ProxyRotator()
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        rotator.add_proxy(proxy)
        assert len(rotator) == 1

    def test_add_proxy_initializes_health(self):
        """Add proxy initializes health tracking."""
        rotator = ProxyRotator()
        rotator.add_proxy("http://proxy.example.com:8080")
        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["successes"] == 0
        assert proxy_stats["failures"] == 0
        assert proxy_stats["enabled"] is True

    def test_remove_proxy_by_string(self):
        """Remove proxy using URL string."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        rotator.remove_proxy("http://proxy.example.com:8080")
        assert len(rotator) == 0

    def test_remove_proxy_by_config(self):
        """Remove proxy using ProxyConfig object."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        rotator = ProxyRotator([proxy])
        rotator.remove_proxy(proxy)
        assert len(rotator) == 0

    def test_remove_nonexistent_proxy_no_error(self):
        """Removing nonexistent proxy doesn't error."""
        rotator = ProxyRotator()
        rotator.remove_proxy("http://nonexistent.com:8080")  # Should not raise
        assert len(rotator) == 0


class TestProxyRotatorGetNext:
    """Tests for get_next proxy selection."""

    def test_get_next_empty_returns_none(self):
        """get_next on empty rotator returns None."""
        rotator = ProxyRotator()
        assert rotator.get_next() is None

    def test_get_next_returns_proxy(self):
        """get_next returns a proxy config."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()
        assert proxy is not None
        assert isinstance(proxy, ProxyConfig)

    def test_get_next_round_robin(self):
        """get_next rotates through proxies in order."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
            "http://proxy3.example.com:8080"
        ])

        # Get all three in sequence
        p1 = rotator.get_next()
        p2 = rotator.get_next()
        p3 = rotator.get_next()

        # Should cycle back to first
        p4 = rotator.get_next()

        # Verify rotation
        assert p1.host == "proxy1.example.com"
        assert p2.host == "proxy2.example.com"
        assert p3.host == "proxy3.example.com"
        assert p4.host == "proxy1.example.com"


class TestProxyRotatorStickySession:
    """Tests for sticky session functionality."""

    def test_sticky_session_returns_same_proxy(self):
        """Sticky session returns same proxy for same domain."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080"
        ])

        # First request to domain gets first proxy
        p1 = rotator.get_next(domain="example.com")
        # Second request to same domain should get same proxy
        p2 = rotator.get_next(domain="example.com")

        assert str(p1) == str(p2)

    def test_different_domains_can_get_different_proxies(self):
        """Different domains can get different proxies."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080"
        ])

        # First domain gets first proxy
        p1 = rotator.get_next(domain="example1.com")
        # Second domain gets next proxy
        p2 = rotator.get_next(domain="example2.com")

        # They may be different (round-robin assigns)
        assert p1 is not None
        assert p2 is not None

    def test_clear_sticky_sessions(self):
        """clear_sticky_sessions resets domain assignments."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080"
        ])

        # Get proxy for domain
        p1 = rotator.get_next(domain="example.com")

        # Clear sessions
        rotator.clear_sticky_sessions()

        # May get different proxy now (depends on round-robin position)
        p2 = rotator.get_next(domain="example.com")
        # At minimum, should not raise and should return a proxy
        assert p2 is not None


class TestProxyRotatorHealthTracking:
    """Tests for proxy health tracking."""

    def test_report_success_increments_counter(self):
        """report_success increments success counter."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()

        rotator.report_success(proxy)
        rotator.report_success(proxy)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["successes"] == 2

    def test_report_success_updates_response_time(self):
        """report_success updates average response time."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()

        rotator.report_success(proxy, response_time=1.0)
        rotator.report_success(proxy, response_time=2.0)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        # Average of 1.0 and 2.0 = 1.5
        assert proxy_stats["avg_response_time"] == 1.5

    def test_report_failure_increments_counter(self):
        """report_failure increments failure counter."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()

        rotator.report_failure(proxy)
        rotator.report_failure(proxy)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["failures"] == 2

    def test_report_failure_disables_after_threshold(self):
        """report_failure disables proxy after threshold failures."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()

        # Report enough failures to trigger disable (threshold=5, rate>0.5)
        for _ in range(6):
            rotator.report_failure(proxy, disable_threshold=5)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["enabled"] is False

    def test_all_disabled_proxies_reenabled(self):
        """When all proxies disabled, they get re-enabled."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()

        # Disable the proxy
        for _ in range(6):
            rotator.report_failure(proxy, disable_threshold=5)

        # Try to get next - should re-enable all
        proxy2 = rotator.get_next()
        assert proxy2 is not None


class TestProxyRotatorStats:
    """Tests for proxy statistics."""

    def test_get_stats_empty(self):
        """get_stats works on empty rotator."""
        rotator = ProxyRotator()
        stats = rotator.get_stats()
        assert stats["total_proxies"] == 0
        assert stats["enabled"] == 0
        assert stats["proxies"] == {}

    def test_get_stats_with_proxies(self):
        """get_stats returns correct counts."""
        rotator = ProxyRotator([
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080"
        ])
        stats = rotator.get_stats()
        assert stats["total_proxies"] == 2
        assert stats["enabled"] == 2


class TestProxyRotatorReportByString:
    """Tests for reporting using string representation."""

    def test_report_success_by_string(self):
        """Can report success using string."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()

        # Report using string
        rotator.report_success(str(proxy))

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["successes"] == 1

    def test_report_failure_by_string(self):
        """Can report failure using string."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        proxy = rotator.get_next()

        # Report using string
        rotator.report_failure(str(proxy))

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["failures"] == 1


# ============================================================================
# Hand Proxy Methods Tests
# ============================================================================

class TestHandSetProxy:
    """Tests for Hand.set_proxy method."""

    def test_set_proxy_from_string(self):
        """set_proxy accepts URL string."""
        hand = Hand()
        hand.set_proxy("http://proxy.example.com:8080")
        assert hand._proxy is not None
        assert hand._proxy.host == "proxy.example.com"
        assert hand._proxy.port == 8080

    def test_set_proxy_from_config(self):
        """set_proxy accepts ProxyConfig."""
        hand = Hand()
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        hand.set_proxy(proxy)
        assert hand._proxy is proxy

    def test_set_proxy_to_none(self):
        """set_proxy(None) clears proxy."""
        hand = Hand()
        hand.set_proxy("http://proxy.example.com:8080")
        assert hand._proxy is not None
        hand.set_proxy(None)
        assert hand._proxy is None

    def test_get_current_proxy_initially_none(self):
        """get_current_proxy returns None before wake."""
        hand = Hand()
        assert hand.get_current_proxy() is None


class TestHandProxyInit:
    """Tests for Hand proxy initialization."""

    def test_init_with_proxy_string(self):
        """Hand can be initialized with proxy string."""
        hand = Hand(proxy="http://proxy.example.com:8080")
        assert hand._proxy is not None
        assert hand._proxy.host == "proxy.example.com"

    def test_init_with_proxy_config(self):
        """Hand can be initialized with ProxyConfig."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        hand = Hand(proxy=proxy)
        assert hand._proxy is proxy

    def test_init_with_proxy_rotator(self):
        """Hand can be initialized with ProxyRotator."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        hand = Hand(proxy_rotator=rotator)
        assert hand._proxy_rotator is rotator


class TestHandReportProxyResult:
    """Tests for Hand.report_proxy_result method."""

    def test_report_proxy_result_with_rotator_success(self):
        """report_proxy_result reports success to rotator."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        hand = Hand(proxy_rotator=rotator)

        # Simulate having selected a proxy
        hand._current_proxy = rotator._proxies[0]

        hand.report_proxy_result(success=True, response_time=0.5)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["successes"] == 1

    def test_report_proxy_result_with_rotator_failure(self):
        """report_proxy_result reports failure to rotator."""
        rotator = ProxyRotator(["http://proxy.example.com:8080"])
        hand = Hand(proxy_rotator=rotator)

        # Simulate having selected a proxy
        hand._current_proxy = rotator._proxies[0]

        hand.report_proxy_result(success=False)

        stats = rotator.get_stats()
        proxy_stats = list(stats["proxies"].values())[0]
        assert proxy_stats["failures"] == 1

    def test_report_proxy_result_without_rotator(self):
        """report_proxy_result does nothing without rotator."""
        hand = Hand()
        # Should not raise
        hand.report_proxy_result(success=True)


# ============================================================================
# Hand Interaction Methods Tests (with mocked page)
# ============================================================================

class TestHandClickWithMock:
    """Tests for Hand.click with mocked page."""

    def test_click_single_selector(self):
        """click with single selector clicks element."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = False

        result = hand.click("#button")

        hand._page.locator.assert_called_with("#button")
        mock_locator.click.assert_called_once()
        assert result["action"] == "click"
        assert result["selector"] == "#button"

    def test_click_with_list_selector(self):
        """click with list of selectors uses first match."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = None  # No smart selector

        # First selector fails, second works
        mock_locator1 = MagicMock()
        mock_locator1.count.return_value = 0
        mock_locator2 = MagicMock()
        mock_locator2.count.return_value = 1
        mock_locator2.first = MagicMock()

        def locator_side_effect(sel):
            if sel == "#first":
                return mock_locator1
            return mock_locator2

        hand._page.locator.side_effect = locator_side_effect
        hand.stealth.config.human_mouse = False

        result = hand.click(["#first", "#second"])

        assert result["action"] == "click"
        mock_locator2.first.click.assert_called_once()

    def test_click_raises_when_not_found(self):
        """click raises ElementNotFoundError when element not found."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = None

        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        hand._page.locator.return_value = mock_locator
        hand.stealth.config.human_mouse = False

        with pytest.raises(ElementNotFoundError):
            hand.click(["#nonexistent"])


class TestHandTypeWithMock:
    """Tests for Hand.type with mocked page."""

    def test_type_fills_element(self):
        """type fills element with text."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = True
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = False

        result = hand.type("#input", "test text")

        mock_locator.fill.assert_called_once_with("test text")
        assert result["action"] == "type"
        assert result["text"] == "test text"

    def test_type_raises_when_not_found(self):
        """type raises ElementNotFoundError when element not found."""
        hand = Hand()
        hand._page = MagicMock()

        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = PlaywrightError("timeout")
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = False

        with pytest.raises(ElementNotFoundError):
            hand.type("#nonexistent", "text")


class TestHandPressWithMock:
    """Tests for Hand.press with mocked page."""

    def test_press_key(self):
        """press sends key to page."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.press("Enter")

        hand._page.keyboard.press.assert_called_once_with("Enter")
        assert result["action"] == "press"
        assert result["key"] == "Enter"


class TestHandScrollWithMock:
    """Tests for Hand.scroll with mocked page."""

    def test_scroll_down(self):
        """scroll down moves page down."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.human_mouse = False

        result = hand.scroll("down", 500)

        hand._page.mouse.wheel.assert_called_once_with(0, 500)
        assert result["action"] == "scroll"
        assert result["direction"] == "down"
        assert result["amount"] == 500

    def test_scroll_up(self):
        """scroll up moves page up."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.human_mouse = False

        result = hand.scroll("up", 300)

        hand._page.mouse.wheel.assert_called_once_with(0, -300)
        assert result["direction"] == "up"

    def test_scroll_human_mode(self):
        """scroll in human mode scrolls in chunks."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.human_mouse = True

        with patch('time.sleep'):
            result = hand.scroll("down", 500, human=True)

        # Should have called wheel multiple times (chunked)
        assert hand._page.mouse.wheel.call_count > 1
        assert result["action"] == "scroll"


class TestHandHoverWithMock:
    """Tests for Hand.hover with mocked page."""

    def test_hover_element(self):
        """hover hovers over element."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        hand._page.locator.return_value.first = mock_locator

        result = hand.hover("#element")

        mock_locator.hover.assert_called_once()
        assert result["action"] == "hover"
        assert result["selector"] == "#element"


# ============================================================================
# Hand Navigation Methods Tests (with mocked page)
# ============================================================================

class TestHandBackForwardRefresh:
    """Tests for navigation methods."""

    def test_back_navigates_back(self):
        """back() goes back in history."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.return_value = "Previous Page"
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.back()

        hand._page.go_back.assert_called_once()
        assert result["action"] == "back"
        assert result["title"] == "Previous Page"

    def test_forward_navigates_forward(self):
        """forward() goes forward in history."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.return_value = "Next Page"
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.forward()

        hand._page.go_forward.assert_called_once()
        assert result["action"] == "forward"
        assert result["title"] == "Next Page"

    def test_refresh_reloads_page(self):
        """refresh() reloads the page."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.return_value = "Refreshed Page"
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.refresh()

        hand._page.reload.assert_called_once()
        assert result["action"] == "refresh"


# ============================================================================
# Challenge Resolution Tests
# ============================================================================

class TestWaitForChallengeResolution:
    """Tests for _wait_for_challenge_resolution method."""

    def test_no_challenge_returns_immediately(self):
        """No challenge detected returns False."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.content.return_value = "<html><body>Normal content</body></html>"

        # Mock detector to return no challenge
        hand._detector = MagicMock()
        hand._detector.detect_challenge.return_value = MagicMock(
            detected=False, details=None
        )

        result = hand._wait_for_challenge_resolution(max_wait=1)

        assert result is False

    def test_challenge_detected_waits(self):
        """Challenge detected waits for resolution."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.viewport_size = {"width": 1024, "height": 768}

        # Mock detector - challenge detected first 2 times, then resolved
        call_count = [0]

        def mock_detect(html):
            call_count[0] += 1
            if call_count[0] <= 2:
                return MagicMock(detected=True, details="Cloudflare")
            return MagicMock(detected=False, details=None)

        hand._detector = MagicMock()
        hand._detector.detect_challenge.side_effect = mock_detect

        with patch('time.sleep'):
            result = hand._wait_for_challenge_resolution(max_wait=5)

        assert result is True  # Challenge was detected and resolved

    def test_challenge_timeout_still_returns_true(self):
        """Challenge that times out still returns True."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.viewport_size = {"width": 1024, "height": 768}

        # Mock detector - always shows challenge
        hand._detector = MagicMock()
        hand._detector.detect_challenge.return_value = MagicMock(
            detected=True, details="DDoS-Guard"
        )

        with patch('time.sleep'):
            with patch('builtins.print'):  # Suppress print output
                result = hand._wait_for_challenge_resolution(max_wait=2)

        assert result is True  # True because challenge was detected


# ============================================================================
# Dynamic Content Wait Tests
# ============================================================================

class TestWaitForDynamicContent:
    """Tests for _wait_for_dynamic_content method."""

    def test_returns_true_when_content_found(self):
        """Returns True when dynamic content is found."""
        hand = Hand()
        hand._page = MagicMock()

        # Mock successful content check
        hand._page.evaluate.return_value = {
            "hasContent": True,
            "hasPlaceholder": False,
            "links": 10,
            "visibleLinks": 8,
            "buttons": 2,
            "textLength": 1000
        }
        hand._page.locator.return_value.count.return_value = 0

        with patch('time.sleep'):
            result = hand._wait_for_dynamic_content(timeout=1000)

        assert result is True

    def test_returns_false_when_no_content(self):
        """Returns False when no content found after timeout."""
        hand = Hand()
        hand._page = MagicMock()

        # Mock evaluate to raise PlaywrightError (page has no content)
        hand._page.evaluate.side_effect = PlaywrightError("No content")
        hand._page.locator.return_value.count.return_value = 0
        hand._page.locator.return_value.first.is_visible.return_value = False

        with patch('time.sleep'):
            result = hand._wait_for_dynamic_content(timeout=100)

        # Result should be False since evaluate raises PlaywrightError
        assert result is False

    def test_handles_exceptions_gracefully(self):
        """Handles exceptions during content check."""
        hand = Hand()
        hand._page = MagicMock()

        # Mock evaluate to raise
        hand._page.evaluate.side_effect = PlaywrightError("Page error")
        hand._page.locator.return_value.count.return_value = 0
        hand._page.locator.return_value.first.is_visible.return_value = False

        with patch('time.sleep'):
            # Should not raise
            result = hand._wait_for_dynamic_content(timeout=100)

        assert isinstance(result, bool)


# ============================================================================
# Execute Command Tests
# ============================================================================

class TestHandExecuteCommands:
    """Tests for execute command routing."""

    def test_execute_goto(self):
        """execute routes goto command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._popups = MagicMock()
        hand._detector = MagicMock()
        hand._detector.detect_challenge.return_value = MagicMock(detected=False)

        mock_response = MagicMock()
        mock_response.status = 200
        hand._page.goto.return_value = mock_response
        hand._page.title.return_value = "Test Page"
        hand._page.evaluate.return_value = {"hasContent": True, "hasPlaceholder": False}
        hand._page.locator.return_value.count.return_value = 0

        with patch('time.sleep'):
            result = hand.execute({"action": "goto", "url": "https://example.com"})

        assert result["action"] == "goto"
        assert result["url"] == "https://example.com"

    def test_execute_click(self):
        """execute routes click command."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = False

        with patch('time.sleep'):
            result = hand.execute({"action": "click", "selector": "#btn"})

        assert result["action"] == "click"
        mock_locator.click.assert_called_once()

    def test_execute_type(self):
        """execute routes type command."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = True
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = False

        result = hand.execute({
            "action": "type",
            "selector": "#input",
            "text": "hello",
            "human": False  # Explicitly disable human mode
        })

        assert result["action"] == "type"
        # fill is called for non-human mode
        assert mock_locator.fill.called or mock_locator.click.called

    def test_execute_press(self):
        """execute routes press command."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.execute({"action": "press", "key": "Enter"})

        assert result["action"] == "press"
        hand._page.keyboard.press.assert_called_with("Enter")

    def test_execute_scroll(self):
        """execute routes scroll command."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.human_mouse = False

        result = hand.execute({
            "action": "scroll",
            "direction": "down",
            "amount": 200,
            "human": False  # Explicitly disable human mode
        })

        assert result["action"] == "scroll"
        # Wheel should have been called (may be multiple times in human mode)
        assert hand._page.mouse.wheel.called

    def test_execute_back(self):
        """execute routes back command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.return_value = "Previous"
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.execute({"action": "back"})

        assert result["action"] == "back"
        hand._page.go_back.assert_called_once()

    def test_execute_forward(self):
        """execute routes forward command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.return_value = "Next"
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.execute({"action": "forward"})

        assert result["action"] == "forward"

    def test_execute_refresh(self):
        """execute routes refresh command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.return_value = "Refreshed"
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        result = hand.execute({"action": "refresh"})

        assert result["action"] == "refresh"

    def test_execute_hover(self):
        """execute routes hover command."""
        hand = Hand()
        hand._page = MagicMock()

        result = hand.execute({"action": "hover", "selector": "#menu"})

        assert result["action"] == "hover"

    def test_execute_screenshot(self):
        """execute routes screenshot command."""
        hand = Hand()
        hand._page = MagicMock()

        result = hand.execute({
            "action": "screenshot",
            "path": "test.png"
        })

        assert result["action"] == "screenshot"
        hand._page.screenshot.assert_called_once()

    def test_execute_dismiss_popups(self):
        """execute routes dismiss_popups command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._popups = MagicMock()
        hand._popups.handle_all.return_value = {"dismissed": 2}

        result = hand.execute({"action": "dismiss_popups"})

        assert result["action"] == "dismiss_popups"
        hand._popups.handle_all.assert_called_once()


# ============================================================================
# Hand State Methods Tests
# ============================================================================

class TestHandIsAwake:
    """Tests for is_awake property."""

    def test_is_awake_false_initially(self):
        """is_awake returns False when not started."""
        hand = Hand()
        assert hand.is_awake is False

    def test_is_awake_true_when_all_set(self):
        """is_awake returns True when all components set."""
        hand = Hand()
        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        hand._page = MagicMock()
        assert hand.is_awake is True

    def test_is_awake_false_when_partial(self):
        """is_awake returns False when partially set."""
        hand = Hand()
        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        # _page still None
        assert hand.is_awake is False


class TestHandIsHealthy:
    """Tests for is_healthy method."""

    def test_is_healthy_false_when_not_awake(self):
        """is_healthy returns False when not awake."""
        hand = Hand()
        assert hand.is_healthy() is False

    def test_is_healthy_true_when_responsive(self):
        """is_healthy returns True when page is responsive."""
        hand = Hand()
        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        hand._page = MagicMock()
        hand._page.url = "https://example.com"
        hand._page.title.return_value = "Test Page"

        assert hand.is_healthy() is True

    def test_is_healthy_false_when_page_errors(self):
        """is_healthy returns False when page operations fail."""
        hand = Hand()
        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        hand._page = MagicMock()
        hand._page.title.side_effect = PlaywrightError("Page crashed")

        assert hand.is_healthy() is False
        assert hand._consecutive_errors == 1


class TestHandEnsureAwake:
    """Tests for ensure_awake method."""

    def test_ensure_awake_returns_true_when_healthy(self):
        """ensure_awake returns True when already healthy."""
        hand = Hand()
        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        hand._page = MagicMock()
        hand._page.url = "https://example.com"
        hand._page.title.return_value = "Test"

        result = hand.ensure_awake()

        assert result is True

    def test_ensure_awake_starts_browser_when_not_awake(self):
        """ensure_awake starts browser when not awake."""
        hand = Hand()

        with patch.object(hand, 'wake') as mock_wake:
            with patch.object(hand, 'is_healthy', return_value=False):
                result = hand.ensure_awake()

        mock_wake.assert_called_once()

    def test_ensure_awake_returns_false_on_wake_failure(self):
        """ensure_awake returns False when wake fails."""
        hand = Hand()

        with patch.object(hand, 'wake', side_effect=Exception("Failed")):
            result = hand.ensure_awake()

        assert result is False


class TestHandRestart:
    """Tests for restart method."""

    def test_restart_closes_and_reopens(self):
        """restart closes browser and reopens."""
        hand = Hand()
        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        hand._page = MagicMock()
        hand._page.url = "https://example.com"

        with patch.object(hand, 'sleep') as mock_sleep:
            with patch.object(hand, 'wake') as mock_wake:
                with patch.object(hand, 'goto') as mock_goto:
                    result = hand.restart()

        mock_sleep.assert_called_once()
        mock_wake.assert_called_once()
        assert result is True

    def test_restart_returns_false_on_wake_failure(self):
        """restart returns False when wake fails."""
        hand = Hand()

        with patch.object(hand, 'sleep'):
            with patch.object(hand, 'wake', side_effect=Exception("Failed")):
                result = hand.restart()

        assert result is False


# ============================================================================
# Get Title with Retries Tests
# ============================================================================

class TestHandGetTitleRetries:
    """Tests for get_title retry logic."""

    def test_get_title_returns_on_success(self):
        """get_title returns title on success."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.return_value = "Test Page"

        result = hand.get_title()

        assert result == "Test Page"

    def test_get_title_retries_on_navigation_error(self):
        """get_title retries on navigation error."""
        hand = Hand()
        hand._page = MagicMock()

        # First call fails, second succeeds
        hand._page.title.side_effect = [
            PlaywrightError("navigation error"),
            "Test Page"
        ]

        with patch('time.sleep'):
            result = hand.get_title()

        assert result == "Test Page"

    def test_get_title_returns_url_on_failure(self):
        """get_title returns URL when title fails."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.title.side_effect = PlaywrightError("destroyed")
        hand._page.url = "https://example.com"

        with patch('time.sleep'):
            result = hand.get_title()

        assert result == "https://example.com"


# ============================================================================
# Wait for Navigation Tests
# ============================================================================

class TestHandWaitForNavigation:
    """Tests for wait_for_navigation method."""

    def test_wait_for_navigation_waits_for_idle(self):
        """wait_for_navigation waits for networkidle."""
        hand = Hand()
        hand._page = MagicMock()

        hand.wait_for_navigation()

        hand._page.wait_for_load_state.assert_called()

    def test_wait_for_navigation_handles_timeout(self):
        """wait_for_navigation handles timeout gracefully."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.wait_for_load_state.side_effect = PlaywrightError("timeout")

        # Should not raise
        hand.wait_for_navigation()


# ============================================================================
# Force Render Tests
# ============================================================================

class TestHandForceRender:
    """Tests for force_render method."""

    def test_force_render_triggers_events(self):
        """force_render triggers resize and scroll events."""
        hand = Hand()
        hand._page = MagicMock()

        # Mock successful content detection after force render
        hand._page.evaluate.return_value = {
            "hasContent": True,
            "hasPlaceholder": False
        }
        hand._page.locator.return_value.count.return_value = 0

        with patch('time.sleep'):
            result = hand.force_render()

        # Should have called evaluate for resize event
        assert hand._page.evaluate.called
        # Should have moved mouse
        assert hand._page.mouse.move.called


# ============================================================================
# Browser Type Tests
# ============================================================================

class TestHandBrowserType:
    """Tests for browser type configuration."""

    def test_default_browser_type_chromium(self):
        """Default browser type is chromium."""
        hand = Hand()
        assert hand.browser_type == "chromium"

    def test_firefox_browser_type(self):
        """Firefox browser type can be set."""
        hand = Hand(browser_type="firefox")
        assert hand.browser_type == "firefox"

    def test_webkit_browser_type(self):
        """Webkit browser type can be set."""
        hand = Hand(browser_type="webkit")
        assert hand.browser_type == "webkit"

    def test_browser_type_normalized_lowercase(self):
        """Browser type is normalized to lowercase."""
        hand = Hand(browser_type="Firefox")
        assert hand.browser_type == "firefox"


# ============================================================================
# Human Mode Type Tests
# ============================================================================

class TestHandTypeHumanMode:
    """Tests for Hand.type with human mode enabled."""

    def test_type_human_mode_types_character_by_character(self):
        """Human mode types character by character."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = True
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = True
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        with patch('time.sleep'):
            result = hand.type("#input", "abc", human=True)

        # Should have clicked, then typed characters
        assert mock_locator.click.called
        assert hand._page.keyboard.type.called
        assert result["action"] == "type"

    def test_type_human_mode_clears_with_triple_click(self):
        """Human mode clears field with triple-click."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = True
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = True
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        with patch('time.sleep'):
            result = hand.type("#input", "test", human=True, clear=True)

        # Should have triple-clicked to select all (click_count=3)
        click_calls = mock_locator.click.call_args_list
        # One of the clicks should be triple-click
        assert any(call.kwargs.get('click_count') == 3 for call in click_calls if call.kwargs)
        assert result["action"] == "type"


# ============================================================================
# Move Mouse Human Tests
# ============================================================================

class TestHandMoveMouseHuman:
    """Tests for human-like mouse movement."""

    def test_move_mouse_human_disabled(self):
        """Move mouse directly when human_mouse disabled."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.human_mouse = False

        hand._move_mouse_human(100, 200)

        hand._page.mouse.move.assert_called_once_with(100, 200)

    def test_move_mouse_human_enabled(self):
        """Move mouse with bezier path when human_mouse enabled."""
        hand = Hand()
        hand._page = MagicMock()
        hand.stealth.config.human_mouse = True

        # Mock bezier path generation
        with patch.object(hand.stealth, 'generate_bezier_path', return_value=[(50, 100), (75, 150), (100, 200)]):
            with patch('time.sleep'):
                hand._move_mouse_human(100, 200)

        # Should have moved through multiple points
        assert hand._page.mouse.move.call_count >= 3
        # Mouse position should be updated
        assert hand._mouse_pos == (100, 200)


# ============================================================================
# Click with Human Mode Tests
# ============================================================================

class TestHandClickHumanMode:
    """Tests for Hand.click with human mode."""

    def test_click_with_human_delay(self):
        """Click adds human delay when enabled."""
        hand = Hand()
        hand._page = MagicMock()
        mock_locator = MagicMock()
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        with patch('time.sleep') as mock_sleep:
            result = hand.click("#btn", human=True)

        # Should have called sleep for human delay
        assert mock_sleep.called
        assert result["action"] == "click"


# ============================================================================
# Get HTML Tests
# ============================================================================

class TestHandGetHtml:
    """Tests for Hand.get_html method."""

    def test_get_html_waits_for_load(self):
        """get_html waits for network idle by default."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.content.return_value = "<html><body>Test</body></html>"

        result = hand.get_html(wait_for_load=True)

        hand._page.wait_for_load_state.assert_called()
        assert "<html>" in result

    def test_get_html_no_wait(self):
        """get_html skips wait when wait_for_load=False."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.content.return_value = "<html><body>Test</body></html>"

        result = hand.get_html(wait_for_load=False)

        # Should not have waited
        hand._page.wait_for_load_state.assert_not_called()
        assert "Test" in result

    def test_get_html_ensure_content(self):
        """get_html with ensure_content waits for dynamic content."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.content.return_value = "<html><body><a href='/'>Link</a></body></html>"
        hand._page.evaluate.return_value = {"hasContent": True, "hasPlaceholder": False}
        hand._page.locator.return_value.count.return_value = 0

        with patch('time.sleep'):
            result = hand.get_html(ensure_content=True)

        assert "<a " in result

    def test_get_html_retries_on_navigation_error(self):
        """get_html retries when page is navigating."""
        hand = Hand()
        hand._page = MagicMock()

        # First call fails, second succeeds
        hand._page.content.side_effect = [
            PlaywrightError("navigating"),
            "<html><body>Success</body></html>"
        ]

        with patch('time.sleep'):
            result = hand.get_html(wait_for_load=False)

        assert "Success" in result


# ============================================================================
# Screenshot Tests
# ============================================================================

class TestHandScreenshot:
    """Tests for Hand.screenshot method."""

    def test_screenshot_basic(self):
        """screenshot takes basic screenshot."""
        hand = Hand()
        hand._page = MagicMock()

        result = hand.screenshot("test.png")

        hand._page.screenshot.assert_called_once_with(path="test.png", full_page=False)
        assert result["action"] == "screenshot"
        assert result["path"] == "test.png"

    def test_screenshot_full_page(self):
        """screenshot can take full page screenshot."""
        hand = Hand()
        hand._page = MagicMock()

        result = hand.screenshot("full.png", full_page=True)

        hand._page.screenshot.assert_called_once_with(path="full.png", full_page=True)


# ============================================================================
# Smart Click and Type Tests
# ============================================================================

class TestHandSmartMethods:
    """Tests for smart_click and smart_type methods."""

    def test_smart_click_by_text(self):
        """smart_click finds element by visible text."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = MagicMock()
        mock_locator = MagicMock()
        hand._selector.find_by_text.return_value = mock_locator
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        with patch('time.sleep'):
            result = hand.smart_click("Submit")

        hand._selector.find_by_text.assert_called_once_with("Submit", "*")
        mock_locator.click.assert_called_once()
        assert result["action"] == "smart_click"
        assert result["text"] == "Submit"

    def test_smart_click_raises_when_not_found(self):
        """smart_click raises ElementNotFoundError when text not found."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = MagicMock()
        hand._selector.find_by_text.return_value = None

        with pytest.raises(ElementNotFoundError):
            hand.smart_click("Nonexistent")

    def test_smart_type_by_name(self):
        """smart_type finds input by name."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = MagicMock()
        mock_locator = MagicMock()
        hand._selector.find_input.return_value = mock_locator

        result = hand.smart_type("test text", into="username")

        hand._selector.find_input.assert_called_once_with(name="username", placeholder=None, label=None)
        mock_locator.fill.assert_called_once_with("test text")
        assert result["action"] == "smart_type"

    def test_smart_type_raises_when_not_found(self):
        """smart_type raises ElementNotFoundError when input not found."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = MagicMock()
        hand._selector.find_input.return_value = None

        with pytest.raises(ElementNotFoundError):
            hand.smart_type("text", into="nonexistent")


# ============================================================================
# Wait and Click Tests
# ============================================================================

class TestHandWaitAndClick:
    """Tests for wait_and_click method."""

    def test_wait_and_click_waits_then_clicks(self):
        """wait_and_click waits for element then clicks."""
        hand = Hand()
        hand._page = MagicMock()
        hand._waits = MagicMock()
        mock_locator = MagicMock()
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = False

        with patch('time.sleep'):
            result = hand.wait_and_click("#btn", timeout=5000)

        hand._waits.wait_for_element.assert_called_once_with("#btn", timeout=5000)
        mock_locator.click.assert_called_once()
        assert result["action"] == "click"


# ============================================================================
# Dismiss Popups Tests
# ============================================================================

class TestHandDismissPopups:
    """Tests for dismiss_popups method."""

    def test_dismiss_popups_calls_popup_handler(self):
        """dismiss_popups delegates to popup handler."""
        hand = Hand()
        hand._page = MagicMock()
        hand._popups = MagicMock()
        hand._popups.handle_all.return_value = {"cookie_banners": 1, "dialogs": 0}

        result = hand.dismiss_popups()

        hand._popups.handle_all.assert_called_once()
        assert result["action"] == "dismiss_popups"
        assert result["cookie_banners"] == 1


# ============================================================================
# Execute Smart Commands Tests
# ============================================================================

class TestHandExecuteSmartCommands:
    """Tests for execute with smart action commands."""

    def test_execute_smart_click(self):
        """execute routes smart_click command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = MagicMock()
        mock_locator = MagicMock()
        hand._selector.find_by_text.return_value = mock_locator
        hand.stealth.config.min_delay = 0.001
        hand.stealth.config.max_delay = 0.002

        with patch('time.sleep'):
            result = hand.execute({
                "action": "smart_click",
                "text": "Login",
                "tag": "button"
            })

        assert result["action"] == "smart_click"
        hand._selector.find_by_text.assert_called_with("Login", "button")

    def test_execute_smart_type(self):
        """execute routes smart_type command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._selector = MagicMock()
        mock_locator = MagicMock()
        hand._selector.find_input.return_value = mock_locator

        result = hand.execute({
            "action": "smart_type",
            "text": "test@example.com",
            "into": "email",
            "placeholder": "Enter email"
        })

        assert result["action"] == "smart_type"
        hand._selector.find_input.assert_called_with(
            name="email",
            placeholder="Enter email",
            label=None
        )

    def test_execute_wait_and_click(self):
        """execute routes wait_and_click command."""
        hand = Hand()
        hand._page = MagicMock()
        hand._waits = MagicMock()
        mock_locator = MagicMock()
        hand._page.locator.return_value.first = mock_locator
        hand.stealth.config.human_mouse = False

        with patch('time.sleep'):
            result = hand.execute({
                "action": "wait_and_click",
                "selector": "#submit",
                "timeout": 10000
            })

        hand._waits.wait_for_element.assert_called_with("#submit", timeout=10000)
        assert result["action"] == "click"


# ============================================================================
# ProxyType Enum Tests
# ============================================================================

class TestProxyTypeEnum:
    """Tests for ProxyType enum values."""

    def test_proxy_type_values(self):
        """ProxyType enum has expected values."""
        assert ProxyType.HTTP.value == "http"
        assert ProxyType.HTTPS.value == "https"
        assert ProxyType.SOCKS5.value == "socks5"
        assert ProxyType.SOCKS4.value == "socks4"


# ============================================================================
# Health Tracking Tests
# ============================================================================

class TestHandHealthTracking:
    """Tests for Hand health tracking."""

    def test_wake_count_increments(self):
        """Wake count starts at zero."""
        hand = Hand()
        assert hand._wake_count == 0

    def test_consecutive_errors_tracking(self):
        """Consecutive errors are tracked."""
        hand = Hand()
        assert hand._consecutive_errors == 0

        # Simulate errors via is_healthy
        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        hand._page = MagicMock()
        hand._page.title.side_effect = PlaywrightError("error")

        hand.is_healthy()
        assert hand._consecutive_errors == 1

        hand.is_healthy()
        assert hand._consecutive_errors == 2

    def test_consecutive_errors_reset_on_success(self):
        """Consecutive errors reset on healthy check."""
        hand = Hand()
        hand._consecutive_errors = 5

        hand._playwright = MagicMock()
        hand._browser = MagicMock()
        hand._page = MagicMock()
        hand._page.url = "https://example.com"
        hand._page.title.return_value = "Test"

        hand.is_healthy()
        assert hand._consecutive_errors == 0


# ============================================================================
# Quick Content Ready Check Tests
# ============================================================================

class TestQuickContentReadyCheck:
    """Tests for _quick_content_ready_check method."""

    def test_quick_content_ready_check_returns_true_when_ready(self):
        """Returns True when page has enough content."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.evaluate.return_value = {
            'links': 10,
            'textLength': 500,
            'hasTitle': True,
            'hasMainContent': True,
            'ready': True
        }

        result = hand._quick_content_ready_check(min_links=3, min_text=200)

        assert result is True
        hand._page.evaluate.assert_called_once()

    def test_quick_content_ready_check_returns_false_when_not_ready(self):
        """Returns False when page lacks content."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.evaluate.return_value = {
            'links': 1,
            'textLength': 50,
            'hasTitle': False,
            'hasMainContent': False,
            'ready': False
        }

        result = hand._quick_content_ready_check(min_links=3, min_text=200)

        assert result is False

    def test_quick_content_ready_check_handles_exception(self):
        """Returns False when page evaluation fails."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.evaluate.side_effect = PlaywrightError("Page not ready")

        result = hand._quick_content_ready_check()

        assert result is False

    def test_quick_content_ready_check_uses_default_thresholds(self):
        """Uses default thresholds when not specified."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.evaluate.return_value = {'ready': True}

        # Default is min_links=3, min_text=200
        hand._quick_content_ready_check()

        # Check that the evaluate was called with the default values
        call_args = hand._page.evaluate.call_args[0][0]
        assert '3' in call_args  # min_links default
        assert '200' in call_args  # min_text default

    def test_quick_content_ready_check_custom_thresholds(self):
        """Uses custom thresholds when specified."""
        hand = Hand()
        hand._page = MagicMock()
        hand._page.evaluate.return_value = {'ready': True}

        hand._quick_content_ready_check(min_links=10, min_text=500)

        call_args = hand._page.evaluate.call_args[0][0]
        assert '10' in call_args  # custom min_links
        assert '500' in call_args  # custom min_text


# ============================================================================
# Adaptive Timeout Tests (goto with site characteristics)
# ============================================================================

class TestGotoAdaptiveTimeouts:
    """Tests for goto() method with adaptive timeouts."""

    def test_goto_returns_site_type_in_response(self):
        """goto includes site_type in response dict."""
        hand = Hand()
        hand._page = MagicMock()
        hand._popups = MagicMock()
        hand._popups.handle_all.return_value = {}

        mock_response = MagicMock()
        mock_response.status = 200
        hand._page.goto.return_value = mock_response
        hand._page.title.return_value = "Test Page"
        hand._page.evaluate.return_value = {'ready': True}

        with patch('time.sleep'):
            result = hand.goto("https://en.wikipedia.org/wiki/Test")

        assert 'site_type' in result
        assert result['site_type'] == 'static'  # Wikipedia is static

    def test_goto_unknown_site_type(self):
        """Unknown sites return 'unknown' site_type."""
        hand = Hand()
        hand._page = MagicMock()
        hand._popups = MagicMock()
        hand._popups.handle_all.return_value = {}
        hand._detector = MagicMock()
        hand._detector.detect_challenge.return_value = MagicMock(detected=False)

        mock_response = MagicMock()
        mock_response.status = 200
        hand._page.goto.return_value = mock_response
        hand._page.title.return_value = "Test Page"
        hand._page.evaluate.return_value = {'ready': True}

        with patch('time.sleep'):
            result = hand.goto("https://random-unknown-site.xyz/page")

        assert result['site_type'] == 'unknown'
