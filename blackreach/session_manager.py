"""
Session Management System (v2.8.0 - v2.9.0)

Provides comprehensive session management:
- Session persistence and recovery
- State snapshots for checkpointing
- Cross-session learning persistence
- Browser state recovery
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from pathlib import Path
import json
import sqlite3
from enum import Enum


class SessionStatus(Enum):
    """Status of a session."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class SessionSnapshot:
    """A snapshot of session state at a point in time."""
    snapshot_id: str
    session_id: int
    step_number: int
    timestamp: datetime
    url: str
    goal: str
    downloads: List[str]
    visited_urls: List[str]
    actions_taken: List[Dict]
    failures: List[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class SessionState:
    """Complete session state for persistence."""
    session_id: int
    goal: str
    status: SessionStatus
    start_time: datetime
    last_update: datetime
    current_step: int
    current_url: str
    start_url: str
    max_steps: int

    # Progress tracking
    downloads: List[str] = field(default_factory=list)
    visited_urls: List[str] = field(default_factory=list)
    actions_taken: List[Dict] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)

    # Learned data
    domain_patterns: Dict[str, List[str]] = field(default_factory=dict)
    successful_selectors: Dict[str, Set[str]] = field(default_factory=dict)

    # Snapshots for recovery
    snapshots: List[str] = field(default_factory=list)  # snapshot_ids


@dataclass
class LearningData:
    """Cross-session learning data."""
    domain_knowledge: Dict[str, Dict] = field(default_factory=dict)
    successful_queries: Dict[str, List[str]] = field(default_factory=dict)
    site_patterns: Dict[str, Dict] = field(default_factory=dict)
    navigation_paths: Dict[str, List[List[str]]] = field(default_factory=dict)


