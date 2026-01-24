"""
Blackreach Progress Tracking - Real-time download and task progress display.

Provides:
- Download progress bars with speed and ETA
- Multi-download tracking
- Task progress aggregation
- Integration with rich library
"""

import time
import threading
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
    TaskID,
    track,
)
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


console = Console()


class DownloadState(Enum):
    """State of a download."""
    PENDING = auto()
    DOWNLOADING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class DownloadInfo:
    """Information about a single download."""
    url: str
    filename: str
    total_size: int = 0
    downloaded_size: int = 0
    state: DownloadState = DownloadState.PENDING
    start_time: float = 0.0
    end_time: float = 0.0
    error: Optional[str] = None
    task_id: Optional[TaskID] = None

    @property
    def progress_percent(self) -> float:
        """Get download progress as percentage."""
        if self.total_size <= 0:
            return 0.0
        return min(100.0, (self.downloaded_size / self.total_size) * 100)

    @property
    def speed(self) -> float:
        """Get download speed in bytes per second."""
        if self.start_time <= 0 or self.downloaded_size <= 0:
            return 0.0
        elapsed = (self.end_time if self.end_time > 0 else time.time()) - self.start_time
        if elapsed <= 0:
            return 0.0
        return self.downloaded_size / elapsed

    @property
    def eta_seconds(self) -> Optional[float]:
        """Get estimated time remaining in seconds."""
        if self.speed <= 0 or self.total_size <= 0:
            return None
        remaining = self.total_size - self.downloaded_size
        if remaining <= 0:
            return 0.0
        return remaining / self.speed

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time <= 0:
            return 0.0
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time


class DownloadProgressTracker:
    """
    Track and display progress for multiple downloads.

    Uses rich Progress for real-time progress bars with:
    - Download speed
    - Estimated time remaining
    - File size
    - Percentage complete
    """

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self._downloads: Dict[str, DownloadInfo] = {}  # url -> DownloadInfo
        self._progress: Optional[Progress] = None
        self._live: Optional[Live] = None
        self._lock = threading.Lock()
        self._total_task_id: Optional[TaskID] = None

    def _create_progress(self) -> Progress:
        """Create a rich Progress instance with download columns."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[filename]}", justify="left"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=False,
        )

    def start(self) -> None:
        """Start the progress display."""
        if self._progress is None:
            self._progress = self._create_progress()
            self._progress.start()

    def stop(self) -> None:
        """Stop the progress display."""
        if self._progress:
            self._progress.stop()
            self._progress = None

    def add_download(
        self,
        url: str,
        filename: str,
        total_size: int = 0
    ) -> DownloadInfo:
        """
        Add a new download to track.

        Args:
            url: Download URL
            filename: Target filename
            total_size: Total file size in bytes (0 if unknown)

        Returns:
            DownloadInfo for the download
        """
        with self._lock:
            # Ensure progress is started
            if self._progress is None:
                self.start()

            # Create download info
            info = DownloadInfo(
                url=url,
                filename=filename,
                total_size=total_size,
                state=DownloadState.PENDING,
            )

            # Add task to progress display
            task_id = self._progress.add_task(
                f"[cyan]{filename}",
                total=total_size if total_size > 0 else None,
                filename=filename[:40] + "..." if len(filename) > 40 else filename,
            )
            info.task_id = task_id

            self._downloads[url] = info
            return info

    def start_download(self, url: str) -> None:
        """Mark a download as started."""
        with self._lock:
            if url in self._downloads:
                info = self._downloads[url]
                info.state = DownloadState.DOWNLOADING
                info.start_time = time.time()

    def update_progress(
        self,
        url: str,
        downloaded: int,
        total: Optional[int] = None
    ) -> None:
        """
        Update download progress.

        Args:
            url: Download URL
            downloaded: Bytes downloaded so far
            total: Total file size (if newly known)
        """
        with self._lock:
            if url not in self._downloads:
                return

            info = self._downloads[url]
            info.downloaded_size = downloaded

            if total is not None and total > 0:
                info.total_size = total

            # Update progress bar
            if self._progress and info.task_id is not None:
                if info.total_size > 0:
                    self._progress.update(
                        info.task_id,
                        completed=downloaded,
                        total=info.total_size
                    )
                else:
                    # Unknown total - just show as indeterminate
                    self._progress.update(
                        info.task_id,
                        completed=downloaded,
                    )

    def complete_download(
        self,
        url: str,
        final_size: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """
        Mark a download as complete.

        Args:
            url: Download URL
            final_size: Final file size
            success: Whether download succeeded
            error: Error message if failed
        """
        with self._lock:
            if url not in self._downloads:
                return

            info = self._downloads[url]
            info.end_time = time.time()

            if success:
                info.state = DownloadState.COMPLETED
                if final_size is not None:
                    info.downloaded_size = final_size
                    info.total_size = final_size
            else:
                info.state = DownloadState.FAILED
                info.error = error

            # Update progress bar to complete
            if self._progress and info.task_id is not None:
                if success:
                    self._progress.update(
                        info.task_id,
                        completed=info.total_size or info.downloaded_size,
                        total=info.total_size or info.downloaded_size,
                    )
                else:
                    # Mark as failed visually
                    self._progress.update(
                        info.task_id,
                        description=f"[red][FAILED] {info.filename[:30]}",
                    )

    def cancel_download(self, url: str) -> None:
        """Cancel a download."""
        with self._lock:
            if url in self._downloads:
                info = self._downloads[url]
                info.state = DownloadState.CANCELLED
                info.end_time = time.time()

                if self._progress and info.task_id is not None:
                    self._progress.update(
                        info.task_id,
                        description=f"[yellow][CANCELLED] {info.filename[:30]}",
                    )

    def get_download(self, url: str) -> Optional[DownloadInfo]:
        """Get download info by URL."""
        return self._downloads.get(url)

    def get_all_downloads(self) -> List[DownloadInfo]:
        """Get all downloads."""
        return list(self._downloads.values())

    def get_active_downloads(self) -> List[DownloadInfo]:
        """Get downloads currently in progress."""
        return [d for d in self._downloads.values()
                if d.state == DownloadState.DOWNLOADING]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all downloads."""
        downloads = list(self._downloads.values())

        total_size = sum(d.total_size for d in downloads if d.total_size > 0)
        downloaded_size = sum(d.downloaded_size for d in downloads)
        completed = sum(1 for d in downloads if d.state == DownloadState.COMPLETED)
        failed = sum(1 for d in downloads if d.state == DownloadState.FAILED)
        active = sum(1 for d in downloads if d.state == DownloadState.DOWNLOADING)

        return {
            "total_downloads": len(downloads),
            "completed": completed,
            "failed": failed,
            "active": active,
            "pending": len(downloads) - completed - failed - active,
            "total_bytes": total_size,
            "downloaded_bytes": downloaded_size,
        }

    def clear_completed(self) -> None:
        """Remove completed downloads from tracking."""
        with self._lock:
            completed_urls = [
                url for url, info in self._downloads.items()
                if info.state in (DownloadState.COMPLETED, DownloadState.FAILED, DownloadState.CANCELLED)
            ]

            for url in completed_urls:
                info = self._downloads.pop(url)
                if self._progress and info.task_id is not None:
                    self._progress.remove_task(info.task_id)


