"""
Download Queue System (v3.1.0)

Provides download queue management:
- Priority queue for downloads
- Parallel download support
- Download progress tracking
- Resume/retry management
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
import threading
from queue import PriorityQueue
import hashlib


class DownloadPriority(Enum):
    """Priority levels for downloads."""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class DownloadStatus(Enum):
    """Status of a download."""
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class DownloadItem:
    """Represents a download in the queue."""
    download_id: str
    url: str
    destination: Path
    priority: DownloadPriority = DownloadPriority.NORMAL
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0         # 0-100
    size: int = 0                 # Total size in bytes
    downloaded: int = 0           # Downloaded bytes
    speed: float = 0.0            # Bytes per second
    retries: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def __lt__(self, other):
        """For priority queue comparison."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


@dataclass
class QueueStats:
    """Statistics about the download queue."""
    total: int = 0
    queued: int = 0
    downloading: int = 0
    completed: int = 0
    failed: int = 0
    total_bytes: int = 0
    downloaded_bytes: int = 0


class DownloadQueue:
    """Manages a queue of downloads."""

    def __init__(
        self,
        max_concurrent: int = 3,
        download_dir: Path = None,
        on_complete: Optional[Callable[[DownloadItem], None]] = None,
        on_progress: Optional[Callable[[DownloadItem], None]] = None,
        on_error: Optional[Callable[[DownloadItem, str], None]] = None
    ):
        self.max_concurrent = max_concurrent
        self.download_dir = download_dir or Path("./downloads")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Callbacks
        self.on_complete = on_complete
        self.on_progress = on_progress
        self.on_error = on_error

        # Download tracking
        self.items: Dict[str, DownloadItem] = {}
        self.queue: PriorityQueue = PriorityQueue()
        self.active: Dict[str, DownloadItem] = {}

        # Threading
        self._lock = threading.Lock()
        self._counter = 0

    def _generate_id(self) -> str:
        """Generate a unique download ID."""
        self._counter += 1
        return f"dl_{self._counter}_{datetime.now().strftime('%H%M%S')}"

    def add(
        self,
        url: str,
        filename: Optional[str] = None,
        priority: DownloadPriority = DownloadPriority.NORMAL,
        metadata: Dict = None
    ) -> str:
        """Add a download to the queue."""
        download_id = self._generate_id()

        # Determine filename
        if not filename:
            # Extract from URL or generate
            url_path = url.split('?')[0].split('/')[-1]
            filename = url_path if url_path else f"download_{download_id}"

        destination = self.download_dir / filename

        item = DownloadItem(
            download_id=download_id,
            url=url,
            destination=destination,
            priority=priority,
            metadata=metadata or {}
        )

        with self._lock:
            self.items[download_id] = item
            self.queue.put(item)

        return download_id

    def get_next(self) -> Optional[DownloadItem]:
        """Get the next download to process."""
        with self._lock:
            if len(self.active) >= self.max_concurrent:
                return None

            try:
                item = self.queue.get_nowait()
                if item.status == DownloadStatus.QUEUED:
                    item.status = DownloadStatus.DOWNLOADING
                    item.started_at = datetime.now()
                    self.active[item.download_id] = item
                    return item
            except Exception:
                pass

        return None

    def update_progress(
        self,
        download_id: str,
        downloaded: int,
        total: int,
        speed: float = 0.0
    ):
        """Update download progress."""
        if download_id in self.items:
            item = self.items[download_id]
            item.downloaded = downloaded
            item.size = total
            item.speed = speed
            item.progress = (downloaded / total * 100) if total > 0 else 0

            if self.on_progress:
                self.on_progress(item)

    def complete(self, download_id: str, file_hash: str = ""):
        """Mark a download as completed."""
        with self._lock:
            if download_id in self.items:
                item = self.items[download_id]
                item.status = DownloadStatus.COMPLETED
                item.completed_at = datetime.now()
                item.progress = 100.0

                if file_hash:
                    item.metadata["hash"] = file_hash

                if download_id in self.active:
                    del self.active[download_id]

                if self.on_complete:
                    self.on_complete(item)

    def fail(self, download_id: str, error: str):
        """Mark a download as failed."""
        with self._lock:
            if download_id in self.items:
                item = self.items[download_id]
                item.error = error
                item.retries += 1

                if download_id in self.active:
                    del self.active[download_id]

                # Retry if under limit
                if item.retries < item.max_retries:
                    item.status = DownloadStatus.QUEUED
                    self.queue.put(item)
                else:
                    item.status = DownloadStatus.FAILED
                    if self.on_error:
                        self.on_error(item, error)

    def cancel(self, download_id: str):
        """Cancel a download."""
        with self._lock:
            if download_id in self.items:
                item = self.items[download_id]
                item.status = DownloadStatus.CANCELLED

                if download_id in self.active:
                    del self.active[download_id]

    def pause(self, download_id: str):
        """Pause a download."""
        with self._lock:
            if download_id in self.items:
                item = self.items[download_id]
                if item.status == DownloadStatus.DOWNLOADING:
                    item.status = DownloadStatus.PAUSED

                    if download_id in self.active:
                        del self.active[download_id]

    def resume(self, download_id: str):
        """Resume a paused download."""
        with self._lock:
            if download_id in self.items:
                item = self.items[download_id]
                if item.status == DownloadStatus.PAUSED:
                    item.status = DownloadStatus.QUEUED
                    self.queue.put(item)

    def get_item(self, download_id: str) -> Optional[DownloadItem]:
        """Get a specific download item."""
        return self.items.get(download_id)

    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        stats = QueueStats()

        with self._lock:
            for item in self.items.values():
                stats.total += 1
                stats.total_bytes += item.size
                stats.downloaded_bytes += item.downloaded

                if item.status == DownloadStatus.QUEUED:
                    stats.queued += 1
                elif item.status == DownloadStatus.DOWNLOADING:
                    stats.downloading += 1
                elif item.status == DownloadStatus.COMPLETED:
                    stats.completed += 1
                elif item.status == DownloadStatus.FAILED:
                    stats.failed += 1

        return stats

    def get_active(self) -> List[DownloadItem]:
        """Get list of active downloads."""
        return list(self.active.values())

    def get_queued(self) -> List[DownloadItem]:
        """Get list of queued downloads."""
        return [
            item for item in self.items.values()
            if item.status == DownloadStatus.QUEUED
        ]

    def get_completed(self) -> List[DownloadItem]:
        """Get list of completed downloads."""
        return [
            item for item in self.items.values()
            if item.status == DownloadStatus.COMPLETED
        ]

    def get_failed(self) -> List[DownloadItem]:
        """Get list of failed downloads."""
        return [
            item for item in self.items.values()
            if item.status == DownloadStatus.FAILED
        ]

    def clear_completed(self):
        """Remove completed downloads from tracking."""
        with self._lock:
            to_remove = [
                did for did, item in self.items.items()
                if item.status == DownloadStatus.COMPLETED
            ]
            for did in to_remove:
                del self.items[did]

    def clear_all(self):
        """Clear all downloads (including active)."""
        with self._lock:
            self.items.clear()
            self.active.clear()
            # Clear queue
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except Exception:
                    break

    def has_pending(self) -> bool:
        """Check if there are pending downloads."""
        return any(
            item.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)
            for item in self.items.values()
        )

    def wait_all(self, timeout: float = None) -> bool:
        """Wait for all downloads to complete."""
        import time
        start = time.time()

        while self.has_pending():
            if timeout and (time.time() - start) > timeout:
                return False
            time.sleep(0.5)

        return True


# Global download queue
_download_queue: Optional[DownloadQueue] = None


def get_download_queue(
    max_concurrent: int = 3,
    download_dir: Path = None
) -> DownloadQueue:
    """Get the global download queue instance."""
    global _download_queue
    if _download_queue is None:
        _download_queue = DownloadQueue(
            max_concurrent=max_concurrent,
            download_dir=download_dir
        )
    return _download_queue
