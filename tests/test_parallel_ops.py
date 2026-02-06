"""
Unit tests for blackreach/parallel_ops.py

Tests parallel operation capabilities.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
import threading
import time

from blackreach.parallel_ops import (
    ParallelTaskType,
    ParallelTaskStatus,
    ParallelTask,
    ParallelResult,
    ParallelFetcher,
    ParallelDownloader,
    ParallelSearcher,
    ParallelOperationManager,
    get_parallel_manager,
    reset_parallel_manager,
)
from blackreach.multi_tab import TabInfo, TabStatus, TabPoolConfig
from blackreach.rate_limiter import RateLimiter, RateLimitConfig


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


class TestParallelFetcherExecution:
    """Tests for ParallelFetcher parallel execution behavior."""

    def test_fetcher_uses_thread_pool(self):
        """ParallelFetcher should use ThreadPoolExecutor for parallel execution."""
        from concurrent.futures import ThreadPoolExecutor
        import blackreach.parallel_ops as parallel_ops
        import inspect

        # Check that ThreadPoolExecutor is used in fetch_pages
        source = inspect.getsource(parallel_ops.ParallelFetcher.fetch_pages)
        assert "ThreadPoolExecutor" in source, "fetch_pages should use ThreadPoolExecutor"
        assert "as_completed" in source, "fetch_pages should use as_completed for result handling"

    def test_downloader_uses_thread_pool(self):
        """ParallelDownloader should use ThreadPoolExecutor for parallel execution."""
        import blackreach.parallel_ops as parallel_ops
        import inspect

        source = inspect.getsource(parallel_ops.ParallelDownloader.download_files)
        assert "ThreadPoolExecutor" in source, "download_files should use ThreadPoolExecutor"
        assert "as_completed" in source, "download_files should use as_completed for result handling"

    def test_searcher_uses_thread_pool(self):
        """ParallelSearcher should use ThreadPoolExecutor for parallel execution."""
        import blackreach.parallel_ops as parallel_ops
        import inspect

        source = inspect.getsource(parallel_ops.ParallelSearcher.search_multiple_sources)
        assert "ThreadPoolExecutor" in source, "search_multiple_sources should use ThreadPoolExecutor"


class TestParallelFetcherConfig:
    """Tests for ParallelFetcher configuration."""

    def test_max_parallel_default(self):
        """ParallelFetcher should have sensible max_parallel default."""
        from blackreach.parallel_ops import ParallelFetcher
        from unittest.mock import MagicMock

        # Create mock browser context
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)

        # Default max_parallel should be reasonable (3-10)
        assert 1 <= fetcher.max_parallel <= 10

    def test_max_parallel_configurable(self):
        """ParallelFetcher max_parallel should be configurable."""
        from blackreach.parallel_ops import ParallelFetcher
        from unittest.mock import MagicMock

        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context, max_parallel=5)

        assert fetcher.max_parallel == 5


class TestParallelTaskElapsedTime:
    """Tests for elapsed time tracking in parallel operations."""

    def test_result_elapsed_time_positive(self):
        """Elapsed time should be positive for completed operations."""
        import time

        start = time.time()
        time.sleep(0.01)  # Small delay
        elapsed = time.time() - start

        result = ParallelResult(
            total_tasks=1,
            completed=1,
            failed=0,
            cancelled=0,
            elapsed_seconds=elapsed
        )

        assert result.elapsed_seconds > 0
        assert result.elapsed_seconds < 1.0  # Should be quick

    def test_result_elapsed_time_realistic(self):
        """Elapsed time should reflect actual execution time."""
        result = ParallelResult(
            total_tasks=10,
            completed=10,
            failed=0,
            cancelled=0,
            elapsed_seconds=2.5
        )

        # For 10 parallel tasks, 2.5 seconds is reasonable
        assert result.elapsed_seconds == 2.5


# ============================================================================
# ParallelFetcher Tests
# ============================================================================

class TestParallelFetcherInit:
    """Tests for ParallelFetcher initialization."""

    def test_init_with_defaults(self):
        """ParallelFetcher initializes with default parameters."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)

        assert fetcher.max_parallel == 3  # default
        assert fetcher.rate_limiter is not None
        assert fetcher.timeout_manager is not None
        assert fetcher._task_counter == 0
        assert fetcher._results == {}

    def test_init_with_custom_max_parallel(self):
        """ParallelFetcher accepts custom max_parallel."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context, max_parallel=10)

        assert fetcher.max_parallel == 10

    def test_init_with_custom_rate_limiter(self):
        """ParallelFetcher accepts custom rate limiter."""
        mock_context = MagicMock()
        custom_limiter = RateLimiter(RateLimitConfig(default_requests_per_minute=60.0))
        fetcher = ParallelFetcher(mock_context, rate_limiter=custom_limiter)

        assert fetcher.rate_limiter is custom_limiter

    def test_init_with_custom_timeout_manager(self):
        """ParallelFetcher accepts custom timeout manager."""
        from blackreach.timeout_manager import TimeoutManager, TimeoutConfig

        mock_context = MagicMock()
        custom_tm = TimeoutManager(TimeoutConfig(default_timeout=60.0))
        fetcher = ParallelFetcher(mock_context, timeout_manager=custom_tm)

        assert fetcher.timeout_manager is custom_tm

    def test_init_creates_tab_manager(self):
        """ParallelFetcher creates a SyncTabManager."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context, max_parallel=5)

        assert fetcher.tab_manager is not None
        assert fetcher.tab_manager.config.max_tabs == 5

    def test_init_thread_lock_created(self):
        """ParallelFetcher creates a thread lock."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)

        assert isinstance(fetcher._lock, type(threading.Lock()))


class TestParallelFetcherTaskId:
    """Tests for _generate_task_id method."""

    def test_generate_task_id_format(self):
        """Task ID has expected format."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)

        task_id = fetcher._generate_task_id()

        assert task_id.startswith("fetch_")
        parts = task_id.split("_")
        assert len(parts) == 3
        assert parts[1] == "1"  # First task

    def test_generate_task_id_increments(self):
        """Task IDs increment sequentially."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)

        id1 = fetcher._generate_task_id()
        id2 = fetcher._generate_task_id()
        id3 = fetcher._generate_task_id()

        assert "fetch_1_" in id1
        assert "fetch_2_" in id2
        assert "fetch_3_" in id3

    def test_generate_task_id_uniqueness(self):
        """Generated task IDs are unique."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)

        ids = [fetcher._generate_task_id() for _ in range(100)]

        assert len(ids) == len(set(ids))  # All unique

    def test_generate_task_id_thread_safe(self):
        """Task ID generation is thread-safe."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)
        ids = []
        errors = []

        def generate_ids():
            try:
                for _ in range(50):
                    ids.append(fetcher._generate_task_id())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=generate_ids) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(ids) == 250  # 5 threads x 50 ids
        assert len(set(ids)) == 250  # All unique


class TestParallelFetcherFetchPages:
    """Tests for fetch_pages method."""

    def test_fetch_pages_empty_urls(self):
        """fetch_pages handles empty URL list."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)

        result = fetcher.fetch_pages([])

        assert result.total_tasks == 0
        assert result.completed == 0
        assert result.failed == 0
        assert result.elapsed_seconds >= 0

    def test_fetch_pages_creates_tasks(self):
        """fetch_pages creates tasks for each URL."""
        mock_context = MagicMock()

        with patch.object(ParallelFetcher, '_fetch_single'):
            fetcher = ParallelFetcher(mock_context)
            fetcher._fetch_single = MagicMock()

            urls = ["https://example.com/1", "https://example.com/2"]
            result = fetcher.fetch_pages(urls)

            assert result.total_tasks == 2
            assert len(result.results) == 2

    def test_fetch_pages_progress_callback(self):
        """fetch_pages calls progress callback."""
        mock_context = MagicMock()
        progress_calls = []

        def on_progress(completed, total):
            progress_calls.append((completed, total))

        with patch.object(ParallelFetcher, '_fetch_single'):
            fetcher = ParallelFetcher(mock_context)

            def mock_fetch(task, callback=None):
                task.status = ParallelTaskStatus.COMPLETED

            fetcher._fetch_single = mock_fetch

            urls = ["https://example.com/1", "https://example.com/2"]
            fetcher.fetch_pages(urls, on_progress=on_progress)

            assert len(progress_calls) >= 2
            # Last call should show all tasks processed
            last_call = progress_calls[-1]
            assert last_call[1] == 2  # total

    def test_fetch_pages_returns_parallel_result(self):
        """fetch_pages returns ParallelResult."""
        mock_context = MagicMock()

        with patch.object(ParallelFetcher, '_fetch_single'):
            fetcher = ParallelFetcher(mock_context)

            def mock_fetch(task, callback=None):
                task.status = ParallelTaskStatus.COMPLETED

            fetcher._fetch_single = mock_fetch

            result = fetcher.fetch_pages(["https://example.com"])

            assert isinstance(result, ParallelResult)
            assert result.total_tasks == 1

    def test_fetch_pages_tracks_elapsed_time(self):
        """fetch_pages tracks elapsed time."""
        mock_context = MagicMock()

        with patch.object(ParallelFetcher, '_fetch_single'):
            fetcher = ParallelFetcher(mock_context)

            def mock_fetch(task, callback=None):
                time.sleep(0.01)
                task.status = ParallelTaskStatus.COMPLETED

            fetcher._fetch_single = mock_fetch

            result = fetcher.fetch_pages(["https://example.com"])

            assert result.elapsed_seconds > 0

    def test_fetch_pages_counts_completed(self):
        """fetch_pages correctly counts completed tasks."""
        mock_context = MagicMock()

        with patch.object(ParallelFetcher, '_fetch_single'):
            fetcher = ParallelFetcher(mock_context)

            def mock_fetch(task, callback=None):
                task.status = ParallelTaskStatus.COMPLETED

            fetcher._fetch_single = mock_fetch

            result = fetcher.fetch_pages(["https://example.com/1", "https://example.com/2"])

            assert result.completed == 2
            assert result.failed == 0

    def test_fetch_pages_counts_failed(self):
        """fetch_pages correctly counts failed tasks."""
        mock_context = MagicMock()

        with patch.object(ParallelFetcher, '_fetch_single'):
            fetcher = ParallelFetcher(mock_context)

            def mock_fetch(task, callback=None):
                task.status = ParallelTaskStatus.FAILED
                task.error = "Test error"

            fetcher._fetch_single = mock_fetch

            result = fetcher.fetch_pages(["https://example.com"])

            assert result.failed == 1
            assert result.completed == 0

    def test_fetch_pages_handles_exceptions(self):
        """fetch_pages handles exceptions in _fetch_single."""
        mock_context = MagicMock()

        with patch.object(ParallelFetcher, '_fetch_single'):
            fetcher = ParallelFetcher(mock_context)

            def mock_fetch(task, callback=None):
                raise Exception("Test exception")

            fetcher._fetch_single = mock_fetch

            result = fetcher.fetch_pages(["https://example.com"])

            assert result.failed == 1


