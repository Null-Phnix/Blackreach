"""
Unit tests for blackreach/logging.py

Tests for structured logging to files with log levels.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from blackreach.logging import (
    LogEntry,
    SessionLogger,
    get_recent_logs,
    read_log,
    cleanup_old_logs,
    LOG_DIR,
    LogLevel,
    filter_logs_by_level,
    get_log_summary,
    search_logs,
    get_error_logs,
    ConsoleLogHandler,
    FileLogHandler,
    GlobalLogger,
    get_logger,
)


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_required_fields(self):
        """LogEntry has required fields."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test"
        )
        assert entry.timestamp == "2026-01-23T10:00:00"
        assert entry.level == "INFO"
        assert entry.event == "test"

    def test_optional_fields_default_none(self):
        """Optional fields default to None."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test"
        )
        assert entry.session_id is None
        assert entry.step is None
        assert entry.data is None

    def test_optional_fields_set(self):
        """Optional fields can be set."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test",
            session_id=1,
            step=5,
            data={"key": "value"}
        )
        assert entry.session_id == 1
        assert entry.step == 5
        assert entry.data == {"key": "value"}

    def test_to_dict_removes_none_values(self):
        """to_dict removes None values."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test"
        )
        d = entry.to_dict()
        assert "session_id" not in d
        assert "step" not in d
        assert "data" not in d

    def test_to_dict_keeps_set_values(self):
        """to_dict keeps non-None values."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test",
            session_id=1
        )
        d = entry.to_dict()
        assert d["session_id"] == 1

    def test_to_json_returns_string(self):
        """to_json returns JSON string."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test"
        )
        json_str = entry.to_json()
        assert isinstance(json_str, str)

    def test_to_json_is_valid_json(self):
        """to_json returns valid JSON."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test",
            data={"key": "value"}
        )
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        assert parsed["event"] == "test"


class TestSessionLogger:
    """Tests for SessionLogger class."""

    def test_init_creates_directory(self, tmp_path, monkeypatch):
        """SessionLogger creates log directory."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")

        assert log_dir.exists()

    def test_init_creates_log_file(self, tmp_path, monkeypatch):
        """SessionLogger creates log file."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")

        assert logger.log_file.exists()

    def test_init_writes_session_start(self, tmp_path, monkeypatch):
        """SessionLogger writes session_start entry."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")

        with open(logger.log_file) as f:
            line = f.readline()
            entry = json.loads(line)
            assert entry["event"] == "session_start"
            assert entry["data"]["goal"] == "test goal"

    def test_step_start(self, tmp_path, monkeypatch):
        """step_start logs step start."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.step_start(5)

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["event"] == "step_start"
            assert entry["step"] == 5

    def test_observe(self, tmp_path, monkeypatch):
        """observe logs observation."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.observe(1, "saw a button", "http://example.com")

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["event"] == "observe"
            assert entry["data"]["url"] == "http://example.com"

    def test_think(self, tmp_path, monkeypatch):
        """think logs thought."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.think(1, "I should click the button", stuck=False)

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["event"] == "think"
            assert entry["data"]["thought"] == "I should click the button"

    def test_act(self, tmp_path, monkeypatch):
        """act logs action."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.act(1, "click", {"selector": "button"}, success=True)

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["event"] == "act"
            assert entry["data"]["action"] == "click"
            assert entry["data"]["success"] is True

    def test_log_error(self, tmp_path, monkeypatch):
        """log_error logs error (backward compatible method)."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.log_error(1, "Element not found", action="click")

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["event"] == "error"
            assert entry["level"] == "ERROR"
            assert entry["data"]["error"] == "Element not found"

    def test_download(self, tmp_path, monkeypatch):
        """download logs download."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.download(1, "file.pdf", "http://example.com/file.pdf", 1024)

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["event"] == "download"
            assert entry["data"]["filename"] == "file.pdf"

    def test_session_end(self, tmp_path, monkeypatch):
        """session_end logs session end."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.session_end(success=True, steps=10, downloads=5, failures=0)

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["event"] == "session_end"
            assert entry["data"]["success"] is True
            assert entry["data"]["steps"] == 10


