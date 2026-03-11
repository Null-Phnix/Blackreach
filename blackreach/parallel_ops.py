"""
Parallel Operations System (v4.0.0-beta.2)

Provides parallel browsing and download capabilities:
- Multi-tab parallel page fetching
- Concurrent download orchestration
- Resource-aware parallelism
- Progress aggregation and reporting
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import queue

from blackreach.multi_tab import SyncTabManager, TabStatus, TabPoolConfig, TabInfo
from blackreach.download_queue import DownloadQueue, DownloadItem, DownloadPriority, DownloadStatus
from blackreach.rate_limiter import RateLimiter, get_rate_limiter
from blackreach.timeout_manager import TimeoutManager, get_timeout_manager


class ParallelTaskType(Enum):
    """Types of parallel tasks."""
    FETCH_PAGE = "fetch_page"
    DOWNLOAD_FILE = "download_file"
    SEARCH = "search"
    EXTRACT_LINKS = "extract_links"


class ParallelTaskStatus(Enum):
    """Status of a parallel task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ParallelTask:
    """Represents a task that can run in parallel."""
    task_id: str
    task_type: ParallelTaskType
    url: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: ParallelTaskStatus = ParallelTaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tab_id: Optional[str] = None


@dataclass
class ParallelResult:
    """Aggregated result from parallel operations."""
    total_tasks: int
    completed: int
    failed: int
    cancelled: int
    results: List[ParallelTask] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.completed / self.total_tasks


