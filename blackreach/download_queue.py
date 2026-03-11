"""
Download Queue System (v3.2.0)

Provides download queue management:
- Priority queue for downloads
- Parallel download support
- Download progress tracking
- Resume/retry management
- Download history tracking
- Deduplication support
- Checksum verification
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
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
    # New fields for enhanced download tracking
    md5_hash: str = ""
    sha256_hash: str = ""
    expected_md5: str = ""        # Expected MD5 for verification
    expected_sha256: str = ""     # Expected SHA256 for verification
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None  # Path to original if duplicate

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
    """Manages a queue of downloads with history tracking and deduplication."""

    def __init__(
        self,
        max_concurrent: int = 3,
        download_dir: Path = None,
        on_complete: Optional[Callable[[DownloadItem], None]] = None,
        on_progress: Optional[Callable[[DownloadItem], None]] = None,
        on_error: Optional[Callable[[DownloadItem, str], None]] = None,
        enable_history: bool = True,
        enable_deduplication: bool = True,
        history_db_path: Path = None
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

        # History and deduplication
        self.enable_history = enable_history
        self.enable_deduplication = enable_deduplication
        self._history = None
        self._history_db_path = history_db_path

    def _get_history(self):
        """Lazy-load download history."""
        if self._history is None and self.enable_history:
            try:
                from blackreach.download_history import DownloadHistory
                self._history = DownloadHistory(self._history_db_path)
            except ImportError:
                self.enable_history = False
        return self._history

    def _generate_id(self) -> str:
        """Generate a unique download ID."""
        self._counter += 1
        return f"dl_{self._counter}_{datetime.now().strftime('%H%M%S')}"

    def add(
        self,
        url: str,
        filename: Optional[str] = None,
        priority: DownloadPriority = DownloadPriority.NORMAL,
        metadata: Dict = None,
        expected_md5: str = "",
        expected_sha256: str = "",
        skip_duplicate_check: bool = False
    ) -> Tuple[str, bool, Optional[str]]:
        """Add a download to the queue.

        Args:
            url: URL to download
            filename: Optional filename (extracted from URL if not provided)
            priority: Download priority
            metadata: Optional metadata dictionary
            expected_md5: Expected MD5 hash for verification
            expected_sha256: Expected SHA256 hash for verification
            skip_duplicate_check: Skip deduplication check

        Returns:
            Tuple of (download_id, is_duplicate, duplicate_path)
            If duplicate found and deduplication enabled, returns existing file path.
        """
        download_id = self._generate_id()

        # Determine filename
        if not filename:
            # Extract from URL or generate
            url_path = url.split('?')[0].split('/')[-1]
            filename = url_path if url_path else f"download_{download_id}"

        destination = self.download_dir / filename

        # Check for duplicates
        is_duplicate = False
        duplicate_path = None

        if self.enable_deduplication and not skip_duplicate_check:
            history = self._get_history()
            if history:
                # Check URL first
                dup_info = history.check_duplicate(
                    url=url,
                    md5_hash=expected_md5,
                    sha256_hash=expected_sha256
                )
                if dup_info.is_duplicate and dup_info.original_entry:
                    is_duplicate = True
                    duplicate_path = dup_info.original_entry.file_path
                    # Check if original file still exists
                    if Path(duplicate_path).exists():
                        # Return without queueing
                        item = DownloadItem(
                            download_id=download_id,
                            url=url,
                            destination=destination,
                            priority=priority,
                            status=DownloadStatus.COMPLETED,
                            metadata=metadata or {},
                            is_duplicate=True,
                            duplicate_of=duplicate_path
                        )
                        with self._lock:
                            self.items[download_id] = item
                        return download_id, True, duplicate_path

        item = DownloadItem(
            download_id=download_id,
            url=url,
            destination=destination,
            priority=priority,
            metadata=metadata or {},
            expected_md5=expected_md5,
            expected_sha256=expected_sha256
        )

        with self._lock:
            self.items[download_id] = item
            self.queue.put(item)

        return download_id, False, None

    def add_simple(
        self,
        url: str,
        filename: Optional[str] = None,
        priority: DownloadPriority = DownloadPriority.NORMAL,
        metadata: Dict = None
    ) -> str:
        """Simple add method for backward compatibility.

        Returns just the download_id without duplicate info.
        """
        download_id, _, _ = self.add(url, filename, priority, metadata)
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

    def complete(
        self,
        download_id: str,
        file_hash: str = "",
        md5_hash: str = "",
        sha256_hash: str = "",
        verify_checksum: bool = True
    ) -> Tuple[bool, str]:
        """Mark a download as completed.

        Args:
            download_id: ID of the download
            file_hash: Legacy hash parameter (SHA256)
            md5_hash: MD5 hash of downloaded file
            sha256_hash: SHA256 hash of downloaded file
            verify_checksum: Whether to verify against expected checksums

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            if download_id not in self.items:
                return False, "Download not found"

            item = self.items[download_id]

            # Use provided hashes or compute them
            if sha256_hash:
                item.sha256_hash = sha256_hash
            elif file_hash:
                item.sha256_hash = file_hash
            if md5_hash:
                item.md5_hash = md5_hash

            # Compute hashes if not provided and file exists
            if item.destination.exists() and (not item.sha256_hash or not item.md5_hash):
                try:
                    from blackreach.content_verify import compute_file_checksums
                    checksums = compute_file_checksums(item.destination)
                    if not item.md5_hash:
                        item.md5_hash = checksums["md5"]
                    if not item.sha256_hash:
                        item.sha256_hash = checksums["sha256"]
                except Exception:
                    pass

            # Verify checksum if expected values provided
            if verify_checksum:
                if item.expected_sha256 and item.sha256_hash:
                    if item.sha256_hash.lower() != item.expected_sha256.lower():
                        item.status = DownloadStatus.FAILED
                        item.error = "SHA256 checksum mismatch"
                        if download_id in self.active:
                            del self.active[download_id]
                        if self.on_error:
                            self.on_error(item, item.error)
                        return False, "SHA256 checksum mismatch"

                if item.expected_md5 and item.md5_hash:
                    if item.md5_hash.lower() != item.expected_md5.lower():
                        item.status = DownloadStatus.FAILED
                        item.error = "MD5 checksum mismatch"
                        if download_id in self.active:
                            del self.active[download_id]
                        if self.on_error:
                            self.on_error(item, item.error)
                        return False, "MD5 checksum mismatch"

            item.status = DownloadStatus.COMPLETED
            item.completed_at = datetime.now()
            item.progress = 100.0
            item.metadata["hash"] = item.sha256_hash
            item.metadata["md5"] = item.md5_hash

            if download_id in self.active:
                del self.active[download_id]

            # Record in history
            if self.enable_history:
                self._record_history(item)

            if self.on_complete:
                self.on_complete(item)

            return True, "Download completed successfully"

    def _record_history(self, item: DownloadItem):
        """Record completed download in history."""
        history = self._get_history()
        if history and not item.is_duplicate:
            try:
                from blackreach.download_history import DownloadSource
                history.add_entry(
                    url=item.url,
                    filename=item.destination.name,
                    file_path=item.destination,
                    file_size=item.size or item.downloaded,
                    md5_hash=item.md5_hash,
                    sha256_hash=item.sha256_hash,
                    source=DownloadSource.DIRECT,
                    metadata=item.metadata
                )
            except Exception:
                pass  # Don't fail download if history recording fails

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

    def check_duplicate(self, url: str = None, md5_hash: str = None, sha256_hash: str = None) -> Optional[Dict]:
        """Check if a URL or file hash is a duplicate.

        Returns:
            Dictionary with duplicate info or None if not a duplicate.
        """
        if not self.enable_deduplication:
            return None

        history = self._get_history()
        if not history:
            return None

        dup_info = history.check_duplicate(url, md5_hash, sha256_hash)
        if dup_info.is_duplicate:
            return {
                "is_duplicate": True,
                "type": dup_info.duplicate_type,
                "original_path": dup_info.original_entry.file_path if dup_info.original_entry else None,
                "original_url": dup_info.original_entry.url if dup_info.original_entry else None,
                "message": dup_info.message
            }
        return None

    def get_download_history(self, limit: int = 50) -> List[Dict]:
        """Get recent download history.

        Returns:
            List of history entry dictionaries.
        """
        history = self._get_history()
        if not history:
            return []

        entries = history.get_recent_downloads(limit)
        return [
            {
                "id": e.entry_id,
                "url": e.url,
                "filename": e.filename,
                "file_path": e.file_path,
                "file_size": e.file_size,
                "md5_hash": e.md5_hash,
                "sha256_hash": e.sha256_hash,
                "downloaded_at": e.downloaded_at.isoformat(),
                "source": e.source.value
            }
            for e in entries
        ]

    def get_history_stats(self) -> Optional[Dict]:
        """Get download history statistics."""
        history = self._get_history()
        if not history:
            return None
        return history.get_statistics()

    def find_by_hash(self, sha256_hash: str = None, md5_hash: str = None) -> Optional[str]:
        """Find a previously downloaded file by its hash.

        Returns:
            File path if found, None otherwise.
        """
        history = self._get_history()
        if not history:
            return None

        entry = history.check_hash_exists(md5_hash, sha256_hash)
        if entry and Path(entry.file_path).exists():
            return entry.file_path
        return None


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
