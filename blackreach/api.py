"""
Blackreach API Interface (v3.4.0)

Provides a clean programmatic API for Blackreach:
- Simple high-level functions
- Async support
- Batch operations
- Progress callbacks
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from pathlib import Path
import asyncio


@dataclass
class BrowseResult:
    """Result from a browse operation."""
    success: bool
    goal: str
    downloads: List[str] = field(default_factory=list)
    pages_visited: int = 0
    steps_taken: int = 0
    errors: List[str] = field(default_factory=list)
    session_id: Optional[int] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """Result from a search operation."""
    query: str
    results: List[Dict] = field(default_factory=list)
    source: str = ""
    total_found: int = 0


@dataclass
class DownloadResult:
    """Result from a download operation."""
    success: bool
    url: str
    filename: str = ""
    path: str = ""
    size: int = 0
    error: Optional[str] = None


@dataclass
class ApiConfig:
    """Configuration for the API."""
    download_dir: Path = field(default_factory=lambda: Path("./downloads"))
    headless: bool = True
    max_steps: int = 50
    browser_type: str = "chromium"
    verbose: bool = False


class BlackreachAPI:
    """High-level API for Blackreach."""

    def __init__(self, config: Optional[ApiConfig] = None):
        self.config = config or ApiConfig()
        self._agent = None
        self._initialized = False

    def _get_agent(self):
        """Get or create the agent instance."""
        if self._agent is None:
            from blackreach.agent import Agent, AgentConfig
            from blackreach.llm import LLMConfig

            agent_config = AgentConfig(
                download_dir=self.config.download_dir,
                headless=self.config.headless,
                max_steps=self.config.max_steps,
                browser_type=self.config.browser_type
            )

            self._agent = Agent(
                agent_config=agent_config
            )
            self._initialized = True

        return self._agent

    def browse(
        self,
        goal: str,
        start_url: Optional[str] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> BrowseResult:
        """
        Browse the web to accomplish a goal.

        Args:
            goal: Natural language description of what to do
            start_url: Optional starting URL
            on_progress: Optional callback (step, max_steps, status)

        Returns:
            BrowseResult with outcome
        """
        from blackreach.agent import AgentCallbacks

        agent = self._get_agent()

        # Set up callbacks
        if on_progress:
            agent.callbacks.on_step = lambda step, max_s, phase, detail: on_progress(step, max_s, phase)

        try:
            result = agent.run(goal, quiet=not self.config.verbose)

            return BrowseResult(
                success=result.get("success", False),
                goal=goal,
                downloads=result.get("downloads", []),
                pages_visited=result.get("pages_visited", 0),
                steps_taken=result.get("steps_taken", 0),
                session_id=result.get("session_id")
            )
        except Exception as e:
            return BrowseResult(
                success=False,
                goal=goal,
                errors=[str(e)]
            )

    def download(
        self,
        what: str,
        count: int = 1,
        quality: str = "best"
    ) -> List[DownloadResult]:
        """
        Download files matching a description.

        Args:
            what: Description of what to download (e.g., "Python ebooks")
            count: Number of items to download
            quality: Quality preference ("best", "any")

        Returns:
            List of DownloadResult
        """
        goal = f"Download {count} {what}"
        if quality == "best":
            goal += " (prefer high quality)"

        result = self.browse(goal)

        downloads = []
        for path in result.downloads:
            from pathlib import Path
            p = Path(path)
            downloads.append(DownloadResult(
                success=True,
                url="",  # URL not tracked in current implementation
                filename=p.name,
                path=str(p),
                size=p.stat().st_size if p.exists() else 0
            ))

        return downloads

    def search(
        self,
        query: str,
        source: str = "google",
        max_results: int = 10
    ) -> SearchResult:
        """
        Search the web and return results.

        Args:
            query: Search query
            source: Search engine ("google", "duckduckgo")
            max_results: Maximum results to return

        Returns:
            SearchResult with found items
        """
        # For now, this is a simplified version
        # Full implementation would extract search results without downloading
        from blackreach.search_intel import get_search_intel

        search_intel = get_search_intel()
        search_query = search_intel.create_search(query)

        return SearchResult(
            query=query,
            results=[],  # Would be populated by actual search
            source=source,
            total_found=0
        )

    def get_page(self, url: str) -> Dict:
        """
        Get page content at a URL.

        Args:
            url: URL to fetch

        Returns:
            Dict with page title, text, links

        Raises:
            ValueError: If URL targets internal/private networks (SSRF protection)
        """
        # P0-SEC: SSRF protection - validate URL before fetching
        from blackreach.browser import _is_ssrf_safe
        _is_ssrf_safe(url)  # Raises ValueError if unsafe

        agent = self._get_agent()

        # Initialize browser if needed
        if not agent.hand:
            agent.hand = agent._create_browser()

        agent.hand.goto(url)
        html = agent.hand.get_html()
        parsed = agent.eyes.see(html)

        return {
            "url": url,
            "title": agent.hand.get_title(),
            "text": parsed.get("text_preview", ""),
            "links": parsed.get("links", []),
            "images": parsed.get("images", [])
        }

    def close(self):
        """Close the API and release resources."""
        if self._agent and self._agent.hand:
            self._agent.hand.sleep()
        self._agent = None
        self._initialized = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience functions

def browse(goal: str, **kwargs) -> BrowseResult:
    """Quick browse function."""
    with BlackreachAPI() as api:
        return api.browse(goal, **kwargs)


def download(what: str, count: int = 1, **kwargs) -> List[DownloadResult]:
    """Quick download function."""
    with BlackreachAPI() as api:
        return api.download(what, count, **kwargs)


def search(query: str, **kwargs) -> SearchResult:
    """Quick search function."""
    with BlackreachAPI() as api:
        return api.search(query, **kwargs)


def get_page(url: str) -> Dict:
    """Quick page fetch function."""
    with BlackreachAPI() as api:
        return api.get_page(url)


# Batch operations

class BatchProcessor:
    """Process multiple goals in batch."""

    def __init__(self, config: Optional[ApiConfig] = None):
        self.config = config or ApiConfig()
        self.results: List[BrowseResult] = []

    def add(self, goal: str) -> int:
        """Add a goal to the batch. Returns index."""
        # Goals are processed immediately in current implementation
        # Future: queue for parallel processing
        return len(self.results)

    def run_all(
        self,
        goals: List[str],
        on_complete: Optional[Callable[[int, BrowseResult], None]] = None
    ) -> List[BrowseResult]:
        """
        Run all goals sequentially.

        Args:
            goals: List of goals to accomplish
            on_complete: Callback when each goal completes

        Returns:
            List of results
        """
        results = []

        with BlackreachAPI(self.config) as api:
            for i, goal in enumerate(goals):
                result = api.browse(goal)
                results.append(result)

                if on_complete:
                    on_complete(i, result)

        self.results = results
        return results

    def get_summary(self) -> Dict:
        """Get summary of batch results."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        total_downloads = sum(len(r.downloads) for r in self.results)

        return {
            "total_goals": total,
            "successful": successful,
            "failed": total - successful,
            "total_downloads": total_downloads,
            "success_rate": successful / total if total > 0 else 0
        }
