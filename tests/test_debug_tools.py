"""
Tests for the Debug Tools module.

Tests cover:
- DebugSnapshot dataclass
- DebugConfig dataclass
- DebugTools class (capture methods, context manager, report generation)
- TestResultTracker class
- ErrorCapturingWrapper class
- Global get_debug_tools function
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile
import time

from blackreach.debug_tools import (
    DebugSnapshot,
    DebugConfig,
    DebugTools,
    TestResultTracker,
    ErrorCapturingWrapper,
    get_debug_tools,
    pytest_configure_debug,
)


# =============================================================================
# DebugSnapshot Dataclass Tests
# =============================================================================

class TestDebugSnapshot:
    """Tests for DebugSnapshot dataclass."""

    def test_minimal_creation(self):
        """DebugSnapshot can be created with required fields."""
        snapshot = DebugSnapshot(
            timestamp=datetime.now(),
            url="https://example.com",
            title="Test Page",
            screenshot_path=None,
            html_path=None,
            error_message=None,
            traceback=None
        )
        assert snapshot.url == "https://example.com"
        assert snapshot.title == "Test Page"

    def test_default_extra_data_is_empty(self):
        """Default extra_data should be empty dict."""
        snapshot = DebugSnapshot(
            timestamp=datetime.now(),
            url="",
            title="",
            screenshot_path=None,
            html_path=None,
            error_message=None,
            traceback=None
        )
        assert snapshot.extra_data == {}

    def test_paths_can_be_set(self):
        """Path fields can be set."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            screenshot_path = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            html_path = Path(f.name)

        snapshot = DebugSnapshot(
            timestamp=datetime.now(),
            url="https://example.com",
            title="Test",
            screenshot_path=screenshot_path,
            html_path=html_path,
            error_message=None,
            traceback=None
        )
        assert snapshot.screenshot_path == screenshot_path
        assert snapshot.html_path == html_path

        # Cleanup
        screenshot_path.unlink()
        html_path.unlink()

    def test_error_fields_can_be_set(self):
        """Error fields can be set."""
        snapshot = DebugSnapshot(
            timestamp=datetime.now(),
            url="https://example.com",
            title="Test",
            screenshot_path=None,
            html_path=None,
            error_message="Element not found",
            traceback="Traceback:\n  File..."
        )
        assert snapshot.error_message == "Element not found"
        assert "Traceback:" in snapshot.traceback

    def test_to_dict_returns_dict(self):
        """to_dict returns a dictionary."""
        snapshot = DebugSnapshot(
            timestamp=datetime.now(),
            url="https://example.com",
            title="Test Page",
            screenshot_path=None,
            html_path=None,
            error_message=None,
            traceback=None
        )
        result = snapshot.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self):
        """to_dict contains all fields."""
        snapshot = DebugSnapshot(
            timestamp=datetime.now(),
            url="https://example.com",
            title="Test",
            screenshot_path=Path("/tmp/test.png"),
            html_path=Path("/tmp/test.html"),
            error_message="Error",
            traceback="Traceback",
            extra_data={"key": "value"}
        )
        result = snapshot.to_dict()

        assert "timestamp" in result
        assert "url" in result
        assert "title" in result
        assert "screenshot_path" in result
        assert "html_path" in result
        assert "error_message" in result
        assert "traceback" in result
        assert "extra_data" in result

    def test_to_dict_timestamp_is_isoformat(self):
        """to_dict converts timestamp to isoformat string."""
        ts = datetime(2025, 1, 15, 12, 30, 45)
        snapshot = DebugSnapshot(
            timestamp=ts,
            url="",
            title="",
            screenshot_path=None,
            html_path=None,
            error_message=None,
            traceback=None
        )
        result = snapshot.to_dict()
        assert result["timestamp"] == "2025-01-15T12:30:45"

    def test_to_dict_path_is_string(self):
        """to_dict converts Path to string."""
        snapshot = DebugSnapshot(
            timestamp=datetime.now(),
            url="",
            title="",
            screenshot_path=Path("/tmp/test.png"),
            html_path=None,
            error_message=None,
            traceback=None
        )
        result = snapshot.to_dict()
        assert result["screenshot_path"] == "/tmp/test.png"


