"""
Tests for Enhanced Download Queue System
Tests for history tracking and deduplication functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime

from blackreach.download_queue import (
    DownloadQueue, DownloadPriority, DownloadStatus, DownloadItem,
    QueueStats, get_download_queue
)


@pytest.fixture
def temp_dir():
    """Create a temporary download directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        os.unlink(db_path)


@pytest.fixture
def queue_with_history(temp_dir, temp_db):
    """Create a DownloadQueue with history enabled."""
    return DownloadQueue(
        download_dir=temp_dir,
        enable_history=True,
        enable_deduplication=True,
        history_db_path=temp_db
    )


@pytest.fixture
def queue_no_history(temp_dir):
    """Create a DownloadQueue without history."""
    return DownloadQueue(
        download_dir=temp_dir,
        enable_history=False,
        enable_deduplication=False
    )


class TestDownloadItemEnhancements:
    """Tests for enhanced DownloadItem fields."""

    def test_download_item_has_hash_fields(self):
        """Test that DownloadItem has hash fields."""
        item = DownloadItem(
            download_id="test_1",
            url="https://example.com/file.pdf",
            destination=Path("/tmp/file.pdf")
        )

        assert hasattr(item, 'md5_hash')
        assert hasattr(item, 'sha256_hash')
        assert hasattr(item, 'expected_md5')
        assert hasattr(item, 'expected_sha256')
        assert hasattr(item, 'is_duplicate')
        assert hasattr(item, 'duplicate_of')

    def test_download_item_default_values(self):
        """Test default values for new fields."""
        item = DownloadItem(
            download_id="test_2",
            url="https://example.com/file.pdf",
            destination=Path("/tmp/file.pdf")
        )

        assert item.md5_hash == ""
        assert item.sha256_hash == ""
        assert item.is_duplicate is False
        assert item.duplicate_of is None


class TestDownloadQueueAdd:
    """Tests for enhanced add method."""

    def test_add_returns_tuple(self, queue_no_history):
        """Test that add returns (id, is_duplicate, path) tuple."""
        result = queue_no_history.add(
            url="https://example.com/file.pdf",
            filename="file.pdf"
        )

        assert isinstance(result, tuple)
        assert len(result) == 3
        download_id, is_duplicate, dup_path = result
        assert download_id.startswith("dl_")
        assert is_duplicate is False
        assert dup_path is None

    def test_add_with_expected_checksums(self, queue_no_history):
        """Test adding with expected checksums."""
        download_id, _, _ = queue_no_history.add(
            url="https://example.com/file.pdf",
            expected_md5="abc123",
            expected_sha256="def456"
        )

        item = queue_no_history.get_item(download_id)
        assert item.expected_md5 == "abc123"
        assert item.expected_sha256 == "def456"

    def test_add_simple_backward_compat(self, queue_no_history):
        """Test add_simple for backward compatibility."""
        download_id = queue_no_history.add_simple(
            url="https://example.com/file.pdf"
        )

        assert isinstance(download_id, str)
        assert download_id.startswith("dl_")


class TestDeduplication:
    """Tests for deduplication functionality."""

    def test_duplicate_by_url(self, queue_with_history, temp_dir):
        """Test detecting duplicate by URL."""
        url = "https://example.com/unique_file.pdf"

        # Create a file at the expected destination
        (temp_dir / "unique_file.pdf").write_bytes(b"test content")

        # First add should work
        id1, is_dup1, path1 = queue_with_history.add(url=url)
        assert is_dup1 is False

        # Complete the first download to record in history
        queue_with_history.complete(id1, sha256_hash="test_hash")

        # Second add with same URL should detect duplicate
        id2, is_dup2, path2 = queue_with_history.add(url=url)
        assert is_dup2 is True
        assert path2 is not None

    def test_skip_duplicate_check(self, queue_with_history, temp_dir):
        """Test skipping duplicate check."""
        url = "https://example.com/force_download.pdf"

        # Create file and first download
        (temp_dir / "force_download.pdf").write_bytes(b"test")
        id1, _, _ = queue_with_history.add(url=url)
        queue_with_history.complete(id1, sha256_hash="hash1")

        # Force download despite duplicate
        id2, is_dup, _ = queue_with_history.add(
            url=url,
            skip_duplicate_check=True
        )
        assert is_dup is False

    def test_check_duplicate_method(self, queue_with_history, temp_dir):
        """Test check_duplicate method."""
        url = "https://example.com/check_test.pdf"

        # Initially not a duplicate
        result = queue_with_history.check_duplicate(url=url)
        assert result is None

        # Add and complete
        (temp_dir / "check_test.pdf").write_bytes(b"test")
        id1, _, _ = queue_with_history.add(url=url)
        queue_with_history.complete(id1, sha256_hash="hash123")

        # Now should be duplicate
        result = queue_with_history.check_duplicate(url=url)
        assert result is not None
        assert result["is_duplicate"] is True


