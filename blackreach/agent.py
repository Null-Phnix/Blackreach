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
    start_url: str = "https://www.wikipedia.org"  # Wikipedia doesn't block headless browsers
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
        self._stuck_counter = 0  # Track how many times stuck detection triggered
        self._last_action = None  # Track repeated actions

    def _emit(self, event: str, *args, **kwargs) -> None:
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
        """Record a download to both memory systems."""
        domain = urlparse(url).netloc if url else ""
        self.session_memory.add_download(filename, url)
        self.persistent_memory.add_download(
            filename=filename,
            url=url,
            source_site=domain
        )

    def _record_failure(self, url: str, action: str, error: str) -> None:
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

        # Get current URL to provide context-specific hints
        current_url = self._recent_urls[-1] if self._recent_urls else ""
        start_url = self.config.start_url

        # Wallpaper-specific hint if on wallhaven
        if 'wallhaven' in current_url:
            return (
                f"\n\nSTUCK! You must navigate to a DIFFERENT page!"
                f"\nGo back to search: {start_url}"
                f"\nThen pick a DIFFERENT wallpaper link to navigate to."
            )

        return (
            f"\n\nSTUCK! Try a DIFFERENT approach:"
            f"\n- Navigate back to: {start_url}"
            f"\n- Or try a completely different URL"
            f"\n- DO NOT repeat the same action"
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
        """Execute one ReAct iteration with a SINGLE LLM call."""

        def log(msg: str, end="\n"):
            if not quiet:
                print(msg, end=end, flush=True)

        # Track current URL for stuck detection
        current_url = self.hand.get_url()
        self._track_url(current_url)

        # Log step start
        if hasattr(self, '_logger'):
            self._logger.step_start(step_num)

        # Get page state
        self._emit("on_step", step_num, self.config.max_steps, "observe", "Analyzing page...")
        html = self.hand.get_html()
        url = self.hand.get_url()
        title = self.hand.get_title()
        parsed = self.eyes.see(html)

        # Build list of URLs to exclude (already visited detail pages + downloaded URLs)
        detail_patterns = ['/w/', '/abs/', '/paper/', '/article/', '/item/', '/full/', '/pdf/']
        exclude_urls = [
            u for u in self.session_memory.visited_urls
            if any(p in u for p in detail_patterns)
        ]
        # Also exclude URLs we've already downloaded from
        exclude_urls.extend(self.session_memory.downloaded_urls)

        elements = self._format_elements(parsed, exclude_urls=exclude_urls)

        # Cache for potential reuse
        self._page_cache["url"] = url
        self._page_cache["html"] = html
        self._page_cache["parsed"] = parsed
        self._page_cache["elements"] = elements

        # Build extra context (stuck hints, learned patterns, etc.)
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
            self._stuck_counter = 0  # Reset counter when not stuck

        # Get learned patterns for the current domain
        domain = self._get_domain()
        if domain:
            patterns = self.persistent_memory.get_best_patterns(domain, "selector")
            if patterns:
                extra_context += f"\nPreviously successful selectors on {domain}: {patterns[:3]}"

        last_failure = self.session_memory.last_failure
        if last_failure:
            extra_context += f"\nLAST ERROR: {last_failure}"

        # Add list of already visited detail pages (to avoid re-navigating)
        # Detect detail pages by common URL patterns
        detail_patterns = ['/w/', '/abs/', '/paper/', '/article/', '/item/', '/full/', '/pdf/']
        visited_detail_pages = [
            u for u in self.session_memory.visited_urls
            if any(p in u for p in detail_patterns)
        ]
        if visited_detail_pages:
            extra_context += f"\nALREADY VISITED (pick a DIFFERENT link): {visited_detail_pages[-5:]}"

        # Add info about downloaded files (so LLM knows to pick different items)
        downloaded = self.session_memory.downloaded_files
        if downloaded:
            filenames = [Path(f).name for f in downloaded[-5:]]
            extra_context += f"\nALREADY DOWNLOADED: {filenames}"

        # Build unified prompt with elements so agent can see what's on page
        prompt = self.prompts["react"].format(
            goal=goal,
            url=url,
            title=title,
            elements=elements,
            download_count=len(self.session_memory.downloaded_files),
            extra_context=extra_context
        )

        # SINGLE LLM call for think + act
        log("  REACT: ", end="")
        self._emit("on_step", step_num, self.config.max_steps, "think", "Reasoning...")
        response = self.llm.generate(
            "You are an autonomous browser agent. Output ONLY valid JSON.",
            prompt
        )

        # Parse the response
        import json
        import re

        thought = ""
        action = None
        args = {}

        # Try to extract JSON from response - handle nested braces
        response_clean = response.strip()

        # Find all JSON-like structures and try to parse
        try:
            # First try to parse the whole response as JSON
            data = json.loads(response_clean)
        except json.JSONDecodeError:
            # Try to find JSON object in response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_clean)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    data = {}
            else:
                data = {}

        # Extract fields with VERY flexible handling for inconsistent LLM outputs
        thought = data.get("thought", data.get("reason", ""))

        # Handle various action formats LLMs produce
        action = None
        args = {}

        # Format 0: {"actions": [{...}, {...}]} - array of actions, take first one
        actions_array = data.get("actions")
        if isinstance(actions_array, list) and len(actions_array) > 0:
            first_action = actions_array[0]
            if isinstance(first_action, dict):
                data = first_action  # Use first action as the data to parse

        # Format 1: {"action": "type", "args": {...}}
        action_val = data.get("action")
        if isinstance(action_val, str):
            action = action_val
            args = data.get("args", {})
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
            args = {k: v for k, v in data.items() if k not in ("type", "thought", "action")}

        # Format 5: Just look for common action words in the data
        if not action:
            for key in data:
                if key in ("navigate", "click", "type", "download", "scroll", "done"):
                    action = key
                    val = data[key]
                    args = val if isinstance(val, dict) else {"value": val}
                    break

        # Log thought and action
        log(f"{thought} -> {action}")
        self._emit("on_think", thought)

        # Log to structured logger
        if hasattr(self, '_logger'):
            self._logger.observe(step_num, f"URL: {url}, Title: {title}", url)
            self._logger.think(step_num, thought, stuck=bool(stuck_hint))

        # Record visit
        self._record_visit(url, title=title)

        # Handle done action
        if action == "done":
            reason = args.get("reason", thought or "Goal complete")
            if hasattr(self, '_logger'):
                self._logger.act(step_num, "done", {"reason": reason}, success=True)
            return {"done": True, "reason": reason}

        # Auto-completion check for download goals
        download_count = len(self.session_memory.downloaded_files)
        goal_lower = goal.lower()
        if download_count > 0 and any(word in goal_lower for word in ['download', 'wallpaper', 'image', 'file', 'picture', 'photo']):
            # Check if we've met a numeric goal
            import re
            numbers = re.findall(r'\b(\d+)\b', goal)
            target = int(numbers[0]) if numbers else 1
            if download_count >= target:
                log(f" [AUTO-COMPLETE: Downloaded {download_count}/{target}]")
                return {"done": True, "reason": f"Downloaded {download_count} files"}

        # Execute the action
        if not action:
            self._record_failure(url, "parse", "Failed to parse action from LLM")
            if hasattr(self, '_logger'):
                self._logger.error(step_num, "Failed to parse action", "parse")
            return {"done": False, "error": "Parse failed"}

        try:
            result = self._execute_action(action, args)
            # Record action in session memory
            self.session_memory.add_action({
                "action": action,
                "args": args,
                "thought": thought
            })

            # Record successful pattern
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

            if hasattr(self, '_logger'):
                self._logger.act(step_num, action, result, success=True)

            return result

        except Exception as e:
            error_msg = str(e)
            self._record_failure(url, action, error_msg)
            self._consecutive_failures += 1

            # Record failed pattern
            selector = args.get("selector", "")
            if selector:
                self.persistent_memory.record_pattern(
                    domain=domain,
                    pattern_type="selector",
                    pattern_data=selector,
                    success=False
                )

            log(f" (failure {self._consecutive_failures}/{self._max_consecutive_failures})")
            self._emit("on_error", error_msg)

            if hasattr(self, '_logger'):
                self._logger.error(step_num, error_msg, action)

            # If too many consecutive failures, reset counter
            if self._consecutive_failures >= self._max_consecutive_failures:
                log(f"  [TOO MANY FAILURES - trying different approach]")
                self._consecutive_failures = 0

            return {"done": False, "error": error_msg, "action": action}

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
            selector = args.get("selector", "")
            text = args.get("text", "")

            # Clean text - strip brackets and quotes that may come from formatting
            if text:
                text = text.strip('[]"\'')

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
            # Auto-submit if typing into a search-like input (most common use case)
            # Only skip submit if explicitly set to False
            submit = args.get("submit", True)
            self.hand.type(selector, text)
            if submit:
                self.hand.page.keyboard.press("Enter")
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
            current_url = self.hand.get_url()

            # Resolve relative URLs to absolute
            if url and not url.startswith(('http://', 'https://')):
                from urllib.parse import urljoin
                url = urljoin(current_url, url)

            # Skip if navigating to the same or similar URL
            if url == current_url or url in current_url or current_url in url:
                print(f"  -> (skipped: already on {url[:50]})")
                return {"action": "navigate", "skipped": True, "url": url}

            print(f"  -> {url[:70]}")
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
                from urllib.parse import urljoin
                base_url = self.hand.get_url()
                url = urljoin(base_url, url)
                print(f"  -> Resolved URL: {url[:70]}")

            # Check if we've already downloaded this URL
            if url and self.persistent_memory.has_downloaded(url=url):
                print(f"  SKIP: Already downloaded - navigate to different page!")
                # Add to session memory as a failure hint
                self.session_memory.last_failure = f"Already downloaded {url[:50]}... Navigate to a DIFFERENT wallpaper page!"
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

                # Check if file is too small (likely a thumbnail) - only for images
                filename_lower = result["filename"].lower()
                is_image = any(filename_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'])
                MIN_FULL_IMAGE_SIZE = 200000  # 200KB - thumbnails are usually smaller

                if is_image and result["size"] < MIN_FULL_IMAGE_SIZE:
                    # Keep the file but don't count it as a real download
                    print(f"  WARNING: Small image ({result['size']} bytes) - likely thumbnail, not counted")
                    # Delete small image files (thumbnails)
                    Path(result["path"]).unlink()
                    return {"action": "download", "skipped": True, "reason": "thumbnail (too small)"}

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

                # Auto-navigate back to search page after download to continue
                if 'search' in self.config.start_url or 'wallhaven' in self.config.start_url:
                    print(f"  (auto-returning to search)")
                    self.hand.goto(self.config.start_url)
                    self._recent_urls = []  # Clear stuck detection

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

    def _format_elements(self, parsed: Dict, exclude_urls: list = None) -> str:
        """Format parsed elements for prompt - prioritize images for download tasks.

        Args:
            parsed: Parsed page elements from Eyes
            exclude_urls: URLs to exclude from output (already visited/downloaded)
        """
        lines = []
        exclude_urls = exclude_urls or []

        # Helper to extract paper/item ID from URL
        def extract_id(url: str) -> str:
            """Extract paper ID from academic URLs (e.g., arxiv.org/abs/2305.14496v2 -> 2305.14496)"""
            import re
            # ArXiv pattern: /abs/ID or /pdf/ID (with optional version suffix like v1, v2)
            arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url.lower())
            if arxiv_match:
                return f"arxiv:{arxiv_match.group(1)}"
            return ""

        # Helper to check if URL should be excluded
        def is_excluded(url: str) -> bool:
            if not url or not exclude_urls:
                return False
            url_lower = url.lower()
            url_id = extract_id(url_lower)

            for excluded in exclude_urls:
                excluded_lower = excluded.lower()
                # Check if URLs match (handle partial matches for detail pages)
                if url_lower == excluded_lower or excluded_lower in url_lower or url_lower in excluded_lower:
                    return True
                # Check if paper IDs match (e.g., /abs/XXXX matches /pdf/XXXX)
                if url_id and url_id == extract_id(excluded_lower):
                    return True
            return False

        # Images (critical for download tasks)
        images = parsed.get("images", [])[:15]
        image_lines = []
        for img in images:
            src = img.get("src", "")
            full_src = img.get("full_src", "")
            link = img.get("link", "")
            alt = img.get("alt", "")[:30]

            # Skip already visited/downloaded URLs
            if is_excluded(link) or is_excluded(src) or is_excluded(full_src):
                continue

            # Detect if this is a thumbnail (should not be downloaded)
            is_thumbnail = any(t in src.lower() for t in ['th.wallhaven', '/small/', '/thumb/', 'thumbnail', 'preview'])
            is_full = any(t in src.lower() for t in ['/full/', 'w.wallhaven.cc/full'])

            # Show the most useful URL for downloading
            if full_src:
                image_lines.append(f"  - DOWNLOAD: {full_src}")
            elif is_full:
                image_lines.append(f"  - DOWNLOAD: {src}")
            elif link and '/w/' in link:
                image_lines.append(f"  - NAVIGATE TO: {link}")  # Detail page
            elif link:
                image_lines.append(f"  - Link: {link}")
            else:
                image_lines.append(f"  - Img: {src[:60]}")

        if image_lines:
            lines.append("Images:")
            lines.extend(image_lines)

        # Links - prioritize actionable links (downloads, detail pages)
        all_links = parsed.get("links", [])

        # Separate and prioritize links
        download_links = []
        detail_links = []
        other_links = []

        for link in all_links:
            href = link.get("href", "")
            href_lower = href.lower()
            text = link.get("text", "")[:40]

            # Skip already visited/downloaded URLs
            if is_excluded(href):
                continue

            # Check for downloadable files by extension or path pattern
            # Exclude wiki pages (e.g. /wiki/File:something.png is a wiki page, not a direct download)
            is_wiki_page = '/wiki/' in href_lower
            download_exts = ['.pdf', '.zip', '.tar', '.gz', '.csv', '.json', '.xlsx', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.mp3', '.mp4', '.doc', '.docx', '.txt', '.md']
            download_paths = ['/pdf/', '/download/', '/file/', 'upload.wikimedia.org']  # ArXiv, GitHub, Wikimedia, etc.
            is_download = (not is_wiki_page) and (any(ext in href_lower for ext in download_exts) or any(p in href_lower for p in download_paths))

            if is_download:
                download_links.append(f"  - DOWNLOAD: \"{text}\" -> {href}")
            elif any(p in href_lower for p in ['/abs/', '/paper/', '/article/', '/item/', '/w/', '/full/']):
                detail_links.append(f"  - DETAIL PAGE: \"{text}\" -> {href}")
            elif 'author' not in href_lower and 'search' not in href_lower:
                other_links.append(f"  - \"{text}\" -> {href[:70]}")

        # Combine with priority: downloads first, then detail pages, then others
        prioritized = download_links[:10] + detail_links[:10] + other_links[:5]
        if prioritized:
            lines.append("Links:")
            lines.extend(prioritized)

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