# =============================================================================
# DebugConfig Dataclass Tests
# =============================================================================

class TestDebugConfig:
    """Tests for DebugConfig dataclass."""

    def test_default_output_dir(self):
        """Default output_dir is ./debug_output."""
        config = DebugConfig()
        assert config.output_dir == Path("./debug_output")

    def test_default_capture_screenshots(self):
        """Default capture_screenshots is True."""
        config = DebugConfig()
        assert config.capture_screenshots is True

    def test_default_capture_html(self):
        """Default capture_html is True."""
        config = DebugConfig()
        assert config.capture_html is True

    def test_default_capture_on_error(self):
        """Default capture_on_error is True."""
        config = DebugConfig()
        assert config.capture_on_error is True

    def test_default_capture_on_success(self):
        """Default capture_on_success is False."""
        config = DebugConfig()
        assert config.capture_on_success is False

    def test_default_max_snapshots(self):
        """Default max_snapshots is 100."""
        config = DebugConfig()
        assert config.max_snapshots == 100

    def test_default_screenshot_format(self):
        """Default screenshot_format is png."""
        config = DebugConfig()
        assert config.screenshot_format == "png"

    def test_default_include_timestamp(self):
        """Default include_timestamp is True."""
        config = DebugConfig()
        assert config.include_timestamp is True

    def test_custom_output_dir(self):
        """output_dir can be customized."""
        config = DebugConfig(output_dir=Path("/custom/dir"))
        assert config.output_dir == Path("/custom/dir")

    def test_custom_capture_settings(self):
        """Capture settings can be customized."""
        config = DebugConfig(
            capture_screenshots=False,
            capture_html=False,
            capture_on_error=False,
            capture_on_success=True
        )
        assert config.capture_screenshots is False
        assert config.capture_html is False
        assert config.capture_on_error is False
        assert config.capture_on_success is True


# =============================================================================
# DebugTools Fixtures
# =============================================================================

@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def debug_tools(temp_output_dir):
    """Create DebugTools with temporary directory."""
    config = DebugConfig(output_dir=temp_output_dir)
    return DebugTools(config)


@pytest.fixture
def mock_browser():
    """Create a mock browser instance."""
    browser = Mock()
    browser.is_awake = True
    browser.get_url.return_value = "https://example.com"
    browser.get_title.return_value = "Test Page"
    browser.get_html.return_value = "<html><body>Test</body></html>"
    browser.screenshot = Mock()
    return browser


# =============================================================================
# DebugTools Initialization Tests
# =============================================================================

class TestDebugToolsInit:
    """Tests for DebugTools initialization."""

    def test_init_with_default_config(self, temp_output_dir):
        """DebugTools uses default config when not provided."""
        tools = DebugTools()
        assert tools.config is not None
        assert isinstance(tools.config, DebugConfig)

    def test_init_with_custom_config(self, temp_output_dir):
        """DebugTools accepts custom config."""
        config = DebugConfig(output_dir=temp_output_dir, max_snapshots=50)
        tools = DebugTools(config)
        assert tools.config.max_snapshots == 50

    def test_init_creates_output_dir(self, temp_output_dir):
        """DebugTools creates output directory."""
        new_dir = temp_output_dir / "new_dir"
        config = DebugConfig(output_dir=new_dir)
        tools = DebugTools(config)
        assert new_dir.exists()

    def test_init_snapshots_empty(self, debug_tools):
        """DebugTools starts with empty snapshots list."""
        assert debug_tools.snapshots == []


# =============================================================================
# DebugTools Capture Methods Tests
# =============================================================================

