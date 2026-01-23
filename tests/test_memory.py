"""
Unit tests for blackreach/memory.py

Tests both SessionMemory (RAM) and PersistentMemory (SQLite).
"""

import pytest
from pathlib import Path

from blackreach.memory import SessionMemory, PersistentMemory


# =============================================================================
# SessionMemory Tests
# =============================================================================

class TestSessionMemory:
    """Tests for the in-memory session storage."""

    def test_init_empty(self):
        """SessionMemory initializes with empty collections."""
        mem = SessionMemory()
        assert mem.downloaded_files == []
        assert mem.downloaded_urls == []
        assert mem.visited_urls == []
        assert mem.actions_taken == []
        assert mem.failures == []

    def test_add_download_file_only(self):
        """Can add download with filename only."""
        mem = SessionMemory()
        mem.add_download("test.pdf")

        assert "test.pdf" in mem.downloaded_files
        assert len(mem.downloaded_urls) == 0

    def test_add_download_with_url(self):
        """Can add download with filename and URL."""
        mem = SessionMemory()
        mem.add_download("test.pdf", "https://example.com/test.pdf")

        assert "test.pdf" in mem.downloaded_files
        assert "https://example.com/test.pdf" in mem.downloaded_urls

    def test_add_download_url_dedup(self):
        """Duplicate URLs are not added to downloaded_urls."""
        mem = SessionMemory()
        url = "https://example.com/test.pdf"

        mem.add_download("test1.pdf", url)
        mem.add_download("test2.pdf", url)  # Same URL

        assert len(mem.downloaded_files) == 2
        assert len(mem.downloaded_urls) == 1

    def test_add_visit(self):
        """Can add visited URL."""
        mem = SessionMemory()
        mem.add_visit("https://example.com")

        assert "https://example.com" in mem.visited_urls

    def test_add_visit_dedup(self):
        """Duplicate visits are not added."""
        mem = SessionMemory()
        mem.add_visit("https://example.com")
        mem.add_visit("https://example.com")

        assert len(mem.visited_urls) == 1

    def test_add_action(self):
        """Can add action to history."""
        mem = SessionMemory()
        action = {"action": "click", "selector": "#btn"}
        mem.add_action(action)

        assert action in mem.actions_taken

    def test_add_failure(self):
        """Can record failures."""
        mem = SessionMemory()
        mem.add_failure("Connection timeout")

        assert "Connection timeout" in mem.failures

    def test_get_history_empty(self):
        """get_history returns empty string when no actions."""
        mem = SessionMemory()
        assert mem.get_history() == ""

    def test_get_history_format(self):
        """get_history formats actions correctly."""
        mem = SessionMemory()
        mem.add_action({"action": "click", "selector": "#btn"})
        mem.add_action({"action": "navigate", "url": "https://example.com"})

        history = mem.get_history()
        assert "click" in history
        assert "navigate" in history

    def test_get_history_limit(self):
        """get_history respects the limit parameter."""
        mem = SessionMemory()
        for i in range(10):
            mem.add_action({"action": f"action_{i}"})

        history = mem.get_history(n=3)
        assert "action_7" in history
        assert "action_8" in history
        assert "action_9" in history
        assert "action_0" not in history

    def test_last_failure_empty(self):
        """last_failure returns 'None' when no failures."""
        mem = SessionMemory()
        assert mem.last_failure == "None"

    def test_last_failure_returns_most_recent(self):
        """last_failure returns the most recent failure."""
        mem = SessionMemory()
        mem.add_failure("Error 1")
        mem.add_failure("Error 2")

        assert mem.last_failure == "Error 2"


# =============================================================================
# PersistentMemory Tests
# =============================================================================