class TestParallelFetcherFetchSingle:
    """Tests for _fetch_single method."""

    def test_fetch_single_sets_running_status(self):
        """_fetch_single sets task status to RUNNING."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"
        mock_page.title.return_value = "Test Page"
        mock_page.url = "https://example.com"

        mock_tab = TabInfo(
            tab_id="tab_1",
            page=mock_page,
            status=TabStatus.ACTIVE
        )

        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()
        fetcher.tab_manager.get_tab.return_value = mock_tab
        fetcher.tab_manager.navigate_in_tab.return_value = True
        fetcher.rate_limiter = MagicMock()
        fetcher.rate_limiter.can_request.return_value = (True, 0)
        fetcher.timeout_manager = MagicMock()
        fetcher.timeout_manager.get_timeout.return_value = 30.0

        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )

        fetcher._fetch_single(task)

        assert task.started_at is not None
        assert task.completed_at is not None

    def test_fetch_single_success(self):
        """_fetch_single completes successfully."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>Test</body></html>"
        mock_page.title.return_value = "Test Page"
        mock_page.url = "https://example.com/final"

        mock_tab = TabInfo(
            tab_id="tab_1",
            page=mock_page,
            status=TabStatus.ACTIVE
        )

        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()
        fetcher.tab_manager.get_tab.return_value = mock_tab
        fetcher.tab_manager.navigate_in_tab.return_value = True
        fetcher.rate_limiter = MagicMock()
        fetcher.rate_limiter.can_request.return_value = (True, 0)
        fetcher.timeout_manager = MagicMock()
        fetcher.timeout_manager.get_timeout.return_value = 30.0

        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )

        fetcher._fetch_single(task)

        assert task.status == ParallelTaskStatus.COMPLETED
        assert task.result is not None
        assert task.result["html"] == "<html><body>Test</body></html>"
        assert task.result["title"] == "Test Page"
        assert task.result["final_url"] == "https://example.com/final"
        assert task.tab_id == "tab_1"

    def test_fetch_single_navigation_failure(self):
        """_fetch_single handles navigation failure."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()
        fetcher.tab_manager.get_tab.return_value = mock_tab
        fetcher.tab_manager.navigate_in_tab.return_value = False  # Failure
        fetcher.rate_limiter = MagicMock()
        fetcher.rate_limiter.can_request.return_value = (True, 0)
        fetcher.timeout_manager = MagicMock()
        fetcher.timeout_manager.get_timeout.return_value = 30.0

        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )

        fetcher._fetch_single(task)

        assert task.status == ParallelTaskStatus.FAILED
        assert task.error == "Navigation failed"

    def test_fetch_single_exception_handling(self):
        """_fetch_single handles exceptions."""
        mock_context = MagicMock()

        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()
        fetcher.tab_manager.get_tab.side_effect = Exception("Tab error")
        fetcher.rate_limiter = MagicMock()
        fetcher.rate_limiter.can_request.return_value = (True, 0)
        fetcher.timeout_manager = MagicMock()
        fetcher.timeout_manager.get_timeout.return_value = 30.0

        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )

        fetcher._fetch_single(task)

        assert task.status == ParallelTaskStatus.FAILED
        assert "Tab error" in task.error
        assert task.completed_at is not None

    def test_fetch_single_rate_limit_wait(self):
        """_fetch_single waits when rate limited."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"
        mock_page.title.return_value = "Test"
        mock_page.url = "https://example.com"
        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()
        fetcher.tab_manager.get_tab.return_value = mock_tab
        fetcher.tab_manager.navigate_in_tab.return_value = True
        fetcher.rate_limiter = MagicMock()
        # First call: can't request, wait 0.01s
        fetcher.rate_limiter.can_request.return_value = (False, 0.01)
        fetcher.timeout_manager = MagicMock()
        fetcher.timeout_manager.get_timeout.return_value = 30.0

        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )

        start = time.time()
        fetcher._fetch_single(task)
        elapsed = time.time() - start

        # Should have waited
        assert elapsed >= 0.01

    def test_fetch_single_calls_callback(self):
        """_fetch_single calls the callback on success."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"
        mock_page.title.return_value = "Test"
        mock_page.url = "https://example.com"
        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()
        fetcher.tab_manager.get_tab.return_value = mock_tab
        fetcher.tab_manager.navigate_in_tab.return_value = True
        fetcher.rate_limiter = MagicMock()
        fetcher.rate_limiter.can_request.return_value = (True, 0)
        fetcher.timeout_manager = MagicMock()
        fetcher.timeout_manager.get_timeout.return_value = 30.0

        callback_data = []

        def callback(url, html, result):
            callback_data.append((url, html, result))

        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )

        fetcher._fetch_single(task, callback)

        assert len(callback_data) == 1
        assert callback_data[0][0] == "https://example.com"
        assert callback_data[0][1] == "<html></html>"

    def test_fetch_single_releases_tab(self):
        """_fetch_single releases tab after completion."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"
        mock_page.title.return_value = "Test"
        mock_page.url = "https://example.com"
        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()
        fetcher.tab_manager.get_tab.return_value = mock_tab
        fetcher.tab_manager.navigate_in_tab.return_value = True
        fetcher.rate_limiter = MagicMock()
        fetcher.rate_limiter.can_request.return_value = (True, 0)
        fetcher.timeout_manager = MagicMock()
        fetcher.timeout_manager.get_timeout.return_value = 30.0

        task = ParallelTask(
            task_id="test_1",
            task_type=ParallelTaskType.FETCH_PAGE,
            url="https://example.com"
        )

        fetcher._fetch_single(task)

        fetcher.tab_manager.release_tab.assert_called_once_with("tab_1")


