"""
Blackreach Agent - ReAct Loop

The core autonomous browser agent that:
1. OBSERVES the current page
2. THINKS about what to do next
3. ACTS by executing browser commands

Memory system:
- SessionMemory: Short-term (RAM) - what happened this run
- PersistentMemory: Long-term (SQLite) - what happened across all runs
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin, quote as url_quote

from blackreach.browser import Hand
from blackreach.detection import SiteDetector
from blackreach.observer import Eyes  # Deprecated: replaced by dom_walker, kept for debug_html()
from blackreach.dom_walker import walk_dom, format_elements as format_dom_elements, format_text_summary
from blackreach.llm import LLM, LLMConfig
from blackreach.stealth import StealthConfig
from blackreach.resilience import RetryConfig
from blackreach.memory import SessionMemory, PersistentMemory
from blackreach.logging import SessionLogger
from blackreach.exceptions import (
    InvalidActionArgsError, UnknownActionError, SessionNotFoundError,
    BrowserError, NavigationError, DownloadError, LLMError, NetworkError,
)
from blackreach.knowledge import reason_about_goal, get_working_url, get_all_urls_for_source, find_best_sources
from blackreach.action_tracker import ActionTracker
from blackreach.stuck_detector import StuckDetector, RecoveryStrategy, compute_content_hash
from blackreach.error_recovery import ErrorRecovery
from blackreach.source_manager import get_source_manager
from blackreach.goal_engine import GoalDecomposition, get_goal_engine
from blackreach.nav_context import PageValue, get_nav_context
from blackreach.site_handlers import get_site_hints
from blackreach.search_intel import get_search_intel
from blackreach.content_verify import VerificationStatus, get_verifier
from blackreach.retry_strategy import get_retry_manager
from blackreach.timeout_manager import get_timeout_manager
from blackreach.rate_limiter import get_rate_limiter
from blackreach.session_manager import get_session_manager

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Timing constants (in seconds)
STEP_PAUSE_SECONDS = 0.5          # Pause between agent steps
CHALLENGE_WAIT_SECONDS = 15       # Max wait for challenge page resolution
RENDER_WAIT_SECONDS = 3           # Wait for page render
SCROLL_WAIT_SECONDS = 2           # Wait after scrolling
EXPANSION_WAIT_SECONDS = 0.8      # Wait after clicking expansion buttons
DYNAMIC_CONTENT_TIMEOUT_MS = 10000  # Timeout for dynamic content loading

# File validation thresholds (in bytes)
MIN_FULL_IMAGE_SIZE = 200000      # 200KB - thumbnails are usually smaller
MIN_EBOOK_SIZE = 50000            # 50KB - real ebooks are at least this size

# URL tracking limits
MAX_RECENT_URLS = 10              # Number of recent URLs to track for stuck detection

# Precompiled regex patterns for performance
RE_URL = re.compile(r'https?://\S+')
RE_DOMAIN = re.compile(r'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}\b')
RE_JSON_BLOCK = re.compile(r'```json\s*')
RE_CODE_BLOCK = re.compile(r'```\s*')
RE_NUMBER = re.compile(r'\b(\d+)\b')
RE_QUOTED_TEXT = re.compile(r"['\"]([^'\"]+)['\"]")
RE_ARXIV_ID = re.compile(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)')
RE_CLICK_PATTERN = re.compile(
    r"click(?:\s+(?:the|on|a))?\s+['\"]?(\w+(?:\s+\w+){0,3})['\"]?\s*(?:button|link|tab)?",
    re.IGNORECASE
)
RE_SLOW_DOWNLOAD = re.compile(r'(slow\s+download)', re.IGNORECASE)
RE_FAST_DOWNLOAD = re.compile(r'(fast\s+download)', re.IGNORECASE)
RE_SLOW_PARTNER = re.compile(r'(slow\s+partner\s+server)', re.IGNORECASE)
RE_FAST_PARTNER = re.compile(r'(fast\s+partner\s+server)', re.IGNORECASE)


@dataclass
class AgentCallbacks:
    """Callbacks for agent progress updates."""
    on_step: Optional[callable] = None      # (step, max_steps, phase, detail)
    on_action: Optional[callable] = None    # (action, args)
    on_observe: Optional[callable] = None   # (observation)
    on_think: Optional[callable] = None     # (thought)
    on_error: Optional[callable] = None     # (error)
    on_complete: Optional[callable] = None  # (success, result)
    on_status: Optional[callable] = None    # (message) - for status updates


@dataclass
class AgentConfig:
    """Agent configuration."""
    max_steps: int = 50
    headless: bool = False
    download_dir: Path = field(default_factory=lambda: Path("./downloads"))
    start_url: str = "https://www.google.com"  # Google is more flexible for searches
    memory_db: Path = field(default_factory=lambda: Path("./memory.db"))
    browser_type: str = "chromium"  # chromium, firefox, or webkit


class Agent:
    """
    Blackreach Autonomous Browser Agent.

    Uses ReAct pattern: Observe -> Think -> Act

    Memory:
        session_memory: Short-term (current run only)
        persistent_memory: Long-term (SQLite, survives restarts)
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        agent_config: Optional[AgentConfig] = None,
        callbacks: Optional[AgentCallbacks] = None,
    ):
        self.llm = LLM(llm_config)
        self.config = agent_config or AgentConfig()
        self.callbacks = callbacks or AgentCallbacks()

        # Dual memory system
        self.session_memory = SessionMemory()  # RAM - dies when program ends
        self.persistent_memory = PersistentMemory(self.config.memory_db)  # SQLite - survives forever
        self.session_id: Optional[int] = None  # Track current session in DB

        # Browser, observer, and detector (reuse instances for performance)
        self.hand: Optional[Hand] = None
        self.eyes = Eyes()
        self.detector = SiteDetector()

        # Action tracking - learns from action outcomes
        self.action_tracker = ActionTracker(self.persistent_memory)

        # Stuck detection - identifies when agent is in a loop
        self.stuck_detector = StuckDetector()

        # Error recovery - handles errors gracefully
        self.error_recovery = ErrorRecovery()

        # Source management - handles multi-source failover
        self.source_manager = get_source_manager()

        # Goal decomposition engine
        self.goal_engine = get_goal_engine()
        self._current_decomposition: Optional[GoalDecomposition] = None
        self._current_subtask_id: Optional[str] = None

        # Context-aware navigation
        self.nav_context = get_nav_context(self.persistent_memory)

        # Search intelligence
        self.search_intel = get_search_intel(self.persistent_memory)
        self._current_search_session = None

        # Content verification
        self.content_verifier = get_verifier()

        # Retry strategies
        self.retry_manager = get_retry_manager()

        # Timeout management
        self.timeout_manager = get_timeout_manager()

        # Rate limiting
        self.rate_limiter = get_rate_limiter()

        # Session management (v2.8.0+)
        self.session_manager = get_session_manager(self.config.memory_db)

        # Load prompts
        self.prompts = self._load_prompts()

        # Cache for parsed page data (avoids re-parsing between observe and act)
        self._page_cache = {
            "url": None,
            "html": None,
            "parsed": None,
            "elements": None,
        }

        # Stuck detection - track recent URLs to detect when we're not making progress
        self._recent_urls = []
        self._max_stuck_count = 3  # How many times on same page before "stuck"
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._stuck_counter = 0  # Track how many times stuck detection triggered
        self._last_action = None  # Track repeated actions
        self._last_failed_action = None  # Track last failed action for stuck detection
        self._repeated_failure_count = 0  # Count how many times same action failed

        # Track clicked elements to avoid re-clicking expansion buttons
        self._clicked_selectors = set()  # Selectors clicked on current page
        self._clicked_page_url = None  # URL when selectors were clicked (reset on navigate)
        self._selector_click_counts = {}  # Count clicks per selector on current page
        self._max_same_selector_clicks = 2  # Max times to click same selector before skipping
        self._expansion_buttons = {  # Buttons that expand content (need to skip on re-click)
            'button:has-text("Downloads")',
            'a:has-text("Downloads")',
            'button:has-text("Download")',  # Might be expansion on Anna's Archive
            'a:has-text("Download")',
            'button:has-text("Show")',
            'button:has-text("Expand")',
            'button:has-text("More")',
            '[class*="download"] button',
            '[class*="download"] a',
        }

        # Action history for LLM context (last N actions + results)
        self._action_history = []
        self._max_action_history = 5

        # Session resume support
        self._paused = False
        self._current_step = 0
        self._current_goal = ""

        # Refusal handling
        self._refusal_count = 0
        self._max_refusals = 3  # After this many, try alternate search

        # Download retry tracking
        self._failed_download_urls = set()  # URLs that failed to download

        # Challenge/DDoS protection tracking
        self._consecutive_challenges = 0  # Track persistent challenge pages
        self._failed_urls = set()  # Specific URLs where challenges didn't resolve
        self._current_source = None  # Track current content source for failover

        # Callback error rate limiting
        self._callback_errors: Dict[str, int] = {}  # Track errors per event type
        self._max_callback_errors_per_event = 3  # Stop logging after this many

    def _emit(self, event: str, *args, **kwargs) -> None:
        """Emit a callback event if handler is set.

        Silently catches and logs callback errors to prevent user-provided
        callbacks from breaking the agent. Rate-limits error logging to
        avoid spam.
        """
        handler = getattr(self.callbacks, event, None)
        if handler:
            try:
                handler(*args, **kwargs)
            except Exception as e:  # User callback - can raise anything
                # Rate-limit callback error logging
                error_count = self._callback_errors.get(event, 0) + 1
                self._callback_errors[event] = error_count

                if error_count <= self._max_callback_errors_per_event:
                    logger.warning("Callback error in %s: %s", event, e)
                    if error_count == self._max_callback_errors_per_event:
                        logger.warning("Callback error in %s: suppressing further errors", event)

    def _load_prompts(self) -> Dict[str, str]:
        """Load ReAct prompts from files."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        prompts = {}

        # Load unified react prompt (single LLM call per step)
        react_file = prompts_dir / "react.txt"
        if react_file.exists():
            prompts["react"] = react_file.read_text()
        else:
            # Fallback prompt
            prompts["react"] = "[REACT prompt not found]"

        # Keep old prompts for backward compatibility
        for name in ["observe", "think", "act"]:
            prompt_file = prompts_dir / f"{name}.txt"
            if prompt_file.exists():
                prompts[name] = prompt_file.read_text()

        return prompts

    def _record_visit(self, url: str, title: str = "", success: bool = True) -> None:
        """Record a visit to both memory systems."""
        self.session_memory.add_visit(url)
        self.persistent_memory.add_visit(url, title=title, goal="", success=success)

    def _record_download(self, filename: str, url: str = "") -> None:
        """Record a download to both memory systems and source manager."""
        domain = urlparse(url).netloc if url else ""
        self.session_memory.add_download(filename, url)
        self.persistent_memory.add_download(
            filename=filename,
            url=url,
            source_site=domain
        )
        if domain:
            self.source_manager.record_success(domain)
            self.error_recovery.record_success()

    def _record_failure(self, url: str, action: str, error: str) -> None:
        """Record a failure to both memory systems and source manager."""
        self.session_memory.add_failure(error)
        self.persistent_memory.add_failure(url, action, error)
        domain = urlparse(url).netloc if url else ""
        if domain:
            self.source_manager.record_failure(domain, error)

    def _get_domain(self, url: str = None) -> str:
        """Extract domain from URL or current page."""
        if url:
            return urlparse(url).netloc
        if self.hand and self.hand.is_awake:
            try:
                return urlparse(self.hand.get_url()).netloc
            except (BrowserError, OSError):  # Best-effort URL extraction
                return ""
        return ""

    def _create_browser(self) -> Hand:
        """
        Create and configure a new browser instance.

        Returns:
            Configured Hand instance (not yet started).
        """
        return Hand(
            headless=self.config.headless,
            stealth_config=StealthConfig(),
            retry_config=RetryConfig(),
            download_dir=self.config.download_dir,
            browser_type=self.config.browser_type
        )

    def ensure_browser(self) -> bool:
        """
        Ensure browser is ready for use, creating/starting it if needed.

        This method is idempotent - safe to call multiple times.

        Returns:
            True if browser is ready, False if failed to start.
        """
        if self.hand is None:
            self.hand = self._create_browser()

        return self.hand.ensure_awake()

    def restart_browser(self, navigate_to: str = None) -> bool:
        """
        Restart the browser, optionally navigating to a URL after restart.

        Args:
            navigate_to: URL to navigate to after restart (optional).

        Returns:
            True if restart successful.
        """
        if self.hand is None:
            self.hand = self._create_browser()

        success = self.hand.restart()

        if success and navigate_to:
            try:
                self.hand.goto(navigate_to)
            except (NavigationError, BrowserError, OSError) as e:
                logger.debug("Best-effort post-restart navigation failed: %s", e)

        return success

    def check_browser_health(self) -> bool:
        """
        Check if browser is healthy and responsive.

        Returns:
            True if browser is healthy, False otherwise.
        """
        if self.hand is None:
            return False
        return self.hand.is_healthy()

    def _is_stuck(self) -> bool:
        """Check if agent is stuck on the same page."""
        if len(self._recent_urls) < self._max_stuck_count:
            return False
        # Check if the last N URLs are the same
        last_urls = self._recent_urls[-self._max_stuck_count:]
        return len(set(last_urls)) == 1

    def _track_url(self, url: str):
        """Track current URL for stuck detection."""
        self._recent_urls.append(url)
        # Keep only recent history
        if len(self._recent_urls) > MAX_RECENT_URLS:
            self._recent_urls.pop(0)

    def _format_action_history(self) -> str:
        """Format recent action history for inclusion in the LLM prompt."""
        if not self._action_history:
            return ""
        return "\n".join(self._action_history)

    def _get_stuck_hint(self) -> str:
        """Get a hint for the LLM when stuck or repeating failed actions."""
        hints = []

        # Check if stuck on same page
        if self._is_stuck():
            start_url = self.config.start_url
            current_url = self._recent_urls[-1] if self._recent_urls else ""

            # Use centralized site handlers for stuck hints
            site_hint = get_site_hints(current_url, "", self._current_goal)
            if site_hint:
                hints.append(f"STUCK! {site_hint}")
            else:
                hints.append(
                    f"STUCK! You've been on the same page too long. Try:"
                    f"\n- Go back to: {start_url}"
                    f"\n- Or navigate to a DIFFERENT link/page"
                )

        # Check for repeated failures
        if self._repeated_failure_count >= 2:
            hints.append(
                f"ACTION FAILING! The same action has failed {self._repeated_failure_count} times."
                f"\n- Try a COMPLETELY DIFFERENT approach"
                f"\n- Look for other buttons, links, or selectors"
                f"\n- If clicking fails, try using text-based click with button text"
            )

        # Check for consecutive failures
        if self._consecutive_failures >= 2:
            hints.append(
                f"MULTIPLE FAILURES! {self._consecutive_failures} actions failed in a row."
                f"\n- The page might have different structure than expected"
                f"\n- Try scrolling to see more content"
                f"\n- Or navigate to a different page/source"
            )

        if not hints:
            return ""

        return "\n\n" + "\n\n".join(hints) + "\n\nDO NOT repeat the same failed action!"

    def pause(self) -> None:
        """Request the agent to pause at next opportunity."""
        self._paused = True

    def save_state(self) -> None:
        """Save current session state for later resume."""
        if not self.session_id or not self._current_goal:
            return

        current_url = self.hand.get_url() if self.hand else ""
        self.persistent_memory.save_session_state(
            session_id=self.session_id,
            goal=self._current_goal,
            current_step=self._current_step,
            current_url=current_url,
            session_memory=self.session_memory,
            start_url=self.config.start_url,
            max_steps=self.config.max_steps,
            status="paused"
        )

    def resume(self, session_id: int, quiet: bool = False) -> Dict[str, Any]:
        """
        Resume a previously paused session.

        Args:
            session_id: The session ID to resume
            quiet: If True, suppress print statements

        Returns:
            Dict with results
        """
        state = self.persistent_memory.load_session_state(session_id)
        if not state:
            raise SessionNotFoundError(str(session_id))

        # Restore state
        self.session_id = state["session_id"]
        self._current_goal = state["goal"]
        self._current_step = state["current_step"]
        self.session_memory = state["session_memory"]
        self.config.start_url = state["start_url"]
        self.config.max_steps = state["max_steps"]

        def log(msg: str):
            if not quiet:
                print(msg)
            self._emit("on_status", msg)

        log(f"\n{'='*60}")
        log(f"RESUMING SESSION #{session_id}")
        log(f"GOAL: {self._current_goal}")
        log(f"From step: {self._current_step}")
        log(f"{'='*60}\n")

        # Start or ensure browser is ready (auto-starts if not initialized)
        log("Starting browser...")
        if not self.ensure_browser():
            log("ERROR: Failed to start browser")
            return {
                "goal": self._current_goal,
                "success": False,
                "paused": False,
                "downloads": [],
                "pages_visited": 0,
                "steps_taken": 0,
                "failures": 1,
                "session_id": self.session_id,
                "error": "Failed to start browser"
            }

        if state["current_url"]:
            log(f"Navigating to saved URL: {state['current_url']}")
            self.hand.goto(state["current_url"])
        else:
            log(f"Navigating to start URL: {self.config.start_url}")
            self.hand.goto(self.config.start_url)

        # Continue running from saved step
        return self._run_loop(self._current_goal, start_step=self._current_step + 1, quiet=quiet)

    def run(self, goal: str, quiet: bool = False) -> Dict[str, Any]:
        """
        Run the agent to accomplish a goal.

        Args:
            goal: Natural language description of what to accomplish
            quiet: If True, suppress print statements (use callbacks instead)

        Returns:
            Dict with results: files downloaded, pages visited, etc.
        """
        def log(msg: str):
            if not quiet:
                print(msg)
            self._emit("on_status", msg)

        self._current_goal = goal
        self._paused = False

        log(f"\n{'='*60}")
        log(f"GOAL: {goal}")
        log(f"{'='*60}\n")

        # Show memory stats from previous runs
        stats = self.persistent_memory.get_stats()
        if stats["total_sessions"] > 0:
            log(f"Memory: {stats['total_downloads']} downloads, "
                f"{stats['total_visits']} visits from {stats['total_sessions']} sessions")

        self.session_id = self.persistent_memory.start_session(goal)
        log(f"Session #{self.session_id} started\n")

        self._current_decomposition = self.goal_engine.decompose(goal)
        if self._current_decomposition.subtasks:
            log(f"Goal decomposed into {len(self._current_decomposition.subtasks)} subtasks:")
            for i, st in enumerate(self._current_decomposition.subtasks[:5], 1):
                optional = " (optional)" if st.optional else ""
                log(f"  {i}. {st.description}{optional}")
            if len(self._current_decomposition.subtasks) > 5:
                log(f"  ... and {len(self._current_decomposition.subtasks) - 5} more")
            log("")

        self._logger = SessionLogger(self.session_id, goal)
        self.config.download_dir.mkdir(parents=True, exist_ok=True)

        # Start or ensure browser is ready (auto-starts if not initialized)
        log("Starting browser...")
        if not self.ensure_browser():
            log("ERROR: Failed to start browser")
            return {
                "goal": goal,
                "success": False,
                "paused": False,
                "downloads": [],
                "pages_visited": 0,
                "steps_taken": 0,
                "failures": 1,
                "session_id": self.session_id,
                "error": "Failed to start browser"
            }

        # Use deep reasoning to determine the best starting point
        start_url, reasoning, search_query = self._get_smart_start_url(goal, quiet=quiet)

        # Store reasoning for later use in prompts
        self._goal_reasoning = {
            "start_url": start_url,
            "reasoning": reasoning,
            "search_query": search_query
        }

        log(f"Navigating to: {start_url}")
        self.hand.goto(start_url)
        self._record_visit(start_url)

        return self._run_loop(goal, start_step=1, quiet=quiet)

    def _get_smart_start_url(self, goal: str, quiet: bool = False) -> tuple:
        """
        Use deep reasoning to choose the best starting URL based on the goal.

        Returns (url, reasoning, search_query) tuple.
        """
        def log(msg: str):
            if not quiet:
                print(msg)

        # If user specified a URL in the goal, use that directly
        url_match = RE_URL.search(goal)
        if url_match:
            url = url_match.group()
            return (url, f"Using URL specified in goal", "")

        # Also check for bare domain names (e.g., "google.com", "example.org")
        domain_match = RE_DOMAIN.search(goal)
        if domain_match:
            domain = domain_match.group()
            # Common domains that users might mention
            if any(tld in domain for tld in ['.com', '.org', '.net', '.edu', '.gov', '.io', '.co']):
                url = f"https://{domain}"
                return (url, f"Using domain specified in goal", "")

        # Use the knowledge base to reason about the best source
        result = reason_about_goal(goal)

        # Use search intelligence for optimized query formulation
        content_type = result['content_types'][0] if result['content_types'] else ""
        search_query = self.search_intel.create_search(goal, content_type)

        # Start a search session for learning
        self._current_search_session = self.search_intel.start_session(search_query)

        # Log the reasoning
        log(f"\n🧠 REASONING:")
        log(f"   Content type: {', '.join(result['content_types'])}")
        log(f"   Subject: \"{result['subject']}\"")
        log(f"   Optimized query: \"{search_query.query}\"")
        log(f"   Decision: {result['reasoning']}")

        if result.get("alternate_sources"):
            alts = [s.name for s in result["alternate_sources"][:2]]
            log(f"   Backups: {', '.join(alts)}")

        # Check if primary URL is reachable, try mirrors if not
        start_url = result["start_url"]
        best_source = result.get("best_source")

        if best_source and best_source.mirrors:
            log(f"   Checking {best_source.name} availability...")
            working_url = get_working_url(best_source, timeout=3.0)
            if working_url:
                if working_url != best_source.url:
                    log(f"   Using mirror: {working_url}")
                start_url = working_url
            else:
                log(f"   ⚠ {best_source.name} unavailable, trying alternates...")
                # Try alternate sources
                for alt_source in result.get("alternate_sources", []):
                    alt_url = get_working_url(alt_source, timeout=3.0) if alt_source.mirrors else alt_source.url
                    if alt_url:
                        log(f"   Using {alt_source.name}: {alt_url}")
                        start_url = alt_url
                        break
                else:
                    # Fallback to Google search
                    encoded = url_quote(result["search_query"])
                    start_url = f"https://www.google.com/search?q={encoded}"
                    log(f"   Falling back to Google search")

        return (
            start_url,
            result["reasoning"],
            result["search_query"]
        )

    def _run_loop(self, goal: str, start_step: int = 1, quiet: bool = False) -> Dict[str, Any]:
        """
        Main ReAct loop - can be called from run() or resume().

        Args:
            goal: The goal to accomplish
            start_step: Step number to start from (for resume)
            quiet: Suppress output

        Returns:
            Dict with results
        """
        def log(msg: str):
            if not quiet:
                print(msg)
            self._emit("on_status", msg)

        success = False
        paused = False

        try:
            # Main ReAct loop
            for step in range(start_step, self.config.max_steps + 1):
                self._current_step = step

                # Check for pause request
                if self._paused:
                    log(f"\n⏸ PAUSED at step {step}")
                    self.save_state()
                    paused = True
                    break

                log(f"\n[Step {step}/{self.config.max_steps}]")
                self._emit("on_step", step, self.config.max_steps, "step", "")

                # Run one iteration
                result = self._step(goal, step, quiet=quiet)

                if result.get("done"):
                    log(f"\n✓ COMPLETE: {result.get('reason', 'Goal achieved')}")
                    success = True
                    break

                time.sleep(STEP_PAUSE_SECONDS)

            else:
                log(f"\n⚠ Reached max steps ({self.config.max_steps})")

        except KeyboardInterrupt:
            log(f"\n⏸ INTERRUPTED at step {self._current_step}")
            # IMPORTANT: Immediately release any stuck keyboard keys
            if self.hand:
                self.hand._release_all_keys()
            # Save state for potential resume
            self.persistent_memory.save_session_state(
                session_id=self.session_id,
                goal=goal,
                current_step=self._current_step,
                current_url=self.hand.get_url() if self.hand else "",
                session_memory=self.session_memory,
                start_url=self.config.start_url,
                max_steps=self.config.max_steps,
                status="interrupted"
            )
            log(f"Session state saved. Resume with: blackreach run --resume {self.session_id}")
            paused = True

        finally:
            # Clean up
            log("\nClosing browser...")
            if self.hand:
                self.hand.sleep()

            # End or update the session in persistent memory
            if not paused:
                self.persistent_memory.end_session(
                    self.session_id,
                    steps=len(self.session_memory.actions_taken),
                    downloads=len(self.session_memory.downloaded_files),
                    success=success
                )
                # Clean up session state if completed successfully
                if success:
                    self.persistent_memory.delete_session_state(self.session_id)
            log(f"Session #{self.session_id} ended (success={success}, paused={paused})")

            # Log session end
            if hasattr(self, '_logger'):
                self._logger.session_end(
                    success=success,
                    steps=len(self.session_memory.actions_taken),
                    downloads=len(self.session_memory.downloaded_files),
                    failures=len(self.session_memory.failures)
                )

        result = {
            "goal": goal,
            "success": success,
            "paused": paused,
            "downloads": self.session_memory.downloaded_files,
            "pages_visited": len(self.session_memory.visited_urls),
            "steps_taken": len(self.session_memory.actions_taken),
            "failures": len(self.session_memory.failures),
            "session_id": self.session_id,
        }

        self._emit("on_complete", success, result)
        return result

    def _step(self, goal: str, step_num: int, quiet: bool = False) -> Dict[str, Any]:
        """Execute one ReAct iteration with a SINGLE LLM call."""

        def log(msg: str, end="\n"):
            if not quiet:
                print(msg, end=end, flush=True)

        # Health check: ensure browser is healthy before proceeding
        if not self.check_browser_health():
            log("  [Browser unhealthy - attempting restart...]")
            if not self.restart_browser():
                log("  [FATAL: Browser restart failed]")
                return {"done": False, "error": "Browser restart failed", "fatal": True}
            log("  [Browser restarted successfully]")

            # Try to navigate back to where we were
            if self._recent_urls:
                last_url = self._recent_urls[-1]
                try:
                    self.hand.goto(last_url, wait_for_content=False)
                except (NavigationError, BrowserError, OSError) as e:
                    logger.debug("Best-effort navigation after restart failed: %s", e)

        # Track current URL for stuck detection
        current_url = self.hand.get_url()
        self._track_url(current_url)

        if hasattr(self, '_logger'):
            self._logger.step_start(step_num)

        # Get page state with content verification
        self._emit("on_step", step_num, self.config.max_steps, "observe", "Analyzing page...")

        # Get HTML with content verification - this waits for JS to render
        html = self.hand.get_html(ensure_content=True)
        url = self.hand.get_url()
        title = self.hand.get_title()

        content_hash = compute_content_hash(html)
        download_count = len(self.session_memory.downloaded_files)
        self.stuck_detector.observe(
            url=url,
            content_hash=content_hash,
            action=self._last_action or "observe",
            action_target="",
            download_count=download_count,
            step_number=step_num
        )

        stuck_state = self.stuck_detector.check()
        if stuck_state.is_stuck:
            strategy, explanation = self.stuck_detector.suggest_strategy()
            log(f"  [STUCK DETECTED: {stuck_state.reason.value}]")
            log(f"  [STRATEGY: {strategy.value} - {explanation}]")

            # Apply recovery strategy
            if strategy == RecoveryStrategy.GO_BACK:
                backtrack_url = self.stuck_detector.get_backtrack_url()
                if backtrack_url:
                    log(f"  [BACKTRACKING to: {backtrack_url[:50]}]")
                    self.hand.goto(backtrack_url)
                    self.stuck_detector.record_recovery_attempt(strategy)
                    self.stuck_detector.soft_reset()
                    # Re-fetch page state
                    html = self.hand.get_html()
                    url = self.hand.get_url()
                    title = self.hand.get_title()
                else:
                    self.hand.back()
                    self.stuck_detector.record_recovery_attempt(strategy)

            elif strategy == RecoveryStrategy.TRY_ALTERNATE_SOURCE:
                # Find alternate source - handled by existing failover logic below
                self.stuck_detector.record_recovery_attempt(strategy)
                self._consecutive_challenges = 2  # Trigger failover logic

            elif strategy == RecoveryStrategy.SCROLL_AND_EXPLORE:
                log(f"  [SCROLLING to find more content]")
                self.hand.scroll("down", 800)
                time.sleep(1)
                self.stuck_detector.record_recovery_attempt(strategy)
                self.stuck_detector.soft_reset()
                html = self.hand.get_html()

        # Check for challenge/interstitial pages (reuse instance for performance)
        challenge = self.detector.detect_challenge(html)
        if challenge.detected:
            log(f"  [Challenge page detected: {challenge.details} - waiting...]")
            challenge_resolved = False
            for attempt in range(CHALLENGE_WAIT_SECONDS):
                time.sleep(1)
                html = self.hand.get_html()
                if not self.detector.detect_challenge(html).detected:
                    log(f"  [Challenge resolved after {attempt+1}s]")
                    challenge_resolved = True
                    self._consecutive_challenges = 0  # Reset counter
                    break

            if not challenge_resolved:
                self._consecutive_challenges += 1
                current_url = self.hand.get_url()
                # Extract base URL (scheme + domain) for comparison
                parsed = urlparse(current_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                self._failed_urls.add(base_url)  # Track base URL (domain) not full path
                log(f"  [Challenge NOT resolved - consecutive failures: {self._consecutive_challenges}]")

                # After 2 consecutive unresolved challenges, try alternate URL/source
                if self._consecutive_challenges >= 2:
                    log(f"  [FAILOVER: {base_url} blocked by challenge protection]")

                    # Record failure in source manager
                    failed_domain = urlparse(base_url).netloc
                    self.source_manager.record_failure(failed_domain, "challenge_blocked")

                    # Use source manager for intelligent failover
                    goal = self._current_goal
                    if goal:
                        # Try getting a failover from source manager first
                        failover = self.source_manager.get_failover(failed_domain, content_type="ebook")
                        if failover:
                            source, next_url = failover
                            log(f"  [SMART FAILOVER: {source.name} at {next_url}]")
                            self.hand.goto(next_url)
                            self._consecutive_challenges = 0
                            html = self.hand.get_html()
                        else:
                            # Fall back to original logic
                            sources = find_best_sources(goal, max_sources=8)
                            found_working = False
                            for source in sources:
                                # Get all URLs for this source (primary + mirrors)
                                all_urls = get_all_urls_for_source(source)
                                # Filter out URLs we've already tried - compare base URLs
                                available_urls = []
                                for u in all_urls:
                                    u_parsed = urlparse(u)
                                    u_base = f"{u_parsed.scheme}://{u_parsed.netloc}"
                                    if u_base not in self._failed_urls:
                                        available_urls.append(u)

                                if not available_urls:
                                    continue  # All URLs for this source have failed

                                # Try the first available URL
                                next_url = available_urls[0]
                                log(f"  [SWITCHING TO: {source.name} at {next_url}]")
                                self.hand.goto(next_url)
                                self._consecutive_challenges = 0
                                # Re-fetch page state
                                html = self.hand.get_html()
                                found_working = True
                                break

                            if not found_working:
                                log(f"  [WARNING: All known sources blocked - continuing with current page]")

            url = self.hand.get_url()
            title = self.hand.get_title()
        else:
            # Reset challenge counter when page loads normally
            self._consecutive_challenges = 0

        # Check for download landing pages (only for download-oriented goals)
        goal_lower_check = goal.lower()
        is_download_goal = any(word in goal_lower_check for word in [
            'download', 'fetch', 'save', 'epub', 'pdf', 'wallpaper',
        ])
        if is_download_goal:
            download_landing = self.detector.detect_download_landing(html, url)
            if download_landing.detected:
                log(f"  [Download landing page detected - look for download button]")

        # Walk the live DOM to get all interactive elements with numeric IDs
        # This replaces the old BeautifulSoup parsing with live browser DOM walking
        context_size = getattr(self.llm.config, 'context_size', 'large')
        dom_result = walk_dom(self.hand.page, context_size=context_size)

        elements = format_dom_elements(dom_result, context_size=context_size)
        text_summary = format_text_summary(dom_result, context_size=context_size)

        # If DOM walker found nothing, try render recovery then re-walk
        if not dom_result.get("elements"):
            debug_info = self.eyes.debug_html(html)
            log(f"  [No elements found - render recovery...]")

            for attempt in range(2):
                if attempt == 0:
                    time.sleep(RENDER_WAIT_SECONDS)
                    self.hand.force_render()
                else:
                    self.hand.refresh()
                    time.sleep(RENDER_WAIT_SECONDS)
                    self.hand._wait_for_dynamic_content(timeout=DYNAMIC_CONTENT_TIMEOUT_MS)

                html = self.hand.get_html()
                dom_result = walk_dom(self.hand.page, context_size=context_size)
                elements = format_dom_elements(dom_result, context_size=context_size)
                text_summary = format_text_summary(dom_result, context_size=context_size)

                if dom_result.get("elements"):
                    log(f"  [Content loaded on attempt {attempt+1}]")
                    break

        # Cache for potential reuse
        self._page_cache["url"] = url
        self._page_cache["html"] = html
        self._page_cache["dom_result"] = dom_result
        self._page_cache["elements"] = elements

        self.nav_context.record_navigation(
            url=url,
            title=title,
            content_preview=text_summary[:200],
            links_found=dom_result.get("total_elements", 0),
            from_action=self._last_action or "initial",
            value=PageValue.NEUTRAL
        )

        # Build extra context
        extra_context = ""

        stuck_hint = self._get_stuck_hint()
        if stuck_hint:
            self._stuck_counter += 1
            extra_context += stuck_hint
            log("  [STUCK DETECTED]")

            # Force reset after being stuck too many times
            if self._stuck_counter >= 5:
                log("  [FORCE RESET - returning to start URL]")
                self.hand.goto(self.config.start_url)
                self._stuck_counter = 0
                self._recent_urls = []
                return {"done": False, "reset": True}
        else:
            self._stuck_counter = 0

        domain = self._get_domain()

        last_failure = self.session_memory.last_failure
        if last_failure:
            extra_context += f"\nLAST ERROR: {last_failure}"

        if self._failed_download_urls:
            extra_context += f"\nFAILED DOWNLOADS ({len(self._failed_download_urls)} URLs) - try different mirrors or sources"

        downloaded = self.session_memory.downloaded_files
        if downloaded:
            filenames = [Path(f).name for f in downloaded[-5:]]
            extra_context += f"\nALREADY DOWNLOADED: {filenames}"

        # Format action history for context
        action_history = self._format_action_history()

        # Build prompt with new format
        prompt = self.prompts["react"].format(
            goal=goal,
            url=url,
            title=title,
            elements=elements,
            text_summary=text_summary,
            download_count=len(self.session_memory.downloaded_files),
            extra_context=extra_context,
            action_history=action_history if action_history else "(none yet)"
        )

        # SINGLE LLM call for think + act
        log("  REACT: ", end="")
        self._emit("on_step", step_num, self.config.max_steps, "think", "Reasoning...")

        # System prompt - autonomous browser agent with element ID system
        system_prompt = """You are an autonomous browser agent. You interact with web pages to accomplish goals.

