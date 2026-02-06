"""
Tests for the Session Management System module.

Tests cover:
- SessionStatus enum
- SessionSnapshot dataclass
- SessionState dataclass
- LearningData dataclass
- SessionManager class (database operations, snapshots, learning)
- Global get_session_manager function
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import sqlite3
import json
import os

from blackreach.session_manager import (
    SessionStatus,
    SessionSnapshot,
    SessionState,
    LearningData,
    SessionManager,
    get_session_manager,
)


# =============================================================================
# SessionStatus Enum Tests
# =============================================================================

class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_active_value(self):
        """SessionStatus.ACTIVE should have value 'active'."""
        assert SessionStatus.ACTIVE.value == "active"

    def test_paused_value(self):
        """SessionStatus.PAUSED should have value 'paused'."""
        assert SessionStatus.PAUSED.value == "paused"

    def test_completed_value(self):
        """SessionStatus.COMPLETED should have value 'completed'."""
        assert SessionStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        """SessionStatus.FAILED should have value 'failed'."""
        assert SessionStatus.FAILED.value == "failed"

    def test_interrupted_value(self):
        """SessionStatus.INTERRUPTED should have value 'interrupted'."""
        assert SessionStatus.INTERRUPTED.value == "interrupted"

    def test_all_status_values_unique(self):
        """All SessionStatus values should be unique."""
        values = [s.value for s in SessionStatus]
        assert len(values) == len(set(values))

    def test_can_iterate_all_statuses(self):
        """Should be able to iterate through all statuses."""
        statuses = list(SessionStatus)
        assert len(statuses) == 5

    def test_status_from_string(self):
        """Should be able to create status from string value."""
        for status in SessionStatus:
            assert SessionStatus(status.value) == status


# =============================================================================
# SessionSnapshot Dataclass Tests
# =============================================================================

class TestSessionSnapshot:
    """Tests for SessionSnapshot dataclass."""

    def test_minimal_creation(self):
        """SessionSnapshot can be created with required fields."""
        snapshot = SessionSnapshot(
            snapshot_id="snap_1",
            session_id=1,
            step_number=5,
            timestamp=datetime.now(),
            url="https://example.com",
            goal="Test goal",
            downloads=[],
            visited_urls=[],
            actions_taken=[],
            failures=[]
        )
        assert snapshot.snapshot_id == "snap_1"
        assert snapshot.session_id == 1

    def test_default_metadata_is_empty_dict(self):
        """Default metadata should be empty dict."""
        snapshot = SessionSnapshot(
            snapshot_id="snap_1",
            session_id=1,
            step_number=5,
            timestamp=datetime.now(),
            url="https://example.com",
            goal="Test goal",
            downloads=[],
            visited_urls=[],
            actions_taken=[],
            failures=[]
        )
        assert snapshot.metadata == {}

    def test_metadata_can_be_set(self):
        """Metadata can be customized."""
        snapshot = SessionSnapshot(
            snapshot_id="snap_1",
            session_id=1,
            step_number=5,
            timestamp=datetime.now(),
            url="https://example.com",
            goal="Test goal",
            downloads=[],
            visited_urls=[],
            actions_taken=[],
            failures=[],
            metadata={"reason": "test"}
        )
        assert snapshot.metadata == {"reason": "test"}

    def test_lists_can_have_content(self):
        """List fields can contain data."""
        snapshot = SessionSnapshot(
            snapshot_id="snap_1",
            session_id=1,
            step_number=5,
            timestamp=datetime.now(),
            url="https://example.com",
            goal="Test goal",
            downloads=["file1.pdf", "file2.pdf"],
            visited_urls=["https://a.com", "https://b.com"],
            actions_taken=[{"action": "click"}],
            failures=["error1"]
        )
        assert len(snapshot.downloads) == 2
        assert len(snapshot.visited_urls) == 2
        assert len(snapshot.actions_taken) == 1
        assert len(snapshot.failures) == 1


# =============================================================================
# SessionState Dataclass Tests
# =============================================================================

class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_minimal_creation(self):
        """SessionState can be created with required fields."""
        state = SessionState(
            session_id=1,
            goal="Download files",
            status=SessionStatus.ACTIVE,
            start_time=datetime.now(),
            last_update=datetime.now(),
            current_step=0,
            current_url="https://example.com",
            start_url="https://example.com",
            max_steps=50
        )
        assert state.session_id == 1
        assert state.goal == "Download files"
        assert state.status == SessionStatus.ACTIVE

    def test_default_lists_are_empty(self):
        """Default list fields should be empty."""
        state = SessionState(
            session_id=1,
            goal="Test",
            status=SessionStatus.ACTIVE,
            start_time=datetime.now(),
            last_update=datetime.now(),
            current_step=0,
            current_url="",
            start_url="",
            max_steps=50
        )
        assert state.downloads == []
        assert state.visited_urls == []
        assert state.actions_taken == []
        assert state.failures == []
        assert state.snapshots == []

    def test_default_dicts_are_empty(self):
        """Default dict fields should be empty."""
        state = SessionState(
            session_id=1,
            goal="Test",
            status=SessionStatus.ACTIVE,
            start_time=datetime.now(),
            last_update=datetime.now(),
            current_step=0,
            current_url="",
            start_url="",
            max_steps=50
        )
        assert state.domain_patterns == {}
        assert state.successful_selectors == {}

    def test_lists_can_be_modified(self):
        """List fields can be appended to."""
        state = SessionState(
            session_id=1,
            goal="Test",
            status=SessionStatus.ACTIVE,
            start_time=datetime.now(),
            last_update=datetime.now(),
            current_step=0,
            current_url="",
            start_url="",
            max_steps=50
        )
        state.downloads.append("file.pdf")
        state.visited_urls.append("https://example.com")
        assert len(state.downloads) == 1
        assert len(state.visited_urls) == 1


# =============================================================================
# LearningData Dataclass Tests
# =============================================================================

class TestLearningData:
    """Tests for LearningData dataclass."""

    def test_default_creation(self):
        """LearningData can be created with defaults."""
        data = LearningData()
        assert data.domain_knowledge == {}
        assert data.successful_queries == {}
        assert data.site_patterns == {}
        assert data.navigation_paths == {}

    def test_domain_knowledge_can_be_set(self):
        """domain_knowledge can be customized."""
        data = LearningData(
            domain_knowledge={"example.com": {"search": "input#search"}}
        )
        assert "example.com" in data.domain_knowledge

    def test_fields_are_independent(self):
        """Each instance has independent field values."""
        data1 = LearningData()
        data2 = LearningData()
        data1.domain_knowledge["test"] = {}
        assert "test" not in data2.domain_knowledge


# =============================================================================
# SessionManager Tests - Fixtures
# =============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    try:
        db_path.unlink()
    except Exception:
        pass


@pytest.fixture
def session_manager(temp_db_path):
    """Create a SessionManager with temporary database."""
    return SessionManager(temp_db_path)


# =============================================================================
# SessionManager Initialization Tests
# =============================================================================

class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_init_creates_database(self, temp_db_path):
        """SessionManager creates database on init."""
        manager = SessionManager(temp_db_path)
        assert temp_db_path.exists()

    def test_init_creates_tables(self, temp_db_path):
        """SessionManager creates required tables."""
        manager = SessionManager(temp_db_path)

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "sessions" in tables
        assert "snapshots" in tables
        assert "learning_data" in tables

        conn.close()

    def test_init_current_session_is_none(self, session_manager):
        """SessionManager starts with no current session."""
        assert session_manager.current_session is None

    def test_init_learning_data_is_created(self, session_manager):
        """SessionManager creates LearningData instance."""
        assert isinstance(session_manager.learning_data, LearningData)


# =============================================================================
# SessionManager Create Session Tests
# =============================================================================

class TestSessionManagerCreateSession:
    """Tests for SessionManager.create_session()."""

    def test_create_session_returns_session_state(self, session_manager):
        """create_session returns SessionState."""
        session = session_manager.create_session(
            goal="Test goal",
            start_url="https://example.com"
        )
        assert isinstance(session, SessionState)

    def test_create_session_sets_goal(self, session_manager):
        """create_session sets the goal."""
        session = session_manager.create_session(
            goal="Download PDFs",
            start_url="https://example.com"
        )
        assert session.goal == "Download PDFs"

    def test_create_session_sets_start_url(self, session_manager):
        """create_session sets the start URL."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://test.com"
        )
        assert session.start_url == "https://test.com"
        assert session.current_url == "https://test.com"

    def test_create_session_sets_max_steps(self, session_manager):
        """create_session sets max_steps."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://example.com",
            max_steps=100
        )
        assert session.max_steps == 100

    def test_create_session_default_max_steps(self, session_manager):
        """create_session uses default max_steps of 50."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        assert session.max_steps == 50

    def test_create_session_status_is_active(self, session_manager):
        """create_session sets status to ACTIVE."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        assert session.status == SessionStatus.ACTIVE

    def test_create_session_increments_id(self, session_manager):
        """create_session creates unique IDs."""
        session1 = session_manager.create_session(
            goal="Test 1",
            start_url="https://example.com"
        )
        session2 = session_manager.create_session(
            goal="Test 2",
            start_url="https://example.com"
        )
        assert session1.session_id != session2.session_id

    def test_create_session_sets_current_session(self, session_manager):
        """create_session sets current_session."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        assert session_manager.current_session == session

    def test_create_session_inserts_to_database(self, session_manager, temp_db_path):
        """create_session inserts record to database."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT goal FROM sessions WHERE session_id = ?", (session.session_id,))
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "Test"


# =============================================================================
# SessionManager Save/Load Session Tests
# =============================================================================

class TestSessionManagerSaveLoadSession:
    """Tests for SessionManager save_session() and load_session()."""

    def test_save_session_updates_database(self, session_manager, temp_db_path):
        """save_session updates database record."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session.current_step = 10
        session.current_url = "https://example.com/page"
        session_manager.save_session()

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT current_step, current_url FROM sessions WHERE session_id = ?",
            (session.session_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 10
        assert row[1] == "https://example.com/page"

    def test_save_session_serializes_state(self, session_manager, temp_db_path):
        """save_session serializes state to JSON."""
        session = session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session.downloads = ["file1.pdf", "file2.pdf"]
        session_manager.save_session()

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT state_json FROM sessions WHERE session_id = ?",
            (session.session_id,)
        )
        row = cursor.fetchone()
        conn.close()

        state_data = json.loads(row[0])
        assert "file1.pdf" in state_data["downloads"]

    def test_load_session_restores_state(self, session_manager):
        """load_session restores session from database."""
        session = session_manager.create_session(
            goal="Load Test",
            start_url="https://load.com"
        )
        session.downloads = ["loaded.pdf"]
        session.current_step = 5
        session_manager.save_session()
        session_id = session.session_id

        # Clear current session
        session_manager.current_session = None

        # Load it back
        loaded = session_manager.load_session(session_id)

        assert loaded is not None
        assert loaded.goal == "Load Test"
        assert loaded.current_step == 5
        assert "loaded.pdf" in loaded.downloads

    def test_load_nonexistent_session(self, session_manager):
        """load_session returns None for nonexistent session."""
        result = session_manager.load_session(99999)
        assert result is None

    def test_save_session_no_current(self, session_manager):
        """save_session does nothing with no current session."""
        session_manager.current_session = None
        # Should not raise
        session_manager.save_session()


