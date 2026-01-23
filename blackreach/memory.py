"""
Blackreach Memory System

Two types of memory:
1. SessionMemory - Lives only during one run (in RAM)
2. PersistentMemory - Survives across runs (SQLite database)

This allows the agent to:
- Remember what it downloaded (don't re-download)
- Remember sites that worked well
- Learn from past failures
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict


# =============================================================================
# SESSION MEMORY (RAM only - dies when program ends)
# =============================================================================

@dataclass
class SessionMemory:
    """
    Short-term memory for the current run.

    This is fast (in RAM) but temporary.
    Used for: recent actions, current session state

    Can be serialized to JSON for session resume.
    """
    downloaded_files: List[str] = field(default_factory=list)
    downloaded_urls: List[str] = field(default_factory=list)
    visited_urls: List[str] = field(default_factory=list)
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)

    def add_download(self, filename: str, url: str = ""):
        """Record a downloaded file and its URL."""
        self.downloaded_files.append(filename)
        if url and url not in self.downloaded_urls:
            self.downloaded_urls.append(url)

    def add_visit(self, url: str, max_urls: int = 500):
        """Record a visited URL (no duplicates, with limit to prevent memory issues)."""
        if url not in self.visited_urls:
            self.visited_urls.append(url)
            # Prevent unbounded growth - keep only recent URLs
            if len(self.visited_urls) > max_urls:
                self.visited_urls = self.visited_urls[-max_urls:]

    def add_action(self, action: Dict[str, Any], max_actions: int = 200):
        """Record an action taken (with limit to prevent memory issues)."""
        self.actions_taken.append(action)
        # Prevent unbounded growth - keep only recent actions
        if len(self.actions_taken) > max_actions:
            self.actions_taken = self.actions_taken[-max_actions:]

    def add_failure(self, error: str):
        """Record a failure."""
        self.failures.append(error)

    def get_history(self, n: int = 5) -> str:
        """Get last n actions as a string for the LLM."""
        recent = self.actions_taken[-n:] if self.actions_taken else []
        return "\n".join([f"- {a.get('action', 'unknown')}: {a}" for a in recent])

    @property
    def last_failure(self) -> str:
        """Get the most recent failure message."""
        return self.failures[-1] if self.failures else "None"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "downloaded_files": self.downloaded_files,
            "downloaded_urls": self.downloaded_urls,
            "visited_urls": self.visited_urls,
            "actions_taken": self.actions_taken,
            "failures": self.failures,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMemory":
        """Restore from dictionary."""
        return cls(
            downloaded_files=data.get("downloaded_files", []),
            downloaded_urls=data.get("downloaded_urls", []),
            visited_urls=data.get("visited_urls", []),
            actions_taken=data.get("actions_taken", []),
            failures=data.get("failures", []),
        )


# =============================================================================
# PERSISTENT MEMORY (SQLite - survives across runs)
# =============================================================================

class PersistentMemory:
    """
    Long-term memory stored in SQLite.

    This survives program restarts. Used for:
    - Tracking all downloads ever (deduplication)
    - Remembering which sites work well
    - Learning from failures
    """

    def __init__(self, db_path: Path = None):
        """
        Initialize the database.

        Args:
            db_path: Where to store the database file.
                     Defaults to ./memory.db
        """
        self.db_path = db_path or Path("./memory.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """Create database tables if they don't exist."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row  # Access columns by name

        cursor = self._conn.cursor()

        # Table: Downloads
        # Tracks every file we've ever downloaded
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                url TEXT,
                source_site TEXT,
                goal TEXT,
                file_hash TEXT,
                file_size INTEGER,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table: Visits
        # Tracks every URL we've visited
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                goal TEXT,
                success BOOLEAN DEFAULT 1,
                visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table: Site Patterns
        # Remembers what works on each site
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                pattern_type TEXT,
                pattern_data TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(domain, pattern_type, pattern_data)
            )
        """)

        # Table: Failures
        # Tracks errors so we can learn from them
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                action TEXT,
                error_message TEXT,
                goal TEXT,
                failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table: Sessions
        # Tracks each run of the agent
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                steps_taken INTEGER DEFAULT 0,
                downloads_count INTEGER DEFAULT 0,
                success BOOLEAN
            )
        """)

        # Table: Session State (for resume functionality)
        # Stores serialized session state for interrupted sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_state (
                session_id INTEGER PRIMARY KEY,
                goal TEXT NOT NULL,
                current_step INTEGER DEFAULT 0,
                current_url TEXT,
                status TEXT DEFAULT 'running',
                memory_json TEXT,
                start_url TEXT,
                max_steps INTEGER DEFAULT 50,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        self._conn.commit()

    # -------------------------------------------------------------------------
    # Download Tracking
    # -------------------------------------------------------------------------

    def add_download(
        self,
        filename: str,
        url: str = "",
        source_site: str = "",
        goal: str = "",
        file_hash: str = "",
        file_size: int = 0
    ):
        """Record a downloaded file."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO downloads (filename, url, source_site, goal, file_hash, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (filename, url, source_site, goal, file_hash, file_size))
        self._conn.commit()

    def has_downloaded(self, url: str = "", file_hash: str = "") -> bool:
        """
        Check if we've already downloaded something.

        Can check by URL or by file hash (content fingerprint).
        """
        cursor = self._conn.cursor()

        if file_hash:
            cursor.execute("SELECT 1 FROM downloads WHERE file_hash = ?", (file_hash,))
        elif url:
            cursor.execute("SELECT 1 FROM downloads WHERE url = ?", (url,))
        else:
            return False

        return cursor.fetchone() is not None

    def get_downloads(self, limit: int = 100) -> List[Dict]:
        """Get recent downloads."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM downloads
            ORDER BY downloaded_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Visit Tracking
    # -------------------------------------------------------------------------

    def add_visit(self, url: str, title: str = "", goal: str = "", success: bool = True):
        """Record a visited URL."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO visits (url, title, goal, success)
            VALUES (?, ?, ?, ?)
        """, (url, title, goal, success))
        self._conn.commit()

    def has_visited(self, url: str) -> bool:
        """Check if we've visited a URL before."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT 1 FROM visits WHERE url = ?", (url,))
        return cursor.fetchone() is not None

    def get_visits_for_domain(self, domain: str, limit: int = 50) -> List[Dict]:
        """Get visits to a specific domain."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM visits
            WHERE url LIKE ?
            ORDER BY visited_at DESC
            LIMIT ?
        """, (f"%{domain}%", limit))
        return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Site Patterns (Learning what works)
    # -------------------------------------------------------------------------

    def record_pattern(
        self,
        domain: str,
        pattern_type: str,
        pattern_data: str,
        success: bool = True
    ):
        """
        Record a pattern that worked (or didn't) on a site.

        Examples:
            pattern_type="search_selector", pattern_data="input#search"
            pattern_type="download_selector", pattern_data="a.pdf-link"
        """
        cursor = self._conn.cursor()

        # Try to update existing pattern
        if success:
            cursor.execute("""
                INSERT INTO site_patterns (domain, pattern_type, pattern_data, success_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(domain, pattern_type, pattern_data)
                DO UPDATE SET success_count = success_count + 1, last_used = CURRENT_TIMESTAMP
            """, (domain, pattern_type, pattern_data))
        else:
            cursor.execute("""
                INSERT INTO site_patterns (domain, pattern_type, pattern_data, fail_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(domain, pattern_type, pattern_data)
                DO UPDATE SET fail_count = fail_count + 1, last_used = CURRENT_TIMESTAMP
            """, (domain, pattern_type, pattern_data))

        self._conn.commit()

    def get_best_patterns(self, domain: str, pattern_type: str, limit: int = 5) -> List[str]:
        """
        Get patterns that have worked well on a domain.

        Returns patterns sorted by success rate.
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT pattern_data,
                   success_count,
                   fail_count,
                   (success_count * 1.0 / (success_count + fail_count + 1)) as success_rate
            FROM site_patterns
            WHERE domain = ? AND pattern_type = ?
            ORDER BY success_rate DESC, success_count DESC
            LIMIT ?
        """, (domain, pattern_type, limit))

        return [row["pattern_data"] for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Failure Tracking
    # -------------------------------------------------------------------------

    def add_failure(self, url: str, action: str, error: str, goal: str = ""):
        """Record a failure for future learning."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO failures (url, action, error_message, goal)
            VALUES (?, ?, ?, ?)
        """, (url, action, error, goal))
        self._conn.commit()

    def get_common_failures(self, domain: str = "", limit: int = 10) -> List[Dict]:
        """Get common failure patterns."""
        cursor = self._conn.cursor()

        if domain:
            cursor.execute("""
                SELECT action, error_message, COUNT(*) as count
                FROM failures
                WHERE url LIKE ?
                GROUP BY action, error_message
                ORDER BY count DESC
                LIMIT ?
            """, (f"%{domain}%", limit))
        else:
            cursor.execute("""
                SELECT action, error_message, COUNT(*) as count
                FROM failures
                GROUP BY action, error_message
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Session Tracking
    # -------------------------------------------------------------------------

    def start_session(self, goal: str) -> int:
        """Start a new session, returns session ID."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (goal)
            VALUES (?)
        """, (goal,))
        self._conn.commit()
        return cursor.lastrowid

    def end_session(self, session_id: int, steps: int, downloads: int, success: bool):
        """End a session with stats."""
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE sessions
            SET end_time = CURRENT_TIMESTAMP,
                steps_taken = ?,
                downloads_count = ?,
                success = ?
            WHERE id = ?
        """, (steps, downloads, success, session_id))
        self._conn.commit()

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get overall memory stats."""
        cursor = self._conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM downloads")
        total_downloads = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM visits")
        total_visits = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM failures")
        total_failures = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT domain) FROM site_patterns")
        known_domains = cursor.fetchone()[0]

        return {
            "total_downloads": total_downloads,
            "total_visits": total_visits,
            "total_sessions": total_sessions,
            "total_failures": total_failures,
            "known_domains": known_domains,
            "db_path": str(self.db_path)
        }

    # -------------------------------------------------------------------------
    # Session State (Resume functionality)
    # -------------------------------------------------------------------------

    def save_session_state(
        self,
        session_id: int,
        goal: str,
        current_step: int,
        current_url: str,
        session_memory: "SessionMemory",
        start_url: str = "",
        max_steps: int = 50,
        status: str = "paused"
    ) -> None:
        """
        Save session state for later resume.

        Args:
            session_id: The session ID
            goal: The original goal
            current_step: Current step number
            current_url: Current page URL
            session_memory: SessionMemory instance to serialize
            start_url: The start URL for the session
            max_steps: Maximum steps allowed
            status: Session status (paused, interrupted, etc.)
        """
        cursor = self._conn.cursor()
        memory_json = json.dumps(session_memory.to_dict())

        cursor.execute("""
            INSERT OR REPLACE INTO session_state
            (session_id, goal, current_step, current_url, status, memory_json, start_url, max_steps, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (session_id, goal, current_step, current_url, status, memory_json, start_url, max_steps))
        self._conn.commit()

    def load_session_state(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Load session state for resume.

        Returns:
            Dict with session state or None if not found
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT session_id, goal, current_step, current_url, status,
                   memory_json, start_url, max_steps, saved_at
            FROM session_state
            WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            return None

        memory_data = json.loads(row["memory_json"]) if row["memory_json"] else {}
        return {
            "session_id": row["session_id"],
            "goal": row["goal"],
            "current_step": row["current_step"],
            "current_url": row["current_url"],
            "status": row["status"],
            "session_memory": SessionMemory.from_dict(memory_data),
            "start_url": row["start_url"],
            "max_steps": row["max_steps"],
            "saved_at": row["saved_at"],
        }

    def get_resumable_sessions(self, limit: int = 10) -> List[Dict]:
        """
        Get list of sessions that can be resumed.

        Returns sessions with status 'paused' or 'interrupted'.
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT ss.session_id, ss.goal, ss.current_step, ss.status, ss.saved_at,
                   s.downloads_count, s.start_time
            FROM session_state ss
            JOIN sessions s ON ss.session_id = s.id
            WHERE ss.status IN ('paused', 'interrupted')
            ORDER BY ss.saved_at DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def mark_session_completed(self, session_id: int) -> None:
        """Mark a session state as completed (removes from resumable list)."""
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE session_state
            SET status = 'completed'
            WHERE session_id = ?
        """, (session_id,))
        self._conn.commit()

    def delete_session_state(self, session_id: int) -> None:
        """Delete session state (after successful completion)."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM session_state WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """Ensure database connection is closed on garbage collection."""
        self.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()
        return False