class TestPersistentMemory:
    """Tests for SQLite-backed persistent storage."""

    def test_init_creates_db(self, memory_db):
        """PersistentMemory creates database file."""
        mem = PersistentMemory(memory_db)
        assert memory_db.exists()
        mem.close()

    def test_init_creates_tables(self, memory_db):
        """Database has all required tables."""
        import sqlite3

        mem = PersistentMemory(memory_db)
        conn = sqlite3.connect(str(memory_db))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "downloads" in tables
        assert "visits" in tables
        assert "site_patterns" in tables
        assert "failures" in tables
        assert "sessions" in tables

        conn.close()
        mem.close()

    # -------------------------------------------------------------------------
    # Download Tests
    # -------------------------------------------------------------------------

    def test_add_download(self, memory_db):
        """Can add a download record."""
        mem = PersistentMemory(memory_db)
        mem.add_download("test.pdf", url="https://example.com/test.pdf")

        downloads = mem.get_downloads()
        assert len(downloads) == 1
        assert downloads[0]["filename"] == "test.pdf"
        mem.close()

    def test_add_download_with_all_fields(self, memory_db):
        """Can add download with all optional fields."""
        mem = PersistentMemory(memory_db)
        mem.add_download(
            filename="paper.pdf",
            url="https://arxiv.org/pdf/123.pdf",
            source_site="arxiv.org",
            goal="download papers",
            file_hash="abc123",
            file_size=1024000
        )

        downloads = mem.get_downloads()
        assert downloads[0]["source_site"] == "arxiv.org"
        assert downloads[0]["file_hash"] == "abc123"
        assert downloads[0]["file_size"] == 1024000
        mem.close()

    def test_has_downloaded_by_url(self, memory_db):
        """has_downloaded works with URL."""
        mem = PersistentMemory(memory_db)
        url = "https://example.com/file.pdf"

        assert not mem.has_downloaded(url=url)
        mem.add_download("file.pdf", url=url)
        assert mem.has_downloaded(url=url)
        mem.close()

    def test_has_downloaded_by_hash(self, memory_db):
        """has_downloaded works with file hash."""
        mem = PersistentMemory(memory_db)

        assert not mem.has_downloaded(file_hash="abc123")
        mem.add_download("file.pdf", file_hash="abc123")
        assert mem.has_downloaded(file_hash="abc123")
        mem.close()

    def test_has_downloaded_no_params(self, memory_db):
        """has_downloaded returns False when no params given."""
        mem = PersistentMemory(memory_db)
        assert not mem.has_downloaded()
        mem.close()

    def test_get_downloads_limit(self, memory_db):
        """get_downloads respects limit."""
        mem = PersistentMemory(memory_db)
        for i in range(10):
            mem.add_download(f"file_{i}.pdf")

        downloads = mem.get_downloads(limit=5)
        assert len(downloads) == 5
        mem.close()

    def test_get_downloads_order(self, memory_db):
        """get_downloads returns most recent first (by ID when timestamps match)."""
        mem = PersistentMemory(memory_db)
        mem.add_download("first.pdf")
        mem.add_download("second.pdf")
        mem.add_download("third.pdf")

        downloads = mem.get_downloads()
        # With same timestamps, ORDER BY DESC returns higher IDs first
        # So third.pdf (id=3) comes before first.pdf (id=1)
        filenames = [d["filename"] for d in downloads]
        assert "first.pdf" in filenames
        assert "third.pdf" in filenames
        assert len(downloads) == 3
        mem.close()

    # -------------------------------------------------------------------------
    # Visit Tests
    # -------------------------------------------------------------------------

    def test_add_visit(self, memory_db):
        """Can add a visit record."""
        mem = PersistentMemory(memory_db)
        mem.add_visit("https://example.com", title="Example")

        assert mem.has_visited("https://example.com")
        mem.close()

    def test_has_visited_false(self, memory_db):
        """has_visited returns False for unvisited URL."""
        mem = PersistentMemory(memory_db)
        assert not mem.has_visited("https://never-visited.com")
        mem.close()

    def test_get_visits_for_domain(self, memory_db):
        """get_visits_for_domain filters correctly."""
        mem = PersistentMemory(memory_db)
        mem.add_visit("https://arxiv.org/page1")
        mem.add_visit("https://arxiv.org/page2")
        mem.add_visit("https://github.com/repo")

        arxiv_visits = mem.get_visits_for_domain("arxiv.org")
        assert len(arxiv_visits) == 2
        mem.close()

    # -------------------------------------------------------------------------
    # Site Pattern Tests
    # -------------------------------------------------------------------------

    def test_record_pattern_success(self, memory_db):
        """Can record successful pattern."""
        mem = PersistentMemory(memory_db)
        mem.record_pattern("arxiv.org", "search_selector", "#search", success=True)

        patterns = mem.get_best_patterns("arxiv.org", "search_selector")
        assert "#search" in patterns
        mem.close()

    def test_record_pattern_failure(self, memory_db):
        """Can record failed pattern."""
        mem = PersistentMemory(memory_db)
        mem.record_pattern("arxiv.org", "search_selector", "#bad", success=False)

        # Still in patterns but with low success rate
        patterns = mem.get_best_patterns("arxiv.org", "search_selector")
        assert "#bad" in patterns
        mem.close()

    def test_get_best_patterns_order(self, memory_db):
        """Patterns are ordered by success rate."""
        mem = PersistentMemory(memory_db)

        # Add pattern with 3 successes
        for _ in range(3):
            mem.record_pattern("test.com", "btn", "#good", success=True)

        # Add pattern with 1 success, 2 failures
        mem.record_pattern("test.com", "btn", "#bad", success=True)
        mem.record_pattern("test.com", "btn", "#bad", success=False)
        mem.record_pattern("test.com", "btn", "#bad", success=False)

        patterns = mem.get_best_patterns("test.com", "btn")
        assert patterns[0] == "#good"  # Higher success rate first
        mem.close()

    # -------------------------------------------------------------------------
    # Failure Tests
    # -------------------------------------------------------------------------

    def test_add_failure(self, memory_db):
        """Can record failure."""
        mem = PersistentMemory(memory_db)
        mem.add_failure("https://example.com", "click", "Element not found")

        failures = mem.get_common_failures()
        assert len(failures) == 1
        assert failures[0]["action"] == "click"
        mem.close()

    def test_get_common_failures_grouped(self, memory_db):
        """Common failures are grouped and counted."""
        mem = PersistentMemory(memory_db)

        # Same error 3 times
        for _ in range(3):
            mem.add_failure("https://example.com", "click", "Timeout")

        # Different error once
        mem.add_failure("https://example.com", "navigate", "404")

        failures = mem.get_common_failures()
        assert failures[0]["count"] == 3
        assert failures[0]["error_message"] == "Timeout"
        mem.close()

    def test_get_common_failures_by_domain(self, memory_db):
        """Can filter failures by domain."""
        mem = PersistentMemory(memory_db)
        mem.add_failure("https://arxiv.org/page", "click", "Error")
        mem.add_failure("https://github.com/repo", "click", "Error")

        arxiv_failures = mem.get_common_failures(domain="arxiv.org")
        assert len(arxiv_failures) == 1
        mem.close()

    # -------------------------------------------------------------------------
    # Session Tests
    # -------------------------------------------------------------------------

    def test_start_session(self, memory_db):
        """start_session returns session ID."""
        mem = PersistentMemory(memory_db)
        session_id = mem.start_session("download papers")

        assert session_id is not None
        assert session_id > 0
        mem.close()

    def test_end_session(self, memory_db):
        """end_session updates session record."""
        mem = PersistentMemory(memory_db)
        session_id = mem.start_session("test goal")
        mem.end_session(session_id, steps=10, downloads=5, success=True)

        # Verify via stats
        stats = mem.get_stats()
        assert stats["total_sessions"] == 1
        mem.close()

    # -------------------------------------------------------------------------
    # Stats Tests
    # -------------------------------------------------------------------------

    def test_get_stats_empty(self, memory_db):
        """get_stats works on empty database."""
        mem = PersistentMemory(memory_db)
        stats = mem.get_stats()

        assert stats["total_downloads"] == 0
        assert stats["total_visits"] == 0
        assert stats["total_sessions"] == 0
        assert stats["total_failures"] == 0
        assert stats["known_domains"] == 0
        mem.close()

    def test_get_stats_populated(self, memory_db):
        """get_stats returns correct counts."""
        mem = PersistentMemory(memory_db)

        mem.add_download("file1.pdf")
        mem.add_download("file2.pdf")
        mem.add_visit("https://example.com")
        mem.start_session("test")
        mem.add_failure("https://example.com", "click", "error")
        mem.record_pattern("example.com", "btn", "#btn")

        stats = mem.get_stats()
        assert stats["total_downloads"] == 2
        assert stats["total_visits"] == 1
        assert stats["total_sessions"] == 1
        assert stats["total_failures"] == 1
        assert stats["known_domains"] == 1
        mem.close()

    def test_close_connection(self, memory_db):
        """close() properly closes database connection."""
        mem = PersistentMemory(memory_db)
        mem.close()

        # Connection should be None after close
        assert mem._conn is None


