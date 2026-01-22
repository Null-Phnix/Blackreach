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

import time
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse

from blackreach.browser import Hand
from blackreach.observer import Eyes
from blackreach.llm import LLM, LLMConfig
from blackreach.stealth import StealthConfig
from blackreach.resilience import RetryConfig
from blackreach.memory import SessionMemory, PersistentMemory
from blackreach.logging import SessionLogger


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
    start_url: str = "https://www.google.com"
    memory_db: Path = field(default_factory=lambda: Path("./memory.db"))


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

        # Browser and observer
        self.hand: Optional[Hand] = None
        self.eyes = Eyes()

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

    def _emit(self, event: str, *args, **kwargs):
        """Emit a callback event if handler is set."""
        handler = getattr(self.callbacks, event, None)
        if handler:
            try:
                handler(*args, **kwargs)
            except Exception as e:
                # Log but don't break the agent
                import sys
                print(f"[callback error] {event}: {e}", file=sys.stderr)

    def _load_prompts(self) -> Dict[str, str]:
        """Load ReAct prompts from files."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        prompts = {}

        for name in ["observe", "think", "act"]:
            prompt_file = prompts_dir / f"{name}.txt"
            if prompt_file.exists():
                prompts[name] = prompt_file.read_text()
            else:
                # Fallback prompts
                prompts[name] = f"[{name.upper()} prompt not found]"

        return prompts

    def _record_visit(self, url: str, title: str = "", success: bool = True):
        """Record a visit to both memory systems."""
        self.session_memory.add_visit(url)
        self.persistent_memory.add_visit(url, title=title, goal="", success=success)

    def _record_download(self, filename: str, url: str = ""):
        """Record a download to both memory systems."""
        domain = urlparse(url).netloc if url else ""
        self.session_memory.add_download(filename, url)
        self.persistent_memory.add_download(
            filename=filename,
            url=url,
            source_site=domain
        )

    def _record_failure(self, url: str, action: str, error: str):
        """Record a failure to both memory systems."""
        self.session_memory.add_failure(error)
        self.persistent_memory.add_failure(url, action, error)

    def _get_domain(self, url: str = None) -> str:
        """Extract domain from URL or current page."""
        if url:
            return urlparse(url).netloc
        if self.hand:
            return urlparse(self.hand.get_url()).netloc
        return ""

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
        if len(self._recent_urls) > 10:
            self._recent_urls.pop(0)

    def _get_stuck_hint(self) -> str:
        """Get a hint for the LLM when stuck."""
        if not self._is_stuck():
            return ""
        return (
            "\n\nWARNING: You appear to be stuck on the same page. "
            "Try a DIFFERENT action:\n"
            "- If clicking failed, try typing or navigating directly\n"
            "- If typing failed, try clicking a button instead\n"
            "- Try scrolling to reveal hidden elements\n"
            "- Navigate directly to your target URL if you know it"
        )

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

        log(f"\n{'='*60}")
        log(f"GOAL: {goal}")
        log(f"{'='*60}\n")

        # Show memory stats from previous runs
        stats = self.persistent_memory.get_stats()
        if stats["total_sessions"] > 0:
            log(f"Memory: {stats['total_downloads']} downloads, "
                f"{stats['total_visits']} visits from {stats['total_sessions']} sessions")

        # Start a new session in persistent memory
        self.session_id = self.persistent_memory.start_session(goal)
        log(f"Session #{self.session_id} started\n")

        # Initialize session logger for structured logging
        self._logger = SessionLogger(self.session_id, goal)

        # Ensure download dir exists
        self.config.download_dir.mkdir(parents=True, exist_ok=True)

        # Wake up the browser
        log("Starting browser...")
        self.hand = Hand(
            headless=self.config.headless,
            stealth_config=StealthConfig(),
            retry_config=RetryConfig(),
            download_dir=self.config.download_dir
        )
        self.hand.wake()

        success = False
        try:
            # Navigate to start URL
            log(f"Navigating to: {self.config.start_url}")
            self.hand.goto(self.config.start_url)
            self._record_visit(self.config.start_url)

            # Main ReAct loop
            for step in range(1, self.config.max_steps + 1):
                log(f"\n[Step {step}/{self.config.max_steps}]")
                self._emit("on_step", step, self.config.max_steps, "step", "")

                # Run one iteration
                result = self._step(goal, step, quiet=quiet)

                if result.get("done"):
                    log(f"\n COMPLETE: {result.get('reason', 'Goal achieved')}")
                    success = True
                    break

                time.sleep(0.5)  # Brief pause between steps

            else:
                log(f"\n Reached max steps ({self.config.max_steps})")

        finally:
            # Clean up
            log("\nClosing browser...")
            if self.hand:
                self.hand.sleep()

            # End the session in persistent memory
            self.persistent_memory.end_session(
                self.session_id,
                steps=len(self.session_memory.actions_taken),
                downloads=len(self.session_memory.downloaded_files),
                success=success
            )
            log(f"Session #{self.session_id} ended (success={success})")

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
            "downloads": self.session_memory.downloaded_files,
            "pages_visited": len(self.session_memory.visited_urls),
            "steps_taken": len(self.session_memory.actions_taken),
            "failures": len(self.session_memory.failures),
            "session_id": self.session_id,
        }

        self._emit("on_complete", success, result)
        return result

    def _step(self, goal: str, step_num: int, quiet: bool = False) -> Dict[str, Any]:
        """Execute one ReAct iteration."""

        def log(msg: str, end="\n"):
            if not quiet:
                print(msg, end=end, flush=True)

        # Track current URL for stuck detection
        current_url = self.hand.get_url()
        self._track_url(current_url)

        # Log step start
        if hasattr(self, '_logger'):
            self._logger.step_start(step_num)

        # 1. OBSERVE
        log("  OBSERVE: ", end="")
        self._emit("on_step", step_num, self.config.max_steps, "observe", "Analyzing page...")
        observation = self._observe()
        obs_short = observation[:100] + "..." if len(observation) > 100 else observation
        log(obs_short)
        self._emit("on_observe", observation)

        # Log observation
        if hasattr(self, '_logger'):
            self._logger.observe(step_num, observation, current_url)

        # 2. THINK (with stuck detection)
        log("  THINK: ", end="")
        self._emit("on_step", step_num, self.config.max_steps, "think", "Reasoning...")
        stuck_hint = self._get_stuck_hint()
        if stuck_hint and not quiet:
            log(f"\n  [STUCK DETECTED]", end="")
        thought = self._think(goal, observation, stuck_hint)
        log(thought)
        self._emit("on_think", thought)

        # Log thought
        if hasattr(self, '_logger'):
            self._logger.think(step_num, thought, stuck=bool(stuck_hint))

        # 3. ACT
        log("  ACT: ", end="")
        self._emit("on_step", step_num, self.config.max_steps, "act", "Executing...")
        result = self._act(thought, observation)
        action_name = result.get("action", "unknown")

        # Track consecutive failures
        if result.get("error"):
            self._consecutive_failures += 1
            if not quiet:
                log(f" (failure {self._consecutive_failures}/{self._max_consecutive_failures})")
            # Log error
            if hasattr(self, '_logger'):
                self._logger.error(step_num, result.get("error"), action_name)
        else:
            self._consecutive_failures = 0
            log(action_name)
            # Log successful action
            if hasattr(self, '_logger'):
                self._logger.act(step_num, action_name, result, success=True)

        self._emit("on_action", action_name, result)

        # If too many consecutive failures, suggest giving up on current approach
        if self._consecutive_failures >= self._max_consecutive_failures:
            if not quiet:
                log(f"  [TOO MANY FAILURES - trying different approach]")
            self._consecutive_failures = 0  # Reset counter

        return result

    def _observe(self) -> str:
        """Observe the current page state."""
        # Get page info
        html = self.hand.get_html()
        url = self.hand.get_url()
        title = self.hand.get_title()

        # Parse with Eyes
        parsed = self.eyes.see(html)

        # Format elements for prompt
        elements = self._format_elements(parsed)
        text_content = parsed.get("text", "")[:2000]

        # Cache parsed data for reuse in _act() (avoids re-parsing)
        self._page_cache["url"] = url
        self._page_cache["html"] = html
        self._page_cache["parsed"] = parsed
        self._page_cache["elements"] = elements

        # Build observation prompt
        prompt = self.prompts["observe"].format(
            url=url,
            title=title,
            elements=elements,
            text_content=text_content
        )

        # Get LLM observation
        response = self.llm.generate(
            "You are a web page observer. Describe what you see concisely.",
            prompt
        )

        # Record visit to both memories
        self._record_visit(url, title=title)
        return response.strip()

    def _think(self, goal: str, observation: str, stuck_hint: str = "") -> str:
        """Think about what to do next."""
        # Get learned patterns for the current domain
        domain = self._get_domain()
        learned_patterns = ""
        if domain:
            patterns = self.persistent_memory.get_best_patterns(domain, "selector")
            if patterns:
                learned_patterns = f"\nPreviously successful selectors on {domain}: {patterns[:3]}"

        prompt = self.prompts["think"].format(
            goal=goal,
            observation=observation,
            history=self.session_memory.get_history(),
            download_count=len(self.session_memory.downloaded_files),
            visit_count=len(self.session_memory.visited_urls),
            last_failure=self.session_memory.last_failure
        )

        # Add learned patterns if available
        if learned_patterns:
            prompt += learned_patterns

        # Add stuck hint if detected
        if stuck_hint:
            prompt += stuck_hint

        response = self.llm.generate(
            "You are a reasoning agent. Think step by step about what to do next.",
            prompt
        )

        return response.strip()

    def _act(self, thought: str, observation: str) -> Dict[str, Any]:
        """Execute an action based on thought."""
        # Use cached elements from _observe() (avoids redundant parsing)
        elements = self._page_cache.get("elements")
        url = self._page_cache.get("url") or self.hand.get_url()
        if not elements:
            # Fallback: re-parse if cache miss (shouldn't happen in normal flow)
            html = self.hand.get_html()
            parsed = self.eyes.see(html)
            elements = self._format_elements(parsed)

        prompt = self.prompts["act"].format(
            thought=thought,
            elements=elements
        )

        response = self.llm.generate(
            "You are a JSON action generator. Output ONLY valid JSON, no explanation. Format: {\"action\": \"type\", \"args\": {\"selector\": \"input\", \"text\": \"query\"}}",
            prompt
        )

        # Parse the action
        parsed_response = self.llm.parse_action(response)

        if parsed_response.done:
            return {"done": True, "reason": parsed_response.reason}

        if not parsed_response.action:
            self._record_failure(url, "parse", "Failed to parse action from LLM")
            return {"done": False, "error": "Parse failed"}

        # Execute the action
        try:
            result = self._execute_action(
                parsed_response.action,
                parsed_response.args
            )
            # Record action in session memory
            self.session_memory.add_action({
                "action": parsed_response.action,
                "args": parsed_response.args,
                "thought": thought
            })

            # Record successful pattern
            selector = parsed_response.args.get("selector", "")
            if selector:
                domain = self._get_domain()
                self.persistent_memory.record_pattern(
                    domain=domain,
                    pattern_type="selector",
                    pattern_data=selector,
                    success=True
                )

            return result
        except Exception as e:
            error_msg = str(e)
            self._record_failure(url, parsed_response.action, error_msg)

            # Record failed pattern
            selector = parsed_response.args.get("selector", "")
            if selector:
                domain = self._get_domain()
                self.persistent_memory.record_pattern(
                    domain=domain,
                    pattern_type="selector",
                    pattern_data=selector,
                    success=False
                )

            self._emit("on_error", error_msg)
            return {"done": False, "error": error_msg}

    def _execute_action(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a browser action."""
        action = action.lower()

        if action == "click":
            selector = args.get("selector", "")
            text = args.get("text", "")

            # If we have text, always try text-based clicking first
            if text:
                try:
                    self.hand.page.get_by_text(text, exact=False).first.click()
                    return {"action": "click", "text": text}
                except Exception:
                    pass  # Fall through to selector-based click

            # If selector is too generic, try to find a visible link instead
            generic_selectors = ['a', 'button', 'div', 'span', 'input', 'li', 'p']
            if selector in generic_selectors or not selector:
                # Try clicking the first visible content link (prioritize image galleries)
                result_selectors = [
                    # Image gallery selectors (wallpaper sites)
                    'a:has(img)',          # Links containing images
                    '.thumb a',            # Thumbnail links
                    '.boxgrid a',          # Alpha Coders grid
                    '.item a',             # Gallery items
                    '.pic a',              # Picture links
                    '.image a',
                    '.wallpaper a',
                    'a[href*="big"]',      # Alpha Coders big image links
                    'a[href*="wallpaper"]',
                    'a[href*=".php"]',     # PHP detail pages
                    # Search result selectors
                    'article a',
                    '.result a',
                    '.result__a',
                    '[data-testid="result"] a',
                    'main a[href^="http"]',
                    'a[href^="http"]:not([href*="duck"])',
                    'a[href*=".html"]',
                ]
                for sel in result_selectors:
                    try:
                        loc = self.hand.page.locator(sel)
                        if loc.count() > 0 and loc.first.is_visible():
                            loc.first.click()
                            return {"action": "click", "selector": sel}
                    except Exception:
                        continue

            # Last resort: use the provided selector
            if selector:
                self.hand.click(selector)
                return {"action": "click", "selector": selector}
            else:
                raise ValueError("Click requires either 'selector' or 'text' argument")

        elif action == "type":
            selector = args.get("selector", "input")
            text = args.get("text", "")
            submit = args.get("submit", False)  # Press Enter after typing
            self.hand.type(selector, text)
            if submit:
                self.hand.page.keyboard.press("Enter")
                import time
                time.sleep(0.5)  # Wait for page to respond
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

            # Check if we've already downloaded this URL
            if url and self.persistent_memory.has_downloaded(url=url):
                print(f"  SKIP: Already downloaded from {url}")
                return {"action": "download", "skipped": True, "reason": "already downloaded"}

            # Perform the download
            try:
                if url:
                    result = self.hand.download_link(url)
                elif selector:
                    result = self.hand.click_and_download(selector)
                else:
                    raise ValueError("Download requires url or selector")

                # Check if we already have this file (by hash)
                if self.persistent_memory.has_downloaded(file_hash=result["hash"]):
                    # Delete the duplicate
                    Path(result["path"]).unlink()
                    print(f"  SKIP: Duplicate content (same hash)")
                    return {"action": "download", "skipped": True, "reason": "duplicate content"}

                # Record the download
                self._record_download(
                    filename=result["filename"],
                    url=result.get("url", url)
                )

                # Update persistent memory with hash and size
                self.persistent_memory.add_download(
                    filename=result["filename"],
                    url=result.get("url", url),
                    source_site=self._get_domain(),
                    file_hash=result["hash"],
                    file_size=result["size"]
                )

                print(f"  Downloaded: {result['filename']} ({result['size']} bytes)")
                return {
                    "action": "download",
                    "filename": result["filename"],
                    "path": result["path"],
                    "size": result["size"]
                }
            except Exception as e:
                self._record_failure(self.hand.get_url(), "download", str(e))
                raise

        elif action == "done":
            return {"done": True, "reason": args.get("reason", "Goal complete")}

        else:
            raise ValueError(f"Unknown action: {action}")

    def _format_elements(self, parsed: Dict) -> str:
        """Format parsed elements for prompt."""
        lines = []

        # Links
        links = parsed.get("links", [])[:20]
        if links:
            lines.append("Links:")
            for link in links:
                text = link.get("text", "")[:50]
                href = link.get("href", "")[:50]
                lines.append(f"  - [{text}]({href})")

        # Inputs
        inputs = parsed.get("inputs", [])[:10]
        if inputs:
            lines.append("Inputs:")
            for inp in inputs:
                name = inp.get("name", inp.get("id", "input"))
                placeholder = inp.get("placeholder", "")
                lines.append(f"  - {name}: {placeholder}")

        # Buttons
        buttons = parsed.get("buttons", [])[:10]
        if buttons:
            lines.append("Buttons:")
            for btn in buttons:
                text = btn.get("text", "button")[:30]
                lines.append(f"  - {text}")

        return "\n".join(lines) if lines else "No interactive elements found"