class TestGetRecentLogs:
    """Tests for get_recent_logs function."""

    def test_returns_list(self, tmp_path, monkeypatch):
        """get_recent_logs returns a list."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        result = get_recent_logs()
        assert isinstance(result, list)

    def test_empty_dir_returns_empty_list(self, tmp_path, monkeypatch):
        """get_recent_logs returns empty list for empty dir."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        result = get_recent_logs()
        assert result == []

    def test_nonexistent_dir_returns_empty_list(self, tmp_path, monkeypatch):
        """get_recent_logs returns empty list if dir doesn't exist."""
        log_dir = tmp_path / "nonexistent"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        result = get_recent_logs()
        assert result == []

    def test_respects_limit(self, tmp_path, monkeypatch):
        """get_recent_logs respects limit parameter."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        # Create multiple log files
        for i in range(10):
            (log_dir / f"session_{i}_20260123.jsonl").touch()

        result = get_recent_logs(n=3)
        assert len(result) == 3


class TestReadLog:
    """Tests for read_log function."""

    def test_reads_valid_jsonl(self, tmp_path):
        """read_log reads valid JSONL file."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text('{"event": "test1"}\n{"event": "test2"}\n')

        entries = read_log(log_file)

        assert len(entries) == 2
        assert entries[0]["event"] == "test1"
        assert entries[1]["event"] == "test2"

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """read_log returns empty list for nonexistent file."""
        log_file = tmp_path / "nonexistent.jsonl"

        entries = read_log(log_file)

        assert entries == []


class TestCleanupOldLogs:
    """Tests for cleanup_old_logs function."""

    def test_nonexistent_dir_no_error(self, tmp_path, monkeypatch):
        """cleanup_old_logs doesn't error on nonexistent dir."""
        log_dir = tmp_path / "nonexistent"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        # Should not raise
        cleanup_old_logs()

    def test_keeps_recent_files(self, tmp_path, monkeypatch):
        """cleanup_old_logs keeps recent files."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        # Create a recent log file
        recent_file = log_dir / "session_1_20260123.jsonl"
        recent_file.touch()

        cleanup_old_logs(keep_days=7)

        assert recent_file.exists()

    def test_deletes_old_files(self, tmp_path, monkeypatch):
        """cleanup_old_logs deletes files older than keep_days."""
        import os
        import time

        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        # Create an old log file
        old_file = log_dir / "session_1_20240101.jsonl"
        old_file.touch()

        # Set modification time to 30 days ago
        old_time = time.time() - (30 * 24 * 60 * 60)
        os.utime(old_file, (old_time, old_time))

        cleanup_old_logs(keep_days=7)

        assert not old_file.exists()


class TestSessionLoggerWriteFailure:
    """Tests for handling write failures gracefully."""

    def test_write_failure_does_not_crash(self, tmp_path, monkeypatch):
        """Write failure does not crash the logger."""
        from unittest.mock import patch, mock_open

        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")

        # Mock open to raise an exception
        with patch("builtins.open", side_effect=PermissionError("Cannot write")):
            # These should not raise even if write fails
            logger.step_start(1)
            logger.observe(1, "test", "https://example.com")
            logger.think(1, "thinking", "act")
            logger.error(1, "error msg")
            # If we got here, the test passes - no crash

    def test_write_failure_with_io_error(self, tmp_path, monkeypatch):
        """IOError during write does not crash."""
        from unittest.mock import patch

        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")

        with patch("builtins.open", side_effect=IOError("Disk full")):
            # Should silently fail
            logger.download(1, "file.pdf", "http://example.com", 1024)
            logger.session_end(success=True, steps=1, downloads=1, failures=0)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_level_values(self):
        """Log levels have correct numeric values."""
        assert LogLevel.DEBUG == 10
        assert LogLevel.INFO == 20
        assert LogLevel.WARNING == 30
        assert LogLevel.ERROR == 40
        assert LogLevel.CRITICAL == 50

    def test_from_string(self):
        """from_string parses level names correctly."""
        assert LogLevel.from_string("debug") == LogLevel.DEBUG
        assert LogLevel.from_string("INFO") == LogLevel.INFO
        assert LogLevel.from_string("WARNING") == LogLevel.WARNING
        assert LogLevel.from_string("warn") == LogLevel.WARNING
        assert LogLevel.from_string("ERROR") == LogLevel.ERROR
        assert LogLevel.from_string("CRITICAL") == LogLevel.CRITICAL

    def test_from_string_unknown_defaults_to_info(self):
        """Unknown level defaults to INFO."""
        assert LogLevel.from_string("unknown") == LogLevel.INFO
        assert LogLevel.from_string("") == LogLevel.INFO

    def test_to_string(self):
        """to_string returns level name."""
        assert LogLevel.DEBUG.to_string() == "DEBUG"
        assert LogLevel.ERROR.to_string() == "ERROR"


class TestLogEntryLevelValue:
    """Tests for LogEntry level_value property."""

    def test_level_value_returns_numeric(self):
        """level_value returns numeric log level."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="ERROR",
            event="test"
        )
        assert entry.level_value == LogLevel.ERROR


