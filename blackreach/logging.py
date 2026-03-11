"""
Blackreach Logging - Structured logging with levels and multiple outputs.

Features:
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- File output in JSON Lines format
- Console output with rich formatting
- Rotating log files with automatic cleanup
- Session-specific logging
- Configurable log levels per output

Logs are written to ~/.blackreach/logs/ in JSON Lines format.
Each session gets its own log file with timestamp.
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Callable, Union
from dataclasses import dataclass, asdict, field
from enum import IntEnum
from contextlib import contextmanager
import threading

from rich.console import Console
from rich.text import Text
from rich.panel import Panel


# Log directory
LOG_DIR = Path.home() / ".blackreach" / "logs"


class LogLevel(IntEnum):
    """Log levels matching Python's logging module."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    WARN = 30  # Alias
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def from_string(cls, level: str) -> "LogLevel":
        """Parse log level from string."""
        mapping = {
            "debug": cls.DEBUG,
            "info": cls.INFO,
            "warning": cls.WARNING,
            "warn": cls.WARNING,
            "error": cls.ERROR,
            "critical": cls.CRITICAL,
        }
        return mapping.get(level.lower(), cls.INFO)

    def to_string(self) -> str:
        """Convert log level to string."""
        return self.name


@dataclass
class LogEntry:
    """A single log entry with enhanced metadata."""
    timestamp: str
    level: str
    event: str
    session_id: Optional[int] = None
    step: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    source: Optional[str] = None  # Module/component source
    duration_ms: Optional[float] = None  # For timing operations

    def to_dict(self) -> Dict:
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @property
    def level_value(self) -> int:
        """Get numeric log level."""
        return LogLevel.from_string(self.level)


# Level-specific styling for console output
LEVEL_STYLES = {
    "DEBUG": "dim",
    "INFO": "cyan",
    "WARNING": "yellow",
    "WARN": "yellow",
    "ERROR": "red bold",
    "CRITICAL": "red bold reverse",
}

LEVEL_ICONS = {
    "DEBUG": "[dim]...[/dim]",
    "INFO": "[cyan]i[/cyan]",
    "WARNING": "[yellow]![/yellow]",
    "WARN": "[yellow]![/yellow]",
    "ERROR": "[red]X[/red]",
    "CRITICAL": "[red reverse]!!![/red reverse]",
}


class ConsoleLogHandler:
    """Handler for console log output with rich formatting."""

    def __init__(
        self,
        console: Console = None,
        level: LogLevel = LogLevel.INFO,
        show_timestamp: bool = False,
        show_source: bool = False,
    ):
        self.console = console or Console()
        self.level = level
        self.show_timestamp = show_timestamp
        self.show_source = show_source

    def emit(self, entry: LogEntry) -> None:
        """Emit a log entry to console."""
        if entry.level_value < self.level:
            return

        # Build message parts
        parts = []

        if self.show_timestamp:
            parts.append(f"[dim]{entry.timestamp[11:19]}[/dim]")

        # Level icon
        icon = LEVEL_ICONS.get(entry.level.upper(), "[dim]?[/dim]")
        parts.append(icon)

        if self.show_source and entry.source:
            parts.append(f"[dim]{entry.source}[/dim]")

        # Event and data
        style = LEVEL_STYLES.get(entry.level.upper(), "")
        parts.append(f"[{style}]{entry.event}[/{style}]")

        # Add relevant data
        if entry.data:
            data_str = self._format_data(entry)
            if data_str:
                parts.append(f"[dim]{data_str}[/dim]")

        self.console.print(" ".join(parts))

    def _format_data(self, entry: LogEntry) -> str:
        """Format entry data for display."""
        if not entry.data:
            return ""

        data = entry.data
        event = entry.event

        # Event-specific formatting
        if event == "act":
            action = data.get("action", "")
            args = data.get("args", {})
            return f"{action}({self._format_args(args)})"

        elif event == "download":
            filename = data.get("filename", "")
            size = data.get("size", 0)
            return f"{filename} ({self._format_size(size)})"

        elif event == "error":
            error = data.get("error", "")[:60]
            return error

        elif event == "observe":
            url = data.get("url", "")[:50]
            return url

        elif event == "think":
            thought = data.get("thought", "")[:50]
            return thought

        # Generic formatting for other events
        items = []
        for k, v in list(data.items())[:3]:
            if isinstance(v, str) and len(v) > 30:
                v = v[:27] + "..."
            items.append(f"{k}={v}")
        return ", ".join(items)

    def _format_args(self, args: Dict) -> str:
        """Format action arguments."""
        if not args:
            return ""
        items = []
        for k, v in list(args.items())[:2]:
            if isinstance(v, str) and len(v) > 20:
                v = v[:17] + "..."
            items.append(f"{k}={v!r}")
        return ", ".join(items)

    def _format_size(self, size: int) -> str:
        """Format file size."""
        if size >= 1024 * 1024:
            return f"{size / (1024*1024):.1f} MB"
        elif size >= 1024:
            return f"{size / 1024:.0f} KB"
        return f"{size} B"


