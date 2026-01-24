"""
Blackreach Error Recovery - Intelligent error handling and recovery.

Categorizes errors and provides automatic recovery strategies:
- Network errors -> retry with backoff
- Element not found -> try alternative selectors
- Timeout -> wait and retry
- Rate limiting -> pause and switch sources
- CAPTCHA/Challenge -> try alternate URL or wait

Example usage:
    recovery = ErrorRecovery()

    try:
        do_something()
    except Exception as e:
        result = recovery.handle(e, context)
        if result.should_retry:
            # Apply recovery action
            result.apply_recovery()
            do_something()  # retry
        elif result.should_skip:
            # Skip this action and continue
            continue
        else:
            # Unrecoverable, fail
            raise
"""

import re
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from functools import wraps


class ErrorCategory(Enum):
    """Categories of errors for recovery strategies."""
    NETWORK = "network"              # Connection issues, DNS, etc.
    TIMEOUT = "timeout"              # Page/element timeouts
    ELEMENT_NOT_FOUND = "not_found"  # Selector doesn't match
    RATE_LIMITED = "rate_limited"    # Too many requests
    BLOCKED = "blocked"              # IP blocked, CAPTCHA, etc.
    AUTH_REQUIRED = "auth_required"  # Login needed
    INVALID_RESPONSE = "invalid"     # Unexpected response
    RESOURCE_ERROR = "resource"      # Out of memory, disk, etc.
    UNKNOWN = "unknown"              # Unclassified


class RecoveryAction(Enum):
    """Actions to take for recovery."""
    RETRY_IMMEDIATE = "retry_now"     # Retry immediately
    RETRY_WITH_BACKOFF = "retry_wait" # Retry after delay
    TRY_ALTERNATIVE = "alternative"   # Try different approach
    SWITCH_SOURCE = "switch_source"   # Use different website
    WAIT_AND_RETRY = "wait"           # Wait longer, then retry
    SKIP_ACTION = "skip"              # Skip this action
    ABORT = "abort"                   # Give up


@dataclass
class ErrorInfo:
    """Detailed information about an error."""
    category: ErrorCategory
    original_error: Exception
    message: str
    recoverable: bool
    confidence: float  # How confident we are in the categorization
    suggested_action: RecoveryAction
    retry_delay: float = 0.0  # Seconds to wait before retry
    max_retries: int = 3
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    action_taken: RecoveryAction
    should_retry: bool
    should_skip: bool
    message: str
    new_context: Dict[str, Any] = field(default_factory=dict)


# Error patterns for categorization
ERROR_PATTERNS = {
    ErrorCategory.NETWORK: [
        r"net::ERR_",
        r"connection refused",
        r"connection reset",
        r"network error",
        r"dns",
        r"unreachable",
        r"socket",
        r"connection timed out",
        r"ERR_INTERNET",
        r"no internet",
    ],
    ErrorCategory.TIMEOUT: [
        r"timeout",
        r"timed out",
        r"deadline exceeded",
        r"waiting for.*failed",
        r"TimeoutError",
    ],
    ErrorCategory.ELEMENT_NOT_FOUND: [
        r"element.*not found",
        r"no element",
        r"locator.*resolved to",
        r"selector.*not found",
        r"cannot find",
        r"does not exist",
        r"NodeNotFoundError",
        r"StaleElementReference",
    ],
    ErrorCategory.RATE_LIMITED: [
        r"rate limit",
        r"too many requests",
        r"429",
        r"throttl",
        r"slow down",
        r"quota exceeded",
    ],
    ErrorCategory.BLOCKED: [
        r"captcha",
        r"challenge",
        r"blocked",
        r"forbidden",
        r"403",
        r"access denied",
        r"bot detection",
        r"cloudflare",
        r"ddos",
    ],
    ErrorCategory.AUTH_REQUIRED: [
        r"login required",
        r"sign in",
        r"401",
        r"unauthorized",
        r"authentication",
        r"not logged in",
    ],
    ErrorCategory.INVALID_RESPONSE: [
        r"invalid response",
        r"parse error",
        r"unexpected",
        r"malformed",
        r"500",
        r"502",
        r"503",
        r"504",
        r"server error",
    ],
    ErrorCategory.RESOURCE_ERROR: [
        r"out of memory",
        r"disk full",
        r"no space",
        r"resource",
        r"memory",
        r"MemoryError",
    ],
}

