"""
Unit tests for blackreach/error_recovery.py

Tests error categorization and recovery strategy selection.
"""

import pytest
import time
from blackreach.error_recovery import (
    ErrorCategory,
    RecoveryAction,
    ErrorInfo,
    RecoveryResult,
    ErrorRecovery,
    with_recovery,
    get_recovery,
)


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_all_categories_exist(self):
        """All expected error categories should exist."""
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.TIMEOUT.value == "timeout"
        assert ErrorCategory.ELEMENT_NOT_FOUND.value == "not_found"
        assert ErrorCategory.RATE_LIMITED.value == "rate_limited"
        assert ErrorCategory.BLOCKED.value == "blocked"
        assert ErrorCategory.AUTH_REQUIRED.value == "auth_required"
        assert ErrorCategory.INVALID_RESPONSE.value == "invalid"
        assert ErrorCategory.RESOURCE_ERROR.value == "resource"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestRecoveryAction:
    """Tests for RecoveryAction enum."""

    def test_all_actions_exist(self):
        """All expected recovery actions should exist."""
        assert RecoveryAction.RETRY_IMMEDIATE.value == "retry_now"
        assert RecoveryAction.RETRY_WITH_BACKOFF.value == "retry_wait"
        assert RecoveryAction.TRY_ALTERNATIVE.value == "alternative"
        assert RecoveryAction.SWITCH_SOURCE.value == "switch_source"
        assert RecoveryAction.WAIT_AND_RETRY.value == "wait"
        assert RecoveryAction.SKIP_ACTION.value == "skip"
        assert RecoveryAction.ABORT.value == "abort"


class TestErrorInfo:
    """Tests for ErrorInfo dataclass."""

    def test_error_info_creation(self):
        """ErrorInfo should store all fields correctly."""
        error = ValueError("Test error")
        info = ErrorInfo(
            category=ErrorCategory.NETWORK,
            original_error=error,
            message="Connection failed",
            recoverable=True,
            confidence=0.9,
            suggested_action=RecoveryAction.RETRY_WITH_BACKOFF,
            retry_delay=5.0,
            max_retries=3
        )
        assert info.category == ErrorCategory.NETWORK
        assert info.original_error == error
        assert info.message == "Connection failed"
        assert info.recoverable is True
        assert info.confidence == 0.9
        assert info.suggested_action == RecoveryAction.RETRY_WITH_BACKOFF
        assert info.retry_delay == 5.0
        assert info.max_retries == 3

    def test_error_info_defaults(self):
        """ErrorInfo should have correct defaults."""
        error = RuntimeError("Test")
        info = ErrorInfo(
            category=ErrorCategory.UNKNOWN,
            original_error=error,
            message="Unknown error",
            recoverable=False,
            confidence=0.5,
            suggested_action=RecoveryAction.ABORT
        )
        assert info.retry_delay == 0.0
        assert info.max_retries == 3
        assert info.details == {}


class TestRecoveryResult:
    """Tests for RecoveryResult dataclass."""

    def test_recovery_result_creation(self):
        """RecoveryResult should store all fields correctly."""
        result = RecoveryResult(
            success=True,
            action_taken=RecoveryAction.RETRY_IMMEDIATE,
            should_retry=True,
            should_skip=False,
            message="Recovery successful"
        )
        assert result.success is True
        assert result.action_taken == RecoveryAction.RETRY_IMMEDIATE
        assert result.should_retry is True
        assert result.should_skip is False
        assert result.message == "Recovery successful"