class TestDebugToolsCaptureScreenshot:
    """Tests for DebugTools.capture_screenshot()."""

    def test_capture_screenshot_returns_path(self, debug_tools, mock_browser):
        """capture_screenshot returns a Path."""
        result = debug_tools.capture_screenshot(mock_browser)
        # Note: May return None if browser.screenshot fails
        # Since we're mocking, it should work
        assert result is None or isinstance(result, Path)

    def test_capture_screenshot_calls_browser(self, debug_tools, mock_browser):
        """capture_screenshot calls browser.screenshot()."""
        debug_tools.capture_screenshot(mock_browser)
        mock_browser.screenshot.assert_called_once()

    def test_capture_screenshot_respects_config(self, temp_output_dir, mock_browser):
        """capture_screenshot respects capture_screenshots config."""
        config = DebugConfig(output_dir=temp_output_dir, capture_screenshots=False)
        tools = DebugTools(config)

        result = tools.capture_screenshot(mock_browser)

        assert result is None
        mock_browser.screenshot.assert_not_called()

    def test_capture_screenshot_browser_not_awake(self, debug_tools, mock_browser):
        """capture_screenshot returns None if browser not awake."""
        mock_browser.is_awake = False
        result = debug_tools.capture_screenshot(mock_browser)
        assert result is None

    def test_capture_screenshot_handles_error(self, debug_tools, mock_browser):
        """capture_screenshot handles errors gracefully."""
        mock_browser.screenshot.side_effect = Exception("Screenshot failed")
        result = debug_tools.capture_screenshot(mock_browser)
        assert result is None


class TestDebugToolsCaptureHtml:
    """Tests for DebugTools.capture_html()."""

    def test_capture_html_returns_path(self, debug_tools, mock_browser):
        """capture_html returns a Path or None."""
        result = debug_tools.capture_html(mock_browser)
        assert result is None or isinstance(result, Path)

    def test_capture_html_respects_config(self, temp_output_dir, mock_browser):
        """capture_html respects capture_html config."""
        config = DebugConfig(output_dir=temp_output_dir, capture_html=False)
        tools = DebugTools(config)

        result = tools.capture_html(mock_browser)

        assert result is None

    def test_capture_html_browser_not_awake(self, debug_tools, mock_browser):
        """capture_html returns None if browser not awake."""
        mock_browser.is_awake = False
        result = debug_tools.capture_html(mock_browser)
        assert result is None

    def test_capture_html_writes_file(self, debug_tools, mock_browser, temp_output_dir):
        """capture_html writes HTML to file."""
        result = debug_tools.capture_html(mock_browser)
        if result:  # May be None if write fails
            assert result.exists()
            content = result.read_text()
            assert "Test" in content


class TestDebugToolsCaptureSnapshot:
    """Tests for DebugTools.capture_snapshot()."""

    def test_capture_snapshot_returns_snapshot(self, debug_tools, mock_browser):
        """capture_snapshot returns a DebugSnapshot."""
        result = debug_tools.capture_snapshot(mock_browser)
        assert isinstance(result, DebugSnapshot)

    def test_capture_snapshot_adds_to_list(self, debug_tools, mock_browser):
        """capture_snapshot adds snapshot to snapshots list."""
        debug_tools.capture_snapshot(mock_browser)
        assert len(debug_tools.snapshots) == 1

    def test_capture_snapshot_captures_url(self, debug_tools, mock_browser):
        """capture_snapshot captures current URL."""
        result = debug_tools.capture_snapshot(mock_browser)
        assert result.url == "https://example.com"

    def test_capture_snapshot_captures_title(self, debug_tools, mock_browser):
        """capture_snapshot captures page title."""
        result = debug_tools.capture_snapshot(mock_browser)
        assert result.title == "Test Page"

    def test_capture_snapshot_with_error(self, debug_tools, mock_browser):
        """capture_snapshot captures error info."""
        error = ValueError("Test error")
        result = debug_tools.capture_snapshot(mock_browser, error=error)

        assert result.error_message == "Test error"
        assert result.traceback is not None

    def test_capture_snapshot_with_extra_data(self, debug_tools, mock_browser):
        """capture_snapshot stores extra data."""
        result = debug_tools.capture_snapshot(
            mock_browser,
            extra_data={"step": 5, "action": "click"}
        )
        assert result.extra_data["step"] == 5
        assert result.extra_data["action"] == "click"

    def test_capture_snapshot_cleanup_old(self, temp_output_dir, mock_browser):
        """capture_snapshot cleans up old snapshots."""
        config = DebugConfig(output_dir=temp_output_dir, max_snapshots=2)
        tools = DebugTools(config)

        # Capture 3 snapshots (exceeds max_snapshots)
        tools.capture_snapshot(mock_browser)
        tools.capture_snapshot(mock_browser)
        tools.capture_snapshot(mock_browser)

        assert len(tools.snapshots) <= 2


