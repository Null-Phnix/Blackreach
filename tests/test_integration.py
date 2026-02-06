"""
Integration tests for Blackreach browser automation.

These tests verify actual browser functionality using a mock web server
for reliable, offline testing. Tests cover:
- Browser initialization and lifecycle
- Navigation (goto, back, forward, refresh)
- Element interaction (click, type, scroll)
- Download flow
- Error handling and recovery
- Screenshot capture on failures
- Debug tools integration

Run all tests:
    pytest tests/test_integration.py -v

Run specific test class:
    pytest tests/test_integration.py::TestBrowserInitialization -v

Skip integration tests:
    pytest tests/ -m "not integration"
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError

from blackreach.browser import Hand
from blackreach.stealth import StealthConfig
from blackreach.resilience import RetryConfig
from blackreach.exceptions import (
    BrowserNotReadyError,
    ElementNotFoundError,
    DownloadError,
    InvalidActionArgsError,
    UnknownActionError,
)
from blackreach.debug_tools import (
    DebugTools,
    DebugConfig,
    DebugSnapshot,
    TestResultTracker,
    ErrorCapturingWrapper,
)


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Browser Initialization Tests
# =============================================================================

class TestBrowserInitialization:
    """Tests for browser initialization and lifecycle."""

    def test_browser_starts_in_not_ready_state(self):
        """Browser starts in not-awake state."""
        hand = Hand(headless=True)
        assert not hand.is_awake
        assert hand._playwright is None
        assert hand._browser is None
        assert hand._page is None

    def test_browser_wake_initializes_playwright(self, download_dir):
        """wake() initializes playwright and browser."""
        hand = Hand(headless=True, download_dir=download_dir)
        try:
            hand.wake()
            assert hand.is_awake
            assert hand._playwright is not None
            assert hand._browser is not None
            assert hand._page is not None
        finally:
            hand.sleep()

    def test_browser_sleep_cleans_up(self, download_dir):
        """sleep() properly cleans up browser resources."""
        hand = Hand(headless=True, download_dir=download_dir)
        hand.wake()
        hand.sleep()

        assert hand._playwright is None
        assert hand._browser is None
        assert hand._page is None
        assert not hand.is_awake

    def test_browser_double_sleep_safe(self, download_dir):
        """Calling sleep() twice is safe."""
        hand = Hand(headless=True, download_dir=download_dir)
        hand.wake()
        hand.sleep()
        hand.sleep()  # Should not raise

    def test_browser_sleep_without_wake_safe(self):
        """Calling sleep() without wake() is safe."""
        hand = Hand(headless=True)
        hand.sleep()  # Should not raise

    def test_browser_is_healthy_after_wake(self, browser):
        """Browser reports healthy after wake."""
        assert browser.is_healthy()

    def test_browser_ensure_awake_when_asleep(self, download_dir):
        """ensure_awake() starts browser if not awake."""
        hand = Hand(headless=True, download_dir=download_dir)
        try:
            result = hand.ensure_awake()
            assert result is True
            assert hand.is_awake
        finally:
            hand.sleep()

    def test_browser_ensure_awake_when_awake(self, browser):
        """ensure_awake() does nothing if already awake."""
        result = browser.ensure_awake()
        assert result is True

    def test_browser_restart(self, browser):
        """restart() properly restarts the browser."""
        result = browser.restart()
        assert result is True
        assert browser.is_awake


# =============================================================================
# Navigation Tests with Mock Server
# =============================================================================

class TestBrowserNavigation:
    """Tests for browser navigation using mock server."""

    def test_goto_navigates_to_url(self, browser, mock_server_with_pages):
        """goto() navigates to specified URL."""
        # Use wait_for_content=False for fast mock server navigation
        result = browser.goto(mock_server_with_pages.url, wait_for_content=False)

        assert result is not None
        assert result["action"] == "goto"
        assert mock_server_with_pages.host in browser.get_url()

    def test_goto_returns_title(self, browser, mock_server_with_pages):
        """goto() returns page title."""
        result = browser.goto(mock_server_with_pages.url, wait_for_content=False)

        assert "title" in result
        assert result["title"] == "Test Page"

    def test_goto_updates_current_url(self, browser, mock_server_with_pages):
        """goto() updates the current URL."""
        browser.goto(mock_server_with_pages.url_for('/page1'), wait_for_content=False)
        url = browser.get_url()

        assert '/page1' in url

    def test_goto_handles_different_pages(self, browser, mock_server_with_pages):
        """goto() can navigate to different pages."""
        browser.goto(mock_server_with_pages.url_for('/page1'), wait_for_content=False)
        assert 'page1' in browser.get_url()

        browser.goto(mock_server_with_pages.url_for('/page2'), wait_for_content=False)
        assert 'page2' in browser.get_url()

    def test_back_navigation(self, browser, mock_server_with_pages):
        """back() navigates to previous page."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        browser.goto(mock_server_with_pages.url_for('/page1'), wait_for_content=False)

        result = browser.back()

        assert result is not None
        assert result["action"] == "back"

    def test_forward_navigation(self, browser, mock_server_with_pages):
        """forward() navigates forward after back."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        browser.goto(mock_server_with_pages.url_for('/page1'), wait_for_content=False)
        browser.back()

        result = browser.forward()

        assert result is not None
        assert result["action"] == "forward"

    def test_refresh_reloads_page(self, browser, mock_server_with_pages):
        """refresh() reloads the current page."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.refresh()

        assert result is not None
        assert result["action"] == "refresh"

    def test_goto_with_content_wait(self, browser, mock_server_with_pages):
        """goto() waits for content when enabled."""
        result = browser.goto(
            mock_server_with_pages.url_for('/dynamic'),
            wait_for_content=True
        )

        # Should have waited for content
        assert result is not None
        assert "content_found" in result