class TestSessionLoggerLevelMethods:
    """Tests for SessionLogger level-specific methods."""

    def test_debug_method(self, tmp_path, monkeypatch):
        """debug() logs at DEBUG level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.debug("debug_event", step=1, key="value")

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["level"] == "DEBUG"
            assert entry["event"] == "debug_event"

    def test_info_method(self, tmp_path, monkeypatch):
        """info() logs at INFO level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.info("info_event", step=1)

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["level"] == "INFO"

    def test_warning_method(self, tmp_path, monkeypatch):
        """warning() logs at WARNING level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.warning("warn_event")

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["level"] == "WARNING"

    def test_error_method_with_kwargs(self, tmp_path, monkeypatch):
        """error() can take keyword args for data."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.error("error_event", error_code=500, message="Server error")

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["level"] == "ERROR"
            assert entry["data"]["error_code"] == 500

    def test_critical_method(self, tmp_path, monkeypatch):
        """critical() logs at CRITICAL level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.critical("critical_event")

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["level"] == "CRITICAL"


class TestFilterLogsByLevel:
    """Tests for filter_logs_by_level function."""

    def test_filters_below_min_level(self):
        """Filters out entries below minimum level."""
        entries = [
            {"level": "DEBUG", "event": "debug"},
            {"level": "INFO", "event": "info"},
            {"level": "WARNING", "event": "warn"},
            {"level": "ERROR", "event": "error"},
        ]

        result = filter_logs_by_level(entries, LogLevel.WARNING)

        assert len(result) == 2
        assert result[0]["event"] == "warn"
        assert result[1]["event"] == "error"

    def test_includes_equal_and_above(self):
        """Includes entries at or above minimum level."""
        entries = [
            {"level": "INFO", "event": "info"},
            {"level": "ERROR", "event": "error"},
        ]

        result = filter_logs_by_level(entries, LogLevel.INFO)

        assert len(result) == 2


class TestGetLogSummary:
    """Tests for get_log_summary function."""

    def test_returns_summary_dict(self, tmp_path):
        """Returns a summary dictionary."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            '{"event": "session_start", "level": "INFO", "data": {"goal": "test"}}\n'
            '{"event": "error", "level": "ERROR", "data": {}}\n'
            '{"event": "session_end", "level": "INFO", "data": {"success": true, "duration_seconds": 10.5}}\n'
        )

        summary = get_log_summary(log_file)

        assert summary["total_entries"] == 3
        assert summary["goal"] == "test"
        assert summary["success"] is True
        assert summary["has_errors"] is True

    def test_empty_file_returns_empty_dict(self, tmp_path):
        """Empty or missing file returns empty dict."""
        log_file = tmp_path / "nonexistent.jsonl"

        summary = get_log_summary(log_file)

        assert summary == {}