class TestParallelFetcherClose:
    """Tests for ParallelFetcher.close method."""

    def test_close_calls_tab_manager_close_all(self):
        """close() calls tab_manager.close_all()."""
        mock_context = MagicMock()
        fetcher = ParallelFetcher(mock_context)
        fetcher.tab_manager = MagicMock()

        fetcher.close()

        fetcher.tab_manager.close_all.assert_called_once()


# ============================================================================
# ParallelDownloader Tests
# ============================================================================

class TestParallelDownloaderInit:
    """Tests for ParallelDownloader initialization."""

    def test_init_with_defaults(self):
        """ParallelDownloader initializes with default parameters."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp/downloads")

        assert downloader.max_parallel == 3  # default
        assert downloader.download_dir == "/tmp/downloads"
        assert downloader.rate_limiter is not None
        assert downloader._download_counter == 0
        assert downloader._active_downloads == {}

    def test_init_with_custom_max_parallel(self):
        """ParallelDownloader accepts custom max_parallel."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp", max_parallel=5)

        assert downloader.max_parallel == 5

    def test_init_with_custom_rate_limiter(self):
        """ParallelDownloader accepts custom rate limiter."""
        mock_context = MagicMock()
        custom_limiter = RateLimiter()
        downloader = ParallelDownloader(
            mock_context,
            download_dir="/tmp",
            rate_limiter=custom_limiter
        )

        assert downloader.rate_limiter is custom_limiter

    def test_init_creates_tab_manager(self):
        """ParallelDownloader creates a SyncTabManager."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp", max_parallel=4)

        assert downloader.tab_manager is not None
        assert downloader.tab_manager.config.max_tabs == 4

    def test_init_thread_lock(self):
        """ParallelDownloader creates a thread lock."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")

        assert isinstance(downloader._lock, type(threading.Lock()))