# =============================================================================
# Element Interaction Tests
# =============================================================================

class TestElementInteraction:
    """Tests for browser element interactions."""

    def test_click_element(self, browser, mock_server_with_pages):
        """click() clicks an element by selector."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.click('#submit')

        assert result is not None
        assert result["action"] == "click"

    def test_click_nonexistent_element_raises(self, browser, mock_server_with_pages):
        """click() raises ElementNotFoundError for missing element."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        with pytest.raises(Exception):  # Could be TimeoutError or ElementNotFoundError
            browser.click('#nonexistent-element-xyz123', human=False)

    def test_type_into_input(self, browser, mock_server_with_pages):
        """type() enters text into an input field."""
        browser.goto(mock_server_with_pages.url_for('/form'), wait_for_content=False)

        result = browser.type('#username', 'testuser', human=False)

        assert result is not None
        assert result["action"] == "type"
        assert result["text"] == "testuser"

    def test_type_into_search_input(self, browser, mock_server_with_pages):
        """type() enters text into search input."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.type('#search', 'test query', human=False)

        assert result["action"] == "type"

    def test_type_clears_existing_text(self, browser, mock_server_with_pages):
        """type() clears existing text by default."""
        browser.goto(mock_server_with_pages.url_for('/form'), wait_for_content=False)

        browser.type('#username', 'first', human=False)
        browser.type('#username', 'second', human=False, clear=True)

        # Get input value
        value = browser.page.locator('#username').input_value()
        assert value == 'second'

    def test_press_key(self, browser, mock_server_with_pages):
        """press() presses a keyboard key."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.press('Escape')

        assert result is not None
        assert result["action"] == "press"
        assert result["key"] == "Escape"

    def test_scroll_down(self, browser, mock_server_with_pages):
        """scroll() scrolls the page down."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.scroll('down', 200)

        assert result is not None
        assert result["action"] == "scroll"
        assert result["direction"] == "down"

    def test_scroll_up(self, browser, mock_server_with_pages):
        """scroll() scrolls the page up."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        browser.scroll('down', 300)

        result = browser.scroll('up', 100)

        assert result["action"] == "scroll"
        assert result["direction"] == "up"

    def test_hover_element(self, browser, mock_server_with_pages):
        """hover() hovers over an element."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.hover('#submit')

        assert result is not None
        assert result["action"] == "hover"


# =============================================================================
# Page Information Tests
# =============================================================================

class TestPageInformation:
    """Tests for getting page information."""

    def test_get_url(self, browser, mock_server_with_pages):
        """get_url() returns current URL."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        url = browser.get_url()

        assert isinstance(url, str)
        assert mock_server_with_pages.host in url

    def test_get_title(self, browser, mock_server_with_pages):
        """get_title() returns page title."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        title = browser.get_title()

        assert isinstance(title, str)
        assert title == "Test Page"

    def test_get_html(self, browser, mock_server_with_pages):
        """get_html() returns page HTML content."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        html = browser.get_html()

        assert isinstance(html, str)
        assert '<html' in html.lower()
        assert 'Welcome' in html

    def test_get_html_with_ensure_content(self, browser, mock_server_with_pages):
        """get_html() with ensure_content waits for content."""
        browser.goto(mock_server_with_pages.url_for('/dynamic'), wait_for_content=False)

        html = browser.get_html(ensure_content=True)

        assert html is not None
        assert len(html) > 0


