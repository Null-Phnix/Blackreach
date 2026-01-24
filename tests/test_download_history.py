"""
Tests for Download History System
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

from blackreach.download_history import (
    DownloadHistory, DownloadSource, HistoryEntry, DuplicateInfo,
    get_download_history
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        os.unlink(db_path)


@pytest.fixture
def history(temp_db):
    """Create a DownloadHistory instance with temp database."""
    return DownloadHistory(temp_db)


class TestDownloadHistory:
    """Tests for DownloadHistory class."""

    def test_init_creates_database(self, temp_db):
        """Test that initialization creates the database."""
        history = DownloadHistory(temp_db)
        assert temp_db.exists()

    def test_add_entry(self, history):
        """Test adding a download entry."""
        entry_id = history.add_entry(
            url="https://example.com/file.pdf",
            filename="file.pdf",
            file_path=Path("/downloads/file.pdf"),
            file_size=1024,
            md5_hash="abc123",
            sha256_hash="def456",
            source=DownloadSource.DIRECT,
            metadata={"author": "Test"}
        )
        assert entry_id > 0

    def test_check_url_exists(self, history):
        """Test checking if URL exists."""
        url = "https://example.com/unique.pdf"

        # Should not exist initially
        assert history.check_url_exists(url) is None

        # Add entry
        history.add_entry(
            url=url,
            filename="unique.pdf",
            file_path=Path("/downloads/unique.pdf"),
            file_size=2048
        )

        # Should exist now
        entry = history.check_url_exists(url)
        assert entry is not None
        assert entry.url == url

    def test_check_hash_exists(self, history):
        """Test checking if hash exists."""
        sha256 = "abcdef1234567890"

        # Should not exist initially
        assert history.check_hash_exists(sha256_hash=sha256) is None

        # Add entry
        history.add_entry(
            url="https://example.com/file.pdf",
            filename="file.pdf",
            file_path=Path("/downloads/file.pdf"),
            sha256_hash=sha256
        )

        # Should exist now
        entry = history.check_hash_exists(sha256_hash=sha256)
        assert entry is not None
        assert entry.sha256_hash == sha256

    def test_check_duplicate_by_url(self, history):
        """Test duplicate detection by URL."""
        url = "https://example.com/dup.pdf"

        history.add_entry(
            url=url,
            filename="dup.pdf",
            file_path=Path("/downloads/dup.pdf")
        )

        dup_info = history.check_duplicate(url=url)
        assert dup_info.is_duplicate is True
        assert dup_info.duplicate_type == "url"

    def test_check_duplicate_by_hash(self, history):
        """Test duplicate detection by hash."""
        sha256 = "unique_hash_123"

        history.add_entry(
            url="https://example.com/original.pdf",
            filename="original.pdf",
            file_path=Path("/downloads/original.pdf"),
            sha256_hash=sha256
        )

        # Different URL, same hash
        dup_info = history.check_duplicate(
            url="https://different.com/copy.pdf",
            sha256_hash=sha256
        )
        assert dup_info.is_duplicate is True
        assert dup_info.duplicate_type == "hash"

    def test_check_no_duplicate(self, history):
        """Test when no duplicate exists."""
        dup_info = history.check_duplicate(
            url="https://new.com/new.pdf",
            sha256_hash="new_hash"
        )
        assert dup_info.is_duplicate is False
        assert dup_info.duplicate_type == "none"

    def test_get_recent_downloads(self, history):
        """Test getting recent downloads."""
        # Add multiple entries
        for i in range(5):
            history.add_entry(
                url=f"https://example.com/file{i}.pdf",
                filename=f"file{i}.pdf",
                file_path=Path(f"/downloads/file{i}.pdf")
            )

        recent = history.get_recent_downloads(limit=3)
        assert len(recent) == 3

    def test_search_history(self, history):
        """Test searching history."""
        history.add_entry(
            url="https://example.com/python_book.pdf",
            filename="python_book.pdf",
            file_path=Path("/downloads/python_book.pdf")
        )
        history.add_entry(
            url="https://example.com/java_guide.pdf",
            filename="java_guide.pdf",
            file_path=Path("/downloads/java_guide.pdf")
        )

        results = history.search_history(query="python")
        assert len(results) == 1
        assert "python" in results[0].filename

    def test_get_statistics(self, history):
        """Test getting statistics."""
        history.add_entry(
            url="https://example.com/file1.pdf",
            filename="file1.pdf",
            file_path=Path("/downloads/file1.pdf"),
            file_size=1000,
            source=DownloadSource.DIRECT
        )
        history.add_entry(
            url="https://example.com/file2.pdf",
            filename="file2.pdf",
            file_path=Path("/downloads/file2.pdf"),
            file_size=2000,
            source=DownloadSource.SEARCH
        )

        stats = history.get_statistics()
        assert stats["total_downloads"] == 2
        assert stats["total_size_bytes"] == 3000
        assert "direct" in stats["by_source"]

    def test_delete_entry(self, history):
        """Test deleting an entry."""
        entry_id = history.add_entry(
            url="https://example.com/delete_me.pdf",
            filename="delete_me.pdf",
            file_path=Path("/downloads/delete_me.pdf")
        )

        assert history.get_entry_by_id(entry_id) is not None
        result = history.delete_entry(entry_id)
        assert result is True
        assert history.get_entry_by_id(entry_id) is None

    def test_clear_history(self, history):
        """Test clearing history."""
        for i in range(3):
            history.add_entry(
                url=f"https://example.com/file{i}.pdf",
                filename=f"file{i}.pdf",
                file_path=Path(f"/downloads/file{i}.pdf")
            )

        count = history.clear_history()
        assert count == 3
        assert len(history.get_recent_downloads()) == 0

    def test_export_import_history(self, history, temp_db):
        """Test exporting and importing history."""
        # Add entries
        history.add_entry(
            url="https://example.com/export_test.pdf",
            filename="export_test.pdf",
            file_path=Path("/downloads/export_test.pdf"),
            sha256_hash="export_hash"
        )

        # Export
        export_path = temp_db.parent / "export.json"
        exported = history.export_history(export_path)
        assert exported == 1
        assert export_path.exists()

        # Clear and import
        history.clear_history()
        assert len(history.get_recent_downloads()) == 0

        imported = history.import_history(export_path)
        assert imported == 1

        entries = history.get_recent_downloads()
        assert len(entries) == 1
        assert entries[0].filename == "export_test.pdf"

        # Cleanup
        export_path.unlink()


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""

    def test_from_row(self):
        """Test creating entry from database row."""
        row = (
            1,  # id
            "https://example.com/test.pdf",  # url
            "test.pdf",  # filename
            "/downloads/test.pdf",  # file_path
            1024,  # file_size
            "md5hash",  # md5_hash
            "sha256hash",  # sha256_hash
            "2024-01-15T10:30:00",  # downloaded_at
            "direct",  # source
            '{"key": "value"}'  # metadata
        )

        entry = HistoryEntry.from_row(row)
        assert entry.entry_id == 1
        assert entry.url == "https://example.com/test.pdf"
        assert entry.file_size == 1024
        assert entry.source == DownloadSource.DIRECT
        assert entry.metadata == {"key": "value"}


class TestDuplicateInfo:
    """Tests for DuplicateInfo dataclass."""

    def test_duplicate_info_creation(self):
        """Test creating DuplicateInfo."""
        info = DuplicateInfo(
            is_duplicate=True,
            duplicate_type="url",
            message="Already downloaded"
        )
        assert info.is_duplicate is True
        assert info.duplicate_type == "url"
        assert info.original_entry is None