class FileLogHandler:
    """Handler for file log output in JSON Lines format."""

    def __init__(
        self,
        log_file: Path,
        level: LogLevel = LogLevel.DEBUG,
        max_size_mb: int = 10,
    ):
        self.log_file = log_file
        self.level = level
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()

        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, entry: LogEntry) -> None:
        """Write a log entry to file."""
        if entry.level_value < self.level:
            return

        try:
            with self._lock:
                # Check file size and rotate if needed
                if self.log_file.exists():
                    if self.log_file.stat().st_size > self.max_size_bytes:
                        self._rotate()

                with open(self.log_file, "a") as f:
                    f.write(entry.to_json() + "\n")
        except Exception:
            pass  # Don't let logging failures crash the application

    def _rotate(self) -> None:
        """Rotate log file when it exceeds max size."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated = self.log_file.with_suffix(f".{timestamp}.jsonl")
        self.log_file.rename(rotated)


class SessionLogger:
    """
    Enhanced logger for agent sessions with multiple outputs.

    Features:
    - File logging in JSON Lines format
    - Optional console logging with rich formatting
    - Configurable log levels per output
    - Timing support for operations
    - Context managers for timed operations
    """

    def __init__(
        self,
        session_id: int,
        goal: str,
        console_level: LogLevel = LogLevel.INFO,
        file_level: LogLevel = LogLevel.DEBUG,
        console: Console = None,
        enable_console: bool = False,
    ):
        self.session_id = session_id
        self.goal = goal
        self.start_time = datetime.now()

        # Create log directory
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.log_file = LOG_DIR / f"session_{session_id}_{timestamp}.jsonl"

        # Set up handlers
        self._file_handler = FileLogHandler(self.log_file, level=file_level)
        self._console_handler = None
        if enable_console:
            self._console_handler = ConsoleLogHandler(
                console=console,
                level=console_level,
                show_timestamp=True,
            )

        # Timing context
        self._timing_stack: List[tuple] = []

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
        """Write a log entry to all handlers."""
        # Always set session_id
        if entry.session_id is None:
            entry.session_id = self.session_id

        # File handler (always active)
        self._file_handler.emit(entry)

        # Console handler (optional)
        if self._console_handler:
            self._console_handler.emit(entry)

    # -------------------------------------------------------------------------
    # Log Level Methods
    # -------------------------------------------------------------------------

    def debug(self, event: str, step: int = None, **data) -> None:
        """Log a debug message."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="DEBUG",
            event=event,
            session_id=self.session_id,
            step=step,
            data=data if data else None,
        ))

    def info(self, event: str, step: int = None, **data) -> None:
        """Log an info message."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="INFO",
            event=event,
            session_id=self.session_id,
            step=step,
            data=data if data else None,
        ))

    def warning(self, event: str, step: int = None, **data) -> None:
        """Log a warning message."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="WARNING",
            event=event,
            session_id=self.session_id,
            step=step,
            data=data if data else None,
        ))

    warn = warning  # Alias

    def error(self, event: str, step: int = None, **data) -> None:
        """Log an error message."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="ERROR",
            event=event,
            session_id=self.session_id,
            step=step,
            data=data if data else None,
        ))

    def critical(self, event: str, step: int = None, **data) -> None:
        """Log a critical message."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="CRITICAL",
            event=event,
            session_id=self.session_id,
            step=step,
            data=data if data else None,
        ))

    # -------------------------------------------------------------------------
    # Agent-Specific Methods (backward compatible)
    # -------------------------------------------------------------------------

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
            level="DEBUG",
            event="observe",
            session_id=self.session_id,
            step=step,
            data={"observation": observation[:500], "url": url}
        ))

    def think(self, step: int, thought: str, stuck: bool = False):
        """Log a thought."""
        self._write(LogEntry(
            timestamp=self._now(),
            level="DEBUG",
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

    def log_error(self, step: int, error: str, action: str = None):
        """Log an error (backward compatible method name)."""
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

    # -------------------------------------------------------------------------
    # Timing Context Managers
    # -------------------------------------------------------------------------

    @contextmanager
    def timed_operation(self, operation: str, step: int = None):
        """
        Context manager to time an operation.

        Usage:
            with logger.timed_operation("fetch_page", step=1):
                # ... operation code ...
        """
        start = time.time()
        self.debug(f"{operation}_start", step=step)

        try:
            yield
            duration_ms = (time.time() - start) * 1000
            self._write(LogEntry(
                timestamp=self._now(),
                level="DEBUG",
                event=f"{operation}_end",
                session_id=self.session_id,
                step=step,
                duration_ms=round(duration_ms, 2),
            ))
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self._write(LogEntry(
                timestamp=self._now(),
                level="ERROR",
                event=f"{operation}_error",
                session_id=self.session_id,
                step=step,
                duration_ms=round(duration_ms, 2),
                data={"error": str(e)},
            ))
            raise

    def set_console_level(self, level: Union[LogLevel, str]) -> None:
        """Change console log level at runtime."""
        if self._console_handler:
            if isinstance(level, str):
                level = LogLevel.from_string(level)
            self._console_handler.level = level

    def set_file_level(self, level: Union[LogLevel, str]) -> None:
        """Change file log level at runtime."""
        if isinstance(level, str):
            level = LogLevel.from_string(level)
        self._file_handler.level = level

    def enable_console(self, console: Console = None, level: LogLevel = LogLevel.INFO) -> None:
        """Enable console logging."""
        self._console_handler = ConsoleLogHandler(
            console=console,
            level=level,
            show_timestamp=True,
        )

    def disable_console(self) -> None:
        """Disable console logging."""
        self._console_handler = None


# Import time module for timed operations
import time


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


def filter_logs_by_level(entries: List[Dict], min_level: LogLevel = LogLevel.INFO) -> List[Dict]:
    """Filter log entries by minimum level."""
    return [
        e for e in entries
        if LogLevel.from_string(e.get("level", "INFO")) >= min_level
    ]


def get_log_summary(log_file: Path) -> Dict[str, Any]:
    """Get summary statistics from a log file."""
    entries = read_log(log_file)
    if not entries:
        return {}

    # Count by level
    level_counts = {}
    for entry in entries:
        level = entry.get("level", "INFO")
        level_counts[level] = level_counts.get(level, 0) + 1

    # Find session info
    start_entry = next((e for e in entries if e.get("event") == "session_start"), None)
    end_entry = next((e for e in reversed(entries) if e.get("event") == "session_end"), None)

    goal = start_entry.get("data", {}).get("goal", "") if start_entry else ""
    success = end_entry.get("data", {}).get("success", False) if end_entry else None
    duration = end_entry.get("data", {}).get("duration_seconds", 0) if end_entry else 0

    return {
        "total_entries": len(entries),
        "level_counts": level_counts,
        "goal": goal,
        "success": success,
        "duration_seconds": duration,
        "has_errors": level_counts.get("ERROR", 0) > 0,
    }


def search_logs(
    query: str,
    log_files: List[Path] = None,
    min_level: LogLevel = LogLevel.DEBUG,
    limit: int = 100,
) -> List[Dict]:
    """
    Search log entries for a query string.

    Args:
        query: String to search for in event names and data
        log_files: Log files to search (defaults to all recent logs)
        min_level: Minimum log level to include
        limit: Maximum number of results

    Returns:
        List of matching log entries with file info
    """
    if log_files is None:
        log_files = get_recent_logs(20)

    results = []
    query_lower = query.lower()

    for log_file in log_files:
        entries = read_log(log_file)
        for entry in entries:
            if len(results) >= limit:
                break

            # Check level
            if LogLevel.from_string(entry.get("level", "INFO")) < min_level:
                continue

            # Search in event and data
            if query_lower in entry.get("event", "").lower():
                entry["_file"] = str(log_file)
                results.append(entry)
                continue

            data = entry.get("data", {})
            if data:
                data_str = json.dumps(data).lower()
                if query_lower in data_str:
                    entry["_file"] = str(log_file)
                    results.append(entry)

    return results


def get_error_logs(
    log_files: List[Path] = None,
    limit: int = 50,
) -> List[Dict]:
    """Get all ERROR and CRITICAL level entries from recent logs."""
    return search_logs("", log_files, min_level=LogLevel.ERROR, limit=limit)


class GlobalLogger:
    """
    Application-wide logger for non-session logging.

    Use this for CLI operations, startup messages, etc.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        LOG_DIR.mkdir(parents=True, exist_ok=True)

        self.log_file = LOG_DIR / "blackreach.log"
        self._file_handler = FileLogHandler(self.log_file, level=LogLevel.DEBUG)
        self._console = Console()
        self._console_level = LogLevel.INFO
        self._initialized = True

    def _log(self, level: str, message: str, **data) -> None:
        """Write a log entry."""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            event=message,
            source="blackreach",
            data=data if data else None,
        )
        self._file_handler.emit(entry)

        # Console output for non-debug
        if LogLevel.from_string(level) >= self._console_level:
            style = LEVEL_STYLES.get(level, "")
            icon = LEVEL_ICONS.get(level, "")
            self._console.print(f"{icon} [{style}]{message}[/{style}]")

    def debug(self, message: str, **data) -> None:
        self._log("DEBUG", message, **data)

    def info(self, message: str, **data) -> None:
        self._log("INFO", message, **data)

    def warning(self, message: str, **data) -> None:
        self._log("WARNING", message, **data)

    def error(self, message: str, **data) -> None:
        self._log("ERROR", message, **data)

    def critical(self, message: str, **data) -> None:
        self._log("CRITICAL", message, **data)

    def set_level(self, level: Union[LogLevel, str]) -> None:
        """Set console log level."""
        if isinstance(level, str):
            level = LogLevel.from_string(level)
        self._console_level = level


def get_logger() -> GlobalLogger:
    """Get the global logger instance."""
    return GlobalLogger()