# =============================================================================
# SessionManager Snapshot Tests
# =============================================================================

class TestSessionManagerSnapshots:
    """Tests for SessionManager snapshot methods."""

    def test_create_snapshot_returns_id(self, session_manager):
        """create_snapshot returns a snapshot ID."""
        session_manager.create_session(
            goal="Snapshot Test",
            start_url="https://example.com"
        )
        snapshot_id = session_manager.create_snapshot()
        assert snapshot_id.startswith("snap_")

    def test_create_snapshot_with_no_session(self, session_manager):
        """create_snapshot returns empty string with no session."""
        session_manager.current_session = None
        result = session_manager.create_snapshot()
        assert result == ""

    def test_create_snapshot_adds_to_session(self, session_manager):
        """create_snapshot adds snapshot ID to session."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        snapshot_id = session_manager.create_snapshot()
        assert snapshot_id in session_manager.current_session.snapshots

    def test_create_snapshot_with_metadata(self, session_manager):
        """create_snapshot accepts metadata."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        snapshot_id = session_manager.create_snapshot(
            metadata={"reason": "checkpoint"}
        )
        assert len(snapshot_id) > 0

    def test_restore_snapshot(self, session_manager):
        """restore_snapshot returns SessionSnapshot."""
        session_manager.create_session(
            goal="Restore Test",
            start_url="https://example.com"
        )
        session_manager.current_session.downloads = ["file.pdf"]
        snapshot_id = session_manager.create_snapshot()

        restored = session_manager.restore_snapshot(snapshot_id)

        assert restored is not None
        assert isinstance(restored, SessionSnapshot)
        assert "file.pdf" in restored.downloads

    def test_restore_nonexistent_snapshot(self, session_manager):
        """restore_snapshot returns None for nonexistent snapshot."""
        result = session_manager.restore_snapshot("nonexistent_snap")
        assert result is None


