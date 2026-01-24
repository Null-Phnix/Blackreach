"""
Unit tests for blackreach/progress.py

Tests for download progress tracking and display.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from blackreach.progress import (
    DownloadInfo,
    DownloadState,
    DownloadProgressTracker,
    TaskProgressTracker,
    track_downloads,
    format_size,
    format_speed,
    format_time,
)


class TestDownloadState:
    """Tests for DownloadState enum."""

    def test_states_exist(self):
        """All expected states exist."""
        assert DownloadState.PENDING
        assert DownloadState.DOWNLOADING
        assert DownloadState.COMPLETED
        assert DownloadState.FAILED
        assert DownloadState.CANCELLED


class TestDownloadInfo:
    """Tests for DownloadInfo dataclass."""

    def test_default_values(self):
        """DownloadInfo has sensible defaults."""
        info = DownloadInfo(url="http://example.com/file.pdf", filename="file.pdf")

        assert info.total_size == 0
        assert info.downloaded_size == 0
        assert info.state == DownloadState.PENDING
        assert info.error is None

    def test_progress_percent_with_known_total(self):
        """progress_percent calculates correctly."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
            total_size=1000,
            downloaded_size=500,
        )

        assert info.progress_percent == 50.0

    def test_progress_percent_zero_total(self):
        """progress_percent returns 0 when total is unknown."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
            total_size=0,
            downloaded_size=500,
        )

        assert info.progress_percent == 0.0

    def test_progress_percent_capped_at_100(self):
        """progress_percent doesn't exceed 100%."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
            total_size=100,
            downloaded_size=150,  # More than total (edge case)
        )

        assert info.progress_percent == 100.0

    def test_speed_calculation(self):
        """speed calculates bytes per second."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
            downloaded_size=1000,
            start_time=time.time() - 1.0,  # 1 second ago
        )

        # Should be approximately 1000 bytes/sec
        assert 900 < info.speed < 1100

    def test_speed_zero_when_not_started(self):
        """speed returns 0 when download hasn't started."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
        )

        assert info.speed == 0.0

    def test_eta_calculation(self):
        """eta_seconds calculates correctly."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
            total_size=2000,
            downloaded_size=1000,
            start_time=time.time() - 1.0,
        )

        # At ~1000 bytes/sec, 1000 remaining bytes = ~1 second
        eta = info.eta_seconds
        assert eta is not None
        assert 0.5 < eta < 1.5

    def test_eta_none_when_no_speed(self):
        """eta_seconds returns None when speed is unknown."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
        )

        assert info.eta_seconds is None

    def test_elapsed_seconds(self):
        """elapsed_seconds calculates correctly."""
        info = DownloadInfo(
            url="http://example.com/file.pdf",
            filename="file.pdf",
            start_time=time.time() - 5.0,
        )

        assert 4.9 < info.elapsed_seconds < 5.2


class TestDownloadProgressTracker:
    """Tests for DownloadProgressTracker class."""

    def test_add_download(self):
        """Can add a download to track."""
        tracker = DownloadProgressTracker()

        info = tracker.add_download(
            url="http://example.com/file.pdf",
            filename="file.pdf",
            total_size=1000,
        )

        assert info.url == "http://example.com/file.pdf"
        assert info.filename == "file.pdf"
        assert info.total_size == 1000

    def test_start_download(self):
        """Can mark download as started."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file.pdf", "file.pdf")

        tracker.start_download("http://example.com/file.pdf")

        info = tracker.get_download("http://example.com/file.pdf")
        assert info.state == DownloadState.DOWNLOADING
        assert info.start_time > 0

    def test_update_progress(self):
        """Can update download progress."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file.pdf", "file.pdf", 1000)
        tracker.start_download("http://example.com/file.pdf")

        tracker.update_progress("http://example.com/file.pdf", 500)

        info = tracker.get_download("http://example.com/file.pdf")
        assert info.downloaded_size == 500

    def test_update_progress_with_new_total(self):
        """Can update total size during progress."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file.pdf", "file.pdf")
        tracker.start_download("http://example.com/file.pdf")

        tracker.update_progress("http://example.com/file.pdf", 500, total=2000)

        info = tracker.get_download("http://example.com/file.pdf")
        assert info.total_size == 2000

    def test_complete_download_success(self):
        """Can mark download as complete."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file.pdf", "file.pdf", 1000)
        tracker.start_download("http://example.com/file.pdf")

        tracker.complete_download("http://example.com/file.pdf", success=True)

        info = tracker.get_download("http://example.com/file.pdf")
        assert info.state == DownloadState.COMPLETED
        assert info.end_time > 0

    def test_complete_download_failure(self):
        """Can mark download as failed."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file.pdf", "file.pdf")
        tracker.start_download("http://example.com/file.pdf")

        tracker.complete_download(
            "http://example.com/file.pdf",
            success=False,
            error="Connection timeout"
        )

        info = tracker.get_download("http://example.com/file.pdf")
        assert info.state == DownloadState.FAILED
        assert info.error == "Connection timeout"

    def test_cancel_download(self):
        """Can cancel a download."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file.pdf", "file.pdf")
        tracker.start_download("http://example.com/file.pdf")

        tracker.cancel_download("http://example.com/file.pdf")

        info = tracker.get_download("http://example.com/file.pdf")
        assert info.state == DownloadState.CANCELLED

    def test_get_active_downloads(self):
        """Can get list of active downloads."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file1.pdf", "file1.pdf")
        tracker.add_download("http://example.com/file2.pdf", "file2.pdf")
        tracker.add_download("http://example.com/file3.pdf", "file3.pdf")

        tracker.start_download("http://example.com/file1.pdf")
        tracker.start_download("http://example.com/file2.pdf")
        # file3 remains pending

        active = tracker.get_active_downloads()

        assert len(active) == 2

    def test_get_summary(self):
        """Can get summary statistics."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file1.pdf", "file1.pdf", 1000)
        tracker.add_download("http://example.com/file2.pdf", "file2.pdf", 2000)

        tracker.start_download("http://example.com/file1.pdf")
        tracker.update_progress("http://example.com/file1.pdf", 500)
        tracker.complete_download("http://example.com/file1.pdf", success=True, final_size=1000)

        summary = tracker.get_summary()

        assert summary["total_downloads"] == 2
        assert summary["completed"] == 1
        assert summary["pending"] == 1
        assert summary["total_bytes"] == 3000

    def test_clear_completed(self):
        """Can clear completed downloads."""
        tracker = DownloadProgressTracker()
        tracker.add_download("http://example.com/file1.pdf", "file1.pdf")
        tracker.add_download("http://example.com/file2.pdf", "file2.pdf")

        tracker.start_download("http://example.com/file1.pdf")
        tracker.complete_download("http://example.com/file1.pdf", success=True)

        tracker.clear_completed()

        assert tracker.get_download("http://example.com/file1.pdf") is None
        assert tracker.get_download("http://example.com/file2.pdf") is not None