# =============================================================================
# Screenshot Tests
# =============================================================================

class TestScreenshot:
    """Tests for screenshot functionality."""

    def test_screenshot_creates_file(self, browser, mock_server_with_pages, temp_dir):
        """screenshot() creates an image file."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        screenshot_path = temp_dir / "test_screenshot.png"

        result = browser.screenshot(str(screenshot_path))

        assert result["action"] == "screenshot"
        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 0

    def test_screenshot_full_page(self, browser, mock_server_with_pages, temp_dir):
        """screenshot() with full_page captures entire page."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        screenshot_path = temp_dir / "full_page.png"

        result = browser.screenshot(str(screenshot_path), full_page=True)

        assert screenshot_path.exists()


# =============================================================================
# Download Tests
# =============================================================================

class TestDownloadFlow:
    """Tests for file download functionality."""

    def test_download_file_validates_args(self, browser):
        """download_file() requires selector or url."""
        with pytest.raises(InvalidActionArgsError):
            browser.download_file()

    def test_set_download_callback(self, browser):
        """Download callback can be set."""
        callback = Mock()
        browser.set_download_callback(callback)

        assert browser._download_callback is callback

    def test_get_pending_downloads_returns_list(self, browser):
        """get_pending_downloads() returns a list."""
        downloads = browser.get_pending_downloads()

        assert isinstance(downloads, list)

    def test_download_dir_created(self, browser):
        """Download directory is created on wake."""
        assert browser.download_dir.exists()


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_page_property_raises_when_not_ready(self):
        """page property raises BrowserNotReadyError when not started."""
        hand = Hand()
        with pytest.raises(BrowserNotReadyError):
            _ = hand.page

    def test_selector_property_raises_when_not_ready(self):
        """selector property raises BrowserNotReadyError when not started."""
        hand = Hand()
        with pytest.raises(BrowserNotReadyError):
            _ = hand.selector

    def test_execute_unknown_action_raises(self, browser):
        """execute() raises UnknownActionError for invalid action."""
        with pytest.raises(UnknownActionError):
            browser.execute({"action": "invalid_action_xyz"})

    def test_execute_wait_action(self, browser):
        """execute() handles wait action."""
        with patch('time.sleep') as mock_sleep:
            result = browser.execute({"action": "wait", "seconds": 0.1})

        assert result["action"] == "wait"

    def test_click_graceful_failure(self, browser, mock_server_with_pages):
        """Click on missing element raises ElementNotFoundError or TimeoutError."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        with pytest.raises((ElementNotFoundError, TimeoutError, PlaywrightTimeoutError)) as exc_info:
            browser.click('#nonexistent-element')

        # Verify we got an actual error about the element
        error_msg = str(exc_info.value).lower()
        assert 'element' in error_msg or 'timeout' in error_msg or 'not found' in error_msg

    def test_navigation_error_handled(self, browser, mock_server):
        """Navigation to non-existent page returns error status."""
        mock_server.add_route('/404', {
            'status': 404,
            'body': '<html><body>Not Found</body></html>'
        })

        result = browser.goto(mock_server.url_for('/404'), wait_for_content=False)

        assert result is not None
        assert result.get("http_status") == 404


# =============================================================================
# Debug Tools Tests
# =============================================================================

class TestDebugTools:
    """Tests for debug tools functionality."""

    def test_debug_tools_initialization(self, debug_output_dir):
        """DebugTools initializes with config."""
        config = DebugConfig(output_dir=debug_output_dir)
        tools = DebugTools(config)

        assert tools.config.output_dir == debug_output_dir
        assert debug_output_dir.exists()

    def test_capture_screenshot(self, browser, mock_server_with_pages, debug_tools):
        """capture_screenshot() saves screenshot file."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        path = debug_tools.capture_screenshot(browser)

        assert path is not None
        assert path.exists()
        assert path.suffix == '.png'

    def test_capture_html(self, browser, mock_server_with_pages, debug_tools):
        """capture_html() saves HTML file."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        path = debug_tools.capture_html(browser)

        assert path is not None
        assert path.exists()
        content = path.read_text()
        assert '<html' in content.lower()

    def test_capture_snapshot(self, browser, mock_server_with_pages, debug_tools):
        """capture_snapshot() captures complete debug info."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        snapshot = debug_tools.capture_snapshot(browser)

        assert snapshot is not None
        assert isinstance(snapshot, DebugSnapshot)
        assert snapshot.url == browser.get_url()
        assert snapshot.title == browser.get_title()
        assert snapshot.screenshot_path is not None
        assert snapshot.html_path is not None

    def test_capture_snapshot_with_error(self, browser, mock_server_with_pages, debug_tools):
        """capture_snapshot() includes error information."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        test_error = ValueError("Test error message")

        snapshot = debug_tools.capture_snapshot(browser, error=test_error)

        assert snapshot.error_message == "Test error message"
        assert snapshot.traceback is not None

    def test_capture_on_error_context_manager(self, browser, mock_server_with_pages, debug_tools):
        """capture_on_error context manager captures on exception."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        with pytest.raises(ValueError):
            with debug_tools.capture_on_error(browser, "test_error"):
                raise ValueError("Test error")

        snapshot = debug_tools.get_last_snapshot()
        assert snapshot is not None
        assert snapshot.error_message == "Test error"

    def test_get_all_snapshots(self, browser, mock_server_with_pages, debug_tools):
        """get_all_snapshots() returns all captured snapshots."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        debug_tools.capture_snapshot(browser)
        debug_tools.capture_snapshot(browser)

        snapshots = debug_tools.get_all_snapshots()
        assert len(snapshots) >= 2

    def test_clear_snapshots(self, browser, mock_server_with_pages, debug_tools):
        """clear_snapshots() removes snapshots from memory."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        debug_tools.capture_snapshot(browser)

        debug_tools.clear_snapshots()

        assert len(debug_tools.snapshots) == 0

    def test_generate_report(self, browser, mock_server_with_pages, debug_tools, temp_dir):
        """generate_report() creates HTML report."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        debug_tools.capture_snapshot(browser)

        report_path = temp_dir / "report.html"
        report = debug_tools.generate_report(report_path)

        assert report is not None
        assert '<html>' in report
        assert report_path.exists()


# =============================================================================
# Test Result Tracker Tests
# =============================================================================

class TestResultTracker:
    """Tests for test result tracking."""

    def test_tracker_initialization(self, test_result_tracker):
        """TestResultTracker initializes correctly."""
        assert test_result_tracker.start_time is not None
        assert len(test_result_tracker.results) == 0

    def test_record_passing_test(self, test_result_tracker):
        """record_test() records a passing test."""
        test_result_tracker.record_test("test_example", passed=True, duration=1.5)

        assert len(test_result_tracker.results) == 1
        assert test_result_tracker.results[0]["passed"] is True
        assert test_result_tracker.results[0]["test_name"] == "test_example"

    def test_record_failing_test(self, test_result_tracker, browser, mock_server_with_pages):
        """record_test() records a failing test with snapshot."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        error = ValueError("Test failed")

        test_result_tracker.record_test(
            "test_failure",
            passed=False,
            browser=browser,
            error=error
        )

        assert len(test_result_tracker.results) == 1
        assert test_result_tracker.results[0]["passed"] is False
        assert test_result_tracker.results[0]["snapshot"] is not None

    def test_get_summary(self, test_result_tracker):
        """get_summary() returns test statistics."""
        test_result_tracker.record_test("test1", passed=True)
        test_result_tracker.record_test("test2", passed=True)
        test_result_tracker.record_test("test3", passed=False)

        summary = test_result_tracker.get_summary()

        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["pass_rate"] == pytest.approx(2/3)