class TaskProgressTracker:
    """
    Track progress of multi-step tasks (like agent operations).

    Shows:
    - Current step / total steps
    - Step descriptions
    - Overall progress bar
    """

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self._progress: Optional[Progress] = None
        self._task_id: Optional[TaskID] = None
        self._current_step = 0
        self._total_steps = 0
        self._step_description = ""

    def start(self, total_steps: int, description: str = "Processing...") -> None:
        """Start task progress tracking."""
        self._total_steps = total_steps
        self._current_step = 0
        self._step_description = description

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("Step {task.completed}/{task.total}"),
            console=self.console,
        )
        self._progress.start()

        self._task_id = self._progress.add_task(
            description,
            total=total_steps,
        )

    def update(self, step: int, description: str = None) -> None:
        """Update progress to a specific step."""
        self._current_step = step
        if description:
            self._step_description = description

        if self._progress and self._task_id is not None:
            self._progress.update(
                self._task_id,
                completed=step,
                description=self._step_description,
            )

    def advance(self, description: str = None) -> None:
        """Advance by one step."""
        self.update(self._current_step + 1, description)

    def complete(self, description: str = None) -> None:
        """Mark task as complete."""
        if self._progress and self._task_id is not None:
            self._progress.update(
                self._task_id,
                completed=self._total_steps,
                description=description or "[green]Complete!",
            )

    def stop(self) -> None:
        """Stop and close progress display."""
        if self._progress:
            self._progress.stop()
            self._progress = None
            self._task_id = None


def track_downloads(
    urls: List[str],
    download_func: Callable[[str, Callable], None],
    console: Console = None,
) -> Dict[str, DownloadInfo]:
    """
    Track multiple downloads with progress display.

    Args:
        urls: List of URLs to download
        download_func: Function that takes (url, progress_callback) and downloads
        console: Rich console to use

    Returns:
        Dict of url -> DownloadInfo with results
    """
    tracker = DownloadProgressTracker(console)
    tracker.start()

    try:
        for url in urls:
            filename = url.split("/")[-1] or "file"
            tracker.add_download(url, filename)
            tracker.start_download(url)

            def progress_callback(downloaded: int, total: int = None):
                tracker.update_progress(url, downloaded, total)

            try:
                download_func(url, progress_callback)
                tracker.complete_download(url, success=True)
            except Exception as e:
                tracker.complete_download(url, success=False, error=str(e))

        return {url: tracker.get_download(url) for url in urls}
    finally:
        tracker.stop()


def format_size(bytes_value: int) -> str:
    """Format bytes as human-readable size."""
    if bytes_value >= 1024 * 1024 * 1024:
        return f"{bytes_value / (1024**3):.2f} GB"
    elif bytes_value >= 1024 * 1024:
        return f"{bytes_value / (1024**2):.1f} MB"
    elif bytes_value >= 1024:
        return f"{bytes_value / 1024:.0f} KB"
    else:
        return f"{bytes_value} B"


def format_speed(bytes_per_second: float) -> str:
    """Format download speed as human-readable string."""
    if bytes_per_second >= 1024 * 1024:
        return f"{bytes_per_second / (1024**2):.1f} MB/s"
    elif bytes_per_second >= 1024:
        return f"{bytes_per_second / 1024:.0f} KB/s"
    else:
        return f"{bytes_per_second:.0f} B/s"


def format_time(seconds: float) -> str:
    """Format time duration as human-readable string."""
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"
