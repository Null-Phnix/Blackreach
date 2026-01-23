"""
Unit tests for blackreach/resilience.py

Tests retry logic, circuit breaker, and smart selectors.
"""

import pytest
import time
from unittest.mock import Mock, patch

from blackreach.resilience import (
    RetryConfig,
    retry_with_backoff,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
)


# =============================================================================
# RetryConfig Tests
# =============================================================================

class TestRetryConfig:
    """Tests for retry configuration."""

    def test_default_values(self):
        """RetryConfig has sensible defaults."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_values(self):
        """RetryConfig accepts custom values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=60.0,
            exponential_base=3.0,
            jitter=False
        )

        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 60.0
        assert config.exponential_base == 3.0
        assert config.jitter is False


# =============================================================================
# Retry With Backoff Tests
# =============================================================================

class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    def test_successful_call_no_retry(self):
        """Successful call doesn't retry."""
        call_count = [0]

        @retry_with_backoff(RetryConfig(max_attempts=3))
        def success():
            call_count[0] += 1
            return "success"

        result = success()

        assert result == "success"
        assert call_count[0] == 1

    def test_retry_on_failure(self):
        """Retries on failure up to max_attempts."""
        call_count = [0]

        @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.01))
        def always_fail():
            call_count[0] += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            always_fail()

        assert call_count[0] == 3

    def test_success_after_retry(self):
        """Succeeds after retry."""
        call_count = [0]

        @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.01))
        def fail_then_succeed():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("fail")
            return "success"

        result = fail_then_succeed()

        assert result == "success"
        assert call_count[0] == 2


# =============================================================================
# CircuitBreakerConfig Tests
# =============================================================================

class TestCircuitBreakerConfig:
    """Tests for circuit breaker configuration."""

    def test_default_values(self):
        """CircuitBreakerConfig has sensible defaults."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 1

    def test_custom_values(self):
        """CircuitBreakerConfig accepts custom values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=10.0,
            half_open_max_calls=2
        )

        assert config.failure_threshold == 3
        assert config.recovery_timeout == 10.0
        assert config.half_open_max_calls == 2


# =============================================================================
# CircuitBreaker State Tests
# =============================================================================

class TestCircuitBreakerStates:
    """Tests for circuit breaker state transitions."""

    def test_initial_state_closed(self):
        """Circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitBreaker.CLOSED
        assert not breaker.is_open

    def test_opens_after_threshold(self):
        """Circuit opens after failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # Record failures up to threshold
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitBreaker.OPEN
        assert breaker.is_open

    def test_stays_closed_below_threshold(self):
        """Circuit stays closed below failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # Record failures below threshold
        for _ in range(2):
            breaker.record_failure()

        assert breaker.state == CircuitBreaker.CLOSED
        assert not breaker.is_open

    def test_transitions_to_half_open(self):
        """Circuit transitions to HALF_OPEN after recovery timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker(config)

        breaker.record_failure()
        assert breaker.state == CircuitBreaker.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        assert breaker.state == CircuitBreaker.HALF_OPEN

    def test_closes_after_half_open_success(self):
        """Circuit closes after successful call in HALF_OPEN."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.01)
        breaker = CircuitBreaker(config)

        breaker.record_failure()
        time.sleep(0.02)  # Wait for half-open

        assert breaker.state == CircuitBreaker.HALF_OPEN

        breaker.record_success()

        assert breaker.state == CircuitBreaker.CLOSED

    def test_reopens_after_half_open_failure(self):
        """Circuit reopens after failure in HALF_OPEN."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.01)
        breaker = CircuitBreaker(config)

        breaker.record_failure()
        time.sleep(0.02)  # Wait for half-open

        assert breaker.state == CircuitBreaker.HALF_OPEN

        breaker.record_failure()

        assert breaker.state == CircuitBreaker.OPEN


# =============================================================================
# CircuitBreaker Request Control Tests
# =============================================================================