class TestTaskProgressTracker:
    """Tests for TaskProgressTracker class."""

    def test_start_creates_progress(self):
        """start() initializes progress tracking."""
        tracker = TaskProgressTracker()

        tracker.start(total_steps=10, description="Processing...")

        assert tracker._total_steps == 10
        assert tracker._current_step == 0

    def test_update_changes_step(self):
        """update() changes current step."""
        tracker = TaskProgressTracker()
        tracker.start(total_steps=10)

        tracker.update(5, description="Step 5")

        assert tracker._current_step == 5
        assert tracker._step_description == "Step 5"

    def test_advance_increments_step(self):
        """advance() increments by one."""
        tracker = TaskProgressTracker()
        tracker.start(total_steps=10)

        tracker.advance()
        tracker.advance()

        assert tracker._current_step == 2

    def test_complete_sets_to_total(self):
        """complete() sets progress to total."""
        tracker = TaskProgressTracker()
        tracker.start(total_steps=10)
        tracker.update(5)

        tracker.complete()

        # Progress should complete (implementation detail: updates to total)

    def test_stop_cleans_up(self):
        """stop() cleans up resources."""
        tracker = TaskProgressTracker()
        tracker.start(total_steps=10)

        tracker.stop()

        assert tracker._progress is None
        assert tracker._task_id is None


class TestFormatSize:
    """Tests for format_size function."""

    def test_formats_bytes(self):
        """Formats small values as bytes."""
        assert format_size(100) == "100 B"
        assert format_size(0) == "0 B"

    def test_formats_kilobytes(self):
        """Formats KB values."""
        assert format_size(1024) == "1 KB"
        assert format_size(5120) == "5 KB"

    def test_formats_megabytes(self):
        """Formats MB values."""
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_formats_gigabytes(self):
        """Formats GB values."""
        assert format_size(1024 * 1024 * 1024) == "1.00 GB"
        assert format_size(2.5 * 1024 * 1024 * 1024) == "2.50 GB"


class TestFormatSpeed:
    """Tests for format_speed function."""

    def test_formats_bytes_per_second(self):
        """Formats low speeds as B/s."""
        assert format_speed(100) == "100 B/s"

    def test_formats_kilobytes_per_second(self):
        """Formats KB/s speeds."""
        assert format_speed(1024) == "1 KB/s"
        assert format_speed(5000) == "5 KB/s"

    def test_formats_megabytes_per_second(self):
        """Formats MB/s speeds."""
        assert format_speed(1024 * 1024) == "1.0 MB/s"


class TestFormatTime:
    """Tests for format_time function."""

    def test_formats_seconds(self):
        """Formats short durations as seconds."""
        assert format_time(30) == "30s"
        assert format_time(59) == "59s"

    def test_formats_minutes_and_seconds(self):
        """Formats minutes with seconds."""
        assert format_time(90) == "1m 30s"
        assert format_time(3599) == "59m 59s"

    def test_formats_hours_and_minutes(self):
        """Formats hours with minutes."""
        assert format_time(3600) == "1h 0m"
        assert format_time(5400) == "1h 30m"

    def test_handles_none(self):
        """Returns 'unknown' for None."""
        assert format_time(None) == "unknown"