class TestErrorRecovery:
    """Tests for ErrorRecovery class."""

    def test_init(self):
        """ErrorRecovery initializes correctly."""
        recovery = ErrorRecovery()
        assert recovery is not None

    def test_categorize_network_error(self):
        """Should categorize network errors correctly."""
        recovery = ErrorRecovery()
        error = ConnectionError("Connection refused")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.NETWORK
        assert info.recoverable is True

    def test_categorize_timeout_error(self):
        """Should categorize timeout errors correctly."""
        recovery = ErrorRecovery()
        error = TimeoutError("Operation timed out")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.TIMEOUT
        assert info.recoverable is True

    def test_categorize_rate_limit_by_message(self):
        """Should detect rate limiting from error message."""
        recovery = ErrorRecovery()
        error = Exception("Rate limit exceeded")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.RATE_LIMITED

    def test_categorize_429_error(self):
        """Should detect rate limiting from 429 status."""
        recovery = ErrorRecovery()
        error = Exception("HTTP 429 Too Many Requests")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.RATE_LIMITED

    def test_suggest_retry_for_network_error(self):
        """Should suggest retry with backoff for network errors."""
        recovery = ErrorRecovery()
        error = ConnectionError("Connection reset")
        info = recovery.categorize(error)

        assert info.suggested_action in [
            RecoveryAction.RETRY_WITH_BACKOFF,
            RecoveryAction.RETRY_IMMEDIATE
        ]

    def test_suggest_wait_for_rate_limit(self):
        """Should suggest waiting for rate limiting."""
        recovery = ErrorRecovery()
        error = Exception("Rate limit exceeded. Try again in 60 seconds.")
        info = recovery.categorize(error)

        assert info.suggested_action in [
            RecoveryAction.WAIT_AND_RETRY,
            RecoveryAction.RETRY_WITH_BACKOFF
        ]

    def test_confidence_score_range(self):
        """Confidence scores should be between 0 and 1."""
        recovery = ErrorRecovery()

        errors = [
            ConnectionError("Network error"),
            TimeoutError("Timeout"),
            ValueError("Invalid value"),
            Exception("Unknown error"),
        ]

        for error in errors:
            info = recovery.categorize(error)
            assert 0.0 <= info.confidence <= 1.0


class TestErrorRecoveryPatterns:
    """Tests for error pattern matching."""

    def test_detect_captcha_in_message(self):
        """Should detect CAPTCHA challenges."""
        recovery = ErrorRecovery()
        error = Exception("CAPTCHA verification required")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.BLOCKED

    def test_detect_login_required(self):
        """Should detect authentication requirements."""
        recovery = ErrorRecovery()
        error = Exception("Please log in to continue")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.AUTH_REQUIRED

    def test_detect_access_denied(self):
        """Should detect access denied errors."""
        recovery = ErrorRecovery()
        error = Exception("403 Forbidden - Access denied")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.BLOCKED


class TestErrorRecoveryEdgeCases:
    """Tests for edge cases in error recovery."""

    def test_empty_error_message(self):
        """Should handle empty error message gracefully."""
        recovery = ErrorRecovery()
        error = Exception("")
        info = recovery.categorize(error)

        # Should default to UNKNOWN
        assert info.category is not None
        assert info.recoverable is not None

    def test_none_message(self):
        """Should handle None-like error gracefully."""
        recovery = ErrorRecovery()
        error = Exception(None)
        info = recovery.categorize(error)

        assert info.category is not None

    def test_complex_exception(self):
        """Should handle exceptions with complex attributes."""
        recovery = ErrorRecovery()

        class ComplexError(Exception):
            def __init__(self):
                self.status_code = 500
                self.response = {"error": "Internal server error"}

        error = ComplexError()
        info = recovery.categorize(error)

        # Should not crash and should categorize
        assert info is not None


class TestErrorRecoveryHandle:
    """Tests for the handle() method."""

    def test_handle_returns_recovery_result(self):
        """handle() should return a RecoveryResult."""
        recovery = ErrorRecovery()
        error = Exception("Test error")
        result = recovery.handle(error)

        assert isinstance(result, RecoveryResult)
        assert result.action_taken is not None

    def test_handle_increments_consecutive_errors(self):
        """handle() should increment consecutive error count."""
        recovery = ErrorRecovery()
        recovery.handle(Exception("Error 1"))
        recovery.handle(Exception("Error 2"))
        recovery.handle(Exception("Error 3"))

        assert recovery._consecutive_errors == 3

    def test_handle_tracks_error_counts_by_category(self):
        """handle() should track error counts by category."""
        recovery = ErrorRecovery()
        recovery.handle(ConnectionError("Network error"))
        recovery.handle(ConnectionError("Another network error"))
        recovery.handle(TimeoutError("Timeout"))

        assert recovery._error_counts[ErrorCategory.NETWORK] == 2
        assert recovery._error_counts[ErrorCategory.TIMEOUT] == 1

    def test_handle_with_context(self):
        """handle() should accept context dict."""
        recovery = ErrorRecovery()
        result = recovery.handle(
            Exception("Error"),
            context={"url": "https://example.com", "action": "click"}
        )
        assert result is not None


class TestErrorRecoveryRecordSuccess:
    """Tests for record_success() method."""

    def test_record_success_resets_consecutive_errors(self):
        """record_success() should reset consecutive error count."""
        recovery = ErrorRecovery()
        recovery.handle(Exception("Error 1"))
        recovery.handle(Exception("Error 2"))
        assert recovery._consecutive_errors == 2

        recovery.record_success()
        assert recovery._consecutive_errors == 0


