"""
Blackreach Logging - Structured logging to files for debugging.

Logs are written to ~/.blackreach/logs/ in JSON Lines format.
Each session gets its own log file with timestamp.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict


# Log directory
LOG_DIR = Path.home() / ".blackreach" / "logs"


@dataclass
class LogEntry:
    """A single log entry."""
    timestamp: str
    level: str
    event: str
    session_id: Optional[int] = None
    step: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class SessionLogger:
    """Logger for a single agent session."""

    def __init__(self, session_id: int, goal: str):
        self.session_id = session_id
        self.goal = goal
        self.start_time = datetime.now()

        # Create log directory
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.log_file = LOG_DIR / f"session_{session_id}_{timestamp}.jsonl"

        # Write session start
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO",
            event="session_start",
            session_id=session_id,
            data={"goal": goal}
        ))

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _write(self, entry: LogEntry):
        """Write a log entry to the file."""
        try:
            with open(self.log_file, "a") as f:
                f.write(entry.to_json() + "\n")
        except Exception:
            pass  # Don't let logging failures crash the agent

    def step_start(self, step: int):
        """Log the start of a step."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO",
            event="step_start",
            session_id=self.session_id,
            step=step
        ))

    def observe(self, step: int, observation: str, url: str):
        """Log an observation."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO",
            event="observe",
            session_id=self.session_id,
            step=step,
            data={"observation": observation[:500], "url": url}
        ))

    def think(self, step: int, thought: str, stuck: bool = False):
        """Log a thought."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO",
            event="think",
            session_id=self.session_id,
            step=step,
            data={"thought": thought, "stuck": stuck}
        ))

    def act(self, step: int, action: str, args: Dict, success: bool = True):
        """Log an action."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO" if success else "WARNING",
            event="act",
            session_id=self.session_id,
            step=step,
            data={"action": action, "args": args, "success": success}
        ))

    def error(self, step: int, error: str, action: str = None):
        """Log an error."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="ERROR",
            event="error",
            session_id=self.session_id,
            step=step,
            data={"error": error, "action": action}
        ))

    def download(self, step: int, filename: str, url: str, size: int):
        """Log a download."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO",
            event="download",
            session_id=self.session_id,
            step=step,
            data={"filename": filename, "url": url, "size": size}
        ))

    def session_end(self, success: bool, steps: int, downloads: int, failures: int):
        """Log session end."""
        duration = (datetime.now() - self.start_time).total_seconds()
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO",
            event="session_end",
            session_id=self.session_id,
            data={
                "success": success,
                "steps": steps,
                "downloads": downloads,
                "failures": failures,
                "duration_seconds": round(duration, 2)
            }
        ))


def get_recent_logs(n: int = 5) -> list:
    """Get the most recent log files."""
    if not LOG_DIR.exists():
        return []

    log_files = sorted(LOG_DIR.glob("session_*.jsonl"), reverse=True)
    return log_files[:n]


def read_log(log_file: Path) -> list:
    """Read all entries from a log file."""
    entries = []
    try:
        with open(log_file) as f:
            for line in f:
                entries.append(json.loads(line))
    except Exception:
        pass
    return entries


def cleanup_old_logs(keep_days: int = 7):
    """Delete logs older than N days."""
    if not LOG_DIR.exists():
        return

    cutoff = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
    for log_file in LOG_DIR.glob("session_*.jsonl"):
        if log_file.stat().st_mtime < cutoff:
            log_file.unlink()