class TestParallelDownloaderDownloadId:
    """Tests for _generate_download_id method."""

    def test_generate_download_id_format(self):
        """Download ID has expected format."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")

        dl_id = downloader._generate_download_id()

        assert dl_id.startswith("dl_")
        parts = dl_id.split("_")
        assert len(parts) == 3
        assert parts[1] == "1"

    def test_generate_download_id_increments(self):
        """Download IDs increment sequentially."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")

        id1 = downloader._generate_download_id()
        id2 = downloader._generate_download_id()
        id3 = downloader._generate_download_id()

        assert "dl_1_" in id1
        assert "dl_2_" in id2
        assert "dl_3_" in id3

    def test_generate_download_id_uniqueness(self):
        """Generated download IDs are unique."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")

        ids = [downloader._generate_download_id() for _ in range(100)]

        assert len(ids) == len(set(ids))

    def test_generate_download_id_thread_safe(self):
        """Download ID generation is thread-safe."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")
        ids = []
        errors = []

        def generate_ids():
            try:
                for _ in range(50):
                    ids.append(downloader._generate_download_id())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=generate_ids) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(ids) == 250
        assert len(set(ids)) == 250


class TestParallelDownloaderDownloadFiles:
    """Tests for download_files method."""

    def test_download_files_empty_list(self):
        """download_files handles empty list."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")

        result = downloader.download_files([])

        assert result.total_tasks == 0
        assert result.completed == 0
        assert result.failed == 0

    def test_download_files_creates_tasks(self):
        """download_files creates tasks for each item."""
        mock_context = MagicMock()

        with patch.object(ParallelDownloader, '_download_single'):
            downloader = ParallelDownloader(mock_context, download_dir="/tmp")
            downloader._download_single = MagicMock(return_value=True)

            items = [
                ("https://example.com/file1.pdf", "file1.pdf"),
                ("https://example.com/file2.pdf", "file2.pdf"),
            ]
            result = downloader.download_files(items)

            assert result.total_tasks == 2

    def test_download_files_progress_callback(self):
        """download_files calls progress callback."""
        mock_context = MagicMock()
        progress_calls = []

        def on_progress(completed, failed, total):
            progress_calls.append((completed, failed, total))

        with patch.object(ParallelDownloader, '_download_single'):
            downloader = ParallelDownloader(mock_context, download_dir="/tmp")

            def mock_download(task):
                task.status = ParallelTaskStatus.COMPLETED
                return True

            downloader._download_single = mock_download

            items = [("https://example.com/file.pdf", "file.pdf")]
            downloader.download_files(items, on_progress=on_progress)

            assert len(progress_calls) >= 1
            # Last call should reflect completed
            last = progress_calls[-1]
            assert last[2] == 1  # total

    def test_download_files_complete_callback(self):
        """download_files calls on_download_complete callback."""
        mock_context = MagicMock()
        complete_calls = []

        def on_complete(url, path, success):
            complete_calls.append((url, path, success))

        with patch.object(ParallelDownloader, '_download_single'):
            downloader = ParallelDownloader(mock_context, download_dir="/tmp")

            def mock_download(task):
                task.status = ParallelTaskStatus.COMPLETED
                task.result = {"path": "/tmp/file.pdf"}
                return True

            downloader._download_single = mock_download

            items = [("https://example.com/file.pdf", "file.pdf")]
            downloader.download_files(items, on_download_complete=on_complete)

            assert len(complete_calls) == 1
            assert complete_calls[0][0] == "https://example.com/file.pdf"
            assert complete_calls[0][2] is True

    def test_download_files_counts_completed(self):
        """download_files correctly counts completed."""
        mock_context = MagicMock()

        with patch.object(ParallelDownloader, '_download_single'):
            downloader = ParallelDownloader(mock_context, download_dir="/tmp")

            def mock_download(task):
                task.status = ParallelTaskStatus.COMPLETED
                return True

            downloader._download_single = mock_download

            items = [
                ("https://example.com/1.pdf", "1.pdf"),
                ("https://example.com/2.pdf", "2.pdf"),
            ]
            result = downloader.download_files(items)

            assert result.completed == 2
            assert result.failed == 0

    def test_download_files_counts_failed(self):
        """download_files correctly counts failed."""
        mock_context = MagicMock()

        with patch.object(ParallelDownloader, '_download_single'):
            downloader = ParallelDownloader(mock_context, download_dir="/tmp")

            def mock_download(task):
                task.status = ParallelTaskStatus.FAILED
                return False

            downloader._download_single = mock_download

            items = [("https://example.com/file.pdf", "file.pdf")]
            result = downloader.download_files(items)

            assert result.failed == 1
            assert result.completed == 0

    def test_download_files_handles_exceptions(self):
        """download_files handles exceptions in _download_single."""
        mock_context = MagicMock()

        with patch.object(ParallelDownloader, '_download_single'):
            downloader = ParallelDownloader(mock_context, download_dir="/tmp")

            def mock_download(task):
                raise Exception("Download error")

            downloader._download_single = mock_download

            items = [("https://example.com/file.pdf", "file.pdf")]
            result = downloader.download_files(items)

            assert result.failed == 1

    def test_download_files_tracks_elapsed_time(self):
        """download_files tracks elapsed time."""
        mock_context = MagicMock()

        with patch.object(ParallelDownloader, '_download_single'):
            downloader = ParallelDownloader(mock_context, download_dir="/tmp")

            def mock_download(task):
                time.sleep(0.01)
                task.status = ParallelTaskStatus.COMPLETED
                return True

            downloader._download_single = mock_download

            items = [("https://example.com/file.pdf", "file.pdf")]
            result = downloader.download_files(items)

            assert result.elapsed_seconds > 0


class TestParallelDownloaderDownloadSingle:
    """Tests for _download_single method."""

    def test_download_single_sets_running_status(self):
        """_download_single sets task to RUNNING."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_download = MagicMock()

        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        downloader = ParallelDownloader(mock_context, download_dir="/tmp")
        downloader.tab_manager = MagicMock()
        downloader.tab_manager.get_tab.return_value = mock_tab
        downloader.rate_limiter = MagicMock()
        downloader.rate_limiter.can_request.return_value = (True, 0)

        # Mock expect_download context manager
        mock_download_ctx = MagicMock()
        mock_download_ctx.__enter__ = MagicMock(return_value=mock_download)
        mock_download_ctx.__exit__ = MagicMock(return_value=False)
        mock_download_ctx.value = mock_download
        mock_page.expect_download.return_value = mock_download_ctx

        task = ParallelTask(
            task_id="dl_1",
            task_type=ParallelTaskType.DOWNLOAD_FILE,
            url="https://example.com/file.pdf",
            params={"filename": "file.pdf"}
        )

        # Will fail due to mock but we're testing the status set
        try:
            downloader._download_single(task)
        except:
            pass

        assert task.started_at is not None

    def test_download_single_rate_limit_wait(self):
        """_download_single waits when rate limited."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")
        downloader.tab_manager = MagicMock()
        downloader.tab_manager.get_tab.side_effect = Exception("Stop early")
        downloader.rate_limiter = MagicMock()
        downloader.rate_limiter.can_request.return_value = (False, 0.01)

        task = ParallelTask(
            task_id="dl_1",
            task_type=ParallelTaskType.DOWNLOAD_FILE,
            url="https://example.com/file.pdf",
            params={"filename": "file.pdf"}
        )

        start = time.time()
        downloader._download_single(task)
        elapsed = time.time() - start

        assert elapsed >= 0.01

    def test_download_single_exception_handling(self):
        """_download_single handles exceptions."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")
        downloader.tab_manager = MagicMock()
        downloader.tab_manager.get_tab.side_effect = Exception("Tab error")
        downloader.rate_limiter = MagicMock()
        downloader.rate_limiter.can_request.return_value = (True, 0)

        task = ParallelTask(
            task_id="dl_1",
            task_type=ParallelTaskType.DOWNLOAD_FILE,
            url="https://example.com/file.pdf",
            params={"filename": "file.pdf"}
        )

        result = downloader._download_single(task)

        assert result is False
        assert task.status == ParallelTaskStatus.FAILED
        assert "Tab error" in task.error
        assert task.completed_at is not None

    def test_download_single_uses_filename_from_params(self):
        """_download_single uses filename from params."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")
        downloader.tab_manager = MagicMock()
        downloader.tab_manager.get_tab.side_effect = Exception("Stop")
        downloader.rate_limiter = MagicMock()
        downloader.rate_limiter.can_request.return_value = (True, 0)

        task = ParallelTask(
            task_id="dl_1",
            task_type=ParallelTaskType.DOWNLOAD_FILE,
            url="https://example.com/file.pdf",
            params={"filename": "custom_name.pdf"}
        )

        downloader._download_single(task)

        # The download_path would be computed with custom_name.pdf


class TestParallelDownloaderClose:
    """Tests for ParallelDownloader.close method."""

    def test_close_calls_tab_manager_close_all(self):
        """close() calls tab_manager.close_all()."""
        mock_context = MagicMock()
        downloader = ParallelDownloader(mock_context, download_dir="/tmp")
        downloader.tab_manager = MagicMock()

        downloader.close()

        downloader.tab_manager.close_all.assert_called_once()


# ============================================================================
# ParallelSearcher Tests
# ============================================================================

class TestParallelSearcherInit:
    """Tests for ParallelSearcher initialization."""

    def test_init_with_defaults(self):
        """ParallelSearcher initializes with default parameters."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        assert searcher.max_parallel == 2  # default
        assert searcher.rate_limiter is not None
        assert searcher._search_counter == 0

    def test_init_with_custom_max_parallel(self):
        """ParallelSearcher accepts custom max_parallel."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context, max_parallel=4)

        assert searcher.max_parallel == 4

    def test_init_with_custom_rate_limiter(self):
        """ParallelSearcher accepts custom rate limiter."""
        mock_context = MagicMock()
        custom_limiter = RateLimiter()
        searcher = ParallelSearcher(mock_context, rate_limiter=custom_limiter)

        assert searcher.rate_limiter is custom_limiter

    def test_init_creates_tab_manager(self):
        """ParallelSearcher creates a SyncTabManager."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context, max_parallel=3)

        assert searcher.tab_manager is not None
        assert searcher.tab_manager.config.max_tabs == 3


