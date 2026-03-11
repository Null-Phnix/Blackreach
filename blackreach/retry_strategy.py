"""
Retry Strategy System (v2.5.0)

Provides intelligent retry mechanisms with:
- Exponential backoff with jitter
- Per-action retry policies
- Retry budgets to prevent infinite loops
- Context-aware retry decisions
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import random
import time
import math


class RetryDecision(Enum):
    """Decision on whether to retry."""
    RETRY = "retry"
    SKIP = "skip"          # Skip this action, try something else
    ABORT = "abort"        # Give up entirely
    WAIT_AND_RETRY = "wait_and_retry"
    CHANGE_APPROACH = "change_approach"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0         # Base delay in seconds
    max_delay: float = 30.0         # Maximum delay cap
    exponential_base: float = 2.0   # Multiplier for exponential backoff
    jitter: float = 0.5             # Random jitter factor (0-1)
    retry_on_errors: List[str] = field(default_factory=lambda: [
        "timeout", "network", "rate_limit", "temporary"
    ])
    skip_on_errors: List[str] = field(default_factory=lambda: [
        "not_found", "invalid_action", "permanent"
    ])


@dataclass
class RetryState:
    """Tracks retry state for an operation."""
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    last_error: Optional[str] = None
    total_wait_time: float = 0.0
    success: bool = False


@dataclass
class RetryBudget:
    """Limits total retries across operations."""
    max_total_retries: int = 50     # Total retries per session
    max_consecutive_failures: int = 5
    budget_window_seconds: float = 300.0  # Reset budget after this time
    current_total: int = 0
    consecutive_failures: int = 0
    window_start: datetime = field(default_factory=datetime.now)

    def can_retry(self) -> bool:
        """Check if retry budget allows another attempt."""
        # Reset window if enough time has passed
        if datetime.now() - self.window_start > timedelta(seconds=self.budget_window_seconds):
            self.current_total = 0
            self.consecutive_failures = 0
            self.window_start = datetime.now()

        return (
            self.current_total < self.max_total_retries and
            self.consecutive_failures < self.max_consecutive_failures
        )

    def record_retry(self, success: bool):
        """Record a retry attempt."""
        self.current_total += 1
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

    def get_status(self) -> Dict[str, Any]:
        """Get current budget status."""
        return {
            "total_retries": self.current_total,
            "max_total": self.max_total_retries,
            "consecutive_failures": self.consecutive_failures,
            "max_consecutive": self.max_consecutive_failures,
            "can_retry": self.can_retry()
        }


# Default policies for different action types
DEFAULT_POLICIES = {
    "navigate": RetryPolicy(
        max_attempts=3,
        base_delay=2.0,
        retry_on_errors=["timeout", "network", "rate_limit"]
    ),
    "click": RetryPolicy(
        max_attempts=2,
        base_delay=0.5,
        retry_on_errors=["timeout", "element_not_found"],
        skip_on_errors=["element_not_interactable"]
    ),
    "type": RetryPolicy(
        max_attempts=2,
        base_delay=0.5,
        retry_on_errors=["timeout", "element_not_found"]
    ),
    "download": RetryPolicy(
        max_attempts=3,
        base_delay=3.0,
        max_delay=60.0,
        retry_on_errors=["timeout", "network", "rate_limit", "temporary"]
    ),
    "scroll": RetryPolicy(
        max_attempts=1,  # Scrolling rarely needs retry
        base_delay=0.3
    ),
    "default": RetryPolicy()
}


class RetryManager:
    """Manages retry logic for operations."""

    def __init__(self, budget: Optional[RetryBudget] = None):
        self.budget = budget or RetryBudget()
        self.policies: Dict[str, RetryPolicy] = DEFAULT_POLICIES.copy()
        self.states: Dict[str, RetryState] = {}  # key -> state
        self.error_classifier = ErrorClassifier()

    def get_policy(self, action: str) -> RetryPolicy:
        """Get retry policy for an action type."""
        return self.policies.get(action, self.policies["default"])

    def set_policy(self, action: str, policy: RetryPolicy):
        """Set custom policy for an action type."""
        self.policies[action] = policy

    def should_retry(
        self,
        action: str,
        error: Exception,
        key: str = ""
    ) -> Tuple[RetryDecision, float]:
        """
        Determine if an operation should be retried.

        Returns: (decision, wait_time_seconds)
        """
        # Get or create state for this operation
        state_key = f"{action}:{key}" if key else action
        if state_key not in self.states:
            self.states[state_key] = RetryState()
        state = self.states[state_key]

        # Get policy
        policy = self.get_policy(action)

        # Classify the error
        error_type = self.error_classifier.classify(error)

        # Check if error type should skip retry
        for skip_pattern in policy.skip_on_errors:
            if skip_pattern in error_type:
                return (RetryDecision.SKIP, 0)

        # Check if we've exceeded max attempts
        if state.attempts >= policy.max_attempts:
            return (RetryDecision.CHANGE_APPROACH, 0)

        # Check budget
        if not self.budget.can_retry():
            return (RetryDecision.ABORT, 0)

        # Check if error is retryable
        retryable = any(pattern in error_type for pattern in policy.retry_on_errors)
        if not retryable:
            return (RetryDecision.SKIP, 0)

        # Calculate wait time with exponential backoff and jitter
        wait_time = self._calculate_wait(state.attempts, policy)

        return (RetryDecision.WAIT_AND_RETRY, wait_time)

    def _calculate_wait(self, attempt: int, policy: RetryPolicy) -> float:
        """Calculate wait time with exponential backoff and jitter."""
        # Exponential backoff
        wait = policy.base_delay * (policy.exponential_base ** attempt)

        # Apply jitter
        jitter_range = wait * policy.jitter
        jitter = random.uniform(-jitter_range, jitter_range)
        wait += jitter

        # Cap at max delay
        wait = min(wait, policy.max_delay)

        return max(0, wait)

    def record_attempt(self, action: str, key: str = "", success: bool = False, error: str = ""):
        """Record an attempt."""
        state_key = f"{action}:{key}" if key else action
        if state_key not in self.states:
            self.states[state_key] = RetryState()

        state = self.states[state_key]
        state.attempts += 1
        state.last_attempt = datetime.now()
        state.success = success
        state.last_error = error if not success else None

        self.budget.record_retry(success)

    def reset_state(self, action: str, key: str = ""):
        """Reset retry state for an operation."""
        state_key = f"{action}:{key}" if key else action
        if state_key in self.states:
            del self.states[state_key]

    def get_state(self, action: str, key: str = "") -> Optional[RetryState]:
        """Get current retry state."""
        state_key = f"{action}:{key}" if key else action
        return self.states.get(state_key)

    def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics."""
        return {
            "budget": self.budget.get_status(),
            "active_states": len(self.states),
            "states": {
                k: {
                    "attempts": v.attempts,
                    "success": v.success,
                    "last_error": v.last_error
                }
                for k, v in self.states.items()
            }
        }


