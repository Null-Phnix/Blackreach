"""
Unit tests for blackreach/retry_strategy.py

Tests retry logic with exponential backoff, jitter, and error classification.
"""

import pytest
import time
from datetime import datetime, timedelta
from blackreach.retry_strategy import (
    RetryDecision,
    RetryPolicy,
    RetryState,
    RetryBudget,
    RetryManager,
    ErrorClassifier,
    with_retry,
    get_retry_manager,
    reset_retry_manager,
    DEFAULT_POLICIES,
)


class TestRetryDecision:
    """Tests for RetryDecision enum."""

    def test_all_decisions_exist(self):
        """All expected retry decisions should exist."""
        assert RetryDecision.RETRY.value == "retry"
        assert RetryDecision.SKIP.value == "skip"
        assert RetryDecision.ABORT.value == "abort"
        assert RetryDecision.WAIT_AND_RETRY.value == "wait_and_retry"
        assert RetryDecision.CHANGE_APPROACH.value == "change_approach"


class TestRetryPolicy:
    """Tests for RetryPolicy dataclass."""

    def test_default_values(self):
        """RetryPolicy has sensible defaults."""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.exponential_base == 2.0
        assert policy.jitter == 0.5
        assert "timeout" in policy.retry_on_errors
        assert "network" in policy.retry_on_errors
        assert "not_found" in policy.skip_on_errors

    def test_custom_values(self):
        """RetryPolicy accepts custom values."""
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=60.0,
            exponential_base=3.0,
            jitter=0.3
        )
        assert policy.max_attempts == 5
        assert policy.base_delay == 2.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 3.0
        assert policy.jitter == 0.3


class TestRetryState:
    """Tests for RetryState dataclass."""

    def test_default_values(self):
        """RetryState has correct defaults."""
        state = RetryState()
        assert state.attempts == 0
        assert state.last_attempt is None
        assert state.last_error is None
        assert state.total_wait_time == 0.0
        assert state.success is False


class TestRetryBudget:
    """Tests for RetryBudget dataclass."""

    def test_default_values(self):
        """RetryBudget has sensible defaults."""
        budget = RetryBudget()
        assert budget.max_total_retries == 50
        assert budget.max_consecutive_failures == 5
        assert budget.budget_window_seconds == 300.0
        assert budget.current_total == 0
        assert budget.consecutive_failures == 0

    def test_can_retry_initially(self):
        """Should allow retries initially."""
        budget = RetryBudget()
        assert budget.can_retry() is True

    def test_can_retry_at_limit(self):
        """Should block retries when at total limit."""
        budget = RetryBudget()
        budget.current_total = 50  # At limit
        assert budget.can_retry() is False

    def test_can_retry_consecutive_limit(self):
        """Should block retries when consecutive failures exceed limit."""
        budget = RetryBudget()
        budget.consecutive_failures = 5  # At limit
        assert budget.can_retry() is False

    def test_record_retry_success(self):
        """Recording success should reset consecutive failures."""
        budget = RetryBudget()
        budget.consecutive_failures = 3
        budget.record_retry(success=True)

        assert budget.current_total == 1
        assert budget.consecutive_failures == 0

    def test_record_retry_failure(self):
        """Recording failure should increment consecutive failures."""
        budget = RetryBudget()
        budget.record_retry(success=False)
        budget.record_retry(success=False)

        assert budget.current_total == 2
        assert budget.consecutive_failures == 2

    def test_budget_window_reset(self):
        """Budget should reset after window expires."""
        budget = RetryBudget(budget_window_seconds=0.1)
        budget.current_total = 40
        budget.consecutive_failures = 4

        # Wait for window to expire
        time.sleep(0.15)

        # Should be able to retry now
        assert budget.can_retry() is True
        # Calling can_retry() triggers the reset

    def test_get_status(self):
        """Should return budget status."""
        budget = RetryBudget()
        budget.current_total = 10
        budget.consecutive_failures = 2

        status = budget.get_status()

        assert status["total_retries"] == 10
        assert status["max_total"] == 50
        assert status["consecutive_failures"] == 2
        assert status["max_consecutive"] == 5
        assert status["can_retry"] is True


class TestDefaultPolicies:
    """Tests for default retry policies."""

    def test_navigate_policy(self):
        """Navigate policy should exist with appropriate settings."""
        policy = DEFAULT_POLICIES["navigate"]
        assert policy.max_attempts == 3
        assert "timeout" in policy.retry_on_errors

    def test_click_policy(self):
        """Click policy should have fewer attempts."""
        policy = DEFAULT_POLICIES["click"]
        assert policy.max_attempts == 2
        assert "element_not_interactable" in policy.skip_on_errors

    def test_download_policy(self):
        """Download policy should have longer delays."""
        policy = DEFAULT_POLICIES["download"]
        assert policy.max_attempts == 3
        assert policy.max_delay == 60.0

    def test_scroll_policy(self):
        """Scroll policy should rarely retry."""
        policy = DEFAULT_POLICIES["scroll"]
        assert policy.max_attempts == 1

    def test_default_policy(self):
        """Default policy should exist."""
        policy = DEFAULT_POLICIES["default"]
        assert policy is not None