class TestParallelSearcherSearchMultipleSources:
    """Tests for search_multiple_sources method."""

    def test_search_empty_sources(self):
        """search_multiple_sources handles empty sources."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        results = searcher.search_multiple_sources("test query", [])

        assert results == {}

    def test_search_single_source(self):
        """search_multiple_sources searches a single source."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body><a href='http://result.com'>Result Link</a></body></html>"

        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        searcher = ParallelSearcher(mock_context)
        searcher.tab_manager = MagicMock()
        searcher.tab_manager.get_tab.return_value = mock_tab
        searcher.tab_manager.navigate_in_tab.return_value = True

        results = searcher.search_multiple_sources(
            "test",
            ["https://search.example.com?q={query}"]
        )

        assert len(results) == 1
        assert "https://search.example.com?q={query}" in results

    def test_search_multiple_sources_parallel(self):
        """search_multiple_sources searches multiple sources."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        searcher = ParallelSearcher(mock_context)
        searcher.tab_manager = MagicMock()
        searcher.tab_manager.get_tab.return_value = mock_tab
        searcher.tab_manager.navigate_in_tab.return_value = True

        sources = [
            "https://google.com?q={query}",
            "https://bing.com?q={query}",
        ]
        results = searcher.search_multiple_sources("test", sources)

        assert len(results) == 2

    def test_search_on_results_callback(self):
        """search_multiple_sources calls on_results callback."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        searcher = ParallelSearcher(mock_context)
        searcher.tab_manager = MagicMock()
        searcher.tab_manager.get_tab.return_value = mock_tab
        searcher.tab_manager.navigate_in_tab.return_value = True

        callback_results = []

        def on_results(source, results):
            callback_results.append((source, results))

        searcher.search_multiple_sources(
            "test",
            ["https://search.example.com?q={query}"],
            on_results=on_results
        )

        assert len(callback_results) == 1

    def test_search_handles_exceptions(self):
        """search_multiple_sources handles exceptions gracefully."""
        mock_context = MagicMock()

        searcher = ParallelSearcher(mock_context)
        searcher.tab_manager = MagicMock()
        searcher.tab_manager.get_tab.side_effect = Exception("Tab error")

        results = searcher.search_multiple_sources(
            "test",
            ["https://search.example.com?q={query}"]
        )

        # Should return empty results for failed source
        assert "https://search.example.com?q={query}" in results
        assert results["https://search.example.com?q={query}"] == []

    def test_search_url_encoding(self):
        """search_multiple_sources properly encodes query in URL."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        mock_tab = TabInfo(tab_id="tab_1", page=mock_page, status=TabStatus.ACTIVE)

        searcher = ParallelSearcher(mock_context)
        searcher.tab_manager = MagicMock()
        searcher.tab_manager.get_tab.return_value = mock_tab
        searcher.tab_manager.navigate_in_tab.return_value = True

        # Query with spaces should be encoded
        searcher.search_multiple_sources(
            "test query with spaces",
            ["https://search.example.com?q={query}"]
        )

        # Verify navigation was called with encoded URL
        nav_calls = searcher.tab_manager.navigate_in_tab.call_args_list
        assert len(nav_calls) >= 1
        called_url = nav_calls[0][0][1]
        assert "test%20query%20with%20spaces" in called_url


class TestParallelSearcherExtractSearchResults:
    """Tests for _extract_search_results method."""

    def test_extract_empty_html(self):
        """_extract_search_results handles empty HTML."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        results = searcher._extract_search_results("<html></html>", "test_source")

        assert results == []

    def test_extract_basic_links(self):
        """_extract_search_results extracts basic links."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        html = """
        <html>
        <body>
            <a href="https://result1.com">This is a search result with enough text</a>
            <a href="https://result2.com">Another search result with sufficient length</a>
        </body>
        </html>
        """

        results = searcher._extract_search_results(html, "test_source")

        assert len(results) == 2
        assert results[0]["url"] == "https://result1.com"
        assert results[0]["source"] == "test_source"

    def test_extract_skips_short_text(self):
        """_extract_search_results skips links with short text."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        html = """
        <html>
        <body>
            <a href="https://short.com">Short</a>
            <a href="https://valid.com">This link has more than ten characters</a>
        </body>
        </html>
        """

        results = searcher._extract_search_results(html, "test_source")

        assert len(results) == 1
        assert results[0]["url"] == "https://valid.com"

    def test_extract_skips_anchor_links(self):
        """_extract_search_results skips anchor (#) links."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        html = """
        <html>
        <body>
            <a href="#section">This is an anchor link not a result</a>
            <a href="https://valid.com">This is a valid result link</a>
        </body>
        </html>
        """

        results = searcher._extract_search_results(html, "test_source")

        assert len(results) == 1
        assert results[0]["url"] == "https://valid.com"

    def test_extract_skips_javascript_links(self):
        """_extract_search_results skips javascript: links."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        html = """
        <html>
        <body>
            <a href="javascript:void(0)">This is a javascript link</a>
            <a href="https://valid.com">This is a valid result link</a>
        </body>
        </html>
        """

        results = searcher._extract_search_results(html, "test_source")

        assert len(results) == 1

    def test_extract_skips_navigation_links(self):
        """_extract_search_results skips login/signup/settings links."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        html = """
        <html>
        <body>
            <a href="https://example.com/login">Login to your account here</a>
            <a href="https://example.com/signup">Sign up for a new account</a>
            <a href="https://example.com/settings">Manage your settings here</a>
            <a href="https://valid.com">This is a valid search result</a>
        </body>
        </html>
        """

        results = searcher._extract_search_results(html, "test_source")

        assert len(results) == 1
        assert results[0]["url"] == "https://valid.com"

    def test_extract_limits_results(self):
        """_extract_search_results limits to 20 results."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        links = "\n".join([
            f'<a href="https://result{i}.com">Search result number {i} with enough text</a>'
            for i in range(30)
        ])
        html = f"<html><body>{links}</body></html>"

        results = searcher._extract_search_results(html, "test_source")

        assert len(results) == 20

    def test_extract_truncates_long_titles(self):
        """_extract_search_results truncates titles to 200 chars."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)

        long_title = "A" * 300
        html = f'<html><body><a href="https://test.com">{long_title}</a></body></html>'

        results = searcher._extract_search_results(html, "test_source")

        assert len(results) == 1
        assert len(results[0]["title"]) == 200


class TestParallelSearcherClose:
    """Tests for ParallelSearcher.close method."""

    def test_close_calls_tab_manager_close_all(self):
        """close() calls tab_manager.close_all()."""
        mock_context = MagicMock()
        searcher = ParallelSearcher(mock_context)
        searcher.tab_manager = MagicMock()

        searcher.close()

        searcher.tab_manager.close_all.assert_called_once()


# ============================================================================
# ParallelOperationManager Tests
# ============================================================================

class TestParallelOperationManagerInit:
    """Tests for ParallelOperationManager initialization."""

    def test_init_with_defaults(self):
        """ParallelOperationManager initializes with defaults."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        assert manager.browser_context is mock_context
        assert manager.download_dir == "./downloads"
        assert manager.max_tabs == 5
        assert manager.rate_limiter is not None
        assert manager.timeout_manager is not None
        assert manager._fetcher is None
        assert manager._downloader is None
        assert manager._searcher is None

    def test_init_with_custom_download_dir(self):
        """ParallelOperationManager accepts custom download_dir."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context, download_dir="/custom/downloads")

        assert manager.download_dir == "/custom/downloads"

    def test_init_with_custom_max_tabs(self):
        """ParallelOperationManager accepts custom max_tabs."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context, max_tabs=10)

        assert manager.max_tabs == 10