class TestSearchLogs:
    """Tests for search_logs function."""

    def test_finds_matching_events(self, tmp_path, monkeypatch):
        """Finds entries matching query in event names."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        log_file = log_dir / "session_1_20260123_100000.jsonl"
        log_file.write_text(
            '{"event": "download_start", "level": "INFO"}\n'
            '{"event": "download_complete", "level": "INFO"}\n'
            '{"event": "navigate", "level": "INFO"}\n'
        )

        results = search_logs("download", [log_file])

        assert len(results) == 2

    def test_finds_matching_data(self, tmp_path, monkeypatch):
        """Finds entries matching query in data."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        log_file = log_dir / "session_1_20260123_100000.jsonl"
        log_file.write_text(
            '{"event": "act", "level": "INFO", "data": {"action": "click", "selector": "button"}}\n'
            '{"event": "act", "level": "INFO", "data": {"action": "type", "text": "hello"}}\n'
        )

        results = search_logs("click", [log_file])

        assert len(results) == 1

    def test_respects_min_level(self, tmp_path, monkeypatch):
        """Respects minimum log level filter."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        log_file = log_dir / "session_1_20260123_100000.jsonl"
        log_file.write_text(
            '{"event": "debug_event", "level": "DEBUG"}\n'
            '{"event": "debug_info", "level": "INFO"}\n'
        )

        results = search_logs("debug", [log_file], min_level=LogLevel.INFO)

        # Only the INFO entry should match
        assert len(results) == 1
        assert results[0]["level"] == "INFO"


class TestGetErrorLogs:
    """Tests for get_error_logs function."""

    def test_returns_only_errors_and_critical(self, tmp_path, monkeypatch):
        """Returns only ERROR and CRITICAL entries."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        log_file = log_dir / "session_1_20260123_100000.jsonl"
        log_file.write_text(
            '{"event": "info", "level": "INFO"}\n'
            '{"event": "warning", "level": "WARNING"}\n'
            '{"event": "error", "level": "ERROR"}\n'
            '{"event": "critical", "level": "CRITICAL"}\n'
        )

        results = get_error_logs([log_file])

        assert len(results) == 2
        levels = [r["level"] for r in results]
        assert "ERROR" in levels
        assert "CRITICAL" in levels


# =============================================================================
# ConsoleLogHandler Tests
# =============================================================================