class TestErrorClassifier:
    """Tests for ErrorClassifier class."""

    def test_classify_timeout(self):
        """Should classify timeout errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("Connection timed out")) == "timeout"
        assert classifier.classify(Exception("Navigation timeout exceeded")) == "timeout"
        assert classifier.classify(Exception("Deadline exceeded")) == "timeout"

    def test_classify_network(self):
        """Should classify network errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("net::err_connection_refused")) == "network"
        assert classifier.classify(Exception("DNS lookup failed")) == "network"
        assert classifier.classify(Exception("Connection reset by peer")) == "network"

    def test_classify_rate_limit(self):
        """Should classify rate limit errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("Rate limit exceeded")) == "rate_limit"
        assert classifier.classify(Exception("429 Too Many Requests")) == "rate_limit"
        assert classifier.classify(Exception("Please slow down")) == "rate_limit"

    def test_classify_element_not_found(self):
        """Should classify element not found errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("Element not found")) == "element_not_found"
        assert classifier.classify(Exception("Unable to locate element")) == "element_not_found"

    def test_classify_not_found(self):
        """Should classify 404 errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("404 Not Found")) == "not_found"
        assert classifier.classify(Exception("Page doesn't exist")) == "not_found"

    def test_classify_temporary(self):
        """Should classify temporary/server errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("503 Service Unavailable")) == "temporary"
        assert classifier.classify(Exception("500 Internal Server Error")) == "temporary"
        assert classifier.classify(Exception("Please try again later")) == "temporary"

    def test_classify_permanent(self):
        """Should classify permanent errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("403 Forbidden")) == "permanent"
        assert classifier.classify(Exception("Access denied")) == "permanent"
        assert classifier.classify(Exception("Blocked by firewall")) == "permanent"

    def test_classify_unknown(self):
        """Should return unknown for unclassified errors."""
        classifier = ErrorClassifier()

        assert classifier.classify(Exception("Something weird happened")) == "unknown"

    def test_is_retryable(self):
        """Should check if error is generally retryable."""
        classifier = ErrorClassifier()

        assert classifier.is_retryable(Exception("Connection timeout")) is True
        assert classifier.is_retryable(Exception("Network error")) is True
        assert classifier.is_retryable(Exception("403 Forbidden")) is False
        assert classifier.is_retryable(Exception("404 Not Found")) is False


class TestRetryManager:
    """Tests for RetryManager class."""

    def test_init(self):
        """RetryManager initializes correctly."""
        manager = RetryManager()
        assert manager is not None
        assert manager.budget is not None

    def test_get_policy(self):
        """Should return policy for action type."""
        manager = RetryManager()

        navigate_policy = manager.get_policy("navigate")
        assert navigate_policy.max_attempts == 3

        unknown_policy = manager.get_policy("unknown_action")
        assert unknown_policy == manager.policies["default"]

    def test_set_policy(self):
        """Should set custom policy."""
        manager = RetryManager()
        custom_policy = RetryPolicy(max_attempts=10)

        manager.set_policy("custom", custom_policy)

        assert manager.get_policy("custom").max_attempts == 10

    def test_should_retry_retryable_error(self):
        """Should recommend retry for retryable error."""
        manager = RetryManager()

        decision, wait_time = manager.should_retry(
            action="navigate",
            error=Exception("Connection timeout"),
            key="test"
        )

        assert decision == RetryDecision.WAIT_AND_RETRY
        assert wait_time > 0

    def test_should_retry_skip_error(self):
        """Should recommend skip for non-retryable error."""
        manager = RetryManager()

        decision, wait_time = manager.should_retry(
            action="navigate",
            error=Exception("404 Not Found"),
            key="test"
        )

        assert decision == RetryDecision.SKIP

    def test_should_retry_max_attempts(self):
        """Should recommend change approach after max attempts."""
        manager = RetryManager()
        policy = manager.get_policy("navigate")

        # Exhaust attempts
        for _ in range(policy.max_attempts):
            manager.record_attempt("navigate", "test", success=False, error="timeout")

        decision, _ = manager.should_retry(
            action="navigate",
            error=Exception("timeout"),
            key="test"
        )

        assert decision == RetryDecision.CHANGE_APPROACH

    def test_should_retry_budget_exhausted(self):
        """Should abort when budget exhausted."""
        budget = RetryBudget(max_total_retries=1)
        manager = RetryManager(budget=budget)
        budget.current_total = 1  # Exhaust budget

        decision, _ = manager.should_retry(
            action="navigate",
            error=Exception("timeout"),
            key="test"
        )

        assert decision == RetryDecision.ABORT

    def test_record_attempt_success(self):
        """Should record successful attempt."""
        manager = RetryManager()
        manager.record_attempt("navigate", "test", success=True)

        state = manager.get_state("navigate", "test")
        assert state is not None
        assert state.attempts == 1
        assert state.success is True

    def test_record_attempt_failure(self):
        """Should record failed attempt."""
        manager = RetryManager()
        manager.record_attempt("navigate", "test", success=False, error="timeout")

        state = manager.get_state("navigate", "test")
        assert state.attempts == 1
        assert state.success is False
        assert state.last_error == "timeout"

    def test_reset_state(self):
        """Should reset state for operation."""
        manager = RetryManager()
        manager.record_attempt("navigate", "test", success=False)
        manager.reset_state("navigate", "test")

        state = manager.get_state("navigate", "test")
        assert state is None

    def test_get_stats(self):
        """Should return manager statistics."""
        manager = RetryManager()
        manager.record_attempt("navigate", "test1", success=True)
        manager.record_attempt("click", "test2", success=False)

        stats = manager.get_stats()

        assert "budget" in stats
        assert stats["active_states"] == 2
        assert "states" in stats


class TestCalculateWait:
    """Tests for wait time calculation."""

    def test_exponential_backoff(self):
        """Wait time should increase exponentially."""
        manager = RetryManager()
        policy = RetryPolicy(base_delay=1.0, exponential_base=2.0, jitter=0)

        wait0 = manager._calculate_wait(0, policy)
        wait1 = manager._calculate_wait(1, policy)
        wait2 = manager._calculate_wait(2, policy)

        assert wait0 == 1.0  # 1.0 * 2^0 = 1.0
        assert wait1 == 2.0  # 1.0 * 2^1 = 2.0
        assert wait2 == 4.0  # 1.0 * 2^2 = 4.0

    def test_max_delay_cap(self):
        """Wait time should be capped at max_delay."""
        manager = RetryManager()
        policy = RetryPolicy(
            base_delay=10.0,
            exponential_base=2.0,
            max_delay=20.0,
            jitter=0
        )

        wait = manager._calculate_wait(5, policy)  # Would be 320 without cap

        assert wait == 20.0

    def test_jitter_applied(self):
        """Jitter should add randomness to wait time."""
        manager = RetryManager()
        policy = RetryPolicy(base_delay=1.0, jitter=0.5)

        waits = [manager._calculate_wait(0, policy) for _ in range(10)]

        # With jitter, not all values should be the same
        assert len(set(waits)) > 1


class TestWithRetry:
    """Tests for with_retry helper function."""

    def test_success_on_first_try(self):
        """Should return result on first successful try."""
        manager = RetryManager()
        call_count = 0

        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = with_retry(success_func, "navigate", manager)

        assert result == "success"
        assert call_count == 1

    def test_retry_on_retryable_error(self):
        """Should retry on retryable errors."""
        manager = RetryManager()
        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Connection timeout")
            return "success"

        result = with_retry(fail_then_succeed, "navigate", manager)

        assert result == "success"
        assert call_count == 2

    def test_raises_after_max_retries(self):
        """Should raise last error after max retries."""
        manager = RetryManager()
        manager.set_policy("test", RetryPolicy(max_attempts=2, base_delay=0.01))

        def always_fail():
            raise Exception("timeout")

        with pytest.raises(Exception, match="timeout"):
            with_retry(always_fail, "test", manager)

    def test_on_retry_callback(self):
        """Should call on_retry callback."""
        manager = RetryManager()
        manager.set_policy("test", RetryPolicy(max_attempts=2, base_delay=0.01))
        retry_calls = []

        def fail_then_succeed():
            if len(retry_calls) < 1:
                raise Exception("timeout")
            return "success"

        def on_retry(attempt, wait_time):
            retry_calls.append((attempt, wait_time))

        result = with_retry(fail_then_succeed, "test", manager, on_retry=on_retry)

        assert result == "success"
        assert len(retry_calls) == 1


class TestGlobalRetryManager:
    """Tests for global retry manager."""

    def test_get_retry_manager(self):
        """Should return global retry manager."""
        reset_retry_manager()  # Start fresh

        manager1 = get_retry_manager()
        manager2 = get_retry_manager()

        assert manager1 is manager2

    def test_reset_retry_manager(self):
        """Should reset global retry manager."""
        manager1 = get_retry_manager()
        reset_retry_manager()
        manager2 = get_retry_manager()

        assert manager1 is not manager2