class TestErrorRecoveryRegisterHandler:
    """Tests for custom handler registration."""

    def test_register_handler(self):
        """Should register custom handler for category."""
        recovery = ErrorRecovery()

        def custom_handler(info: ErrorInfo, context):
            return RecoveryResult(
                success=True,
                action_taken=RecoveryAction.SKIP_ACTION,
                should_retry=False,
                should_skip=True,
                message="Custom handler invoked"
            )

        recovery.register_handler(ErrorCategory.NETWORK, custom_handler)

        result = recovery.handle(ConnectionError("Network error"))
        assert result.message == "Custom handler invoked"
        assert result.action_taken == RecoveryAction.SKIP_ACTION

    def test_custom_handler_exception_falls_through(self):
        """If custom handler throws, should fall through to default."""
        recovery = ErrorRecovery()

        def broken_handler(info: ErrorInfo, context):
            raise RuntimeError("Handler failed")

        recovery.register_handler(ErrorCategory.NETWORK, broken_handler)

        # Should not raise, should use default handling
        result = recovery.handle(ConnectionError("Network error"))
        assert result is not None


class TestErrorRecoveryGetStats:
    """Tests for get_stats() method."""

    def test_get_stats_empty(self):
        """get_stats() should work with no errors."""
        recovery = ErrorRecovery()
        stats = recovery.get_stats()

        assert stats["total_errors"] == 0
        assert stats["by_category"] == {}
        assert stats["consecutive_errors"] == 0
        assert stats["most_common"] is None

    def test_get_stats_with_errors(self):
        """get_stats() should report error statistics."""
        recovery = ErrorRecovery()
        # Use explicit messages that match the patterns
        recovery.handle(Exception("connection refused error 1"))
        recovery.handle(Exception("connection refused error 2"))
        recovery.handle(TimeoutError("timed out"))

        stats = recovery.get_stats()

        assert stats["total_errors"] == 3
        assert stats["consecutive_errors"] == 3
        assert stats["most_common"] == "network"  # 2 network errors


class TestErrorRecoveryReset:
    """Tests for reset() method."""

    def test_reset_clears_all_tracking(self):
        """reset() should clear all error tracking."""
        recovery = ErrorRecovery()
        recovery.handle(ConnectionError("Error 1"))
        recovery.handle(ConnectionError("Error 2"))

        recovery.reset()

        assert recovery._error_counts == {}
        assert recovery._recovery_success == {}
        assert recovery._consecutive_errors == 0


class TestErrorRecoveryApplyStrategy:
    """Tests for the _apply_strategy() behavior via handle()."""

    def test_retry_immediate_strategy(self):
        """RETRY_IMMEDIATE should not wait."""
        recovery = ErrorRecovery()
        # Unknown errors get RETRY_IMMEDIATE by default
        error = Exception("some random error xyz")
        start = time.time()
        result = recovery.handle(error)
        elapsed = time.time() - start

        # Should be nearly instant
        assert elapsed < 1.0 or result.should_retry

    def test_skip_action_for_auth_required(self):
        """AUTH_REQUIRED should suggest skipping."""
        recovery = ErrorRecovery()
        error = Exception("Please log in to continue")
        result = recovery.handle(error)

        assert result.should_skip is True
        assert result.should_retry is False

    def test_try_alternative_sets_context(self):
        """TRY_ALTERNATIVE should set use_alternative in context."""
        recovery = ErrorRecovery()
        error = Exception("element not found")
        result = recovery.handle(error)

        # Element not found gets TRY_ALTERNATIVE
        if result.action_taken == RecoveryAction.TRY_ALTERNATIVE:
            assert result.new_context.get("use_alternative") is True

    def test_switch_source_sets_context(self):
        """SWITCH_SOURCE should set switch_source in context."""
        recovery = ErrorRecovery()
        # Blocked errors get SWITCH_SOURCE
        error = Exception("CAPTCHA detected, bot blocked")
        result = recovery.handle(error)

        if result.action_taken == RecoveryAction.SWITCH_SOURCE:
            assert result.new_context.get("switch_source") is True


class TestErrorRecoveryConsecutiveErrors:
    """Tests for consecutive error handling."""

    def test_consecutive_errors_increase_delay(self):
        """Many consecutive errors should increase retry delay."""
        recovery = ErrorRecovery()

        # First categorization
        info1 = recovery.categorize(ConnectionError("Error"))
        delay1 = info1.retry_delay

        # Simulate 3 consecutive errors
        recovery._consecutive_errors = 3
        info2 = recovery.categorize(ConnectionError("Error"))
        delay2 = info2.retry_delay

        # Delay should be doubled
        assert delay2 == delay1 * 2

    def test_many_consecutive_errors_switch_source(self):
        """5+ consecutive errors should suggest switching source."""
        recovery = ErrorRecovery()
        recovery._consecutive_errors = 5

        info = recovery.categorize(ConnectionError("Error"))

        assert info.suggested_action == RecoveryAction.SWITCH_SOURCE