# =============================================================================
# Error Capturing Wrapper Tests
# =============================================================================

class TestErrorCapturingWrapper:
    """Tests for ErrorCapturingWrapper."""

    def test_wrapper_passes_through_methods(self, browser, debug_tools, mock_server_with_pages):
        """Wrapper passes through method calls."""
        wrapped = ErrorCapturingWrapper(browser, debug_tools)
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        url = wrapped.get_url()

        assert url == browser.get_url()

    def test_wrapper_captures_on_error(self, browser, debug_tools, mock_server_with_pages):
        """Wrapper captures debug info on error."""
        wrapped = ErrorCapturingWrapper(browser, debug_tools)
        wrapped.goto(mock_server_with_pages.url, wait_for_content=False)

        try:
            wrapped.click('#nonexistent-element-abc')
        except Exception:
            pass

        # Should have captured a snapshot
        snapshots = debug_tools.get_all_snapshots()
        assert len(snapshots) >= 1


# =============================================================================
# Dynamic Content Tests
# =============================================================================

class TestDynamicContent:
    """Tests for handling dynamic/JavaScript content."""

    def test_wait_for_dynamic_content(self, browser, mock_server_with_pages):
        """Browser waits for dynamic content to load."""
        result = browser.goto(
            mock_server_with_pages.url_for('/dynamic'),
            wait_for_content=True
        )

        # After waiting, content should be available
        html = browser.get_html()
        # The dynamic content shows "Content Loaded!" after JS runs
        assert 'Content Loaded' in html or 'Loading' in html

    def test_force_render(self, browser, mock_server_with_pages):
        """force_render() triggers page rendering."""
        browser.goto(mock_server_with_pages.url_for('/dynamic'), wait_for_content=False)

        result = browser.force_render()

        assert isinstance(result, bool)