# =============================================================================
# SessionManager Update Progress Tests
# =============================================================================

class TestSessionManagerUpdateProgress:
    """Tests for SessionManager.update_progress()."""

    def test_update_progress_sets_step(self, session_manager):
        """update_progress sets current_step."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.update_progress(
            step=5,
            url="https://example.com/page5"
        )
        assert session_manager.current_session.current_step == 5

    def test_update_progress_sets_url(self, session_manager):
        """update_progress sets current_url."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.update_progress(
            step=1,
            url="https://newurl.com"
        )
        assert session_manager.current_session.current_url == "https://newurl.com"

    def test_update_progress_adds_to_visited(self, session_manager):
        """update_progress adds URL to visited_urls."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.update_progress(
            step=1,
            url="https://visited.com"
        )
        assert "https://visited.com" in session_manager.current_session.visited_urls

    def test_update_progress_no_duplicate_urls(self, session_manager):
        """update_progress doesn't add duplicate URLs."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.update_progress(step=1, url="https://same.com")
        session_manager.update_progress(step=2, url="https://same.com")

        count = session_manager.current_session.visited_urls.count("https://same.com")
        assert count == 1

    def test_update_progress_adds_action(self, session_manager):
        """update_progress adds action to actions_taken."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.update_progress(
            step=1,
            url="https://example.com",
            action={"type": "click", "selector": "#btn"}
        )
        assert {"type": "click", "selector": "#btn"} in session_manager.current_session.actions_taken

    def test_update_progress_adds_download(self, session_manager):
        """update_progress adds download to downloads."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.update_progress(
            step=1,
            url="https://example.com",
            download="downloaded_file.pdf"
        )
        assert "downloaded_file.pdf" in session_manager.current_session.downloads

    def test_update_progress_adds_failure(self, session_manager):
        """update_progress adds failure to failures."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.update_progress(
            step=1,
            url="https://example.com",
            failure="Element not found"
        )
        assert "Element not found" in session_manager.current_session.failures

    def test_update_progress_no_session(self, session_manager):
        """update_progress does nothing with no session."""
        session_manager.current_session = None
        # Should not raise
        session_manager.update_progress(step=1, url="https://example.com")


# =============================================================================
# SessionManager Complete/Pause Session Tests
# =============================================================================

class TestSessionManagerCompleteSession:
    """Tests for SessionManager.complete_session()."""

    def test_complete_session_success(self, session_manager):
        """complete_session sets COMPLETED status on success."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.complete_session(success=True)
        assert session_manager.current_session.status == SessionStatus.COMPLETED

    def test_complete_session_failure(self, session_manager):
        """complete_session sets FAILED status on failure."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.complete_session(success=False)
        assert session_manager.current_session.status == SessionStatus.FAILED

    def test_complete_session_no_session(self, session_manager):
        """complete_session does nothing with no session."""
        session_manager.current_session = None
        # Should not raise
        session_manager.complete_session(success=True)


class TestSessionManagerPauseSession:
    """Tests for SessionManager.pause_session()."""

    def test_pause_session_sets_paused_status(self, session_manager):
        """pause_session sets PAUSED status."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        session_manager.pause_session()
        assert session_manager.current_session.status == SessionStatus.PAUSED

    def test_pause_session_creates_snapshot(self, session_manager):
        """pause_session creates a snapshot."""
        session_manager.create_session(
            goal="Test",
            start_url="https://example.com"
        )
        initial_snapshots = len(session_manager.current_session.snapshots)
        session_manager.pause_session()
        assert len(session_manager.current_session.snapshots) == initial_snapshots + 1

    def test_pause_session_no_session(self, session_manager):
        """pause_session does nothing with no session."""
        session_manager.current_session = None
        # Should not raise
        session_manager.pause_session()