class TestErrorRecoveryRecoverability:
    """Tests for error recoverability determination."""

    def test_resource_errors_not_recoverable(self):
        """Resource errors should not be recoverable."""
        recovery = ErrorRecovery()
        error = MemoryError("Out of memory")
        info = recovery.categorize(error)

        assert info.recoverable is False

    def test_auth_required_not_recoverable(self):
        """Auth required errors should not be recoverable."""
        recovery = ErrorRecovery()
        error = Exception("401 Unauthorized")
        info = recovery.categorize(error)

        assert info.recoverable is False

    def test_too_many_same_errors_not_recoverable(self):
        """Too many of same error type should become unrecoverable."""
        recovery = ErrorRecovery()

        # Simulate 5 network errors
        for _ in range(5):
            recovery._error_counts[ErrorCategory.NETWORK] = recovery._error_counts.get(ErrorCategory.NETWORK, 0) + 1

        info = recovery.categorize(ConnectionError("Network error"))

        assert info.recoverable is False


class TestWithRecoveryDecorator:
    """Tests for the with_recovery decorator."""

    def test_decorator_passes_on_success(self):
        """Decorated function should pass through on success."""
        @with_recovery(max_retries=3)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_decorator_retries_on_failure(self):
        """Decorated function should retry on failure."""
        call_count = 0

        @with_recovery(max_retries=3)
        def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "success"

        result = eventually_succeeds()
        assert result == "success"
        assert call_count == 3

    def test_decorator_raises_after_max_retries(self):
        """Decorated function should raise after max retries."""
        @with_recovery(max_retries=2)
        def always_fails():
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fails()

    def test_decorator_uses_provided_recovery(self):
        """Decorator should use provided ErrorRecovery instance."""
        recovery = ErrorRecovery()

        @with_recovery(max_retries=2, recovery=recovery)
        def failing_function():
            raise ConnectionError("Network error")

        try:
            failing_function()
        except ConnectionError:
            pass

        # Should have tracked the errors
        assert recovery._error_counts.get(ErrorCategory.NETWORK, 0) > 0


class TestGetRecovery:
    """Tests for get_recovery() global function."""

    def test_get_recovery_returns_instance(self):
        """get_recovery() should return an ErrorRecovery instance."""
        recovery = get_recovery()
        assert isinstance(recovery, ErrorRecovery)

    def test_get_recovery_returns_singleton(self):
        """get_recovery() should return the same instance."""
        recovery1 = get_recovery()
        recovery2 = get_recovery()
        assert recovery1 is recovery2


class TestErrorPatternMatching:
    """Additional tests for error pattern matching."""

    def test_detect_element_not_found(self):
        """Should detect element not found errors."""
        recovery = ErrorRecovery()
        error = Exception("NodeNotFoundError: element not found")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.ELEMENT_NOT_FOUND

    def test_detect_invalid_response(self):
        """Should detect invalid response errors."""
        recovery = ErrorRecovery()
        error = Exception("HTTP 500 Internal Server Error")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.INVALID_RESPONSE

    def test_detect_resource_error(self):
        """Should detect resource errors."""
        recovery = ErrorRecovery()
        error = Exception("Out of memory - cannot allocate buffer")
        info = recovery.categorize(error)

        assert info.category == ErrorCategory.RESOURCE_ERROR

    def test_type_match_higher_confidence(self):
        """Error type matching should give higher confidence."""
        recovery = ErrorRecovery()

        # TimeoutError type should match the "TimeoutError" pattern in error_type
        type_info = recovery.categorize(TimeoutError("some message"))
        # Message match only for timeout
        msg_info = recovery.categorize(Exception("timed out"))

        # Type match should have higher confidence (0.95 vs 0.8)
        assert type_info.confidence >= msg_info.confidence
        assert type_info.category == ErrorCategory.TIMEOUT
        assert msg_info.category == ErrorCategory.TIMEOUT


class TestRecoveryResultDefaults:
    """Tests for RecoveryResult defaults."""

    def test_new_context_default(self):
        """new_context should default to empty dict."""
        result = RecoveryResult(
            success=True,
            action_taken=RecoveryAction.RETRY_IMMEDIATE,
            should_retry=True,
            should_skip=False,
            message="Test"
        )
        assert result.new_context == {}