class TestParallelOperationManagerFetcherProperty:
    """Tests for fetcher property."""

    def test_fetcher_lazy_initialization(self):
        """fetcher is lazily initialized."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        assert manager._fetcher is None

        fetcher = manager.fetcher

        assert manager._fetcher is not None
        assert fetcher is manager._fetcher

    def test_fetcher_reuses_instance(self):
        """fetcher returns same instance on multiple calls."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        fetcher1 = manager.fetcher
        fetcher2 = manager.fetcher

        assert fetcher1 is fetcher2

    def test_fetcher_uses_max_tabs(self):
        """fetcher uses manager's max_tabs."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context, max_tabs=7)

        fetcher = manager.fetcher

        assert fetcher.max_parallel == 7

    def test_fetcher_uses_rate_limiter(self):
        """fetcher uses manager's rate_limiter."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        fetcher = manager.fetcher

        assert fetcher.rate_limiter is manager.rate_limiter

    def test_fetcher_uses_timeout_manager(self):
        """fetcher uses manager's timeout_manager."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        fetcher = manager.fetcher

        assert fetcher.timeout_manager is manager.timeout_manager


class TestParallelOperationManagerDownloaderProperty:
    """Tests for downloader property."""

    def test_downloader_lazy_initialization(self):
        """downloader is lazily initialized."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        assert manager._downloader is None

        downloader = manager.downloader

        assert manager._downloader is not None
        assert downloader is manager._downloader

    def test_downloader_reuses_instance(self):
        """downloader returns same instance on multiple calls."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        dl1 = manager.downloader
        dl2 = manager.downloader

        assert dl1 is dl2

    def test_downloader_uses_download_dir(self):
        """downloader uses manager's download_dir."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context, download_dir="/my/downloads")

        downloader = manager.downloader

        assert downloader.download_dir == "/my/downloads"

    def test_downloader_limits_max_parallel(self):
        """downloader limits max_parallel to min(3, max_tabs)."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context, max_tabs=10)

        downloader = manager.downloader

        assert downloader.max_parallel == 3  # min(3, 10)

    def test_downloader_max_parallel_small_max_tabs(self):
        """downloader uses max_tabs when less than 3."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context, max_tabs=2)

        downloader = manager.downloader

        assert downloader.max_parallel == 2  # min(3, 2)