class TestCircuitBreakerRequests:
    """Tests for circuit breaker request control."""

    def test_allows_requests_when_closed(self):
        """Allows requests when circuit is closed."""
        breaker = CircuitBreaker()
        assert breaker.allow_request() is True

    def test_blocks_requests_when_open(self):
        """Blocks requests when circuit is open."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config)

        breaker.record_failure()

        assert breaker.allow_request() is False

    def test_allows_limited_requests_half_open(self):
        """Allows limited requests in HALF_OPEN state."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_max_calls=2
        )
        breaker = CircuitBreaker(config)

        breaker.record_failure()
        time.sleep(0.02)

        assert breaker.allow_request() is True  # 1st call
        assert breaker.allow_request() is True  # 2nd call
        assert breaker.allow_request() is False  # 3rd call blocked


# =============================================================================
# CircuitBreaker Context Manager Tests
# =============================================================================

class TestCircuitBreakerContextManager:
    """Tests for circuit breaker context manager usage."""

    def test_context_manager_success(self):
        """Context manager records success."""
        breaker = CircuitBreaker()

        with breaker:
            pass  # Successful operation

        # Should still be closed
        assert breaker.state == CircuitBreaker.CLOSED

    def test_context_manager_failure(self):
        """Context manager records failure."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config)

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("fail")

        # Should be open after failure
        assert breaker.state == CircuitBreaker.OPEN

    def test_context_manager_raises_when_open(self):
        """Context manager raises CircuitBreakerOpen when open."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config)

        breaker.record_failure()  # Open the circuit

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            with breaker:
                pass

        assert breaker.name in str(exc_info.value)

    def test_context_manager_exception_not_suppressed(self):
        """Context manager doesn't suppress exceptions."""
        breaker = CircuitBreaker()

        with pytest.raises(ValueError) as exc_info:
            with breaker:
                raise ValueError("test error")

        assert "test error" in str(exc_info.value)


# =============================================================================
# CircuitBreaker Reset Tests
# =============================================================================

class TestCircuitBreakerReset:
    """Tests for circuit breaker reset functionality."""

    def test_manual_reset(self):
        """Can manually reset circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config)

        breaker.record_failure()
        assert breaker.state == CircuitBreaker.OPEN

        breaker.reset()

        assert breaker.state == CircuitBreaker.CLOSED
        assert breaker.allow_request() is True

    def test_reset_clears_failure_count(self):
        """Reset clears failure count."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # Record some failures
        breaker.record_failure()
        breaker.record_failure()

        breaker.reset()

        # Should need full threshold again
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitBreaker.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitBreaker.OPEN


# =============================================================================
# CircuitBreakerOpen Exception Tests
# =============================================================================

class TestCircuitBreakerOpenException:
    """Tests for CircuitBreakerOpen exception."""

    def test_exception_message(self):
        """Exception has informative message."""
        exc = CircuitBreakerOpen("test-breaker", 10.5)

        assert "test-breaker" in str(exc)
        assert "10.5" in str(exc)

    def test_exception_attributes(self):
        """Exception stores name and time remaining."""
        exc = CircuitBreakerOpen("test", 5.0)

        assert exc.name == "test"
        assert exc.time_remaining == 5.0

    def test_negative_time_clamped(self):
        """Negative time remaining is clamped to 0."""
        exc = CircuitBreakerOpen("test", -5.0)
        assert exc.time_remaining == 0


# =============================================================================
# CircuitBreaker Named Instance Tests
# =============================================================================

class TestCircuitBreakerNaming:
    """Tests for named circuit breaker instances."""

    def test_custom_name(self):
        """Circuit breaker stores custom name."""
        breaker = CircuitBreaker(name="api-calls")
        assert breaker.name == "api-calls"

    def test_default_name(self):
        """Circuit breaker has default name."""
        breaker = CircuitBreaker()
        assert breaker.name == "default"

    def test_name_in_exception(self):
        """Name appears in CircuitBreakerOpen exception."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config, name="my-service")

        breaker.record_failure()

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            with breaker:
                pass

        assert "my-service" in str(exc_info.value)