# =============================================================================
# SessionManager Get Resumable Sessions Tests
# =============================================================================

class TestSessionManagerGetResumableSessions:
    """Tests for SessionManager.get_resumable_sessions()."""

    def test_get_resumable_empty(self, session_manager):
        """get_resumable_sessions returns empty list when no sessions."""
        result = session_manager.get_resumable_sessions()
        assert result == []

    def test_get_resumable_includes_active(self, session_manager):
        """get_resumable_sessions includes active sessions."""
        session = session_manager.create_session(
            goal="Active Session",
            start_url="https://example.com"
        )
        session_manager.save_session()

        result = session_manager.get_resumable_sessions()

        assert len(result) == 1
        assert result[0]["status"] == "active"

    def test_get_resumable_includes_paused(self, session_manager):
        """get_resumable_sessions includes paused sessions."""
        session_manager.create_session(
            goal="Paused Session",
            start_url="https://example.com"
        )
        session_manager.pause_session()

        result = session_manager.get_resumable_sessions()

        assert len(result) == 1
        assert result[0]["status"] == "paused"

    def test_get_resumable_excludes_completed(self, session_manager):
        """get_resumable_sessions excludes completed sessions."""
        session_manager.create_session(
            goal="Completed Session",
            start_url="https://example.com"
        )
        session_manager.complete_session(success=True)

        result = session_manager.get_resumable_sessions()

        assert len(result) == 0

    def test_get_resumable_respects_limit(self, session_manager):
        """get_resumable_sessions respects limit parameter."""
        for i in range(5):
            session_manager.create_session(
                goal=f"Session {i}",
                start_url="https://example.com"
            )
            session_manager.save_session()

        result = session_manager.get_resumable_sessions(limit=3)

        assert len(result) == 3