# Default recovery strategies per category
DEFAULT_STRATEGIES = {
    ErrorCategory.NETWORK: RecoveryAction.RETRY_WITH_BACKOFF,
    ErrorCategory.TIMEOUT: RecoveryAction.WAIT_AND_RETRY,
    ErrorCategory.ELEMENT_NOT_FOUND: RecoveryAction.TRY_ALTERNATIVE,
    ErrorCategory.RATE_LIMITED: RecoveryAction.WAIT_AND_RETRY,
    ErrorCategory.BLOCKED: RecoveryAction.SWITCH_SOURCE,
    ErrorCategory.AUTH_REQUIRED: RecoveryAction.SKIP_ACTION,
    ErrorCategory.INVALID_RESPONSE: RecoveryAction.RETRY_WITH_BACKOFF,
    ErrorCategory.RESOURCE_ERROR: RecoveryAction.ABORT,
    ErrorCategory.UNKNOWN: RecoveryAction.RETRY_IMMEDIATE,
}

# Retry delays per category (seconds)
DEFAULT_DELAYS = {
    ErrorCategory.NETWORK: 2.0,
    ErrorCategory.TIMEOUT: 3.0,
    ErrorCategory.ELEMENT_NOT_FOUND: 0.5,
    ErrorCategory.RATE_LIMITED: 10.0,
    ErrorCategory.BLOCKED: 5.0,
    ErrorCategory.AUTH_REQUIRED: 0.0,
    ErrorCategory.INVALID_RESPONSE: 2.0,
    ErrorCategory.RESOURCE_ERROR: 0.0,
    ErrorCategory.UNKNOWN: 1.0,
}