class ErrorClassifier:
    """Classifies errors into categories for retry decisions."""

    def __init__(self):
        self.patterns = {
            "timeout": [
                "timeout", "timed out", "deadline exceeded",
                "navigation timeout", "waiting failed"
            ],
            "network": [
                "net::err_", "network", "connection", "refused",
                "dns", "unreachable", "reset by peer"
            ],
            "rate_limit": [
                "rate limit", "too many requests", "429",
                "throttle", "slow down"
            ],
            "element_not_found": [
                "element not found", "no element", "unable to locate",
                "waiting for selector", "not visible"
            ],
            "element_not_interactable": [
                "not interactable", "intercepted", "obscured",
                "disabled", "hidden"
            ],
            "not_found": [
                "404", "not found", "page doesn't exist",
                "no such file"
            ],
            "temporary": [
                "temporary", "503", "502", "500",
                "server error", "try again"
            ],
            "permanent": [
                "403", "forbidden", "access denied",
                "authentication required", "blocked"
            ],
            "invalid_action": [
                "invalid", "illegal", "cannot perform",
                "not supported"
            ]
        }

    def classify(self, error: Exception) -> str:
        """Classify an error into a category."""
        error_str = str(error).lower()

        for category, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern in error_str:
                    return category

        return "unknown"

    def is_retryable(self, error: Exception) -> bool:
        """Quick check if an error is generally retryable."""
        category = self.classify(error)
        return category in ["timeout", "network", "rate_limit", "temporary", "element_not_found"]


def with_retry(
    func: Callable,
    action: str,
    manager: RetryManager,
    key: str = "",
    on_retry: Optional[Callable[[int, float], None]] = None
) -> Any:
    """
    Execute a function with retry logic.

    Args:
        func: Function to execute
        action: Action type for policy lookup
        manager: RetryManager instance
        key: Optional unique key for this specific operation
        on_retry: Optional callback when retry happens (attempt, wait_time)

    Returns:
        Result from func

    Raises:
        Last exception if all retries exhausted
    """
    last_error = None
    policy = manager.get_policy(action)

    for attempt in range(policy.max_attempts):
        try:
            result = func()
            manager.record_attempt(action, key, success=True)
            return result
        except Exception as e:
            last_error = e
            decision, wait_time = manager.should_retry(action, e, key)

            manager.record_attempt(action, key, success=False, error=str(e))

            if decision == RetryDecision.WAIT_AND_RETRY:
                if on_retry:
                    on_retry(attempt + 1, wait_time)
                time.sleep(wait_time)
            elif decision in (RetryDecision.SKIP, RetryDecision.ABORT, RetryDecision.CHANGE_APPROACH):
                break

    # All retries exhausted
    manager.reset_state(action, key)
    raise last_error


# Global retry manager instance
_retry_manager: Optional[RetryManager] = None


def get_retry_manager() -> RetryManager:
    """Get the global retry manager instance."""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = RetryManager()
    return _retry_manager


def reset_retry_manager():
    """Reset the global retry manager."""
    global _retry_manager
    _retry_manager = None
