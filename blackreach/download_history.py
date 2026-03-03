"""
Download History Tracking System (v1.0.0)

Tracks download history to prevent re-downloading same files:
- Persistent history storage (SQLite)
- URL-based deduplication
- Hash-based deduplication
- Download statistics and analytics
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging
import sqlite3
import json
import hashlib
import threading

logger = logging.getLogger(__name__)


class DownloadSource(Enum):
    """Source of the download."""
    DIRECT = "direct"
    SEARCH = "search"
    CRAWL = "crawl"
    API = "api"
    MANUAL = "manual"


@dataclass
class HistoryEntry:
    """Represents a download history entry."""
    entry_id: int
    url: str
    filename: str
    file_path: str
    file_size: int
    md5_hash: str
    sha256_hash: str
    downloaded_at: datetime
    source: DownloadSource
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: tuple) -> "HistoryEntry":
        """Create entry from database row."""
        return cls(
            entry_id=row[0],
            url=row[1],
            filename=row[2],
            file_path=row[3],
            file_size=row[4],
            md5_hash=row[5],
            sha256_hash=row[6],
            downloaded_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
            source=DownloadSource(row[8]) if row[8] else DownloadSource.DIRECT,
            metadata=json.loads(row[9]) if row[9] else {}
        )


@dataclass
class DuplicateInfo:
    """Information about a duplicate file."""
    is_duplicate: bool
    duplicate_type: str  # 'url', 'hash', 'none'
    original_entry: Optional[HistoryEntry] = None
    message: str = ""


class DownloadHistory:
    """Manages download history with persistent storage."""

    def __init__(self, db_path: Path = None):
        """Initialize download history.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.blackreach/download_history.db
        """
        if db_path is None:
            db_path = Path.home() / ".blackreach" / "download_history.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    md5_hash TEXT,
                    sha256_hash TEXT,
                    downloaded_at TEXT NOT NULL,
                    source TEXT DEFAULT 'direct',
                    metadata TEXT
                )
            """)

            # Create indexes for fast lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON download_history(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_md5 ON download_history(md5_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sha256 ON download_history(sha256_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_filename ON download_history(filename)")
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path, timeout=10.0)

    def add_entry(
        self,
        url: str,
        filename: str,
        file_path: Path,
        file_size: int = 0,
        md5_hash: str = "",
        sha256_hash: str = "",
        source: DownloadSource = DownloadSource.DIRECT,
        metadata: Dict = None
    ) -> int:
        """Add a download to history.

        Returns:
            The entry ID of the new record.
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO download_history
                    (url, filename, file_path, file_size, md5_hash, sha256_hash,
                     downloaded_at, source, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    url,
                    filename,
                    str(file_path),
                    file_size,
                    md5_hash,
                    sha256_hash,
                    datetime.now().isoformat(),
                    source.value,
                    json.dumps(metadata or {})
                ))
                conn.commit()
                return cursor.lastrowid

    def check_url_exists(self, url: str) -> Optional[HistoryEntry]:
        """Check if a URL has been downloaded before.

        Returns:
            HistoryEntry if URL exists, None otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM download_history WHERE url = ? ORDER BY downloaded_at DESC LIMIT 1",
                (url,)
            )
            row = cursor.fetchone()
            if row:
                return HistoryEntry.from_row(row)
        return None

    def check_hash_exists(
        self,
        md5_hash: str = None,
        sha256_hash: str = None
    ) -> Optional[HistoryEntry]:
        """Check if a file with the same hash has been downloaded.

        Returns:
            HistoryEntry if hash exists, None otherwise.
        """
        with self._get_connection() as conn:
            if sha256_hash:
                cursor = conn.execute(
                    "SELECT * FROM download_history WHERE sha256_hash = ? LIMIT 1",
                    (sha256_hash,)
                )
                row = cursor.fetchone()
                if row:
                    return HistoryEntry.from_row(row)

            if md5_hash:
                cursor = conn.execute(
                    "SELECT * FROM download_history WHERE md5_hash = ? LIMIT 1",
                    (md5_hash,)
                )
                row = cursor.fetchone()
                if row:
                    return HistoryEntry.from_row(row)

        return None

    def check_duplicate(
        self,
        url: str = None,
        md5_hash: str = None,
        sha256_hash: str = None
    ) -> DuplicateInfo:
        """Check if a download would be a duplicate.

        Args:
            url: URL to check
            md5_hash: MD5 hash to check
            sha256_hash: SHA256 hash to check

        Returns:
            DuplicateInfo with duplicate status and original entry if found.
        """
        # Check URL first (fastest)
        if url:
            entry = self.check_url_exists(url)
            if entry:
                return DuplicateInfo(
                    is_duplicate=True,
                    duplicate_type="url",
                    original_entry=entry,
                    message=f"URL already downloaded on {entry.downloaded_at.strftime('%Y-%m-%d %H:%M')}"
                )

        # Check hash (more reliable)
        entry = self.check_hash_exists(md5_hash, sha256_hash)
        if entry:
            return DuplicateInfo(
                is_duplicate=True,
                duplicate_type="hash",
                original_entry=entry,
                message=f"File with same hash already exists: {entry.filename}"
            )

        return DuplicateInfo(
            is_duplicate=False,
            duplicate_type="none",
            message="No duplicate found"
        )

    def get_entry_by_id(self, entry_id: int) -> Optional[HistoryEntry]:
        """Get a specific history entry by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM download_history WHERE id = ?",
                (entry_id,)
            )
            row = cursor.fetchone()
            if row:
                return HistoryEntry.from_row(row)
        return None

    def get_recent_downloads(self, limit: int = 50) -> List[HistoryEntry]:
        """Get most recent downloads."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM download_history ORDER BY downloaded_at DESC LIMIT ?",
                (limit,)
            )
            return [HistoryEntry.from_row(row) for row in cursor.fetchall()]

    def search_history(
        self,
        query: str = None,
        source: DownloadSource = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> List[HistoryEntry]:
        """Search download history with filters."""
        conditions = []
        params = []

        if query:
            conditions.append("(filename LIKE ? OR url LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        if source:
            conditions.append("source = ?")
            params.append(source.value)

        if start_date:
            conditions.append("downloaded_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            conditions.append("downloaded_at <= ?")
            params.append(end_date.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM download_history WHERE {where_clause} "
                f"ORDER BY downloaded_at DESC LIMIT ?",
                params + [limit]
            )
            return [HistoryEntry.from_row(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict:
        """Get download statistics."""
        with self._get_connection() as conn:
            # Total downloads
            total = conn.execute("SELECT COUNT(*) FROM download_history").fetchone()[0]

            # Total size
            total_size = conn.execute(
                "SELECT SUM(file_size) FROM download_history"
            ).fetchone()[0] or 0

            # By source
            by_source = {}
            for row in conn.execute(
                "SELECT source, COUNT(*) FROM download_history GROUP BY source"
            ):
                by_source[row[0]] = row[1]

            # Unique files (by hash)
            unique_by_hash = conn.execute(
                "SELECT COUNT(DISTINCT sha256_hash) FROM download_history WHERE sha256_hash != ''"
            ).fetchone()[0]

            # Duplicates prevented (same hash, different entries)
            duplicates = conn.execute("""
                SELECT COUNT(*) - COUNT(DISTINCT sha256_hash)
                FROM download_history WHERE sha256_hash != ''
            """).fetchone()[0]

            # Downloads by day (last 30 days)
            daily = {}
            for row in conn.execute("""
                SELECT DATE(downloaded_at) as day, COUNT(*)
                FROM download_history
                WHERE downloaded_at >= DATE('now', '-30 days')
                GROUP BY day ORDER BY day
            """):
                daily[row[0]] = row[1]

            return {
                "total_downloads": total,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "by_source": by_source,
                "unique_files": unique_by_hash,
                "duplicates_found": duplicates,
                "daily_downloads": daily
            }

    def delete_entry(self, entry_id: int) -> bool:
        """Delete a history entry by ID."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM download_history WHERE id = ?",
                    (entry_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def clear_history(self, before_date: datetime = None) -> int:
        """Clear download history.

        Args:
            before_date: If provided, only clear entries before this date.

        Returns:
            Number of entries deleted.
        """
        with self._lock:
            with self._get_connection() as conn:
                if before_date:
                    cursor = conn.execute(
                        "DELETE FROM download_history WHERE downloaded_at < ?",
                        (before_date.isoformat(),)
                    )
                else:
                    cursor = conn.execute("DELETE FROM download_history")
                conn.commit()
                return cursor.rowcount

    def export_history(self, output_path: Path) -> int:
        """Export history to JSON file.

        Returns:
            Number of entries exported.
        """
        entries = self.get_recent_downloads(limit=10000)

        data = {
            "exported_at": datetime.now().isoformat(),
            "total_entries": len(entries),
            "entries": [
                {
                    "id": e.entry_id,
                    "url": e.url,
                    "filename": e.filename,
                    "file_path": e.file_path,
                    "file_size": e.file_size,
                    "md5_hash": e.md5_hash,
                    "sha256_hash": e.sha256_hash,
                    "downloaded_at": e.downloaded_at.isoformat(),
                    "source": e.source.value,
                    "metadata": e.metadata
                }
                for e in entries
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        return len(entries)

    def import_history(self, input_path: Path) -> int:
        """Import history from JSON file.

        Returns:
            Number of entries imported.
        """
        with open(input_path, 'r') as f:
            data = json.load(f)

        count = 0
        for entry in data.get("entries", []):
            try:
                self.add_entry(
                    url=entry["url"],
                    filename=entry["filename"],
                    file_path=Path(entry["file_path"]),
                    file_size=entry.get("file_size", 0),
                    md5_hash=entry.get("md5_hash", ""),
                    sha256_hash=entry.get("sha256_hash", ""),
                    source=DownloadSource(entry.get("source", "direct")),
                    metadata=entry.get("metadata", {})
                )
                count += 1
            except (KeyError, ValueError, sqlite3.DatabaseError) as e:
                logger.debug("Skipping invalid history entry during import: %s", e)
                continue

        return count


# Global instance
_download_history: Optional[DownloadHistory] = None


def get_download_history(db_path: Path = None) -> DownloadHistory:
    """Get the global download history instance."""
    global _download_history
    if _download_history is None:
        _download_history = DownloadHistory(db_path)
    return _download_history