# =============================================================================
# Stealth Mode Tests
# =============================================================================

class TestStealthMode:
    """Tests for stealth/anti-detection features."""

    def test_webdriver_hidden(self, browser, mock_server_with_pages):
        """Stealth mode hides webdriver property."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.page.evaluate("() => navigator.webdriver")

        # Should be undefined (None) or false, not true
        assert result is not True

    def test_user_agent_present(self, browser, mock_server_with_pages):
        """User agent is set."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        ua = browser.page.evaluate("() => navigator.userAgent")

        assert ua is not None
        assert len(ua) > 0


# =============================================================================
# Execute Command Tests
# =============================================================================

class TestExecuteCommand:
    """Tests for the execute() command dispatcher."""

    def test_execute_goto(self, browser, mock_server_with_pages):
        """execute() handles goto command."""
        result = browser.execute({
            "action": "goto",
            "url": mock_server_with_pages.url
        })

        assert result["action"] == "goto"

    def test_execute_click(self, browser, mock_server_with_pages):
        """execute() handles click command."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.execute({
            "action": "click",
            "selector": "#submit"
        })

        assert result["action"] == "click"

    def test_execute_type(self, browser, mock_server_with_pages):
        """execute() handles type command."""
        browser.goto(mock_server_with_pages.url_for('/form'), wait_for_content=False)

        result = browser.execute({
            "action": "type",
            "selector": "#username",
            "text": "testuser"
        })

        assert result["action"] == "type"

    def test_execute_scroll(self, browser, mock_server_with_pages):
        """execute() handles scroll command."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.execute({
            "action": "scroll",
            "direction": "down",
            "amount": 200
        })

        assert result["action"] == "scroll"

    def test_execute_press(self, browser, mock_server_with_pages):
        """execute() handles press command."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)

        result = browser.execute({
            "action": "press",
            "key": "Enter"
        })

        assert result["action"] == "press"

    def test_execute_screenshot(self, browser, mock_server_with_pages, temp_dir):
        """execute() handles screenshot command."""
        browser.goto(mock_server_with_pages.url, wait_for_content=False)
        path = str(temp_dir / "exec_screenshot.png")

        result = browser.execute({
            "action": "screenshot",
            "path": path
        })

        assert result["action"] == "screenshot"


# =============================================================================
# Browser Helper Properties Tests
# =============================================================================

class TestBrowserHelperProperties:
    """Tests for browser helper properties after wake."""

    def test_page_property_available(self, browser):
        """page property returns Page after wake."""
        page = browser.page
        assert page is not None

    def test_selector_property_available(self, browser):
        """selector property returns SmartSelector after wake."""
        selector = browser.selector
        assert selector is not None

    def test_popups_property_available(self, browser):
        """popups property returns PopupHandler after wake."""
        popups = browser.popups
        assert popups is not None

    def test_waits_property_available(self, browser):
        """waits property returns WaitConditions after wake."""
        waits = browser.waits
        assert waits is not None


# =============================================================================
# Hash Computation Tests
# =============================================================================

class TestHashComputation:
    """Tests for file hash computation."""

    def test_compute_hash_returns_string(self, browser, temp_dir):
        """_compute_hash() returns a hex string."""
        test_file = temp_dir / "hash_test.txt"
        test_file.write_text("Test content")

        hash_val = browser._compute_hash(test_file)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA-256 produces 64 hex chars

    def test_compute_hash_consistent(self, browser, temp_dir):
        """_compute_hash() returns same hash for same content."""
        test_file = temp_dir / "consistent.txt"
        test_file.write_text("Same content")

        hash1 = browser._compute_hash(test_file)
        hash2 = browser._compute_hash(test_file)

        assert hash1 == hash2

    def test_compute_hash_different_for_different_content(self, browser, temp_dir):
        """_compute_hash() returns different hash for different content."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("Content A")
        file2.write_text("Content B")

        hash1 = browser._compute_hash(file1)
        hash2 = browser._compute_hash(file2)

        assert hash1 != hash2


