"""
Unit tests for blackreach/parallel_ops.py

Tests parallel operation capabilities.
"""

import pytest
from datetime import datetime
from blackreach.parallel_ops import (
    ParallelTaskType,
    ParallelTaskStatus,
    ParallelTask,
    ParallelResult,
)


class TestParallelTaskType:
    """Tests for ParallelTaskType enum."""

    def test_task_types_exist(self):
        """All expected task types should exist."""
        assert ParallelTaskType.FETCH_PAGE.value == "fetch_page"
        assert ParallelTaskType.DOWNLOAD_FILE.value == "download_file"
        assert ParallelTaskType.SEARCH.value == "search"
        assert ParallelTaskType.EXTRACT_LINKS.value == "extract_links"


class TestParallelTaskStatus:
    """Tests for ParallelTaskStatus enum."""

    def test_task_statuses_exist(self):
        """All expected statuses should exist."""
        assert ParallelTaskStatus.PENDING.value == "pending"
        assert ParallelTaskStatus.RUNNING.value == "running"
        assert ParallelTaskStatus.COMPLETED.value == "completed"
        assert ParallelTaskStatus.FAILED.value == "failed"
        assert ParallelTaskStatus.CANCELLED.value == "cancelled"


class TestParallelTask:
    """Tests for ParallelTask dataclass."""

    def test_default_values(self):
        """ParallelTask has correct defaults."""
        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )
        assert task.params == {}
        assert task.status == ParallelTaskStatus.PENDING
        assert task.result is None
        assert task.error is None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.tab_id is None

    def test_custom_values(self):
        """ParallelTask accepts custom values."""
        now = datetime.now()
        task = ParallelTask(
            task_id="test_2",
            task_type=ParallelTaskType.DOWNLOAD_FILE,
            url="https://example.com/file.pdf",
            params={"filename": "test.pdf"},
            status=ParallelTaskStatus.COMPLETED,
            result={"path": "/tmp/test.pdf"},
            created_at=now,
            tab_id="tab_1"
        )
        assert task.task_id == "test_2"
        assert task.task_type == ParallelTaskType.DOWNLOAD_FILE
        assert task.params["filename"] == "test.pdf"
        assert task.status == ParallelTaskStatus.COMPLETED
        assert task.result["path"] == "/tmp/test.pdf"

    def test_task_id_required(self):
        """Task ID is required."""
        task = ParallelTask(
            task_id="required_id",
            task_type=ParallelTaskType.SEARCH,
            url="https://google.com"
        )
        assert task.task_id == "required_id"


class TestParallelResult:
    """Tests for ParallelResult dataclass."""

    def test_default_values(self):
        """ParallelResult has correct defaults."""
        result = ParallelResult(
            total_tasks=10,
            completed=8,
            failed=2,
            cancelled=0
        )
        assert result.results == []
        assert result.elapsed_seconds == 0.0

    def test_success_rate_calculation(self):
        """success_rate should calculate correctly."""
        result = ParallelResult(
            total_tasks=10,
            completed=8,
            failed=2,
            cancelled=0
        )
        assert result.success_rate == 0.8

    def test_success_rate_zero_tasks(self):
        """success_rate should be 0 when no tasks."""
        result = ParallelResult(
            total_tasks=0,
            completed=0,
            failed=0,
            cancelled=0
        )
        assert result.success_rate == 0.0

    def test_success_rate_all_successful(self):
        """success_rate should be 1.0 when all tasks succeed."""
        result = ParallelResult(
            total_tasks=5,
            completed=5,
            failed=0,
            cancelled=0
        )
        assert result.success_rate == 1.0

    def test_results_list(self):
        """Results list should store tasks."""
        task1 = ParallelTask(
            task_id="t1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com/1",
            status=ParallelTaskStatus.COMPLETED
        )
        task2 = ParallelTask(
            task_id="t2",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com/2",
            status=ParallelTaskStatus.FAILED
        )
        result = ParallelResult(
            total_tasks=2,
            completed=1,
            failed=1,
            cancelled=0,
            results=[task1, task2],
            elapsed_seconds=5.5
        )
        assert len(result.results) == 2
        assert result.elapsed_seconds == 5.5


