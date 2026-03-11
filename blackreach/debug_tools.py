"""
Debug Tools - Debugging utilities for Blackreach browser automation.

Provides:
- Screenshot capture on error
- HTML snapshot on error
- Debug context manager for automatic capture
- Test result aggregation
"""

import traceback
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class DebugSnapshot:
    """Represents a captured debug snapshot."""
    timestamp: datetime
    url: str
    title: str
    screenshot_path: Optional[Path]
    html_path: Optional[Path]
    error_message: Optional[str]
    traceback: Optional[str]
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "url": self.url,
            "title": self.title,
            "screenshot_path": str(self.screenshot_path) if self.screenshot_path else None,
            "html_path": str(self.html_path) if self.html_path else None,
            "error_message": self.error_message,
            "traceback": self.traceback,
            "extra_data": self.extra_data,
        }


@dataclass
class DebugConfig:
    """Configuration for debug tools."""
    output_dir: Path = field(default_factory=lambda: Path("./debug_output"))
    capture_screenshots: bool = True
    capture_html: bool = True
    capture_on_error: bool = True
    capture_on_success: bool = False
    max_snapshots: int = 100  # Max snapshots to keep
    screenshot_format: str = "png"  # png or jpeg
    include_timestamp: bool = True


class DebugTools:
    """
    Debug utilities for browser automation testing.

    Provides automatic screenshot and HTML capture on errors,
    plus manual capture methods for debugging.
    """

    def __init__(self, config: Optional[DebugConfig] = None):
        self.config = config or DebugConfig()
        self.snapshots: List[DebugSnapshot] = []
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """Ensure output directory exists."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, prefix: str, extension: str) -> Path:
        """Generate a unique filename with optional timestamp."""
        if self.config.include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{prefix}_{timestamp}.{extension}"
        else:
            # Use incrementing counter
            existing = list(self.config.output_dir.glob(f"{prefix}_*.{extension}"))
            counter = len(existing) + 1
            filename = f"{prefix}_{counter:04d}.{extension}"
        return self.config.output_dir / filename

    def capture_screenshot(
        self,
        browser,
        prefix: str = "screenshot",
        full_page: bool = False
    ) -> Optional[Path]:
        """
        Capture a screenshot from the browser.

        Args:
            browser: Hand browser instance (must be awake)
            prefix: Filename prefix
            full_page: Whether to capture full page or viewport only

        Returns:
            Path to screenshot file or None if capture failed
        """
        if not self.config.capture_screenshots:
            return None

        if not browser.is_awake:
            return None

        try:
            ext = self.config.screenshot_format
            path = self._generate_filename(prefix, ext)
            browser.screenshot(str(path), full_page=full_page)
            return path
        except Exception as e:
            # Don't let debug capture fail the test
            print(f"[debug] Screenshot capture failed: {e}")
            return None

    def capture_html(
        self,
        browser,
        prefix: str = "html_snapshot"
    ) -> Optional[Path]:
        """
        Capture HTML snapshot from the browser.

        Args:
            browser: Hand browser instance (must be awake)
            prefix: Filename prefix

        Returns:
            Path to HTML file or None if capture failed
        """
        if not self.config.capture_html:
            return None

        if not browser.is_awake:
            return None

        try:
            path = self._generate_filename(prefix, "html")
            html = browser.get_html(wait_for_load=False)
            path.write_text(html, encoding="utf-8")
            return path
        except Exception as e:
            print(f"[debug] HTML capture failed: {e}")
            return None

    def capture_snapshot(
        self,
        browser,
        error: Optional[Exception] = None,
        prefix: str = "snapshot",
        extra_data: Optional[Dict[str, Any]] = None
    ) -> DebugSnapshot:
        """
        Capture a complete debug snapshot including screenshot, HTML, and metadata.

        Args:
            browser: Hand browser instance
            error: Optional exception that triggered the capture
            prefix: Filename prefix for outputs
            extra_data: Additional data to include in snapshot

        Returns:
            DebugSnapshot with captured data
        """
        timestamp = datetime.now()
        url = ""
        title = ""
        screenshot_path = None
        html_path = None
        error_message = None
        error_traceback = None

        # Get page info
        try:
            if browser.is_awake:
                url = browser.get_url()
                title = browser.get_title()
        except Exception:
            pass

        # Capture screenshot
        screenshot_path = self.capture_screenshot(browser, f"{prefix}_screenshot")

        # Capture HTML
        html_path = self.capture_html(browser, f"{prefix}_html")

        # Capture error info
        if error:
            error_message = str(error)
            error_traceback = traceback.format_exc()

        snapshot = DebugSnapshot(
            timestamp=timestamp,
            url=url,
            title=title,
            screenshot_path=screenshot_path,
            html_path=html_path,
            error_message=error_message,
            traceback=error_traceback,
            extra_data=extra_data or {},
        )

        self.snapshots.append(snapshot)
        self._cleanup_old_snapshots()

        return snapshot

    def _cleanup_old_snapshots(self) -> None:
        """Remove old snapshots if we exceed max_snapshots."""
        while len(self.snapshots) > self.config.max_snapshots:
            old = self.snapshots.pop(0)
            # Optionally delete files
            if old.screenshot_path and old.screenshot_path.exists():
                old.screenshot_path.unlink(missing_ok=True)
            if old.html_path and old.html_path.exists():
                old.html_path.unlink(missing_ok=True)

    @contextmanager
    def capture_on_error(self, browser, prefix: str = "error"):
        """
        Context manager that captures debug info on exception.

        Usage:
            with debug_tools.capture_on_error(browser, "test_navigation"):
                browser.goto("https://example.com")
                browser.click("#nonexistent")  # Will capture on error
        """
        try:
            yield
        except Exception as e:
            if self.config.capture_on_error:
                self.capture_snapshot(browser, error=e, prefix=prefix)
            raise

    def get_last_snapshot(self) -> Optional[DebugSnapshot]:
        """Get the most recent snapshot."""
        return self.snapshots[-1] if self.snapshots else None

    def get_all_snapshots(self) -> List[DebugSnapshot]:
        """Get all captured snapshots."""
        return self.snapshots.copy()

    def clear_snapshots(self) -> None:
        """Clear all snapshots from memory (does not delete files)."""
        self.snapshots.clear()

    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """
        Generate a debug report from all captured snapshots.

        Args:
            output_path: Optional path to write report HTML file

        Returns:
            Report as HTML string
        """
        html_parts = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<title>Blackreach Debug Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".snapshot { border: 1px solid #ccc; margin: 10px 0; padding: 15px; }",
            ".error { background-color: #ffe0e0; }",
            ".success { background-color: #e0ffe0; }",
            "img { max-width: 800px; border: 1px solid #999; }",
            "pre { background: #f5f5f5; padding: 10px; overflow-x: auto; }",
            "</style>",
            "</head><body>",
            f"<h1>Debug Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</h1>",
            f"<p>Total snapshots: {len(self.snapshots)}</p>",
        ]

        for i, snapshot in enumerate(self.snapshots):
            css_class = "error" if snapshot.error_message else "success"
            html_parts.append(f'<div class="snapshot {css_class}">')
            html_parts.append(f"<h3>Snapshot {i + 1} - {snapshot.timestamp.strftime('%H:%M:%S')}</h3>")
            html_parts.append(f"<p><strong>URL:</strong> {snapshot.url}</p>")
            html_parts.append(f"<p><strong>Title:</strong> {snapshot.title}</p>")

            if snapshot.error_message:
                html_parts.append(f"<p><strong>Error:</strong> {snapshot.error_message}</p>")
                if snapshot.traceback:
                    html_parts.append(f"<pre>{snapshot.traceback}</pre>")

            if snapshot.screenshot_path and snapshot.screenshot_path.exists():
                # Use relative path for portability
                rel_path = snapshot.screenshot_path.name
                html_parts.append(f'<p><strong>Screenshot:</strong><br><img src="{rel_path}"></p>')

            if snapshot.html_path:
                html_parts.append(f"<p><strong>HTML saved to:</strong> {snapshot.html_path}</p>")

            if snapshot.extra_data:
                html_parts.append(f"<p><strong>Extra data:</strong></p>")
                html_parts.append(f"<pre>{snapshot.extra_data}</pre>")

            html_parts.append("</div>")

        html_parts.extend(["</body></html>"])
        report = "\n".join(html_parts)

        if output_path:
            output_path.write_text(report, encoding="utf-8")

        return report


class TestResultTracker:
    """
    Track test results with debug info for comprehensive reporting.
    """

    def __init__(self, debug_tools: Optional[DebugTools] = None):
        self.debug_tools = debug_tools or DebugTools()
        self.results: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None

    def start_session(self) -> None:
        """Start a test session."""
        self.start_time = time.time()
        self.results.clear()

    def record_test(
        self,
        test_name: str,
        passed: bool,
        browser=None,
        error: Optional[Exception] = None,
        duration: Optional[float] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a test result with optional debug snapshot.

        Args:
            test_name: Name of the test
            passed: Whether the test passed
            browser: Browser instance for snapshot capture
            error: Exception if test failed
            duration: Test duration in seconds
            extra_data: Additional test data
        """
        snapshot = None
        if browser and (error or not passed):
            snapshot = self.debug_tools.capture_snapshot(
                browser,
                error=error,
                prefix=f"test_{test_name.replace(' ', '_')}"
            )

        self.results.append({
            "test_name": test_name,
            "passed": passed,
            "error": str(error) if error else None,
            "duration": duration,
            "snapshot": snapshot.to_dict() if snapshot else None,
            "extra_data": extra_data or {},
            "timestamp": datetime.now().isoformat(),
        })

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of test results."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        duration = time.time() - self.start_time if self.start_time else 0

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0,
            "duration_seconds": duration,
            "results": self.results,
        }