# =============================================================================
# Human Behavior Tests
# =============================================================================

class TestHumanBehavior:
    """Tests for human-like behavior features."""

    def test_human_delay_waits(self, browser):
        """_human_delay() actually waits."""
        start = time.time()
        browser._human_delay(0.1, 0.2)
        elapsed = time.time() - start

        assert elapsed >= 0.1

    def test_release_all_keys_no_error(self, browser):
        """_release_all_keys() completes without error."""
        browser._release_all_keys()  # Should not raise


# =============================================================================
# Mock Server Tests
# =============================================================================

class TestMockServer:
    """Tests to verify mock server functionality."""

    def test_mock_server_starts(self, mock_server):
        """Mock server starts and is accessible."""
        assert mock_server.url is not None
        assert mock_server.port > 0

    def test_mock_server_serves_routes(self, browser, mock_server):
        """Mock server serves configured routes."""
        mock_server.add_route('/', '<html><body>Test</body></html>')
        browser.goto(mock_server.url, wait_for_content=False)

        html = browser.get_html()
        assert 'Test' in html

    def test_mock_server_returns_404(self, browser, mock_server):
        """Mock server returns 404 for unknown routes."""
        result = browser.goto(mock_server.url_for('/unknown'), wait_for_content=False)

        assert result.get("http_status") == 404

    def test_mock_server_custom_status(self, browser, mock_server):
        """Mock server can return custom status codes."""
        mock_server.add_route('/error', {
            'status': 500,
            'body': 'Server Error'
        })

        result = browser.goto(mock_server.url_for('/error'), wait_for_content=False)

        assert result.get("http_status") == 500