class ErrorRecovery:
    """
    Intelligent error recovery system.

    Categorizes errors and provides context-aware recovery strategies.
    Tracks error history to adapt strategies over time.
    """

    def __init__(self):
        # Error history for adaptive strategies
        self._error_counts: Dict[ErrorCategory, int] = {}
        self._recovery_success: Dict[ErrorCategory, List[bool]] = {}
        self._consecutive_errors = 0

        # Custom handlers
        self._custom_handlers: Dict[ErrorCategory, Callable] = {}

        # Compiled patterns for performance
        self._compiled_patterns: Dict[ErrorCategory, List[re.Pattern]] = {}
        for category, patterns in ERROR_PATTERNS.items():
            self._compiled_patterns[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def categorize(self, error: Exception) -> ErrorInfo:
        """
        Categorize an error and determine recovery strategy.

        Args:
            error: The exception that occurred

        Returns:
            ErrorInfo with category, recoverability, and suggested action
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Try to match against known patterns
        best_match = ErrorCategory.UNKNOWN
        best_confidence = 0.0

        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(error_str) or pattern.search(error_type):
                    # Calculate confidence based on match quality
                    confidence = 0.8
                    if pattern.search(error_type):
                        confidence = 0.95  # Type match is more reliable

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = category

        # Determine recoverability
        recoverable = best_match not in [
            ErrorCategory.RESOURCE_ERROR,
            ErrorCategory.AUTH_REQUIRED,
        ]

        # Check if we've seen too many of this error
        error_count = self._error_counts.get(best_match, 0)
        if error_count >= 5:
            recoverable = False  # Give up after too many of same error

        # Get suggested action
        suggested_action = DEFAULT_STRATEGIES.get(
            best_match, RecoveryAction.RETRY_IMMEDIATE
        )

        # Get retry delay
        retry_delay = DEFAULT_DELAYS.get(best_match, 1.0)

        # Adjust based on consecutive errors
        if self._consecutive_errors >= 3:
            retry_delay *= 2  # Increase delay for consecutive errors
            if self._consecutive_errors >= 5:
                suggested_action = RecoveryAction.SWITCH_SOURCE

        return ErrorInfo(
            category=best_match,
            original_error=error,
            message=str(error),
            recoverable=recoverable,
            confidence=best_confidence,
            suggested_action=suggested_action,
            retry_delay=retry_delay,
            max_retries=3 if recoverable else 0,
            details={
                "error_type": error_type,
                "consecutive_errors": self._consecutive_errors,
                "category_count": error_count,
            }
        )

    def handle(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> RecoveryResult:
        """
        Handle an error and attempt recovery.

        Args:
            error: The exception that occurred
            context: Additional context (url, action, etc.)

        Returns:
            RecoveryResult with action taken and retry guidance
        """
        context = context or {}
        info = self.categorize(error)

        # Update tracking
        self._error_counts[info.category] = self._error_counts.get(info.category, 0) + 1
        self._consecutive_errors += 1

        # Check for custom handler
        if info.category in self._custom_handlers:
            try:
                return self._custom_handlers[info.category](info, context)
            except Exception:
                pass  # Fall through to default handling

        # Apply default recovery strategy
        return self._apply_strategy(info, context)

    def _apply_strategy(
        self,
        info: ErrorInfo,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """Apply the recovery strategy for an error."""

        action = info.suggested_action

        if action == RecoveryAction.RETRY_IMMEDIATE:
            return RecoveryResult(
                success=True,
                action_taken=action,
                should_retry=info.recoverable,
                should_skip=False,
                message=f"Retrying immediately: {info.message[:50]}",
            )

        elif action == RecoveryAction.RETRY_WITH_BACKOFF:
            time.sleep(info.retry_delay)
            return RecoveryResult(
                success=True,
                action_taken=action,
                should_retry=info.recoverable,
                should_skip=False,
                message=f"Retrying after {info.retry_delay}s delay",
            )

        elif action == RecoveryAction.WAIT_AND_RETRY:
            wait_time = info.retry_delay * 2
            time.sleep(wait_time)
            return RecoveryResult(
                success=True,
                action_taken=action,
                should_retry=info.recoverable,
                should_skip=False,
                message=f"Waited {wait_time}s, retrying",
            )

        elif action == RecoveryAction.TRY_ALTERNATIVE:
            return RecoveryResult(
                success=True,
                action_taken=action,
                should_retry=True,
                should_skip=False,
                message="Trying alternative approach",
                new_context={"use_alternative": True}
            )

        elif action == RecoveryAction.SWITCH_SOURCE:
            return RecoveryResult(
                success=True,
                action_taken=action,
                should_retry=True,
                should_skip=False,
                message="Switching to alternate source",
                new_context={"switch_source": True}
            )

        elif action == RecoveryAction.SKIP_ACTION:
            return RecoveryResult(
                success=True,
                action_taken=action,
                should_retry=False,
                should_skip=True,
                message=f"Skipping action: {info.message[:50]}",
            )

        else:  # ABORT
            return RecoveryResult(
                success=False,
                action_taken=action,
                should_retry=False,
                should_skip=False,
                message=f"Unrecoverable error: {info.message[:50]}",
            )

    def record_success(self) -> None:
        """Record a successful operation (resets consecutive error count)."""
        self._consecutive_errors = 0

    def register_handler(
        self,
        category: ErrorCategory,
        handler: Callable[[ErrorInfo, Dict], RecoveryResult]
    ) -> None:
        """Register a custom handler for an error category."""
        self._custom_handlers[category] = handler

    def get_stats(self) -> Dict:
        """Get error statistics."""
        total_errors = sum(self._error_counts.values())
        return {
            "total_errors": total_errors,
            "by_category": dict(self._error_counts),
            "consecutive_errors": self._consecutive_errors,
            "most_common": max(self._error_counts.items(), key=lambda x: x[1])[0].value
            if self._error_counts else None,
        }

    def reset(self) -> None:
        """Reset error tracking."""
        self._error_counts.clear()
        self._recovery_success.clear()
        self._consecutive_errors = 0


def with_recovery(
    max_retries: int = 3,
    recovery: Optional[ErrorRecovery] = None
):
    """
    Decorator for automatic error recovery.

    Example:
        @with_recovery(max_retries=3)
        def risky_operation():
            # May throw exceptions
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            _recovery = recovery or ErrorRecovery()
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    _recovery.record_success()
                    return result
                except Exception as e:
                    last_error = e
                    result = _recovery.handle(e)

                    if not result.should_retry:
                        break

                    # Apply any context changes
                    if result.new_context.get("use_alternative"):
                        kwargs["use_alternative"] = True

            raise last_error

        return wrapper
    return decorator


# Global instance for convenience
_global_recovery: Optional[ErrorRecovery] = None


def get_recovery() -> ErrorRecovery:
    """Get or create the global error recovery instance."""
    global _global_recovery
    if _global_recovery is None:
        _global_recovery = ErrorRecovery()
    return _global_recovery