class TestParallelTaskStatusTransitions:
    """Tests for task status transitions."""

    def test_pending_to_running(self):
        """Task can transition from pending to running."""
        task = ParallelTask(
            task_id="test",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )
        assert task.status == ParallelTaskStatus.PENDING
        task.status = ParallelTaskStatus.RUNNING
        task.started_at = datetime.now()
        assert task.status == ParallelTaskStatus.RUNNING
        assert task.started_at is not None

    def test_running_to_completed(self):
        """Task can transition from running to completed."""
        task = ParallelTask(
            task_id="test",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com",
            status=ParallelTaskStatus.RUNNING
        )
        task.status = ParallelTaskStatus.COMPLETED
        task.result = {"html": "<html></html>"}
        task.completed_at = datetime.now()
        assert task.status == ParallelTaskStatus.COMPLETED
        assert task.result is not None
        assert task.completed_at is not None

    def test_running_to_failed(self):
        """Task can transition from running to failed."""
        task = ParallelTask(
            task_id="test",
            task_type=ParallelTaskType.DOWNLOAD_FILE,
            url="https://example.com/file.pdf",
            status=ParallelTaskStatus.RUNNING
        )
        task.status = ParallelTaskStatus.FAILED
        task.error = "Connection timeout"
        task.completed_at = datetime.now()
        assert task.status == ParallelTaskStatus.FAILED
        assert task.error == "Connection timeout"


class TestParallelResultAggregation:
    """Tests for result aggregation scenarios."""

    def test_all_tasks_completed(self):
        """Result correctly reflects all tasks completed."""
        tasks = [
            ParallelTask(
                task_id=f"t{i}",
                task_type=ParallelTaskType.FETCH_PAGE,
                url=f"https://example.com/{i}",
                status=ParallelTaskStatus.COMPLETED
            )
            for i in range(5)
        ]
        result = ParallelResult(
            total_tasks=5,
            completed=5,
            failed=0,
            cancelled=0,
            results=tasks
        )
        assert result.total_tasks == 5
        assert result.completed == 5
        assert result.success_rate == 1.0

    def test_mixed_results(self):
        """Result correctly handles mixed outcomes."""
        result = ParallelResult(
            total_tasks=10,
            completed=6,
            failed=3,
            cancelled=1
        )
        assert result.completed + result.failed + result.cancelled == 10
        assert result.success_rate == 0.6

    def test_elapsed_time_tracking(self):
        """Elapsed time is tracked correctly."""
        result = ParallelResult(
            total_tasks=3,
            completed=3,
            failed=0,
            cancelled=0,
            elapsed_seconds=12.345
        )
        assert result.elapsed_seconds == 12.345


class TestParallelImports:
    """Tests that parallel module imports correctly."""

    def test_import_parallel_fetcher(self):
        """ParallelFetcher should be importable."""
        from blackreach.parallel_ops import ParallelFetcher
        assert ParallelFetcher is not None

    def test_import_parallel_downloader(self):
        """ParallelDownloader should be importable."""
        from blackreach.parallel_ops import ParallelDownloader
        assert ParallelDownloader is not None

    def test_import_parallel_searcher(self):
        """ParallelSearcher should be importable."""
        from blackreach.parallel_ops import ParallelSearcher
        assert ParallelSearcher is not None

    def test_import_parallel_operation_manager(self):
        """ParallelOperationManager should be importable."""
        from blackreach.parallel_ops import ParallelOperationManager
        assert ParallelOperationManager is not None

    def test_import_get_parallel_manager(self):
        """get_parallel_manager should be importable."""
        from blackreach.parallel_ops import get_parallel_manager
        assert get_parallel_manager is not None
        # Without browser context, should return None
        assert get_parallel_manager() is None

    def test_import_reset_parallel_manager(self):
        """reset_parallel_manager should be importable."""
        from blackreach.parallel_ops import reset_parallel_manager
        assert reset_parallel_manager is not None
        # Should not raise
        reset_parallel_manager()