class ParallelFetcher:
    """
    Fetches multiple pages in parallel using browser tabs.

    Uses a tab pool to manage concurrent page loads while
    respecting rate limits and resource constraints.
    """

    def __init__(
        self,
        browser_context,
        max_parallel: int = 3,
        rate_limiter: Optional[RateLimiter] = None,
        timeout_manager: Optional[TimeoutManager] = None
    ):
        self.tab_manager = SyncTabManager(
            browser_context,
            TabPoolConfig(max_tabs=max_parallel, reuse_tabs=True)
        )
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.timeout_manager = timeout_manager or get_timeout_manager()
        self.max_parallel = max_parallel
        self._task_counter = 0
        self._lock = threading.Lock()
        self._results: Dict[str, ParallelTask] = {}

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        with self._lock:
            self._task_counter += 1
            return f"fetch_{self._task_counter}_{int(time.time())}"

    def fetch_pages(
        self,
        urls: List[str],
        on_page_loaded: Optional[Callable[[str, str, Any], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> ParallelResult:
        """
        Fetch multiple pages in parallel.

        Args:
            urls: List of URLs to fetch
            on_page_loaded: Callback(url, html, parsed) when a page loads
            on_progress: Callback(completed, total) for progress updates

        Returns:
            ParallelResult with all fetch results
        """
        start_time = time.time()
        tasks = []

        # Create tasks for all URLs
        for url in urls:
            task = ParallelTask(
                task_id=self._generate_task_id(),
                task_type=ParallelTaskType.FETCH_PAGE,
                url=url
            )
            tasks.append(task)
            self._results[task.task_id] = task

        # P0-PERF: Use ThreadPoolExecutor for actual parallel execution
        # Previous implementation was sequential despite claiming to be parallel
        completed = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            # Submit all tasks to the executor
            future_to_task = {
                executor.submit(self._fetch_single, task, on_page_loaded): task
                for task in tasks
            }

            # Process results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    future.result()  # Get any exception that occurred
                    if task.status == ParallelTaskStatus.COMPLETED:
                        completed += 1
                    else:
                        failed_count += 1
                except Exception:  # Future may propagate any error from the task thread
                    failed_count += 1
                    task.status = ParallelTaskStatus.FAILED

                if on_progress:
                    on_progress(completed + failed_count, len(tasks))

        # Compile results
        elapsed = time.time() - start_time
        result = ParallelResult(
            total_tasks=len(tasks),
            completed=sum(1 for t in tasks if t.status == ParallelTaskStatus.COMPLETED),
            failed=sum(1 for t in tasks if t.status == ParallelTaskStatus.FAILED),
            cancelled=sum(1 for t in tasks if t.status == ParallelTaskStatus.CANCELLED),
            results=tasks,
            elapsed_seconds=elapsed
        )

        # Clean up completed tasks from internal tracking to prevent memory leak
        for task in tasks:
            self._results.pop(task.task_id, None)

        return result

    def _fetch_single(
        self,
        task: ParallelTask,
        callback: Optional[Callable] = None
    ):
        """Fetch a single page."""
        from urllib.parse import urlparse

        task.status = ParallelTaskStatus.RUNNING
        task.started_at = datetime.now()

        try:
            # Check rate limit
            domain = urlparse(task.url).netloc
            can_request, wait_time = self.rate_limiter.can_request(domain)
            if not can_request:
                time.sleep(wait_time)

            # Get timeout
            timeout = self.timeout_manager.get_timeout("navigate", domain)

            # Get a tab
            tab = self.tab_manager.get_tab(task=f"fetch_{task.url}")
            task.tab_id = tab.tab_id

            # Navigate
            success = self.tab_manager.navigate_in_tab(tab.tab_id, task.url)

            if success:
                # Get page content
                html = tab.page.content()
                task.result = {
                    "url": task.url,
                    "html": html,
                    "title": tab.page.title(),
                    "final_url": tab.page.url
                }
                task.status = ParallelTaskStatus.COMPLETED

                if callback:
                    callback(task.url, html, task.result)
            else:
                task.status = ParallelTaskStatus.FAILED
                task.error = "Navigation failed"

            # Release tab back to pool
            self.tab_manager.release_tab(tab.tab_id)

        except Exception as e:  # Task may raise any error type (browser, network, timeout, etc.)
            task.status = ParallelTaskStatus.FAILED
            task.error = str(e)
        finally:
            task.completed_at = datetime.now()

    def close(self):
        """Close all tabs and cleanup."""
        self.tab_manager.close_all()


class ParallelDownloader:
    """
    Manages parallel file downloads.

    Coordinates multiple download streams while respecting
    bandwidth limits and server rate limits.
    """

    def __init__(
        self,
        browser_context,
        download_dir: str,
        max_parallel: int = 3,
        rate_limiter: Optional[RateLimiter] = None
    ):
        self.tab_manager = SyncTabManager(
            browser_context,
            TabPoolConfig(max_tabs=max_parallel, reuse_tabs=True)
        )
        self.download_dir = download_dir
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.max_parallel = max_parallel
        self._active_downloads: Dict[str, ParallelTask] = {}
        self._lock = threading.Lock()
        self._download_counter = 0

    def _generate_download_id(self) -> str:
        """Generate unique download ID."""
        with self._lock:
            self._download_counter += 1
            return f"dl_{self._download_counter}_{int(time.time())}"

    def download_files(
        self,
        download_items: List[Tuple[str, str]],  # List of (url, filename) tuples
        on_download_complete: Optional[Callable[[str, str, bool], None]] = None,
        on_progress: Optional[Callable[[int, int, int], None]] = None
    ) -> ParallelResult:
        """
        Download multiple files in parallel.

        Args:
            download_items: List of (url, filename) tuples
            on_download_complete: Callback(url, path, success) when download finishes
            on_progress: Callback(completed, failed, total) for progress

        Returns:
            ParallelResult with download outcomes
        """
        start_time = time.time()
        tasks = []

        # Create tasks
        for url, filename in download_items:
            task = ParallelTask(
                task_id=self._generate_download_id(),
                task_type=ParallelTaskType.DOWNLOAD_FILE,
                url=url,
                params={"filename": filename}
            )
            tasks.append(task)

        # P0-PERF: Use ThreadPoolExecutor for actual parallel downloads
        completed = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            # Submit all download tasks
            future_to_task = {
                executor.submit(self._download_single, task): task
                for task in tasks
            }

            # Process as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success = future.result()
                    if success:
                        completed += 1
                    else:
                        failed += 1
                except Exception:  # Future may propagate any error from the download thread
                    failed += 1
                    task.status = ParallelTaskStatus.FAILED

                if on_progress:
                    on_progress(completed, failed, len(tasks))

                if on_download_complete:
                    path = task.result.get("path", "") if task.result else ""
                    success = task.status == ParallelTaskStatus.COMPLETED
                    on_download_complete(task.url, path, success)

        elapsed = time.time() - start_time
        return ParallelResult(
            total_tasks=len(tasks),
            completed=completed,
            failed=failed,
            cancelled=0,
            results=tasks,
            elapsed_seconds=elapsed
        )

    def _download_single(self, task: ParallelTask) -> bool:
        """Download a single file."""
        from urllib.parse import urlparse
        from pathlib import Path

        task.status = ParallelTaskStatus.RUNNING
        task.started_at = datetime.now()

        try:
            # Check rate limit
            domain = urlparse(task.url).netloc
            can_request, wait_time = self.rate_limiter.can_request(domain)
            if not can_request:
                time.sleep(wait_time)

            # Get a tab for download
            tab = self.tab_manager.get_tab(task=f"download_{task.url}")
            task.tab_id = tab.tab_id

            filename = task.params.get("filename", "download")
            download_path = Path(self.download_dir) / filename

            # Set up download handling
            with tab.page.expect_download(timeout=60000) as download_info:
                # Navigate to trigger download
                tab.page.goto(task.url)

            download = download_info.value

            # Save file
            download.save_as(str(download_path))

            task.result = {
                "url": task.url,
                "path": str(download_path),
                "filename": filename,
                "size": download_path.stat().st_size if download_path.exists() else 0
            }
            task.status = ParallelTaskStatus.COMPLETED

            # Release tab
            self.tab_manager.release_tab(tab.tab_id)
            return True

        except Exception as e:  # Task may raise any error type (browser, network, I/O, etc.)
            task.status = ParallelTaskStatus.FAILED
            task.error = str(e)
            return False
        finally:
            task.completed_at = datetime.now()

    def close(self):
        """Cleanup resources."""
        self.tab_manager.close_all()


class ParallelSearcher:
    """
    Performs parallel searches across multiple search engines/sources.
    """

    def __init__(
        self,
        browser_context,
        max_parallel: int = 2,
        rate_limiter: Optional[RateLimiter] = None
    ):
        self.tab_manager = SyncTabManager(
            browser_context,
            TabPoolConfig(max_tabs=max_parallel, reuse_tabs=True)
        )
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.max_parallel = max_parallel
        self._search_counter = 0

    def search_multiple_sources(
        self,
        query: str,
        sources: List[str],
        on_results: Optional[Callable[[str, List[Dict]], None]] = None
    ) -> Dict[str, List[Dict]]:
        """
        Search multiple sources in parallel.

        Args:
            query: Search query
            sources: List of source URLs (search engine URLs with {query} placeholder)
            on_results: Callback(source, results) when results are ready

        Returns:
            Dict mapping source to list of results
        """
        from urllib.parse import quote

        all_results = {}
        lock = threading.Lock()

        def search_single(source: str) -> Tuple[str, List[Dict]]:
            """Search a single source."""
            search_url = source.replace("{query}", quote(query))
            try:
                tab = self.tab_manager.get_tab(task=f"search_{source}")
                self.tab_manager.navigate_in_tab(tab.tab_id, search_url)

                # Extract search results (basic extraction)
                html = tab.page.content()
                results = self._extract_search_results(html, source)

                self.tab_manager.release_tab(tab.tab_id)
                return (source, results)

            except Exception as e:  # Search task may raise any error type (browser, network, parse, etc.)
                return (source, [])

        # P0-PERF: Use ThreadPoolExecutor for parallel search
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = [executor.submit(search_single, source) for source in sources]

            for future in as_completed(futures):
                source, results = future.result()
                with lock:
                    all_results[source] = results
                if on_results:
                    on_results(source, results)

        return all_results

    def _extract_search_results(self, html: str, source: str) -> List[Dict]:
        """Extract search results from HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Generic extraction - find links that look like results
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)

            # Skip navigation/utility links
            if not text or len(text) < 10:
                continue
            if href.startswith("#") or href.startswith("javascript:"):
                continue
            if any(skip in href.lower() for skip in ["login", "signup", "settings"]):
                continue

            results.append({
                "title": text[:200],
                "url": href,
                "source": source
            })

            if len(results) >= 20:
                break

        return results

    def close(self):
        """Cleanup."""
        self.tab_manager.close_all()


class ParallelOperationManager:
    """
    High-level manager for parallel operations.

    Provides a unified interface for running parallel fetches,
    downloads, and searches while managing resources.
    """

    def __init__(
        self,
        browser_context,
        download_dir: str = "./downloads",
        max_tabs: int = 5
    ):
        self.browser_context = browser_context
        self.download_dir = download_dir
        self.max_tabs = max_tabs
        self.rate_limiter = get_rate_limiter()
        self.timeout_manager = get_timeout_manager()

        # Lazy initialization
        self._fetcher: Optional[ParallelFetcher] = None
        self._downloader: Optional[ParallelDownloader] = None
        self._searcher: Optional[ParallelSearcher] = None

    @property
    def fetcher(self) -> ParallelFetcher:
        """Get or create the parallel fetcher."""
        if self._fetcher is None:
            self._fetcher = ParallelFetcher(
                self.browser_context,
                max_parallel=self.max_tabs,
                rate_limiter=self.rate_limiter,
                timeout_manager=self.timeout_manager
            )
        return self._fetcher

    @property
    def downloader(self) -> ParallelDownloader:
        """Get or create the parallel downloader."""
        if self._downloader is None:
            self._downloader = ParallelDownloader(
                self.browser_context,
                self.download_dir,
                max_parallel=min(3, self.max_tabs),  # Limit concurrent downloads
                rate_limiter=self.rate_limiter
            )
        return self._downloader

    @property
    def searcher(self) -> ParallelSearcher:
        """Get or create the parallel searcher."""
        if self._searcher is None:
            self._searcher = ParallelSearcher(
                self.browser_context,
                max_parallel=min(2, self.max_tabs),  # Limit concurrent searches
                rate_limiter=self.rate_limiter
            )
        return self._searcher

    def fetch_pages(self, urls: List[str], **kwargs) -> ParallelResult:
        """Fetch multiple pages in parallel."""
        return self.fetcher.fetch_pages(urls, **kwargs)

    def download_files(self, items: List[Tuple[str, str]], **kwargs) -> ParallelResult:
        """Download multiple files in parallel."""
        return self.downloader.download_files(items, **kwargs)

    def search_sources(self, query: str, sources: List[str], **kwargs) -> Dict[str, List[Dict]]:
        """Search multiple sources in parallel."""
        return self.searcher.search_multiple_sources(query, sources, **kwargs)

    def close(self):
        """Close all parallel operation handlers."""
        if self._fetcher:
            self._fetcher.close()
        if self._downloader:
            self._downloader.close()
        if self._searcher:
            self._searcher.close()


# Singleton instance
_parallel_manager: Optional[ParallelOperationManager] = None


def get_parallel_manager(
    browser_context=None,
    download_dir: str = "./downloads",
    max_tabs: int = 5
) -> Optional[ParallelOperationManager]:
    """Get the global parallel operation manager."""
    global _parallel_manager
    if _parallel_manager is None and browser_context is not None:
        _parallel_manager = ParallelOperationManager(
            browser_context,
            download_dir,
            max_tabs
        )
    return _parallel_manager


def reset_parallel_manager():
    """Reset the parallel manager (for testing)."""
    global _parallel_manager
    if _parallel_manager:
        _parallel_manager.close()
    _parallel_manager = None
