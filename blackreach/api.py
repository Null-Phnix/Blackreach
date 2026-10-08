"""
Blackreach API Interface (v3.4.0)

Provides a clean programmatic API for Blackreach:
- Simple high-level functions
- Async support
- Batch operations
- Progress callbacks
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

# Huginn/BlackCrawl is the shared scrape+search backend (localhost:7432).
HUGINN_URL = os.environ.get("HUGINN_URL", "http://127.0.0.1:7432")
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from blackreach.llm import LLMConfig


def safe_browse_error(exc: Exception) -> str:
    """Expose actionable Blackreach errors without echoing arbitrary SDK payloads."""
    from blackreach.exceptions import BlackreachError
    from blackreach.logging import redact_log_text
    if isinstance(exc, BlackreachError):
        return redact_log_text(str(exc))
    return f"Browse execution failed ({type(exc).__name__}); check configuration and the session log."


def _huginn_api_key() -> str:
    direct = os.environ.get("HUGINN_API_KEY", "").strip()
    if direct:
        return direct
    key_file = os.environ.get("HUGINN_API_KEY_FILE")
    if not key_file:
        return ""
    try:
        return Path(key_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read HUGINN_API_KEY_FILE {key_file}: {exc}") from exc


def _clean_result_url(url: str) -> str:
    """Huginn's DDG-sourced results wrap the target in a redirect
    (//duckduckgo.com/l/?uddg=<encoded>). Unwrap it to the real URL."""
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    if "\\" in url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return ""
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return ""
    hostname = (parsed.hostname or "").rstrip(".").lower()
    is_duckduckgo = hostname == "duckduckgo.com" or hostname.endswith(".duckduckgo.com")
    if is_duckduckgo and parsed.path.startswith("/l/"):
        uddg = urllib.parse.parse_qs(parsed.query).get("uddg")
        if uddg:
            target = uddg[0]
            try:
                parsed_target = urllib.parse.urlparse(target)
            except ValueError:
                return ""
            if (
                "\\" not in target
                and parsed_target.scheme in {"http", "https"}
                and parsed_target.hostname
                and parsed_target.username is None
                and parsed_target.password is None
            ):
                return target
            return ""
    return url


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
    result: str = ""  # The agent's final extracted text/answer
    status: str = ""
    stop_reason: str = ""
    resumable: bool = False
    paused: bool = False
    actions_taken: int = 0
    actions_count_estimated: bool = False
    failures: int = 0

    def __post_init__(self):
        if not self.status:
            self.status = "success" if self.success else "error" if self.errors else "stopped"

    def outcome(self) -> Dict[str, Any]:
        """Run outcome, separate from HTTP transport/job completion."""
        return {name: getattr(self, name) for name in (
            "status", "stop_reason", "resumable", "paused", "actions_taken",
            "actions_count_estimated", "failures",
        )}


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
    headless: bool = False
    max_steps: int = 50
    browser_type: str = "chromium"
    verbose: bool = False
    llm_config: Optional["LLMConfig"] = None


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
            from blackreach.config import config_manager
            from blackreach.llm import LLMConfig

            agent_config = AgentConfig(
                download_dir=self.config.download_dir,
                headless=self.config.headless,
                max_steps=self.config.max_steps,
                browser_type=self.config.browser_type
            )

            # Explicit API settings win, then the saved CLI provider settings.
            # Preserve the historical DeepSeek environment shortcut only while
            # the saved default is Ollama; never replace a selected cloud provider.
            llm_config = self.config.llm_config
            if llm_config is None:
                cfg = config_manager.load()
                provider = cfg.default_provider
                provider_cfg = getattr(cfg, provider)
                deepseek_key = os.environ.get("DEEPSEEK_API_KEY") if provider == "ollama" else None
                if deepseek_key:
                    llm_config = LLMConfig(
                        provider="openai", model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                        api_key=deepseek_key, api_base="https://api.deepseek.com", api_mode="chat",
                        **{name: value for name, value in provider_cfg.llm_settings().items() if name != "api_mode"},
                    )
                else:
                    llm_config = LLMConfig(
                        provider=provider, model=provider_cfg.default_model,
                        api_key=config_manager.get_api_key(provider) if provider != "ollama" else None,
                        api_base=provider_cfg.base_url or None, **provider_cfg.llm_settings(),
                    )

            self._agent = Agent(
                agent_config=agent_config,
                llm_config=llm_config,
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
        from blackreach.logging import redact_log_text
        agent, previous_callback = None, None
        try:
            agent = self._get_agent()
            previous_callback = agent.callbacks.on_step
            if on_progress:
                agent.callbacks.on_step = lambda step, max_s, phase, detail: on_progress(step, max_s, phase)
            result = agent.run(goal, quiet=not self.config.verbose, start_url=start_url)
            errors = [redact_log_text(str(error)) for error in result.get("errors", [])]
            if result.get("error"):
                error = redact_log_text(str(result["error"]))
                if error not in errors:
                    errors.append(error)
            status = result.get("status") or (
                "success" if result.get("success") else "paused" if result.get("paused") else "error" if errors else "stopped"
            )
            outcome = {
                "status": status, "stop_reason": result.get("stop_reason") or "unspecified",
                "resumable": bool(result.get("resumable", result.get("paused", False))),
                "paused": bool(result.get("paused", False)),
                "actions_taken": result.get("actions_taken", 0),
                "actions_count_estimated": bool(result.get("actions_count_estimated", False)),
                "failures": result.get("failures", len(errors)),
            }
            return BrowseResult(
                success=bool(result.get("success", False)) and status == "success",
                goal=goal,
                downloads=result.get("downloads", []),
                pages_visited=result.get("pages_visited", 0),
                steps_taken=result.get("steps_taken", 0),
                session_id=result.get("session_id"),
                result=result.get("result") or "",
                errors=errors, metadata=outcome.copy(), **outcome,
            )
        except Exception as e:
            failure = BrowseResult(
                success=False, goal=goal, errors=[safe_browse_error(e)], status="error",
                stop_reason="startup_error" if agent is None else "permanent_error",
                failures=1,
            )
            failure.metadata = failure.outcome()
            return failure
        finally:
            if agent is not None and on_progress:
                agent.callbacks.on_step = previous_callback

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
        source: str = "starsearch",
        max_results: int = 10
    ) -> SearchResult:
        """
        Keyless web search through Huginn, the suite's shared web-data plane.
        Huginn routes the request through StarSearch; Blackreach talks directly
        to StarSearch only as a local availability fallback.

        Args:
            query: Search query
            source: label kept for API compatibility (unused)
            max_results: Maximum results to return
        """
        # Primary: centralize search policy, result normalization, and future
        # engine fallback in Huginn instead of maintaining two competing paths.
        try:
            headers = {"Content-Type": "application/json"}
            api_key = _huginn_api_key()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            req = urllib.request.Request(
                f"{HUGINN_URL}/v1/seek",
                data=json.dumps({
                    "query": query,
                    "search_options": {"limit": max_results},
                    "scrape_results": False,
                }).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.loads(resp.read().decode())
            results = []
            for item in (payload.get("data") or []):
                meta = item.get("metadata") or {}
                results.append({
                    "title": meta.get("title") or item.get("title") or "",
                    "url": _clean_result_url(meta.get("url") or item.get("url") or ""),
                    "description": (
                        meta.get("description")
                        or meta.get("snippet")
                        or item.get("summary")
                        or ""
                    ),
                })
            if results:
                return SearchResult(
                    query=query,
                    results=results[:max_results],
                    source="huginn-starsearch",
                    total_found=len(results[:max_results]),
                )
        except Exception as exc:
            logger.warning("Huginn search unavailable; using direct StarSearch: %s", exc)

        try:
            from blackreach.starsearch_search import search as _starsearch_bing
            rows = _starsearch_bing(query, limit=max_results)
            return SearchResult(
                query=query,
                results=rows,
                source="starsearch-bing",
                total_found=len(rows),
            )
        except Exception as exc:
            logger.warning("Direct StarSearch search failed: %s", exc)
            return SearchResult(
                query=query, results=[], source="unavailable", total_found=0
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
        agent.hand.get_html()
        from blackreach.dom_walker import walk_dom
        dom = walk_dom(agent.hand.page)
        parsed = {
            "text_preview": dom.get("text_preview", ""),
            "links": dom.get("links", []),
            "images": dom.get("images", [])
        }

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