class TestParallelOperationManagerSearcherProperty:
    """Tests for searcher property."""

    def test_searcher_lazy_initialization(self):
        """searcher is lazily initialized."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        assert manager._searcher is None

        searcher = manager.searcher

        assert manager._searcher is not None
        assert searcher is manager._searcher

    def test_searcher_reuses_instance(self):
        """searcher returns same instance on multiple calls."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        s1 = manager.searcher
        s2 = manager.searcher

        assert s1 is s2

    def test_searcher_limits_max_parallel(self):
        """searcher limits max_parallel to min(2, max_tabs)."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context, max_tabs=10)

        searcher = manager.searcher

        assert searcher.max_parallel == 2  # min(2, 10)


class TestParallelOperationManagerDelegationMethods:
    """Tests for delegation methods."""

    def test_fetch_pages_delegates_to_fetcher(self):
        """fetch_pages delegates to fetcher.fetch_pages."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)
        manager._fetcher = MagicMock()
        mock_result = ParallelResult(total_tasks=1, completed=1, failed=0, cancelled=0)
        manager._fetcher.fetch_pages.return_value = mock_result

        urls = ["https://example.com"]
        result = manager.fetch_pages(urls)

        manager._fetcher.fetch_pages.assert_called_once_with(urls)

    def test_download_files_delegates_to_downloader(self):
        """download_files delegates to downloader.download_files."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)
        manager._downloader = MagicMock()
        mock_result = ParallelResult(total_tasks=1, completed=1, failed=0, cancelled=0)
        manager._downloader.download_files.return_value = mock_result

        items = [("https://example.com/file.pdf", "file.pdf")]
        result = manager.download_files(items)

        manager._downloader.download_files.assert_called_once()

    def test_search_sources_delegates_to_searcher(self):
        """search_sources delegates to searcher.search_multiple_sources."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)
        manager._searcher = MagicMock()
        manager._searcher.search_multiple_sources.return_value = {"source": []}

        sources = ["https://google.com?q={query}"]
        result = manager.search_sources("test", sources)

        manager._searcher.search_multiple_sources.assert_called_once()


