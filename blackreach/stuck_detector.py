"""
Blackreach Stuck Detector - Intelligent loop and stuck state detection.

Goes beyond URL-based detection to identify when the agent is truly stuck:
- Content similarity detection (same content, different URLs)
- Action loop detection (repeating same actions)
- Progress stagnation (no meaningful progress toward goal)
- Automatic strategy suggestions

Example usage:
    detector = StuckDetector()

    # Add observations
    detector.observe(url, content_hash, action, download_count)

    # Check if stuck
    if detector.is_stuck():
        strategy = detector.suggest_strategy()
        print(f"Stuck! Suggested strategy: {strategy}")

        # Reset detection after taking corrective action
        detector.reset()
"""

import hashlib
import re
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum


# P0-PERF: Pre-compiled regex patterns for content hashing
_RE_SCRIPT = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE)
_RE_STYLE = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
_RE_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
_RE_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_RE_TIME = re.compile(r'\d{1,2}:\d{2}')
_RE_ID_ATTR = re.compile(r'id="[^"]*"')
_RE_HTML_TAGS = re.compile(r'<[^>]+>')


class StuckReason(Enum):
    """Reasons why the agent might be stuck."""
    URL_LOOP = "url_loop"                    # Visiting same URL repeatedly
    CONTENT_LOOP = "content_loop"            # Same content across different URLs
    ACTION_LOOP = "action_loop"              # Repeating same actions
    NO_PROGRESS = "no_progress"              # No downloads/achievements
    CHALLENGE_BLOCKED = "challenge_blocked"  # Blocked by challenge pages
    DEAD_END = "dead_end"                    # No more links to follow
    NOT_STUCK = "not_stuck"


class RecoveryStrategy(Enum):
    """Strategies for recovering from stuck states."""
    GO_BACK = "go_back"                      # Navigate back
    TRY_ALTERNATE_SOURCE = "alternate"       # Try a different source
    REFORMULATE_SEARCH = "reformulate"       # Try different search terms
    SCROLL_AND_EXPLORE = "scroll"            # Scroll to find more content
    WAIT_AND_RETRY = "wait"                  # Wait for dynamic content
    SWITCH_BROWSER = "switch_browser"        # Try different browser
    GIVE_UP = "give_up"                      # Can't recover


@dataclass
class Observation:
    """A single observation of the agent's state."""
    url: str
    content_hash: str
    action: str
    action_target: str
    download_count: int
    step_number: int
    timestamp: float = 0.0


@dataclass
class StuckState:
    """Information about a stuck state."""
    is_stuck: bool
    reason: StuckReason
    confidence: float  # 0.0 - 1.0
    details: str
    stuck_since_step: int = 0
    steps_stuck: int = 0