# =============================================================================
# SessionManager Learning Data Tests
# =============================================================================

class TestSessionManagerLearningData:
    """Tests for SessionManager learning data methods."""

    def test_record_successful_pattern(self, session_manager):
        """record_successful_pattern stores pattern."""
        session_manager.record_successful_pattern(
            domain="example.com",
            pattern_type="search_selector",
            pattern="input#search"
        )

        patterns = session_manager.learning_data.site_patterns
        assert "example.com" in patterns
        assert "search_selector" in patterns["example.com"]
        assert "input#search" in patterns["example.com"]["search_selector"]

    def test_record_successful_pattern_multiple(self, session_manager):
        """record_successful_pattern stores multiple patterns."""
        session_manager.record_successful_pattern(
            domain="example.com",
            pattern_type="search",
            pattern="input#q"
        )
        session_manager.record_successful_pattern(
            domain="example.com",
            pattern_type="search",
            pattern="input#search"
        )

        patterns = session_manager.learning_data.site_patterns["example.com"]["search"]
        assert len(patterns) == 2

    def test_record_pattern_no_duplicate(self, session_manager):
        """record_successful_pattern doesn't add duplicate patterns."""
        session_manager.record_successful_pattern(
            domain="example.com",
            pattern_type="search",
            pattern="input#q"
        )
        session_manager.record_successful_pattern(
            domain="example.com",
            pattern_type="search",
            pattern="input#q"  # Same pattern
        )

        patterns = session_manager.learning_data.site_patterns["example.com"]["search"]
        assert len(patterns) == 1

    def test_get_learned_patterns(self, session_manager):
        """get_learned_patterns retrieves stored patterns."""
        session_manager.record_successful_pattern(
            domain="test.com",
            pattern_type="download_link",
            pattern="a.download-btn"
        )

        result = session_manager.get_learned_patterns("test.com", "download_link")
        assert "a.download-btn" in result

    def test_get_learned_patterns_unknown_domain(self, session_manager):
        """get_learned_patterns returns empty for unknown domain."""
        result = session_manager.get_learned_patterns("unknown.com", "search")
        assert result == []

    def test_get_learned_patterns_unknown_type(self, session_manager):
        """get_learned_patterns returns empty for unknown pattern type."""
        session_manager.record_successful_pattern(
            domain="test.com",
            pattern_type="search",
            pattern="input#q"
        )

        result = session_manager.get_learned_patterns("test.com", "download")
        assert result == []

    def test_save_learning_data(self, session_manager, temp_db_path):
        """save_learning_data persists to database."""
        session_manager.record_successful_pattern(
            domain="save.com",
            pattern_type="test",
            pattern="selector"
        )
        session_manager.save_learning_data()

        # Verify in database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT data_json FROM learning_data WHERE key = 'site_patterns'")
        row = cursor.fetchone()
        conn.close()

        data = json.loads(row[0])
        assert "save.com" in data

    def test_load_learning_data(self, temp_db_path):
        """Learning data is loaded on init."""
        # Pre-populate database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_data (
                key TEXT PRIMARY KEY,
                data_json TEXT,
                updated TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO learning_data (key, data_json, updated)
            VALUES ('site_patterns', ?, ?)
        """, (json.dumps({"preload.com": {"test": ["value"]}}), datetime.now().isoformat()))
        conn.commit()
        conn.close()

        # Create new manager - should load the data
        manager = SessionManager(temp_db_path)

        assert "preload.com" in manager.learning_data.site_patterns


# =============================================================================
# Global get_session_manager Tests
# =============================================================================

class TestGetSessionManager:
    """Tests for get_session_manager function."""

    def test_get_session_manager_creates_instance(self, temp_db_path):
        """get_session_manager creates a SessionManager instance."""
        import blackreach.session_manager as sm
        sm._session_manager = None  # Reset singleton

        manager = get_session_manager(temp_db_path)
        assert isinstance(manager, SessionManager)

    def test_get_session_manager_returns_same_instance(self, temp_db_path):
        """get_session_manager returns same instance on subsequent calls."""
        import blackreach.session_manager as sm
        sm._session_manager = None  # Reset singleton

        manager1 = get_session_manager(temp_db_path)
        manager2 = get_session_manager()

        assert manager1 is manager2

    def test_get_session_manager_default_path(self):
        """get_session_manager uses default path if not provided."""
        import blackreach.session_manager as sm
        sm._session_manager = None  # Reset singleton

        manager = get_session_manager()
        # Should not raise
        assert manager is not None

        # Cleanup
        sm._session_manager = None