## How You See Pages
You receive numbered interactive elements on the current page. Reference them by [N] ID.
You also receive a text summary of visible page content. READ BOTH CAREFULLY before acting.

## Available Actions
- click: Click element by ID. {"action":"click","element":N}
- type: Type into input. {"action":"type","element":N,"text":"query","submit":true}
- navigate: Go to a known URL directly. {"action":"navigate","args":{"url":"https://..."}}
- download: Download a file by URL. {"action":"download","args":{"url":"https://..."}}
- scroll: Scroll to reveal more. {"action":"scroll","args":{"direction":"down"}}
- back: Go to previous page. {"action":"back"}
- done: Task complete. {"action":"done","args":{"reason":"what was accomplished"}}

## When to Navigate vs Click
- Use "navigate" when you know the exact URL (e.g., from a link's href or a known site).
- Use "click" when interacting with a page element (buttons, links, tabs) by its [N] ID.

## Examples
Example 1 - Searching: {"thought":"I need to search for machine learning papers","action":"type","element":3,"text":"machine learning papers","submit":true}
Example 2 - Clicking a link: {"thought":"Element [15] links to the download page I need","action":"click","element":15}
Example 3 - Task complete: {"thought":"I found and downloaded 3 papers as requested","action":"done","args":{"reason":"Downloaded 3 papers from arxiv"}}

## Rules
- READ the page content and element list CAREFULLY before deciding your action.
- Output ONLY valid JSON. No markdown, no explanation, no extra text.
- Always include a "thought" field explaining your reasoning.
- Check RECENT ACTIONS to avoid repeating failed actions. Try a different approach.
- If you already have the answer in the page content, say "done" immediately.
- If you found MOST of the requested information but can't find the rest after several tries, report what you found rather than looping forever.
- If stuck, try a different approach (navigate to a specific section, use search, go back)."""

        try:
            response = self.llm.generate(
                system_prompt,
                prompt
            )
        except (LLMError, NetworkError, OSError) as e:
            log(f"LLM Error: {e}")
            self._record_failure(url, "llm", str(e))
            return {"done": False, "error": f"LLM call failed: {e}"}

        if not response or not response.strip():
            log("Empty response from LLM")
            self._record_failure(url, "llm", "Empty response")
            return {"done": False, "error": "Empty LLM response"}

        # Parse the response
        thought = ""
        action = None
        args = {}

        # CRITICAL: Detect refusal language in the raw response
        # LLMs often refuse by saying things like "I cannot assist", "policy prohibits", etc.
        refusal_phrases = [
            "cannot assist", "cannot help", "can't assist", "can't help",
            "policy prohibits", "policies prohibit", "violates policy",
            "cannot proceed", "unable to assist", "unable to help",
            "illegal", "piracy", "pirated", "copyright infringement",
            "i cannot", "i can't", "not able to", "against policy",
            "refuse to", "declining to", "will not help",
        ]
        response_lower = response.lower()
        is_refusal = any(phrase in response_lower for phrase in refusal_phrases)

        # Try to extract JSON from response - handle nested braces
        response_clean = response.strip()

        # Strip markdown code blocks (common with reasoning models)
        if "```json" in response_clean:
            response_clean = RE_JSON_BLOCK.sub('', response_clean)
            response_clean = RE_CODE_BLOCK.sub('', response_clean)
        elif "```" in response_clean:
            response_clean = RE_CODE_BLOCK.sub('', response_clean)

        # Find all JSON-like structures and try to parse
        data = {}
        try:
            # First try to parse the whole response as JSON
            data = json.loads(response_clean)
        except json.JSONDecodeError:
            # Try to find JSON object in response (handle nested braces)
            # Look for patterns like {"action": ...}
            json_patterns = [
                r'\{[^{}]*"action"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # With action key
                r'\{[^{}]*"done"[^{}]*\}',  # Done pattern
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Any JSON object
            ]
            for pattern in json_patterns:
                json_match = re.search(pattern, response_clean)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        break
                    except json.JSONDecodeError:
                        continue

        if not data:
            log(f"No valid JSON found in response: {response_clean[:200]}...")
            self._record_failure(url, "parse", "No JSON in LLM response")
            return {"done": False, "error": "No valid JSON in response"}

        # Extract fields with VERY flexible handling for inconsistent LLM outputs
        thought = data.get("thought", data.get("reason", ""))

        # Handle various action formats LLMs produce
        action = None
        args = {}
        element_id = None

        # Extract element ID from top-level (our new format)
        if "element" in data:
            try:
                element_id = int(data["element"])
            except (ValueError, TypeError):
                pass

        # Format 0: {"actions": [{...}, {...}]} - array of actions, take first one
        actions_array = data.get("actions")
        if isinstance(actions_array, list) and len(actions_array) > 0:
            first_action = actions_array[0]
            if isinstance(first_action, dict):
                data = first_action  # Use first action as the data to parse
                if element_id is None and "element" in first_action:
                    try:
                        element_id = int(first_action["element"])
                    except (ValueError, TypeError):
                        pass

        # Format 1: {"action": "type", "args": {...}} or {"action": "click", "element": 5}
        action_val = data.get("action")
        if isinstance(action_val, str):
            action = action_val
            args = data.get("args", {})
            # Element ID can also be in args
            if element_id is None and "element" in args:
                try:
                    element_id = int(args["element"])
                except (ValueError, TypeError):
                    pass
        elif isinstance(action_val, dict):
            # Format 2: {"action": {"type": "click", "args": {...}}}
            action = action_val.get("type", action_val.get("action", ""))
            args = action_val.get("args", {})

        # Format 3: {"done": true} or {"status": "done"}
        if not action:
            if data.get("done") == True or data.get("status") == "done":
                action = "done"
                args = {"reason": data.get("reason", "complete")}

        # Format 4: {"type": "navigate", "url": "..."}
        if not action and "type" in data:
            action = data.get("type")
            args = {k: v for k, v in data.items() if k not in ("type", "thought", "action", "element")}

        # Format 5: Just look for common action words in the data
        if not action:
            for key in data:
                if key in ("navigate", "click", "type", "download", "scroll", "done"):
                    action = key
                    val = data[key]
                    args = val if isinstance(val, dict) else {"value": val}
                    break

        # Also extract text/submit from top-level data (LLMs sometimes put these at root)
        if "text" in data and "text" not in args:
            args["text"] = data["text"]
        if "submit" in data and "submit" not in args:
            args["submit"] = data["submit"]

        # Inject element_id into args for _execute_action
        if element_id is not None:
            args["_element_id"] = element_id

        # CRITICAL: Handle refusal - don't let LLM quit just because it doesn't want to help
        if is_refusal:
            self._refusal_count += 1
            log(f"  [REFUSAL #{self._refusal_count} DETECTED - forcing continue]")
            download_count = len(self.session_memory.downloaded_files)
            goal_lower = goal.lower()

            # Check if goal requires downloads
            needs_download = any(word in goal_lower for word in [
                'download', 'fetch', 'save', 'epub', 'pdf',
                'wallpaper', 'picture', 'photo',
            ])

            # If we need downloads and have none, override whatever action the LLM chose
            if needs_download and download_count == 0:
                self._record_failure(url, "llm_refusal", f"LLM refused: {thought[:100] if thought else response[:100]}")

                # Use knowledge base to get alternate sources
                result = reason_about_goal(goal)
                search_query = result["search_query"]

                if self._refusal_count <= self._max_refusals:
                    # Use the knowledge base's recommended source
                    if result.get("best_source"):
                        search_url = result["start_url"]
                        log(f"  [OVERRIDE: Using {result['best_source'].name} - {search_url}]")
                    else:
                        encoded = url_quote(search_query)
                        search_url = f"https://www.google.com/search?q={encoded}"
                        log(f"  [OVERRIDE: Forcing search - {search_url[:50]}]")
                else:
                    # After many refusals, try alternate sources from knowledge base
                    alt_sources = result.get("alternate_sources", [])
                    if alt_sources:
                        alt = alt_sources[self._refusal_count % len(alt_sources)]
                        search_url = alt.url
                        log(f"  [ALTERNATE: Trying {alt.name} - {search_url}]")
                    else:
                        encoded = url_quote(search_query)
                        search_url = f"https://www.google.com/search?q={encoded}+free+download"
                        log(f"  [FALLBACK SEARCH: {search_url[:50]}]")

                self.hand.goto(search_url)
                self._record_visit(search_url)

                return {"done": False, "override": True, "reason": "LLM refusal overridden"}
        else:
            # Reset refusal counter on successful non-refusal response
            self._refusal_count = 0

        log(f"{thought} -> {action}")
        self._emit("on_think", thought)

        if hasattr(self, '_logger'):
            self._logger.observe(step_num, f"URL: {url}, Title: {title}", url)
            self._logger.think(step_num, thought, stuck=bool(stuck_hint))

        self._record_visit(url, title=title)

        # Handle done action - but validate it first
        if action == "done":
            reason = args.get("reason", thought or "Goal complete")
            download_count = len(self.session_memory.downloaded_files)
            goal_lower = goal.lower()

            # Check if goal requires downloads
            needs_download = any(word in goal_lower for word in [
                'download', 'fetch', 'save', 'epub', 'pdf',
                'wallpaper', 'picture', 'photo',
            ])

            # Don't allow "done" if goal needs downloads but we have 0
            if needs_download and download_count == 0:
                log(f"  [BLOCKED: Goal needs downloads but have 0 - continuing search]")
                self._record_failure(url, "premature_done", f"LLM tried to quit: {reason}")
                # Return a non-done result to force loop to continue
                return {"done": False, "blocked": True, "reason": "Premature done blocked"}
            else:
                if hasattr(self, '_logger'):
                    self._logger.act(step_num, "done", {"reason": reason}, success=True)
                return {"done": True, "reason": reason}

        # Auto-completion check for download goals
        download_count = len(self.session_memory.downloaded_files)
        goal_lower = goal.lower()
        if download_count > 0 and any(word in goal_lower for word in ['download', 'wallpaper', 'image', 'file', 'picture', 'photo']):
            # Check if we've met a numeric goal
            numbers = RE_NUMBER.findall(goal)
            target = int(numbers[0]) if numbers else 1
            if download_count >= target:
                log(f" [AUTO-COMPLETE: Downloaded {download_count}/{target}]")
                return {"done": True, "reason": f"Downloaded {download_count} files"}

        # Execute the action
        if not action:
            self._record_failure(url, "parse", "Failed to parse action from LLM")
            if hasattr(self, '_logger'):
                self._logger.error("Failed to parse action", step=step_num, action="parse")

            # If we need downloads and have none, don't just give up - force a search
            download_count = len(self.session_memory.downloaded_files)
            goal_lower = goal.lower()
            needs_download = any(word in goal_lower for word in [
                'download', 'fetch', 'save', 'epub', 'pdf',
                'wallpaper', 'picture', 'photo',
            ])

            if needs_download and download_count == 0:
                log(f"  [NO ACTION PARSED - using knowledge base fallback]")
                result = reason_about_goal(goal)
                if result.get("best_source"):
                    search_url = result["start_url"]
                    log(f"  [FALLBACK: Using {result['best_source'].name}]")
                else:
                    encoded = url_quote(result["search_query"])
                    search_url = f"https://www.google.com/search?q={encoded}"
                self.hand.goto(search_url)
                self._record_visit(search_url)
                return {"done": False, "fallback": True, "reason": "Forced search on parse failure"}

            return {"done": False, "error": "Parse failed"}

        try:
            # Determine target for action tracking
            element_id_for_tracking = args.get("_element_id")
            target = args.get("selector", args.get("url", args.get("text", "")))
            if element_id_for_tracking is not None:
                target = f"element:{element_id_for_tracking}"

            # Pass thought to execute_action for text extraction when args are missing
            args["_thought"] = thought
            result = self._execute_action(action, args)

            self._last_action = action

            self.action_tracker.record(
                action_type=action,
                target=target,
                success=True,
                domain=domain,
                context=self.hand.get_title() if self.hand else ""
            )

            self.session_memory.add_action({
                "action": action,
                "args": {k: v for k, v in args.items() if not k.startswith("_")},
                "thought": thought
            })

            selector = args.get("selector", "")
            if selector:
                self.persistent_memory.record_pattern(
                    domain=domain,
                    pattern_type="selector",
                    pattern_data=selector,
                    success=True
                )

            self._consecutive_failures = 0
            self._emit("on_action", action, result)

            # Record to action history for LLM context
            history_entry = f"[Step {step_num}] {action}"
            if element_id_for_tracking is not None:
                history_entry += f" element {element_id_for_tracking}"
            if args.get("text"):
                history_entry += f' "{args["text"][:30]}"'
            outcome = result.get("url", result.get("filename", result.get("reason", "ok")))
            if isinstance(outcome, str) and len(outcome) > 50:
                outcome = outcome[:47] + "..."
            history_entry += f" -> {outcome}"
            self._action_history.append(history_entry)
            if len(self._action_history) > self._max_action_history:
                self._action_history.pop(0)

            if hasattr(self, '_logger'):
                self._logger.act(step_num, action, result, success=True)

            return result

        except Exception as e:  # Top-level agent loop - must catch all
            error_msg = str(e)
            self._record_failure(url, action, error_msg)
            self._consecutive_failures += 1

            # Record failure to action history
            history_entry = f"[Step {step_num}] {action}"
            if element_id_for_tracking is not None:
                history_entry += f" element {element_id_for_tracking}"
            history_entry += f" -> ERROR: {str(e)[:40]}"
            self._action_history.append(history_entry)
            if len(self._action_history) > self._max_action_history:
                self._action_history.pop(0)

            # Use error recovery system to categorize and handle
            recovery_result = self.error_recovery.handle(e, context={
                "url": url,
                "action": action,
                "domain": domain,
                "args": args,
            })

            # Apply recovery delay at agent level (not inside ThreadPoolExecutor)
            if recovery_result.wait_seconds > 0:
                time.sleep(recovery_result.wait_seconds)

            error_info = self.error_recovery.categorize(e)
            log(f" ({error_info.category.value}: {error_msg[:40]})")

            target = args.get("selector", args.get("url", args.get("text", "")))
            self.action_tracker.record(
                action_type=action,
                target=target,
                success=False,
                domain=domain,
                context=self.hand.get_title() if self.hand else "",
                error=error_msg
            )

            # Track repeated failures of the same action type
            current_action_key = f"{action}:{args.get('selector', '')}:{args.get('text', '')}"
            if current_action_key == self._last_failed_action:
                self._repeated_failure_count += 1
            else:
                self._last_failed_action = current_action_key
                self._repeated_failure_count = 1

            selector = args.get("selector", "")
            if selector:
                self.persistent_memory.record_pattern(
                    domain=domain,
                    pattern_type="selector",
                    pattern_data=selector,
                    success=False
                )

            self._emit("on_error", error_msg)

            if hasattr(self, '_logger'):
                self._logger.error(error_msg, step=step_num, action=action)

            # Apply recovery strategy suggestions
            if recovery_result.should_skip:
                log(f"  [SKIPPING: {recovery_result.message}]")
                return {"done": False, "skipped": True, "reason": recovery_result.message}

            if recovery_result.new_context.get("switch_source"):
                log(f"  [RECOVERY: Switching source due to {error_info.category.value}]")
                self._consecutive_challenges = 2  # Trigger source failover

            if recovery_result.new_context.get("use_alternative"):
                log(f"  [RECOVERY: Trying alternative approach]")
                # Get alternative selectors from action tracker
                alternatives = self.action_tracker.get_alternative_actions(action, target, domain)
                if alternatives:
                    log(f"  [ALTERNATIVES: {', '.join(alternatives[:3])}]")

            # If repeating the same failed action too many times, add hint for LLM
            if self._repeated_failure_count >= 3:
                log(f"  [REPEATED FAILURE x{self._repeated_failure_count} - same action keeps failing]")
                self.session_memory.add_failure(
                    f"Action '{action}' failed {self._repeated_failure_count} times - try a DIFFERENT approach"
                )
                self._repeated_failure_count = 0  # Reset to avoid spam

            # If too many consecutive failures, reset counter
            if self._consecutive_failures >= self._max_consecutive_failures:
                log(f"  [TOO MANY FAILURES - trying different approach]")
                self._consecutive_failures = 0

            return {"done": False, "error": error_msg, "action": action, "recoverable": error_info.recoverable}

    def _execute_action(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a browser action."""
        action = action.lower()

        # Normalize action aliases (LLMs sometimes use different names)
        action_aliases = {
            "search": "type",     # search is just type with submit:true
            "go": "navigate",
            "goto": "navigate",
            "visit": "navigate",
            "enter": "type",
            "input": "type",
            "link": "click",
            "press_key": "press",
            "finish": "done",
            "complete": "done",
        }
        action = action_aliases.get(action, action)

        if action == "click":
            element_id = args.get("_element_id")
            selector = args.get("selector", "")
            text = args.get("text", "")
            thought = args.get("_thought", "")

            # Priority 1: Click by element ID (new DOM walker system)
            if element_id is not None:
                br_selector = f'[data-br-id="{element_id}"]'
                loc = self.hand.page.locator(br_selector)
                if loc.count() > 0:
                    loc.first.click(timeout=10000)
                    return {"action": "click", "element": element_id}

            # Priority 2: Click by explicit text
            if text:
                text = text.strip('[]"\'')
                try:
                    self.hand.page.get_by_text(text, exact=False).first.click()
                    return {"action": "click", "text": text}
                except (BrowserError, OSError) as e:
                    logger.debug("Click by text '%s' failed, trying fallback: %s", text, e)

            # Priority 3: Extract text from thought (backward compat)
            if not text and thought:
                quoted = RE_QUOTED_TEXT.findall(thought)
                if quoted:
                    text = quoted[0].strip('[]"\'')
                    try:
                        self.hand.page.get_by_text(text, exact=False).first.click()
                        return {"action": "click", "text": text}
                    except (BrowserError, OSError) as e:
                        logger.debug("Click by quoted text '%s' failed: %s", text, e)

            # Priority 4: Click by CSS selector (backward compat)
            if selector:
                self.hand.click(selector)
                return {"action": "click", "selector": selector}

            raise InvalidActionArgsError("click", "Must provide element ID, text, or selector")

        elif action == "type":
            element_id = args.get("_element_id")
            text = args.get("text", "")
            submit = args.get("submit", True)

            # Priority 1: Type into element by ID (new DOM walker system)
            if element_id is not None:
                br_selector = f'[data-br-id="{element_id}"]'
                loc = self.hand.page.locator(br_selector)
                if loc.count() > 0:
                    loc.first.click(timeout=10000)
                    loc.first.fill(text, timeout=10000)
                    if submit:
                        self.hand.page.keyboard.press("Enter")
                        time.sleep(STEP_PAUSE_SECONDS)
                    return {"action": "type", "element": element_id, "text": text, "submit": submit}

            # Priority 2: Type by CSS selector (backward compat)
            selector = args.get("selector", "input")
            self.hand.type(selector, text)
            if submit:
                self.hand.page.keyboard.press("Enter")
                time.sleep(STEP_PAUSE_SECONDS)
            return {"action": "type", "selector": selector, "text": text, "submit": submit}

        elif action == "press":
            key = args.get("key", "Enter")
            self.hand.page.keyboard.press(key)
            return {"action": "press", "key": key}

        elif action == "scroll":
            direction = args.get("direction", "down")
            amount = args.get("amount", 500)
            self.hand.scroll(direction, amount)
            return {"action": "scroll", "direction": direction}

        elif action == "navigate":
            url = args.get("url", "")
            current_url = self.hand.get_url()

            # Resolve relative URLs to absolute
            if url and not url.startswith(('http://', 'https://')):
                url = urljoin(current_url, url)

            # Skip only if navigating to the exact same URL (normalized)
            # Compare without trailing slash and fragment
            def normalize_url(u):
                u = u.rstrip('/').split('#')[0]
                return u

            if normalize_url(url) == normalize_url(current_url):
                logger.debug("Navigate skipped: already on %s", url[:50])
                return {"action": "navigate", "skipped": True, "url": url}

            logger.debug("Navigating to %s", url[:70])
            self.hand.goto(url)
            self._record_visit(url)
            return {"action": "navigate", "url": url}

        elif action == "back":
            self.hand.back()
            return {"action": "back"}

        elif action == "wait":
            seconds = args.get("seconds", 1)
            time.sleep(seconds)
            return {"action": "wait", "seconds": seconds}

        elif action == "download":
            url = args.get("url", "")
            selector = args.get("selector", "")

            # Resolve relative URLs to absolute
            if url and not url.startswith(('http://', 'https://')):
                base_url = self.hand.get_url()
                url = urljoin(base_url, url)
                logger.debug("Resolved download URL: %s", url[:70])

            # Check if we've already downloaded this URL
            if url and self.persistent_memory.has_downloaded(url=url):
                logger.info("SKIP: Already downloaded %s", url[:50])
                self.session_memory.add_failure(f"Already downloaded {url[:50]}... Try a different item!")
                return {"action": "download", "skipped": True, "reason": "already downloaded"}

            # Check if this URL previously failed
            if url and url in self._failed_download_urls:
                logger.info("SKIP: URL previously failed %s", url[:50])
                self.session_memory.add_failure(f"Download URL failed before - use a different link")
                return {"action": "download", "skipped": True, "reason": "previously failed"}

            try:
                logger.info("Starting download...")
                download_start = time.time()

                if url:
                    result = self.hand.download_link(url)
                elif selector:
                    result = self.hand.click_and_download(selector)
                else:
                    raise InvalidActionArgsError("download", "Must provide either url or selector")

                download_time = time.time() - download_start
                logger.info("Download completed in %.1fs", download_time)

                # Check if we already have this file (by hash)
                if self.persistent_memory.has_downloaded(file_hash=result["hash"]):
                    # Delete the duplicate
                    Path(result["path"]).unlink()
                    logger.info("SKIP: Duplicate content (same hash)")
                    return {"action": "download", "skipped": True, "reason": "duplicate content"}

                # Use centralized content verification
                file_path = Path(result["path"])
                if file_path.exists():
                    verification = self.content_verifier.verify_file(file_path)

                    if verification.status != VerificationStatus.VALID:
                        # Delete invalid file
                        file_path.unlink()
                        logger.warning("INVALID download: %s", verification.message)
                        self.session_memory.add_failure(verification.message)
                        return {
                            "action": "download",
                            "skipped": True,
                            "reason": verification.status.value,
                            "verification": verification.message
                        }

                self._record_download(
                    filename=result["filename"],
                    url=result.get("url", url)
                )

                self.persistent_memory.add_download(
                    filename=result["filename"],
                    url=result.get("url", url),
                    source_site=self._get_domain(),
                    file_hash=result["hash"],
                    file_size=result["size"]
                )

                # Reset selector click counts on successful download (we made progress!)
                self._selector_click_counts = {}
                self._clicked_selectors = set()

                # Mark current page as excellent in navigation context (we got a download!)
                current_url = self.hand.get_url()
                self.nav_context.mark_page_value(current_url, PageValue.EXCELLENT)

                # Also record the selector that led to the download as valuable
                domain = self._get_domain()
                if selector:
                    self.nav_context.record_valuable_selector(domain, selector)

                logger.info("Downloaded: %s (%d bytes)", result['filename'], result['size'])

                return {
                    "action": "download",
                    "filename": result["filename"],
                    "path": result["path"],
                    "size": result["size"]
                }
            except (DownloadError, BrowserError, NetworkError, OSError) as e:
                error_str = str(e)
                current_url = self.hand.get_url()
                self._record_failure(current_url, "download", error_str)

                # Mark page as low value (download failed)
                self.nav_context.mark_page_value(current_url, PageValue.LOW)

                # Track failed download URL to avoid retrying
                if url:
                    self._failed_download_urls.add(url)

                # Provide helpful hints for common download failures
                if "Timeout" in error_str:
                    logger.warning("Download timeout - file may be very large or server is slow")
                    self.session_memory.add_failure("Download timed out - try a different mirror or source")
                elif "Download is starting" in error_str:
                    # This usually means the page didn't trigger a download
                    logger.warning("No download triggered - may need to click a different button")
                    self.session_memory.add_failure("No download triggered - look for actual file download links")
                elif "net::ERR" in error_str or "NetworkError" in error_str:
                    logger.warning("Network error on download - try a different mirror")
                    self.session_memory.add_failure("Network error - try alternative download source")
                else:
                    logger.warning("Download failed: %s", error_str[:100])

                # Add hint about failed URLs for LLM
                if len(self._failed_download_urls) > 0:
                    self.session_memory.add_failure(
                        f"Already tried {len(self._failed_download_urls)} download URLs that failed - use a different link"
                    )

                raise

        elif action == "done":
            return {"done": True, "reason": args.get("reason", "Goal complete")}

        else:
            raise UnknownActionError(action)

    def _format_elements(self, parsed: Dict, exclude_urls: list = None) -> str:
        """Format parsed elements for prompt - general purpose for any content type.

        Args:
            parsed: Parsed page elements from Eyes
            exclude_urls: URLs to exclude from output (already visited/downloaded)
        """
        lines = []
        exclude_urls = exclude_urls or []

        # Helper to extract content ID from URL (papers, items, etc.)
        def extract_content_id(url: str) -> str:
            """Extract content ID from various URL patterns."""
            url_lower = url.lower()
            # ArXiv pattern (precompiled)
            arxiv_match = RE_ARXIV_ID.search(url_lower)
            if arxiv_match:
                return f"arxiv:{arxiv_match.group(1)}"
            # Generic ID patterns
            for pattern in [r'/(\d{5,})', r'/([a-f0-9]{8,})', r'id=(\w+)']:
                match = re.search(pattern, url_lower)
                if match:
                    return match.group(1)
            return ""

        # Helper to check if URL should be excluded
        def is_excluded(url: str) -> bool:
            if not url or not exclude_urls:
                return False
            url_lower = url.lower()
            url_id = extract_content_id(url_lower)

            for excluded in exclude_urls:
                excluded_lower = excluded.lower()
                if url_lower == excluded_lower or excluded_lower in url_lower or url_lower in excluded_lower:
                    return True
                if url_id and url_id == extract_content_id(excluded_lower):
                    return True
            return False

        # Images with downloadable content
        images = parsed.get("images", [])[:15]
        image_lines = []
        for img in images:
            src = img.get("src", "")
            full_src = img.get("full_src", "")
            link = img.get("link", "")

            if is_excluded(link) or is_excluded(src) or is_excluded(full_src):
                continue

            # Detect thumbnails vs full images
            src_lower = src.lower()
            is_thumbnail = any(t in src_lower for t in ['/small/', '/thumb/', 'thumbnail', 'preview', '_s.', '_t.'])
            is_full = any(t in src_lower for t in ['/full/', '/large/', '/original/', '_o.', '_l.'])

            if full_src:
                image_lines.append(f"  - DOWNLOAD: {full_src}")
            elif is_full:
                image_lines.append(f"  - DOWNLOAD: {src}")
            elif link:
                image_lines.append(f"  - NAVIGATE TO: {link}")
            elif not is_thumbnail:
                image_lines.append(f"  - Img: {src[:60]}")

        if image_lines:
            lines.append("Images:")
            lines.extend(image_lines[:10])

        # Links - use pre-scored links from observer
        all_links = parsed.get("links", [])

        download_links = []
        detail_links = []
        other_links = []

        for link in all_links:
            href = link.get("href", "")
            text = link.get("text", "")[:40]
            link_type = link.get("type", "other")

            if is_excluded(href):
                continue

            if link_type == "download":
                download_links.append(f"  - DOWNLOAD: \"{text}\" -> {href}")
            elif link_type == "detail":
                detail_links.append(f"  - DETAIL PAGE: \"{text}\" -> {href}")
            else:
                other_links.append(f"  - \"{text}\" -> {href[:70]}")

        # Combine with priority
        prioritized = download_links[:10] + detail_links[:10] + other_links[:5]
        if prioritized:
            lines.append("Links:")
            lines.extend(prioritized)

        # Pagination info (if available)
        pagination = parsed.get("pagination", {})
        if pagination.get("has_pagination"):
            lines.append("Pagination:")
            if pagination.get("current_page"):
                lines.append(f"  - Current page: {pagination['current_page']}")
            if pagination.get("total_pages"):
                lines.append(f"  - Total pages: {pagination['total_pages']}")
            if pagination.get("next_page"):
                lines.append(f"  - NEXT PAGE: {pagination['next_page']}")

        # Inputs
        inputs = parsed.get("inputs", [])[:5]
        if inputs:
            lines.append("Inputs:")
            for inp in inputs:
                name = inp.get("name", inp.get("id", "input"))
                placeholder = inp.get("placeholder", "")
                lines.append(f"  - {name}: {placeholder}")

        # Buttons
        buttons = parsed.get("buttons", [])[:5]
        if buttons:
            lines.append("Buttons:")
            for btn in buttons:
                text = btn.get("text", "button")[:30]
                lines.append(f"  - {text}")

        return "\n".join(lines) if lines else "No interactive elements found"