class TestCompleteEnhanced:
    """Tests for enhanced complete method."""

    def test_complete_returns_tuple(self, queue_no_history, temp_dir):
        """Test that complete returns (success, message) tuple."""
        (temp_dir / "test.pdf").write_bytes(b"content")
        id1, _, _ = queue_no_history.add(url="https://example.com/test.pdf")
        queue_no_history.get_next()  # Start download

        success, message = queue_no_history.complete(id1)
        assert isinstance(success, bool)
        assert isinstance(message, str)

    def test_complete_with_hashes(self, queue_no_history, temp_dir):
        """Test completing with hash values."""
        (temp_dir / "hash_test.pdf").write_bytes(b"content")
        id1, _, _ = queue_no_history.add(url="https://example.com/hash_test.pdf")
        queue_no_history.get_next()

        success, _ = queue_no_history.complete(
            id1,
            md5_hash="abc123",
            sha256_hash="def456"
        )

        item = queue_no_history.get_item(id1)
        assert item.md5_hash == "abc123"
        assert item.sha256_hash == "def456"

    def test_complete_verifies_expected_sha256(self, queue_no_history, temp_dir):
        """Test checksum verification on complete."""
        (temp_dir / "verify.pdf").write_bytes(b"content")
        id1, _, _ = queue_no_history.add(
            url="https://example.com/verify.pdf",
            expected_sha256="expected_hash"
        )
        queue_no_history.get_next()

        # Wrong hash should fail
        success, message = queue_no_history.complete(
            id1,
            sha256_hash="wrong_hash"
        )

        assert success is False
        assert "mismatch" in message.lower()

        item = queue_no_history.get_item(id1)
        assert item.status == DownloadStatus.FAILED

    def test_complete_records_history(self, queue_with_history, temp_dir):
        """Test that complete records to history."""
        (temp_dir / "history_test.pdf").write_bytes(b"content")
        id1, _, _ = queue_with_history.add(url="https://example.com/history_test.pdf")
        queue_with_history.get_next()
        queue_with_history.complete(id1, sha256_hash="hash123")

        history = queue_with_history.get_download_history(limit=10)
        assert len(history) > 0
        assert any(h["sha256_hash"] == "hash123" for h in history)


class TestHistoryMethods:
    """Tests for history-related methods."""

    def test_get_download_history(self, queue_with_history, temp_dir):
        """Test getting download history."""
        for i in range(3):
            filename = f"file{i}.pdf"
            (temp_dir / filename).write_bytes(b"content")
            id_, _, _ = queue_with_history.add(
                url=f"https://example.com/{filename}",
                filename=filename
            )
            queue_with_history.get_next()
            queue_with_history.complete(id_, sha256_hash=f"hash{i}")

        history = queue_with_history.get_download_history(limit=10)
        assert len(history) == 3

    def test_get_history_stats(self, queue_with_history, temp_dir):
        """Test getting history statistics."""
        (temp_dir / "stat_test.pdf").write_bytes(b"content")
        id1, _, _ = queue_with_history.add(url="https://example.com/stat_test.pdf")
        queue_with_history.get_next()
        queue_with_history.complete(id1, sha256_hash="hash")

        stats = queue_with_history.get_history_stats()
        assert stats is not None
        assert "total_downloads" in stats
        assert stats["total_downloads"] >= 1

    def test_find_by_hash(self, queue_with_history, temp_dir):
        """Test finding file by hash."""
        file_path = temp_dir / "findme.pdf"
        file_path.write_bytes(b"findable content")

        id1, _, _ = queue_with_history.add(
            url="https://example.com/findme.pdf",
            filename="findme.pdf"
        )
        queue_with_history.get_next()
        queue_with_history.complete(id1, sha256_hash="findable_hash")

        found_path = queue_with_history.find_by_hash(sha256_hash="findable_hash")
        assert found_path is not None
        assert "findme.pdf" in found_path

    def test_find_by_hash_nonexistent(self, queue_with_history):
        """Test finding non-existent hash."""
        found = queue_with_history.find_by_hash(sha256_hash="nonexistent")
        assert found is None


class TestDisabledHistory:
    """Tests for queue with history disabled."""

    def test_no_history_methods_return_none(self, queue_no_history):
        """Test history methods return None/empty when disabled."""
        assert queue_no_history.get_history_stats() is None
        assert queue_no_history.get_download_history() == []
        assert queue_no_history.find_by_hash("any_hash") is None
        assert queue_no_history.check_duplicate(url="any_url") is None