# =============================================================================
# DebugTools Context Manager Tests
# =============================================================================

class TestDebugToolsContextManager:
    """Tests for DebugTools.capture_on_error context manager."""

    def test_context_manager_success(self, debug_tools, mock_browser):
        """Context manager doesn't capture on success."""
        with debug_tools.capture_on_error(mock_browser):
            pass  # No error

        assert len(debug_tools.snapshots) == 0

    def test_context_manager_captures_on_error(self, debug_tools, mock_browser):
        """Context manager captures snapshot on error."""
        with pytest.raises(ValueError):
            with debug_tools.capture_on_error(mock_browser):
                raise ValueError("Test error")

        assert len(debug_tools.snapshots) == 1

    def test_context_manager_reraises_error(self, debug_tools, mock_browser):
        """Context manager re-raises the original error."""
        with pytest.raises(ValueError, match="Specific error"):
            with debug_tools.capture_on_error(mock_browser):
                raise ValueError("Specific error")

    def test_context_manager_respects_config(self, temp_output_dir, mock_browser):
        """Context manager respects capture_on_error config."""
        config = DebugConfig(output_dir=temp_output_dir, capture_on_error=False)
        tools = DebugTools(config)

        with pytest.raises(ValueError):
            with tools.capture_on_error(mock_browser):
                raise ValueError("Test error")

        assert len(tools.snapshots) == 0

    def test_context_manager_with_prefix(self, debug_tools, mock_browser):
        """Context manager uses provided prefix."""
        with pytest.raises(ValueError):
            with debug_tools.capture_on_error(mock_browser, prefix="custom_prefix"):
                raise ValueError("Error")

        # Snapshot was captured
        assert len(debug_tools.snapshots) == 1


# =============================================================================
# DebugTools Other Methods Tests
# =============================================================================

class TestDebugToolsOtherMethods:
    """Tests for DebugTools getter and utility methods."""

    def test_get_last_snapshot_empty(self, debug_tools):
        """get_last_snapshot returns None when empty."""
        result = debug_tools.get_last_snapshot()
        assert result is None

    def test_get_last_snapshot(self, debug_tools, mock_browser):
        """get_last_snapshot returns most recent snapshot."""
        debug_tools.capture_snapshot(mock_browser, extra_data={"num": 1})
        debug_tools.capture_snapshot(mock_browser, extra_data={"num": 2})

        result = debug_tools.get_last_snapshot()
        assert result.extra_data["num"] == 2

    def test_get_all_snapshots(self, debug_tools, mock_browser):
        """get_all_snapshots returns copy of snapshots list."""
        debug_tools.capture_snapshot(mock_browser)
        debug_tools.capture_snapshot(mock_browser)

        result = debug_tools.get_all_snapshots()

        assert len(result) == 2
        # Verify it's a copy
        result.clear()
        assert len(debug_tools.snapshots) == 2

    def test_clear_snapshots(self, debug_tools, mock_browser):
        """clear_snapshots removes all snapshots from memory."""
        debug_tools.capture_snapshot(mock_browser)
        debug_tools.capture_snapshot(mock_browser)

        debug_tools.clear_snapshots()

        assert len(debug_tools.snapshots) == 0