class StuckDetector:
    """
    Intelligent stuck state detection.

    Uses multiple signals to determine if the agent is stuck:
    1. URL history - are we visiting the same URLs?
    2. Content hashes - is the content the same even with different URLs?
    3. Action history - are we repeating the same actions?
    4. Progress metrics - are we making progress toward the goal?
    """

    # Detection thresholds
    URL_REPEAT_THRESHOLD = 3        # Same URL visited N times = stuck
    CONTENT_REPEAT_THRESHOLD = 3    # Same content seen N times = stuck
    ACTION_REPEAT_THRESHOLD = 4     # Same action repeated N times = stuck
    NO_PROGRESS_STEPS = 10          # No downloads for N steps = concern
    HISTORY_SIZE = 50               # Number of observations to keep

    def __init__(self):
        # Observation history
        self._observations: deque = deque(maxlen=self.HISTORY_SIZE)

        # Specific tracking
        self._url_counts: Dict[str, int] = {}
        self._content_counts: Dict[str, int] = {}
        self._action_sequence: List[Tuple[str, str]] = []  # (action, target)

        # Progress tracking
        self._last_download_step = 0
        self._initial_downloads = 0
        self._current_step = 0

        # State
        self._stuck_since_step: Optional[int] = None
        self._recovery_attempts: Dict[RecoveryStrategy, int] = {}

        # Breadcrumbs for backtracking
        self._breadcrumbs: List[str] = []  # URLs we came from
        self._max_breadcrumbs = 20

    def observe(
        self,
        url: str,
        content_hash: str,
        action: str,
        action_target: str = "",
        download_count: int = 0,
        step_number: int = 0
    ) -> None:
        """
        Record an observation of the agent's state.

        Call this after each agent step to update detection state.
        """
        import time

        self._current_step = step_number

        # Create observation
        obs = Observation(
            url=url,
            content_hash=content_hash,
            action=action,
            action_target=action_target,
            download_count=download_count,
            step_number=step_number,
            timestamp=time.time()
        )
        self._observations.append(obs)

        # Update URL counts
        normalized_url = self._normalize_url(url)
        self._url_counts[normalized_url] = self._url_counts.get(normalized_url, 0) + 1

        # Update content counts
        if content_hash:
            self._content_counts[content_hash] = self._content_counts.get(content_hash, 0) + 1

        # Update action sequence
        action_pair = (action, self._normalize_target(action_target))
        self._action_sequence.append(action_pair)
        if len(self._action_sequence) > self.HISTORY_SIZE:
            self._action_sequence.pop(0)

        # Track downloads
        if download_count > self._initial_downloads:
            self._last_download_step = step_number
            self._stuck_since_step = None  # Reset stuck state on progress

        # Track breadcrumbs (for backtracking)
        if action == "navigate" and url:
            # Add current URL to breadcrumbs before navigating away
            if self._observations and len(self._observations) > 1:
                prev_url = self._observations[-2].url
                if prev_url and prev_url not in self._breadcrumbs[-3:]:  # Avoid recent duplicates
                    self._breadcrumbs.append(prev_url)
                    if len(self._breadcrumbs) > self._max_breadcrumbs:
                        self._breadcrumbs.pop(0)

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        if not url:
            return ""
        # Remove fragments and trailing slashes
        url = url.split('#')[0].rstrip('/')
        # Remove common tracking parameters
        for param in ['utm_', 'ref=', 'source=', 'fbclid=']:
            if param in url:
                url = url.split(param)[0].rstrip('&?')
        return url.lower()

    def _normalize_target(self, target: str) -> str:
        """Normalize action target for comparison."""
        if not target:
            return ""
        # Remove specific indices and quotes
        target = target.lower().strip('"\'')
        return target

    def check(self) -> StuckState:
        """
        Check if the agent is stuck.

        Returns a StuckState with details about the stuck condition.
        """
        # Check URL loop
        url_stuck = self._check_url_loop()
        if url_stuck.is_stuck:
            return url_stuck

        # Check content loop
        content_stuck = self._check_content_loop()
        if content_stuck.is_stuck:
            return content_stuck

        # Check action loop
        action_stuck = self._check_action_loop()
        if action_stuck.is_stuck:
            return action_stuck

        # Check progress stagnation
        progress_stuck = self._check_progress()
        if progress_stuck.is_stuck:
            return progress_stuck

        return StuckState(
            is_stuck=False,
            reason=StuckReason.NOT_STUCK,
            confidence=0.0,
            details="Agent is making progress"
        )

    def is_stuck(self) -> bool:
        """Simple check if stuck (for quick conditionals)."""
        return self.check().is_stuck

    def get_stuck_state(self) -> StuckState:
        """Alias for check() for API compatibility."""
        return self.check()

    def _check_url_loop(self) -> StuckState:
        """Check if stuck in URL loop."""
        for url, count in self._url_counts.items():
            if count >= self.URL_REPEAT_THRESHOLD:
                return StuckState(
                    is_stuck=True,
                    reason=StuckReason.URL_LOOP,
                    confidence=min(count / (self.URL_REPEAT_THRESHOLD + 2), 1.0),
                    details=f"Visited '{url[:50]}...' {count} times",
                    stuck_since_step=self._find_first_repeat_step(url),
                    steps_stuck=count
                )
        return StuckState(False, StuckReason.NOT_STUCK, 0.0, "")

    def _check_content_loop(self) -> StuckState:
        """Check if stuck seeing same content."""
        for content_hash, count in self._content_counts.items():
            if count >= self.CONTENT_REPEAT_THRESHOLD:
                return StuckState(
                    is_stuck=True,
                    reason=StuckReason.CONTENT_LOOP,
                    confidence=min(count / (self.CONTENT_REPEAT_THRESHOLD + 2), 1.0),
                    details=f"Same page content seen {count} times (different URLs)",
                    steps_stuck=count
                )
        return StuckState(False, StuckReason.NOT_STUCK, 0.0, "")

    def _check_action_loop(self) -> StuckState:
        """Check if stuck repeating same actions."""
        if len(self._action_sequence) < self.ACTION_REPEAT_THRESHOLD:
            return StuckState(False, StuckReason.NOT_STUCK, 0.0, "")

        # Check for immediate repeats
        recent = self._action_sequence[-self.ACTION_REPEAT_THRESHOLD:]
        if len(set(recent)) == 1:
            action, target = recent[0]
            # Don't consider "download" as an action loop - downloads are progress
            if action == "download":
                return StuckState(False, StuckReason.NOT_STUCK, 0.0, "")
            return StuckState(
                is_stuck=True,
                reason=StuckReason.ACTION_LOOP,
                confidence=0.9,
                details=f"Action '{action}' on '{target[:30]}' repeated {len(recent)} times",
                steps_stuck=len(recent)
            )

        # Check for action patterns (A-B-A-B loops)
        if len(self._action_sequence) >= 6:
            last_6 = self._action_sequence[-6:]
            # Check if it's a 2-step loop repeated 3 times
            if last_6[0] == last_6[2] == last_6[4] and last_6[1] == last_6[3] == last_6[5]:
                return StuckState(
                    is_stuck=True,
                    reason=StuckReason.ACTION_LOOP,
                    confidence=0.85,
                    details=f"Stuck in action loop: {last_6[0]} -> {last_6[1]}",
                    steps_stuck=6
                )

        return StuckState(False, StuckReason.NOT_STUCK, 0.0, "")

    def _check_progress(self) -> StuckState:
        """Check if making progress toward goal."""
        steps_since_download = self._current_step - self._last_download_step

        if steps_since_download >= self.NO_PROGRESS_STEPS:
            return StuckState(
                is_stuck=True,
                reason=StuckReason.NO_PROGRESS,
                confidence=min(steps_since_download / 20, 0.8),
                details=f"No downloads in {steps_since_download} steps",
                stuck_since_step=self._last_download_step,
                steps_stuck=steps_since_download
            )

        return StuckState(False, StuckReason.NOT_STUCK, 0.0, "")

    def _find_first_repeat_step(self, url: str) -> int:
        """Find the step where URL repeats started."""
        normalized = self._normalize_url(url)
        for obs in self._observations:
            if self._normalize_url(obs.url) == normalized:
                return obs.step_number
        return self._current_step

    def suggest_strategy(self) -> Tuple[RecoveryStrategy, str]:
        """
        Suggest a recovery strategy based on the stuck state.

        Returns (strategy, explanation)
        """
        state = self.check()

        if not state.is_stuck:
            return (RecoveryStrategy.WAIT_AND_RETRY, "Not stuck, continue normally")

        # Track recovery attempts to avoid repeating failed strategies
        def get_best_strategy(strategies: List[RecoveryStrategy]) -> RecoveryStrategy:
            """Get the strategy with fewest attempts."""
            min_attempts = float('inf')
            best = strategies[0]
            for s in strategies:
                attempts = self._recovery_attempts.get(s, 0)
                if attempts < min_attempts:
                    min_attempts = attempts
                    best = s
            return best

        if state.reason == StuckReason.URL_LOOP:
            strategies = [
                RecoveryStrategy.GO_BACK,
                RecoveryStrategy.TRY_ALTERNATE_SOURCE,
                RecoveryStrategy.REFORMULATE_SEARCH
            ]
            strategy = get_best_strategy(strategies)
            return (strategy, f"URL loop detected: {state.details}")

        elif state.reason == StuckReason.CONTENT_LOOP:
            strategies = [
                RecoveryStrategy.TRY_ALTERNATE_SOURCE,
                RecoveryStrategy.REFORMULATE_SEARCH,
                RecoveryStrategy.GO_BACK
            ]
            strategy = get_best_strategy(strategies)
            return (strategy, f"Content loop: {state.details}")

        elif state.reason == StuckReason.ACTION_LOOP:
            strategies = [
                RecoveryStrategy.SCROLL_AND_EXPLORE,
                RecoveryStrategy.GO_BACK,
                RecoveryStrategy.TRY_ALTERNATE_SOURCE
            ]
            strategy = get_best_strategy(strategies)
            return (strategy, f"Action loop: {state.details}")

        elif state.reason == StuckReason.NO_PROGRESS:
            strategies = [
                RecoveryStrategy.TRY_ALTERNATE_SOURCE,
                RecoveryStrategy.REFORMULATE_SEARCH,
                RecoveryStrategy.SCROLL_AND_EXPLORE
            ]
            strategy = get_best_strategy(strategies)
            return (strategy, f"No progress: {state.details}")

        elif state.reason == StuckReason.CHALLENGE_BLOCKED:
            strategies = [
                RecoveryStrategy.TRY_ALTERNATE_SOURCE,
                RecoveryStrategy.WAIT_AND_RETRY,
                RecoveryStrategy.SWITCH_BROWSER
            ]
            strategy = get_best_strategy(strategies)
            return (strategy, f"Blocked by challenge: {state.details}")

        return (RecoveryStrategy.TRY_ALTERNATE_SOURCE, "Unknown stuck state")

    def record_recovery_attempt(self, strategy: RecoveryStrategy) -> None:
        """Record that a recovery strategy was attempted."""
        self._recovery_attempts[strategy] = self._recovery_attempts.get(strategy, 0) + 1

    def get_backtrack_url(self) -> Optional[str]:
        """Get a URL to backtrack to."""
        if self._breadcrumbs:
            return self._breadcrumbs.pop()
        return None

    def get_recent_urls(self, count: int = 5) -> List[str]:
        """Get the most recent unique URLs visited."""
        urls = []
        seen = set()
        for obs in reversed(self._observations):
            if obs.url not in seen:
                urls.append(obs.url)
                seen.add(obs.url)
            if len(urls) >= count:
                break
        return urls

    def reset(self) -> None:
        """Reset detection state after recovery action."""
        self._url_counts.clear()
        self._content_counts.clear()
        self._action_sequence.clear()
        self._stuck_since_step = None
        # Keep breadcrumbs for continued backtracking
        # Keep observations for learning

    def soft_reset(self) -> None:
        """Partial reset - reduce counts instead of clearing."""
        # Halve all counts instead of clearing
        for url in self._url_counts:
            self._url_counts[url] = self._url_counts[url] // 2
        for content_hash in self._content_counts:
            self._content_counts[content_hash] = self._content_counts[content_hash] // 2
        # Keep recent actions, trim older ones
        if len(self._action_sequence) > 10:
            self._action_sequence = self._action_sequence[-10:]

    def get_stats(self) -> Dict:
        """Get detection statistics."""
        state = self.check()
        return {
            "is_stuck": state.is_stuck,
            "reason": state.reason.value,
            "confidence": state.confidence,
            "details": state.details,
            "observations": len(self._observations),
            "unique_urls": len(self._url_counts),
            "unique_content": len(self._content_counts),
            "breadcrumbs": len(self._breadcrumbs),
            "recovery_attempts": dict(self._recovery_attempts),
            "steps_since_download": self._current_step - self._last_download_step,
        }


def compute_content_hash(html: str) -> str:
    """
    Compute a hash of page content for comparison.

    Ignores dynamic elements like timestamps, ads, etc.
    """
    if not html:
        return ""

    # Simple approach: hash the text content length + key elements
    # This catches "same page" even with minor dynamic changes
    # P0-PERF: Uses pre-compiled module-level regex patterns

    # Remove script, style, and common dynamic content
    cleaned = _RE_SCRIPT.sub('', html)
    cleaned = _RE_STYLE.sub('', cleaned)
    cleaned = _RE_COMMENT.sub('', cleaned)

    # Remove timestamps and IDs that change
    cleaned = _RE_DATE.sub('DATE', cleaned)
    cleaned = _RE_TIME.sub('TIME', cleaned)
    cleaned = _RE_ID_ATTR.sub('id=""', cleaned)

    # Get text content
    text = _RE_HTML_TAGS.sub(' ', cleaned)
    text = ' '.join(text.split())  # Normalize whitespace

    # Hash based on content length and key terms
    # Using blake2b (faster than MD5) with 8-byte digest (16 hex chars)
    content_sig = f"{len(text)}:{text[:500]}:{text[-500:]}"
    return hashlib.blake2b(content_sig.encode(), digest_size=8).hexdigest()