class ErrorCapturingWrapper:
    """
    Wrapper that captures debug info on any method call that raises.

    Usage:
        wrapped_browser = ErrorCapturingWrapper(browser, debug_tools)
        wrapped_browser.click("#button")  # Will capture on error
    """

    def __init__(self, browser, debug_tools: DebugTools, prefix: str = "wrapped"):
        self._browser = browser
        self._debug_tools = debug_tools
        self._prefix = prefix

    def __getattr__(self, name: str):
        """Wrap attribute access to capture errors on method calls."""
        attr = getattr(self._browser, name)

        if callable(attr):
            def wrapper(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except Exception as e:
                    self._debug_tools.capture_snapshot(
                        self._browser,
                        error=e,
                        prefix=f"{self._prefix}_{name}"
                    )
                    raise
            return wrapper
        return attr


# Singleton instance for convenience
_debug_tools: Optional[DebugTools] = None


def get_debug_tools(config: Optional[DebugConfig] = None) -> DebugTools:
    """Get or create the global debug tools instance."""
    global _debug_tools
    if _debug_tools is None or config is not None:
        _debug_tools = DebugTools(config)
    return _debug_tools


# Pytest plugin hooks for automatic screenshot capture
def pytest_configure_debug(output_dir: Path = None) -> DebugTools:
    """
    Configure debug tools for pytest.
    Call this in conftest.py to enable automatic screenshot capture.
    """
    config = DebugConfig(
        output_dir=output_dir or Path("./test_debug_output"),
        capture_on_error=True,
    )
    return get_debug_tools(config)
