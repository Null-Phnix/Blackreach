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


# =============================================================================
# PopupHandler Constants Tests
# =============================================================================

class TestPopupHandlerConstants:
    """Tests for PopupHandler selector constants."""

    def test_cookie_selectors_not_empty(self):
        """Cookie selectors list is not empty."""
        from blackreach.resilience import PopupHandler
        assert len(PopupHandler.COOKIE_SELECTORS) > 0

    def test_close_selectors_not_empty(self):
        """Close selectors list is not empty."""
        from blackreach.resilience import PopupHandler
        assert len(PopupHandler.CLOSE_SELECTORS) > 0

    def test_cookie_selectors_are_strings(self):
        """All cookie selectors are strings."""
        from blackreach.resilience import PopupHandler
        for selector in PopupHandler.COOKIE_SELECTORS:
            assert isinstance(selector, str)

    def test_close_selectors_are_strings(self):
        """All close selectors are strings."""
        from blackreach.resilience import PopupHandler
        for selector in PopupHandler.CLOSE_SELECTORS:
            assert isinstance(selector, str)

    def test_cookie_selectors_include_common_patterns(self):
        """Cookie selectors include common accept buttons."""
        from blackreach.resilience import PopupHandler
        selectors_str = " ".join(PopupHandler.COOKIE_SELECTORS).lower()
        assert "accept" in selectors_str
        assert "agree" in selectors_str

    def test_close_selectors_include_close_buttons(self):
        """Close selectors include common close patterns."""
        from blackreach.resilience import PopupHandler
        selectors_str = " ".join(PopupHandler.CLOSE_SELECTORS).lower()
        assert "close" in selectors_str


# =============================================================================
# SmartSelector Basic Tests
# =============================================================================

class TestSmartSelectorBasic:
    """Basic tests for SmartSelector that don't require browser."""

    def test_smart_selector_import(self):
        """SmartSelector can be imported."""
        from blackreach.resilience import SmartSelector
        assert SmartSelector is not None

    def test_smart_selector_has_find_method(self):
        """SmartSelector has find method."""
        from blackreach.resilience import SmartSelector
        assert hasattr(SmartSelector, 'find')

    def test_smart_selector_has_find_by_text_method(self):
        """SmartSelector has find_by_text method."""
        from blackreach.resilience import SmartSelector
        assert hasattr(SmartSelector, 'find_by_text')


# =============================================================================
# WaitConditions Tests
# =============================================================================

class TestWaitConditionsBasic:
    """Basic tests for WaitConditions."""

    def test_wait_conditions_import(self):
        """WaitConditions can be imported."""
        from blackreach.resilience import WaitConditions
        assert WaitConditions is not None

    def test_wait_conditions_has_wait_for_url(self):
        """WaitConditions has wait_for_url method."""
        from blackreach.resilience import WaitConditions
        assert hasattr(WaitConditions, 'wait_for_url')

    def test_wait_conditions_has_wait_for_text(self):
        """WaitConditions has wait_for_text method."""
        from blackreach.resilience import WaitConditions
        assert hasattr(WaitConditions, 'wait_for_text')

    def test_wait_conditions_has_wait_for_network_idle(self):
        """WaitConditions has wait_for_network_idle method."""
        from blackreach.resilience import WaitConditions
        assert hasattr(WaitConditions, 'wait_for_network_idle')

    def test_wait_conditions_has_wait_for_element(self):
        """WaitConditions has wait_for_element method."""
        from blackreach.resilience import WaitConditions
        assert hasattr(WaitConditions, 'wait_for_element')

    def test_wait_conditions_has_wait_for_navigation(self):
        """WaitConditions has wait_for_navigation method."""
        from blackreach.resilience import WaitConditions
        assert hasattr(WaitConditions, 'wait_for_navigation')


# =============================================================================
# SmartSelector Method Tests (with mocks)
# =============================================================================