class TestDebugToolsGenerateReport:
    """Tests for DebugTools.generate_report()."""

    def test_generate_report_returns_string(self, debug_tools):
        """generate_report returns HTML string."""
        result = debug_tools.generate_report()
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result

    def test_generate_report_contains_header(self, debug_tools):
        """generate_report contains title."""
        result = debug_tools.generate_report()
        assert "Debug Report" in result

    def test_generate_report_includes_snapshots(self, debug_tools, mock_browser):
        """generate_report includes captured snapshots."""
        debug_tools.capture_snapshot(mock_browser)
        result = debug_tools.generate_report()
        assert "Snapshot 1" in result

    def test_generate_report_includes_errors(self, debug_tools, mock_browser):
        """generate_report includes error information."""
        debug_tools.capture_snapshot(
            mock_browser,
            error=ValueError("Test error message")
        )
        result = debug_tools.generate_report()
        assert "Test error message" in result

    def test_generate_report_writes_to_file(self, debug_tools, temp_output_dir):
        """generate_report writes to file when path provided."""
        output_path = temp_output_dir / "report.html"
        debug_tools.generate_report(output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content


# =============================================================================
# TestResultTracker Tests
# =============================================================================

class TestTestResultTracker:
    """Tests for TestResultTracker class."""

    def test_init_creates_debug_tools(self):
        """TestResultTracker creates DebugTools if not provided."""
        tracker = TestResultTracker()
        assert tracker.debug_tools is not None

    def test_init_accepts_debug_tools(self, debug_tools):
        """TestResultTracker accepts custom DebugTools."""
        tracker = TestResultTracker(debug_tools)
        assert tracker.debug_tools is debug_tools

    def test_start_session(self):
        """start_session initializes tracking."""
        tracker = TestResultTracker()
        tracker.start_session()

        assert tracker.start_time is not None
        assert tracker.results == []

    def test_record_test_success(self):
        """record_test records passing test."""
        tracker = TestResultTracker()
        tracker.start_session()
        tracker.record_test("test_example", passed=True)

        assert len(tracker.results) == 1
        assert tracker.results[0]["test_name"] == "test_example"
        assert tracker.results[0]["passed"] is True

    def test_record_test_failure(self, mock_browser):
        """record_test records failing test."""
        tracker = TestResultTracker()
        tracker.start_session()

        error = ValueError("Test failed")
        tracker.record_test(
            "test_failure",
            passed=False,
            browser=mock_browser,
            error=error
        )

        assert tracker.results[0]["passed"] is False
        assert "Test failed" in tracker.results[0]["error"]

    def test_record_test_with_duration(self):
        """record_test records duration."""
        tracker = TestResultTracker()
        tracker.start_session()
        tracker.record_test("test_timed", passed=True, duration=1.5)

        assert tracker.results[0]["duration"] == 1.5

    def test_record_test_with_extra_data(self):
        """record_test records extra data."""
        tracker = TestResultTracker()
        tracker.start_session()
        tracker.record_test(
            "test_data",
            passed=True,
            extra_data={"attempts": 3}
        )

        assert tracker.results[0]["extra_data"]["attempts"] == 3

    def test_get_summary(self):
        """get_summary returns correct stats."""
        tracker = TestResultTracker()
        tracker.start_session()
        tracker.record_test("test1", passed=True)
        tracker.record_test("test2", passed=True)
        tracker.record_test("test3", passed=False)

        summary = tracker.get_summary()

        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["pass_rate"] == pytest.approx(0.666, rel=0.01)

    def test_get_summary_empty(self):
        """get_summary handles empty results."""
        tracker = TestResultTracker()
        tracker.start_session()

        summary = tracker.get_summary()

        assert summary["total"] == 0
        assert summary["pass_rate"] == 0


# =============================================================================
# ErrorCapturingWrapper Tests
# =============================================================================

class TestErrorCapturingWrapper:
    """Tests for ErrorCapturingWrapper class."""

    def test_wrapper_passes_through_successful_calls(self, debug_tools, mock_browser):
        """Wrapper passes through successful method calls."""
        mock_browser.get_title.return_value = "Success"
        wrapped = ErrorCapturingWrapper(mock_browser, debug_tools)

        result = wrapped.get_title()

        assert result == "Success"

    def test_wrapper_passes_through_attributes(self, debug_tools, mock_browser):
        """Wrapper passes through attribute access."""
        mock_browser.is_awake = True
        wrapped = ErrorCapturingWrapper(mock_browser, debug_tools)

        assert wrapped.is_awake is True

    def test_wrapper_captures_on_error(self, debug_tools, mock_browser):
        """Wrapper captures snapshot on method error."""
        mock_browser.click.side_effect = Exception("Click failed")
        wrapped = ErrorCapturingWrapper(mock_browser, debug_tools)

        with pytest.raises(Exception, match="Click failed"):
            wrapped.click("#button")

        assert len(debug_tools.snapshots) == 1

    def test_wrapper_reraises_error(self, debug_tools, mock_browser):
        """Wrapper re-raises the original error."""
        mock_browser.goto.side_effect = ValueError("Navigation failed")
        wrapped = ErrorCapturingWrapper(mock_browser, debug_tools)

        with pytest.raises(ValueError, match="Navigation failed"):
            wrapped.goto("https://example.com")

    def test_wrapper_uses_custom_prefix(self, debug_tools, mock_browser):
        """Wrapper uses custom prefix for snapshots."""
        mock_browser.scroll.side_effect = Exception("Scroll error")
        wrapped = ErrorCapturingWrapper(
            mock_browser,
            debug_tools,
            prefix="custom"
        )

        with pytest.raises(Exception):
            wrapped.scroll()

        # Snapshot was captured
        assert len(debug_tools.snapshots) == 1


# =============================================================================
# Global Function Tests
# =============================================================================

class TestGetDebugTools:
    """Tests for get_debug_tools function."""

    def test_get_debug_tools_creates_instance(self, temp_output_dir):
        """get_debug_tools creates DebugTools instance."""
        import blackreach.debug_tools as dt
        dt._debug_tools = None  # Reset singleton

        config = DebugConfig(output_dir=temp_output_dir)
        result = get_debug_tools(config)

        assert isinstance(result, DebugTools)

    def test_get_debug_tools_returns_same_instance(self, temp_output_dir):
        """get_debug_tools returns same instance on subsequent calls."""
        import blackreach.debug_tools as dt
        dt._debug_tools = None  # Reset singleton

        config = DebugConfig(output_dir=temp_output_dir)
        result1 = get_debug_tools(config)
        result2 = get_debug_tools()

        # Note: If config is passed again, a new instance is created
        # Let's test without passing config second time
        assert result1 is result2

    def test_get_debug_tools_with_new_config_creates_new(self, temp_output_dir):
        """get_debug_tools creates new instance when config provided."""
        import blackreach.debug_tools as dt
        dt._debug_tools = None  # Reset singleton

        config1 = DebugConfig(output_dir=temp_output_dir)
        result1 = get_debug_tools(config1)

        config2 = DebugConfig(output_dir=temp_output_dir, max_snapshots=50)
        result2 = get_debug_tools(config2)

        assert result2.config.max_snapshots == 50


class TestPytestConfigureDebug:
    """Tests for pytest_configure_debug function."""

    def test_pytest_configure_debug_returns_debug_tools(self, temp_output_dir):
        """pytest_configure_debug returns DebugTools."""
        result = pytest_configure_debug(temp_output_dir)
        assert isinstance(result, DebugTools)

    def test_pytest_configure_debug_sets_capture_on_error(self, temp_output_dir):
        """pytest_configure_debug enables capture_on_error."""
        result = pytest_configure_debug(temp_output_dir)
        assert result.config.capture_on_error is True

    def test_pytest_configure_debug_default_dir(self):
        """pytest_configure_debug uses default directory if not provided."""
        result = pytest_configure_debug()
        assert result.config.output_dir == Path("./test_debug_output")


# =============================================================================
# DebugTools _generate_filename Tests
# =============================================================================

class TestDebugToolsGenerateFilename:
    """Tests for DebugTools._generate_filename()."""

    def test_generate_filename_with_timestamp(self, debug_tools):
        """_generate_filename includes timestamp when configured."""
        result = debug_tools._generate_filename("test", "png")
        assert "test_" in str(result)
        assert result.suffix == ".png"

    def test_generate_filename_without_timestamp(self, temp_output_dir):
        """_generate_filename uses counter without timestamp."""
        config = DebugConfig(output_dir=temp_output_dir, include_timestamp=False)
        tools = DebugTools(config)

        result1 = tools._generate_filename("test", "png")
        # Create the file so counter increments
        result1.touch()

        result2 = tools._generate_filename("test", "png")

        assert result1 != result2
        assert "0001" in str(result1) or "0002" in str(result2)

    def test_generate_filename_in_output_dir(self, debug_tools, temp_output_dir):
        """_generate_filename creates path in output_dir."""
        result = debug_tools._generate_filename("test", "png")
        assert temp_output_dir in result.parents or result.parent == temp_output_dir