class TestConsoleLogHandler:
    """Tests for ConsoleLogHandler class."""

    def test_init_default_console(self):
        """ConsoleLogHandler creates default console if not provided."""
        handler = ConsoleLogHandler()
        assert handler.console is not None
        assert handler.level == LogLevel.INFO

    def test_init_custom_console(self):
        """ConsoleLogHandler accepts custom console."""
        from rich.console import Console
        custom_console = Console()
        handler = ConsoleLogHandler(console=custom_console)
        assert handler.console is custom_console

    def test_init_custom_level(self):
        """ConsoleLogHandler accepts custom level."""
        handler = ConsoleLogHandler(level=LogLevel.DEBUG)
        assert handler.level == LogLevel.DEBUG

    def test_init_show_timestamp(self):
        """ConsoleLogHandler accepts show_timestamp setting."""
        handler = ConsoleLogHandler(show_timestamp=True)
        assert handler.show_timestamp is True

    def test_init_show_source(self):
        """ConsoleLogHandler accepts show_source setting."""
        handler = ConsoleLogHandler(show_source=True)
        assert handler.show_source is True

    def test_emit_filters_below_level(self):
        """emit() does not output entries below handler level."""
        from unittest.mock import Mock
        mock_console = Mock()
        handler = ConsoleLogHandler(console=mock_console, level=LogLevel.WARNING)

        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            event="info_event"
        )
        handler.emit(entry)

        mock_console.print.assert_not_called()

    def test_emit_outputs_at_level(self):
        """emit() outputs entries at handler level."""
        from unittest.mock import Mock
        mock_console = Mock()
        handler = ConsoleLogHandler(console=mock_console, level=LogLevel.INFO)

        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            event="info_event"
        )
        handler.emit(entry)

        mock_console.print.assert_called_once()

    def test_emit_outputs_above_level(self):
        """emit() outputs entries above handler level."""
        from unittest.mock import Mock
        mock_console = Mock()
        handler = ConsoleLogHandler(console=mock_console, level=LogLevel.INFO)

        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="ERROR",
            event="error_event"
        )
        handler.emit(entry)

        mock_console.print.assert_called_once()

    def test_format_data_act_event(self):
        """_format_data formats act events correctly."""
        handler = ConsoleLogHandler()
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            event="act",
            data={"action": "click", "args": {"selector": "#btn"}}
        )
        result = handler._format_data(entry)
        assert "click" in result
        assert "selector" in result

    def test_format_data_download_event(self):
        """_format_data formats download events correctly."""
        handler = ConsoleLogHandler()
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            event="download",
            data={"filename": "test.pdf", "size": 1024}
        )
        result = handler._format_data(entry)
        assert "test.pdf" in result
        assert "KB" in result

    def test_format_data_error_event(self):
        """_format_data formats error events correctly."""
        handler = ConsoleLogHandler()
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="ERROR",
            event="error",
            data={"error": "Something went wrong"}
        )
        result = handler._format_data(entry)
        assert "Something went wrong" in result

    def test_format_size_bytes(self):
        """_format_size formats bytes correctly."""
        handler = ConsoleLogHandler()
        assert "B" in handler._format_size(100)

    def test_format_size_kilobytes(self):
        """_format_size formats kilobytes correctly."""
        handler = ConsoleLogHandler()
        assert "KB" in handler._format_size(1024)

    def test_format_size_megabytes(self):
        """_format_size formats megabytes correctly."""
        handler = ConsoleLogHandler()
        assert "MB" in handler._format_size(1024 * 1024)


# =============================================================================
# FileLogHandler Tests
# =============================================================================

class TestFileLogHandler:
    """Tests for FileLogHandler class."""

    def test_init_creates_directory(self, tmp_path):
        """FileLogHandler creates parent directory."""
        log_file = tmp_path / "logs" / "test.jsonl"
        handler = FileLogHandler(log_file)
        assert log_file.parent.exists()

    def test_init_default_level(self, tmp_path):
        """FileLogHandler defaults to DEBUG level."""
        log_file = tmp_path / "test.jsonl"
        handler = FileLogHandler(log_file)
        assert handler.level == LogLevel.DEBUG

    def test_init_custom_level(self, tmp_path):
        """FileLogHandler accepts custom level."""
        log_file = tmp_path / "test.jsonl"
        handler = FileLogHandler(log_file, level=LogLevel.INFO)
        assert handler.level == LogLevel.INFO

    def test_init_custom_max_size(self, tmp_path):
        """FileLogHandler accepts custom max_size_mb."""
        log_file = tmp_path / "test.jsonl"
        handler = FileLogHandler(log_file, max_size_mb=5)
        assert handler.max_size_bytes == 5 * 1024 * 1024

    def test_emit_writes_to_file(self, tmp_path):
        """emit() writes entry to file."""
        log_file = tmp_path / "test.jsonl"
        handler = FileLogHandler(log_file)

        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            event="test_event"
        )
        handler.emit(entry)

        content = log_file.read_text()
        assert "test_event" in content

    def test_emit_filters_below_level(self, tmp_path):
        """emit() does not write entries below level."""
        log_file = tmp_path / "test.jsonl"
        handler = FileLogHandler(log_file, level=LogLevel.WARNING)

        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="DEBUG",
            event="debug_event"
        )
        handler.emit(entry)

        content = log_file.read_text() if log_file.exists() else ""
        assert "debug_event" not in content

    def test_emit_handles_write_error(self, tmp_path):
        """emit() handles write errors gracefully."""
        log_file = tmp_path / "test.jsonl"
        handler = FileLogHandler(log_file)

        # Make the file unwritable by removing the parent directory
        import shutil
        # Write to check it works first
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            event="test"
        )
        handler.emit(entry)

        # This should not raise even if path is broken
        handler.log_file = tmp_path / "nonexistent_dir" / "test.jsonl"
        handler.emit(entry)  # Should not raise