class TestSmartSelectorMethods:
    """Tests for SmartSelector methods with mocked Playwright objects."""

    def test_find_with_single_selector(self):
        """find() works with a single selector string."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=1000)
        result = selector.find("button.submit")

        assert result is not None
        mock_page.locator.assert_called()

    def test_find_with_list_of_selectors(self):
        """find() works with a list of selectors."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=1000)
        result = selector.find(["#id1", "#id2", "#id3"])

        assert result is not None

    def test_find_returns_none_when_no_match(self):
        """find() returns None when no element matches."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 0
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.side_effect = Exception("Timeout")
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=100)
        result = selector.find("nonexistent")

        assert result is None

    def test_find_input_by_name(self):
        """find_input() finds input by name."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_input(name="email")

        assert result is not None

    def test_find_input_by_placeholder(self):
        """find_input() finds input by placeholder."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_input(placeholder="Enter email")

        assert result is not None

    def test_find_input_by_label(self):
        """find_input() finds input by label."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_input(label="Username")

        assert result is not None

    def test_find_input_by_type(self):
        """find_input() finds input by type."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_input(input_type="password")

        assert result is not None

    def test_find_input_returns_none_without_params(self):
        """find_input() returns None when no parameters given."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        selector = SmartSelector(mock_page)
        result = selector.find_input()

        assert result is None

    def test_find_button_by_text(self):
        """find_button() finds button by text."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_button(text="Submit")

        assert result is not None

    def test_find_button_submit(self):
        """find_button() finds submit button."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_button(submit=True)

        assert result is not None

    def test_find_button_returns_none_without_params(self):
        """find_button() returns None when no parameters given."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        selector = SmartSelector(mock_page)
        result = selector.find_button()

        assert result is None


class TestSmartSelectorFindByText:
    """Tests for SmartSelector.find_by_text method."""

    def test_find_by_text_exact_match(self):
        """find_by_text() with exact=True."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.first = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.get_by_text.return_value = mock_locator
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=1000)
        result = selector.find_by_text("Click Here", exact=True)

        assert result is not None
        mock_page.get_by_text.assert_called_with("Click Here", exact=True)

    def test_find_by_text_partial_match(self):
        """find_by_text() with exact=False (default)."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.first = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.get_by_text.return_value = mock_locator
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=1000)
        result = selector.find_by_text("Click")

        assert result is not None
        mock_page.get_by_text.assert_called_with("Click", exact=False)

    def test_find_by_text_with_tag_filter(self):
        """find_by_text() filters by tag."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.get_by_text.return_value = mock_locator
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=1000)
        result = selector.find_by_text("Click", tag="button")

        assert result is not None
        mock_page.locator.assert_called_with("button")

    def test_find_by_text_timeout_returns_none(self):
        """find_by_text() returns None on timeout."""
        from blackreach.resilience import SmartSelector
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.first = mock_locator
        mock_locator.wait_for.side_effect = PlaywrightTimeout("Timeout")
        mock_page.get_by_text.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=100)
        result = selector.find_by_text("Nonexistent")

        assert result is None

    def test_find_by_text_fallback_on_error(self):
        """find_by_text() falls back to CSS selector on error."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.first = mock_locator
        mock_locator.wait_for.return_value = None

        # First call raises, second (fallback) succeeds
        mock_page.get_by_text.side_effect = Exception("Error")
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page, timeout=1000)
        result = selector.find_by_text("Test")

        assert result is not None
        mock_page.locator.assert_called()


# =============================================================================
# SmartSelector Link Finding Tests
# =============================================================================

class TestSmartSelectorFindLink:
    """Tests for SmartSelector.find_link method."""

    def test_find_link_by_text(self):
        """find_link() finds link by text."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_link(text="Download")

        assert result is not None

    def test_find_link_by_href_contains(self):
        """find_link() finds link by href pattern."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_link(href_contains="/download")

        assert result is not None

    def test_find_link_with_download_attr(self):
        """find_link() finds download links."""
        from blackreach.resilience import SmartSelector

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.count.return_value = 1
        mock_locator.first = mock_locator
        mock_locator.filter.return_value = mock_locator
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        selector = SmartSelector(mock_page)
        result = selector.find_link(download=True)

        assert result is not None


# =============================================================================
# PopupHandler Tests (with mocks)
# =============================================================================

class TestPopupHandlerMethods:
    """Tests for PopupHandler methods with mocked Playwright objects."""

    def test_popup_handler_init(self):
        """PopupHandler initializes correctly."""
        from blackreach.resilience import PopupHandler

        mock_page = Mock()
        handler = PopupHandler(mock_page)

        assert handler.page == mock_page

    def test_close_popups_no_popups(self):
        """close_popups() handles no popups gracefully."""
        from blackreach.resilience import PopupHandler

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.is_visible.return_value = False
        mock_locator.first = mock_locator
        mock_page.locator.return_value = mock_locator

        handler = PopupHandler(mock_page)
        count = handler.close_popups()

        assert count == 0

    def test_close_popups_clicks_close_buttons(self):
        """close_popups() clicks close buttons when visible."""
        from blackreach.resilience import PopupHandler

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.is_visible.return_value = True
        mock_locator.click.return_value = None
        mock_locator.first = mock_locator
        mock_page.locator.return_value = mock_locator

        handler = PopupHandler(mock_page)
        count = handler.close_popups()

        assert count > 0
        mock_locator.click.assert_called()

    def test_dismiss_cookie_banner_success(self):
        """dismiss_cookie_banner() clicks accept buttons when visible."""
        from blackreach.resilience import PopupHandler

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.is_visible.return_value = True
        mock_locator.click.return_value = None
        mock_locator.first = mock_locator
        mock_page.locator.return_value = mock_locator
        mock_page.frames = []

        handler = PopupHandler(mock_page)
        result = handler.dismiss_cookie_banner()

        assert result is True

    def test_dismiss_cookie_banner_no_banner(self):
        """dismiss_cookie_banner() returns False when no banner found."""
        from blackreach.resilience import PopupHandler

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.is_visible.return_value = False
        mock_locator.first = mock_locator
        mock_page.locator.return_value = mock_locator
        mock_page.frames = []
        mock_page.keyboard = Mock()

        handler = PopupHandler(mock_page)
        result = handler.dismiss_cookie_banner()

        assert result is False

    def test_handle_all_returns_dict(self):
        """handle_all() returns dictionary with results."""
        from blackreach.resilience import PopupHandler

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.is_visible.return_value = False
        mock_locator.first = mock_locator
        mock_page.locator.return_value = mock_locator
        mock_page.frames = []
        mock_page.keyboard = Mock()

        handler = PopupHandler(mock_page)
        result = handler.handle_all()

        assert isinstance(result, dict)
        assert "cookies_dismissed" in result
        assert "popups_closed" in result


# =============================================================================
# WaitConditions Tests (with mocks)
# =============================================================================

class TestWaitConditionsMethods:
    """Tests for WaitConditions methods with mocked Playwright objects."""

    def test_wait_conditions_init(self):
        """WaitConditions initializes correctly."""
        from blackreach.resilience import WaitConditions

        mock_page = Mock()
        waits = WaitConditions(mock_page)

        assert waits.page == mock_page

    def test_wait_for_url_success(self):
        """wait_for_url() waits for URL pattern."""
        from blackreach.resilience import WaitConditions

        mock_page = Mock()
        mock_page.wait_for_url.return_value = None

        waits = WaitConditions(mock_page)
        result = waits.wait_for_url("**/success**")

        assert result is True
        mock_page.wait_for_url.assert_called()

    def test_wait_for_url_timeout(self):
        """wait_for_url() returns False on timeout."""
        from blackreach.resilience import WaitConditions
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page = Mock()
        mock_page.wait_for_url.side_effect = PlaywrightTimeout("Timeout")

        waits = WaitConditions(mock_page)
        result = waits.wait_for_url("**/never**", timeout=100)

        assert result is False

    def test_wait_for_text_success(self):
        """wait_for_text() waits for text to appear."""
        from blackreach.resilience import WaitConditions

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.wait_for.return_value = None
        mock_page.get_by_text.return_value = mock_locator

        waits = WaitConditions(mock_page)
        result = waits.wait_for_text("Welcome")

        assert result is True

    def test_wait_for_text_timeout(self):
        """wait_for_text() returns False on timeout."""
        from blackreach.resilience import WaitConditions
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.wait_for.side_effect = PlaywrightTimeout("Timeout")
        mock_page.get_by_text.return_value = mock_locator

        waits = WaitConditions(mock_page)
        result = waits.wait_for_text("Never", timeout=100)

        assert result is False

    def test_wait_for_element_success(self):
        """wait_for_element() waits for element."""
        from blackreach.resilience import WaitConditions

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.wait_for.return_value = None
        mock_page.locator.return_value = mock_locator

        waits = WaitConditions(mock_page)
        result = waits.wait_for_element("#submit-btn")

        assert result is True

    def test_wait_for_element_timeout(self):
        """wait_for_element() returns False on timeout."""
        from blackreach.resilience import WaitConditions
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page = Mock()
        mock_locator = Mock()
        mock_locator.wait_for.side_effect = PlaywrightTimeout("Timeout")
        mock_page.locator.return_value = mock_locator

        waits = WaitConditions(mock_page)
        result = waits.wait_for_element("#nonexistent", timeout=100)

        assert result is False

    def test_wait_for_network_idle_success(self):
        """wait_for_network_idle() waits for network to settle."""
        from blackreach.resilience import WaitConditions

        mock_page = Mock()
        mock_page.wait_for_load_state.return_value = None

        waits = WaitConditions(mock_page)
        result = waits.wait_for_network_idle()

        assert result is True
        mock_page.wait_for_load_state.assert_called_with("networkidle", timeout=30000)

    def test_wait_for_network_idle_timeout(self):
        """wait_for_network_idle() returns False on timeout."""
        from blackreach.resilience import WaitConditions
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page = Mock()
        mock_page.wait_for_load_state.side_effect = PlaywrightTimeout("Timeout")

        waits = WaitConditions(mock_page)
        result = waits.wait_for_network_idle(timeout=100)

        assert result is False

    def test_wait_for_navigation_success(self):
        """wait_for_navigation() waits for page navigation."""
        from blackreach.resilience import WaitConditions

        mock_page = Mock()
        mock_page.wait_for_load_state.return_value = None

        waits = WaitConditions(mock_page)
        result = waits.wait_for_navigation()

        assert result is True

    def test_wait_for_navigation_timeout(self):
        """wait_for_navigation() returns False on timeout."""
        from blackreach.resilience import WaitConditions
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page = Mock()
        mock_page.wait_for_load_state.side_effect = PlaywrightTimeout("Timeout")

        waits = WaitConditions(mock_page)
        result = waits.wait_for_navigation(timeout=100)

        assert result is False


# =============================================================================
# CircuitBreaker Thread Safety Tests
# =============================================================================

class TestCircuitBreakerThreadSafety:
    """Tests for CircuitBreaker thread safety."""

    def test_has_lock_attribute(self):
        """CircuitBreaker should have a _lock attribute."""
        import threading
        breaker = CircuitBreaker()
        assert hasattr(breaker, '_lock')
        assert isinstance(breaker._lock, type(threading.Lock()))

    def test_concurrent_record_failures(self):
        """Concurrent record_failure calls should be atomic."""
        import threading
        import concurrent.futures

        config = CircuitBreakerConfig(failure_threshold=100)
        breaker = CircuitBreaker(config)

        num_threads = 10
        failures_per_thread = 10

        def record_failures():
            for _ in range(failures_per_thread):
                breaker.record_failure()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(record_failures) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # Should have exactly num_threads * failures_per_thread failures
        assert breaker._failure_count == num_threads * failures_per_thread

    def test_concurrent_record_success_resets_count(self):
        """Concurrent success after half-open should properly close circuit."""
        import threading
        import concurrent.futures

        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.001)
        breaker = CircuitBreaker(config)

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitBreaker.OPEN

        # Wait for half-open
        time.sleep(0.01)
        assert breaker.state == CircuitBreaker.HALF_OPEN

        # Record success from multiple threads
        def record_success():
            breaker.record_success()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(record_success) for _ in range(5)]
            concurrent.futures.wait(futures)

        # Circuit should be closed
        assert breaker.state == CircuitBreaker.CLOSED
        assert breaker._failure_count == 0

    def test_concurrent_allow_request_limits_half_open(self):
        """Concurrent allow_request in half-open should respect limits."""
        import threading
        import concurrent.futures

        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.001,
            half_open_max_calls=3
        )
        breaker = CircuitBreaker(config)

        # Open then half-open
        breaker.record_failure()
        time.sleep(0.01)
        assert breaker.state == CircuitBreaker.HALF_OPEN

        results = []
        lock = threading.Lock()

        def try_request():
            allowed = breaker.allow_request()
            with lock:
                results.append(allowed)

        # Try more requests than allowed
        num_threads = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(try_request) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # Exactly half_open_max_calls should be allowed
        allowed_count = sum(1 for r in results if r)
        assert allowed_count == config.half_open_max_calls

    def test_concurrent_state_transitions(self):
        """Concurrent state access should be consistent."""
        import threading
        import concurrent.futures

        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=0.01)
        breaker = CircuitBreaker(config)

        states_seen = []
        lock = threading.Lock()
        stop_event = threading.Event()

        def read_state():
            while not stop_event.is_set():
                state = breaker.state
                with lock:
                    states_seen.append(state)
                time.sleep(0.001)

        def modify_state():
            for _ in range(5):
                breaker.record_failure()
                time.sleep(0.005)
            time.sleep(0.02)  # Wait for half-open
            breaker.record_success()

        # Start readers
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            reader_futures = [executor.submit(read_state) for _ in range(5)]
            modifier_future = executor.submit(modify_state)

            # Wait for modifier to complete
            modifier_future.result()
            stop_event.set()

            # Wait for readers
            concurrent.futures.wait(reader_futures)

        # Verify all states seen are valid
        valid_states = {CircuitBreaker.CLOSED, CircuitBreaker.OPEN, CircuitBreaker.HALF_OPEN}
        assert all(s in valid_states for s in states_seen)

    def test_concurrent_context_manager_usage(self):
        """Concurrent context manager usage should be thread-safe."""
        import threading
        import concurrent.futures

        config = CircuitBreakerConfig(failure_threshold=100)
        breaker = CircuitBreaker(config)

        success_count = [0]
        count_lock = threading.Lock()

        def use_breaker():
            try:
                with breaker:
                    with count_lock:
                        success_count[0] += 1
                    time.sleep(0.001)
            except CircuitBreakerOpen:
                pass

        num_threads = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(use_breaker) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # All should succeed (threshold is 100)
        assert success_count[0] == num_threads

    def test_concurrent_reset_and_operations(self):
        """Reset during concurrent operations should be safe."""
        import threading
        import concurrent.futures

        config = CircuitBreakerConfig(failure_threshold=50)
        breaker = CircuitBreaker(config)

        def record_and_reset():
            for i in range(20):
                if i % 5 == 0:
                    breaker.reset()
                else:
                    breaker.record_failure()

        num_threads = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(record_and_reset) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # Should not raise any exceptions - state is consistent
        state = breaker.state
        assert state in {CircuitBreaker.CLOSED, CircuitBreaker.OPEN}