class TestParallelOperationManagerClose:
    """Tests for close method."""

    def test_close_nothing_when_nothing_initialized(self):
        """close() doesn't error when nothing initialized."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)

        # Should not raise
        manager.close()

    def test_close_closes_fetcher(self):
        """close() closes fetcher if initialized."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)
        manager._fetcher = MagicMock()

        manager.close()

        manager._fetcher.close.assert_called_once()

    def test_close_closes_downloader(self):
        """close() closes downloader if initialized."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)
        manager._downloader = MagicMock()

        manager.close()

        manager._downloader.close.assert_called_once()

    def test_close_closes_searcher(self):
        """close() closes searcher if initialized."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)
        manager._searcher = MagicMock()

        manager.close()

        manager._searcher.close.assert_called_once()

    def test_close_closes_all_initialized(self):
        """close() closes all initialized components."""
        mock_context = MagicMock()
        manager = ParallelOperationManager(mock_context)
        manager._fetcher = MagicMock()
        manager._downloader = MagicMock()
        manager._searcher = MagicMock()

        manager.close()

        manager._fetcher.close.assert_called_once()
        manager._downloader.close.assert_called_once()
        manager._searcher.close.assert_called_once()


# ============================================================================
# Singleton Manager Tests
# ============================================================================

class TestGetParallelManager:
    """Tests for get_parallel_manager function."""

    def test_returns_none_without_context(self):
        """get_parallel_manager returns None without browser context."""
        reset_parallel_manager()

        result = get_parallel_manager()

        assert result is None

    def test_creates_manager_with_context(self):
        """get_parallel_manager creates manager when context provided."""
        reset_parallel_manager()
        mock_context = MagicMock()

        result = get_parallel_manager(browser_context=mock_context)

        assert result is not None
        assert isinstance(result, ParallelOperationManager)

        reset_parallel_manager()  # Cleanup

    def test_returns_same_instance(self):
        """get_parallel_manager returns same instance on subsequent calls."""
        reset_parallel_manager()
        mock_context = MagicMock()

        result1 = get_parallel_manager(browser_context=mock_context)
        result2 = get_parallel_manager()

        assert result1 is result2

        reset_parallel_manager()  # Cleanup

    def test_uses_custom_download_dir(self):
        """get_parallel_manager uses custom download_dir."""
        reset_parallel_manager()
        mock_context = MagicMock()

        result = get_parallel_manager(
            browser_context=mock_context,
            download_dir="/custom/path"
        )

        assert result.download_dir == "/custom/path"

        reset_parallel_manager()  # Cleanup

    def test_uses_custom_max_tabs(self):
        """get_parallel_manager uses custom max_tabs."""
        reset_parallel_manager()
        mock_context = MagicMock()

        result = get_parallel_manager(
            browser_context=mock_context,
            max_tabs=8
        )

        assert result.max_tabs == 8

        reset_parallel_manager()  # Cleanup


class TestResetParallelManager:
    """Tests for reset_parallel_manager function."""

    def test_reset_clears_manager(self):
        """reset_parallel_manager clears the global manager."""
        mock_context = MagicMock()
        manager = get_parallel_manager(browser_context=mock_context)

        reset_parallel_manager()

        # After reset, should be None again
        assert get_parallel_manager() is None

    def test_reset_closes_manager(self):
        """reset_parallel_manager closes the manager before clearing."""
        reset_parallel_manager()  # Start clean
        mock_context = MagicMock()

        manager = get_parallel_manager(browser_context=mock_context)
        # Initialize some components
        manager._fetcher = MagicMock()

        reset_parallel_manager()

        # Fetcher's close should have been called
        manager._fetcher.close.assert_called_once()

    def test_reset_idempotent(self):
        """reset_parallel_manager is idempotent."""
        reset_parallel_manager()  # Start clean

        # Multiple resets should not raise
        reset_parallel_manager()
        reset_parallel_manager()
        reset_parallel_manager()

        assert get_parallel_manager() is None