class SessionManager:
    """Manages session persistence and recovery."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
        self.current_session: Optional[SessionState] = None
        self.learning_data = LearningData()
        self._load_learning_data()

    def _init_db(self):
        """Initialize the session database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                start_time TEXT NOT NULL,
                last_update TEXT NOT NULL,
                current_step INTEGER DEFAULT 0,
                current_url TEXT,
                start_url TEXT,
                max_steps INTEGER DEFAULT 50,
                state_json TEXT
            )
        """)

        # Snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                session_id INTEGER,
                step_number INTEGER,
                timestamp TEXT,
                url TEXT,
                state_json TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # Learning data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_data (
                key TEXT PRIMARY KEY,
                data_json TEXT,
                updated TEXT
            )
        """)

        conn.commit()
        conn.close()

    def create_session(
        self,
        goal: str,
        start_url: str,
        max_steps: int = 50
    ) -> SessionState:
        """Create a new session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO sessions (goal, status, start_time, last_update, start_url, max_steps)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (goal, SessionStatus.ACTIVE.value, now, now, start_url, max_steps))

        session_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.current_session = SessionState(
            session_id=session_id,
            goal=goal,
            status=SessionStatus.ACTIVE,
            start_time=datetime.now(),
            last_update=datetime.now(),
            current_step=0,
            current_url=start_url,
            start_url=start_url,
            max_steps=max_steps
        )

        return self.current_session

    def save_session(self, session: Optional[SessionState] = None):
        """Save current session state."""
        session = session or self.current_session
        if not session:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Serialize state
        state_dict = {
            "downloads": session.downloads,
            "visited_urls": session.visited_urls,
            "actions_taken": session.actions_taken,
            "failures": session.failures,
            "domain_patterns": session.domain_patterns,
            "successful_selectors": {
                k: list(v) for k, v in session.successful_selectors.items()
            },
            "snapshots": session.snapshots
        }

        cursor.execute("""
            UPDATE sessions SET
                status = ?,
                last_update = ?,
                current_step = ?,
                current_url = ?,
                state_json = ?
            WHERE session_id = ?
        """, (
            session.status.value,
            datetime.now().isoformat(),
            session.current_step,
            session.current_url,
            json.dumps(state_dict),
            session.session_id
        ))

        conn.commit()
        conn.close()

    def load_session(self, session_id: int) -> Optional[SessionState]:
        """Load a session from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT session_id, goal, status, start_time, last_update,
                   current_step, current_url, start_url, max_steps, state_json
            FROM sessions WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        state_json = row[9]
        state_dict = json.loads(state_json) if state_json else {}

        session = SessionState(
            session_id=row[0],
            goal=row[1],
            status=SessionStatus(row[2]),
            start_time=datetime.fromisoformat(row[3]),
            last_update=datetime.fromisoformat(row[4]),
            current_step=row[5],
            current_url=row[6] or "",
            start_url=row[7] or "",
            max_steps=row[8],
            downloads=state_dict.get("downloads", []),
            visited_urls=state_dict.get("visited_urls", []),
            actions_taken=state_dict.get("actions_taken", []),
            failures=state_dict.get("failures", []),
            domain_patterns=state_dict.get("domain_patterns", {}),
            successful_selectors={
                k: set(v) for k, v in state_dict.get("successful_selectors", {}).items()
            },
            snapshots=state_dict.get("snapshots", [])
        )

        self.current_session = session
        return session

    def create_snapshot(
        self,
        session: Optional[SessionState] = None,
        metadata: Dict = None
    ) -> str:
        """Create a snapshot of current session state."""
        session = session or self.current_session
        if not session:
            return ""

        snapshot_id = f"snap_{session.session_id}_{session.current_step}_{datetime.now().strftime('%H%M%S')}"

        snapshot = SessionSnapshot(
            snapshot_id=snapshot_id,
            session_id=session.session_id,
            step_number=session.current_step,
            timestamp=datetime.now(),
            url=session.current_url,
            goal=session.goal,
            downloads=list(session.downloads),
            visited_urls=list(session.visited_urls),
            actions_taken=list(session.actions_taken),
            failures=list(session.failures),
            metadata=metadata or {}
        )

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO snapshots (snapshot_id, session_id, step_number, timestamp, url, state_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id,
            session.session_id,
            session.current_step,
            snapshot.timestamp.isoformat(),
            snapshot.url,
            json.dumps({
                "goal": snapshot.goal,
                "downloads": snapshot.downloads,
                "visited_urls": snapshot.visited_urls,
                "actions_taken": snapshot.actions_taken,
                "failures": snapshot.failures,
                "metadata": snapshot.metadata
            })
        ))

        conn.commit()
        conn.close()

        session.snapshots.append(snapshot_id)
        return snapshot_id

    def restore_snapshot(self, snapshot_id: str) -> Optional[SessionSnapshot]:
        """Restore a session from a snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT snapshot_id, session_id, step_number, timestamp, url, state_json
            FROM snapshots WHERE snapshot_id = ?
        """, (snapshot_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        state = json.loads(row[5])

        return SessionSnapshot(
            snapshot_id=row[0],
            session_id=row[1],
            step_number=row[2],
            timestamp=datetime.fromisoformat(row[3]),
            url=row[4],
            goal=state.get("goal", ""),
            downloads=state.get("downloads", []),
            visited_urls=state.get("visited_urls", []),
            actions_taken=state.get("actions_taken", []),
            failures=state.get("failures", []),
            metadata=state.get("metadata", {})
        )

    def get_resumable_sessions(self, limit: int = 10) -> List[Dict]:
        """Get list of sessions that can be resumed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT session_id, goal, status, last_update, current_step
            FROM sessions
            WHERE status IN ('active', 'paused', 'interrupted')
            ORDER BY last_update DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "session_id": row[0],
                "goal": row[1],
                "status": row[2],
                "last_update": row[3],
                "current_step": row[4]
            })

        conn.close()
        return sessions

    def update_progress(
        self,
        step: int,
        url: str,
        action: Optional[Dict] = None,
        download: Optional[str] = None,
        failure: Optional[str] = None
    ):
        """Update session progress."""
        if not self.current_session:
            return

        self.current_session.current_step = step
        self.current_session.current_url = url
        self.current_session.last_update = datetime.now()

        if url and url not in self.current_session.visited_urls:
            self.current_session.visited_urls.append(url)

        if action:
            self.current_session.actions_taken.append(action)

        if download:
            self.current_session.downloads.append(download)

        if failure:
            self.current_session.failures.append(failure)

    def complete_session(self, success: bool):
        """Mark session as completed."""
        if not self.current_session:
            return

        self.current_session.status = SessionStatus.COMPLETED if success else SessionStatus.FAILED
        self.save_session()

    def pause_session(self):
        """Pause current session."""
        if not self.current_session:
            return

        self.current_session.status = SessionStatus.PAUSED
        self.create_snapshot(metadata={"reason": "paused"})
        self.save_session()

    # Learning data persistence

    def _load_learning_data(self):
        """Load cross-session learning data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT key, data_json FROM learning_data")

        for row in cursor.fetchall():
            key, data_json = row
            data = json.loads(data_json)

            if key == "domain_knowledge":
                self.learning_data.domain_knowledge = data
            elif key == "successful_queries":
                self.learning_data.successful_queries = data
            elif key == "site_patterns":
                self.learning_data.site_patterns = data
            elif key == "navigation_paths":
                self.learning_data.navigation_paths = data

        conn.close()

    def save_learning_data(self):
        """Save cross-session learning data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        for key, data in [
            ("domain_knowledge", self.learning_data.domain_knowledge),
            ("successful_queries", self.learning_data.successful_queries),
            ("site_patterns", self.learning_data.site_patterns),
            ("navigation_paths", self.learning_data.navigation_paths),
        ]:
            cursor.execute("""
                INSERT OR REPLACE INTO learning_data (key, data_json, updated)
                VALUES (?, ?, ?)
            """, (key, json.dumps(data), now))

        conn.commit()
        conn.close()

    def record_successful_pattern(self, domain: str, pattern_type: str, pattern: str):
        """Record a successful pattern for learning."""
        if domain not in self.learning_data.site_patterns:
            self.learning_data.site_patterns[domain] = {}

        if pattern_type not in self.learning_data.site_patterns[domain]:
            self.learning_data.site_patterns[domain][pattern_type] = []

        if pattern not in self.learning_data.site_patterns[domain][pattern_type]:
            self.learning_data.site_patterns[domain][pattern_type].append(pattern)

    def get_learned_patterns(self, domain: str, pattern_type: str) -> List[str]:
        """Get previously successful patterns."""
        return self.learning_data.site_patterns.get(domain, {}).get(pattern_type, [])


# Global session manager
_session_manager: Optional[SessionManager] = None


def get_session_manager(db_path: Path = None) -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        db_path = db_path or Path("./memory.db")
        _session_manager = SessionManager(db_path)
    return _session_manager