# =============================================================================
# SessionLogger Additional Tests
# =============================================================================

class TestSessionLoggerAdvanced:
    """Advanced tests for SessionLogger."""

    def test_warn_alias(self, tmp_path, monkeypatch):
        """warn is an alias for warning."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.warn("warn_event")

        with open(logger.log_file) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["level"] == "WARNING"

    def test_set_console_level(self, tmp_path, monkeypatch):
        """set_console_level changes console handler level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal", enable_console=True)
        logger.set_console_level(LogLevel.DEBUG)

        assert logger._console_handler.level == LogLevel.DEBUG

    def test_set_console_level_string(self, tmp_path, monkeypatch):
        """set_console_level accepts string level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal", enable_console=True)
        logger.set_console_level("warning")

        assert logger._console_handler.level == LogLevel.WARNING

    def test_set_file_level(self, tmp_path, monkeypatch):
        """set_file_level changes file handler level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.set_file_level(LogLevel.WARNING)

        assert logger._file_handler.level == LogLevel.WARNING

    def test_set_file_level_string(self, tmp_path, monkeypatch):
        """set_file_level accepts string level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")
        logger.set_file_level("error")

        assert logger._file_handler.level == LogLevel.ERROR

    def test_enable_console(self, tmp_path, monkeypatch):
        """enable_console enables console logging."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal", enable_console=False)
        assert logger._console_handler is None

        logger.enable_console()
        assert logger._console_handler is not None

    def test_disable_console(self, tmp_path, monkeypatch):
        """disable_console disables console logging."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal", enable_console=True)
        assert logger._console_handler is not None

        logger.disable_console()
        assert logger._console_handler is None

    def test_timed_operation_success(self, tmp_path, monkeypatch):
        """timed_operation logs start and end with duration."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")

        with logger.timed_operation("test_op", step=1):
            import time
            time.sleep(0.01)

        with open(logger.log_file) as f:
            lines = f.readlines()

        # Should have start and end entries (plus session_start)
        events = [json.loads(line)["event"] for line in lines]
        assert "test_op_start" in events
        assert "test_op_end" in events

    def test_timed_operation_with_error(self, tmp_path, monkeypatch):
        """timed_operation logs error when exception raised."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        logger = SessionLogger(1, "test goal")

        with pytest.raises(ValueError):
            with logger.timed_operation("test_op", step=1):
                raise ValueError("Test error")

        with open(logger.log_file) as f:
            lines = f.readlines()

        events = [json.loads(line)["event"] for line in lines]
        assert "test_op_error" in events


# =============================================================================
# GlobalLogger Tests
# =============================================================================

class TestGlobalLogger:
    """Tests for GlobalLogger singleton."""

    def test_is_singleton(self, tmp_path, monkeypatch):
        """GlobalLogger returns same instance."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)

        # Reset singleton for testing
        GlobalLogger._instance = None

        logger1 = GlobalLogger()
        logger2 = GlobalLogger()

        assert logger1 is logger2

    def test_debug_method(self, tmp_path, monkeypatch):
        """GlobalLogger.debug logs at DEBUG level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.debug("test_debug")

        content = logger.log_file.read_text()
        assert "DEBUG" in content
        assert "test_debug" in content

    def test_info_method(self, tmp_path, monkeypatch):
        """GlobalLogger.info logs at INFO level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.info("test_info")

        content = logger.log_file.read_text()
        assert "INFO" in content

    def test_warning_method(self, tmp_path, monkeypatch):
        """GlobalLogger.warning logs at WARNING level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.warning("test_warning")

        content = logger.log_file.read_text()
        assert "WARNING" in content

    def test_error_method(self, tmp_path, monkeypatch):
        """GlobalLogger.error logs at ERROR level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.error("test_error")

        content = logger.log_file.read_text()
        assert "ERROR" in content

    def test_critical_method(self, tmp_path, monkeypatch):
        """GlobalLogger.critical logs at CRITICAL level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.critical("test_critical")

        content = logger.log_file.read_text()
        assert "CRITICAL" in content

    def test_set_level(self, tmp_path, monkeypatch):
        """GlobalLogger.set_level changes console level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.set_level(LogLevel.ERROR)

        assert logger._console_level == LogLevel.ERROR

    def test_set_level_string(self, tmp_path, monkeypatch):
        """GlobalLogger.set_level accepts string level."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.set_level("warning")

        assert logger._console_level == LogLevel.WARNING

    def test_log_with_data(self, tmp_path, monkeypatch):
        """GlobalLogger methods accept keyword data."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = GlobalLogger()
        logger.info("test_with_data", key="value", number=42)

        content = logger.log_file.read_text()
        assert "key" in content
        assert "value" in content