# =============================================================================
# Integration Tests
# =============================================================================

class TestMemoryIntegration:
    """Tests for using both memory types together."""

    def test_session_and_persistent_sync(self, memory_db):
        """Session actions can be persisted correctly."""
        session = SessionMemory()
        persistent = PersistentMemory(memory_db)

        # Simulate agent workflow
        session.add_visit("https://arxiv.org")
        persistent.add_visit("https://arxiv.org")

        session.add_download("paper.pdf", "https://arxiv.org/pdf/123.pdf")
        persistent.add_download("paper.pdf", "https://arxiv.org/pdf/123.pdf")

        # Session has the data
        assert "paper.pdf" in session.downloaded_files

        # Persistent has the data
        assert persistent.has_downloaded(url="https://arxiv.org/pdf/123.pdf")

        persistent.close()

    def test_dedup_across_sessions(self, memory_db):
        """Persistent memory prevents re-downloads across sessions."""
        # First "session"
        mem1 = PersistentMemory(memory_db)
        mem1.add_download("paper.pdf", url="https://arxiv.org/pdf/123.pdf", file_hash="abc123")
        mem1.close()

        # Second "session" - new instance
        mem2 = PersistentMemory(memory_db)

        # Should detect duplicate by URL
        assert mem2.has_downloaded(url="https://arxiv.org/pdf/123.pdf")

        # Should detect duplicate by hash
        assert mem2.has_downloaded(file_hash="abc123")

        mem2.close()