class TestGetLoggerFunction:
    """Tests for get_logger function."""

    def test_returns_global_logger(self, tmp_path, monkeypatch):
        """get_logger returns GlobalLogger instance."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger = get_logger()
        assert isinstance(logger, GlobalLogger)

    def test_returns_same_instance(self, tmp_path, monkeypatch):
        """get_logger returns same instance on multiple calls."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("blackreach.logging.LOG_DIR", log_dir)
        GlobalLogger._instance = None

        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2


# =============================================================================
# LogLevel Additional Tests
# =============================================================================

class TestLogLevelAdvanced:
    """Additional tests for LogLevel enum."""

    def test_warn_alias_equals_warning(self):
        """WARN alias has same value as WARNING."""
        assert LogLevel.WARN == LogLevel.WARNING
        assert LogLevel.WARN.value == LogLevel.WARNING.value

    def test_from_string_case_insensitive(self):
        """from_string is case insensitive."""
        assert LogLevel.from_string("DEBUG") == LogLevel.DEBUG
        assert LogLevel.from_string("debug") == LogLevel.DEBUG
        assert LogLevel.from_string("Debug") == LogLevel.DEBUG

    def test_from_string_warn_alias(self):
        """from_string handles warn alias."""
        assert LogLevel.from_string("warn") == LogLevel.WARNING

    def test_comparison_works(self):
        """LogLevel comparisons work correctly."""
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.CRITICAL

    def test_can_use_as_int(self):
        """LogLevel can be used as integer."""
        assert int(LogLevel.DEBUG) == 10
        assert int(LogLevel.INFO) == 20
        assert int(LogLevel.WARNING) == 30
        assert int(LogLevel.ERROR) == 40
        assert int(LogLevel.CRITICAL) == 50


# =============================================================================
# LogEntry Additional Tests
# =============================================================================

class TestLogEntryAdvanced:
    """Additional tests for LogEntry dataclass."""

    def test_source_field(self):
        """LogEntry has source field."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test",
            source="browser"
        )
        assert entry.source == "browser"

    def test_duration_ms_field(self):
        """LogEntry has duration_ms field."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test",
            duration_ms=123.45
        )
        assert entry.duration_ms == 123.45

    def test_to_dict_includes_source(self):
        """to_dict includes source if set."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test",
            source="agent"
        )
        d = entry.to_dict()
        assert d["source"] == "agent"

    def test_to_dict_includes_duration(self):
        """to_dict includes duration_ms if set."""
        entry = LogEntry(
            timestamp="2026-01-23T10:00:00",
            level="INFO",
            event="test",
            duration_ms=50.0
        )
        d = entry.to_dict()
        assert d["duration_ms"] == 50.0
