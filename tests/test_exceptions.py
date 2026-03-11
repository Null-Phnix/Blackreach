"""
Unit tests for blackreach/exceptions.py

Tests the exception hierarchy and error message formatting.
"""

import pytest
from blackreach.exceptions import (
    # Base
    BlackreachError,
    # Browser
    BrowserError,
    BrowserNotReadyError,
    BrowserUnhealthyError,
    BrowserRestartFailedError,
    ElementNotFoundError,
    NavigationError,
    DownloadError,
    TimeoutError,
    # LLM
    LLMError,
    ProviderError,
    ProviderNotInstalledError,
    ParseError,
    APIError,
    RateLimitError,
    # Agent
    AgentError,
    ActionError,
    UnknownActionError,
    InvalidActionArgsError,
    StuckError,
    MaxStepsExceededError,
    # Site
    SiteError,
    CaptchaError,
    LoginRequiredError,
    PaywallError,
    AccessDeniedError,
    # Config
    ConfigError,
    InvalidConfigError,
    # Network
    NetworkError,
    ConnectionError,
    SSLError,
    # Session
    SessionError,
    SessionNotFoundError,
    SessionCorruptedError,
)


# =============================================================================
# Base Exception Tests
# =============================================================================

class TestBlackreachError:
    """Tests for the base BlackreachError."""

    def test_basic_creation(self):
        """Can create error with just a message."""
        err = BlackreachError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"

    def test_with_details(self):
        """Error includes details in string representation."""
        err = BlackreachError("Error", details={"key": "value"})
        assert "key=value" in str(err)

    def test_recoverable_default_false(self):
        """Recoverable defaults to False."""
        err = BlackreachError("Error")
        assert err.recoverable is False

    def test_recoverable_explicit(self):
        """Can set recoverable explicitly."""
        err = BlackreachError("Error", recoverable=True)
        assert err.recoverable is True

    def test_details_default_empty_dict(self):
        """Details defaults to empty dict."""
        err = BlackreachError("Error")
        assert err.details == {}

    def test_inheritance(self):
        """BlackreachError inherits from Exception."""
        err = BlackreachError("Error")
        assert isinstance(err, Exception)


# =============================================================================
# Browser Error Tests
# =============================================================================

class TestBrowserErrors:
    """Tests for browser-related exceptions."""

    def test_browser_error_inheritance(self):
        """BrowserError inherits from BlackreachError."""
        err = BrowserError("Browser error")
        assert isinstance(err, BlackreachError)

    def test_browser_not_ready_default_message(self):
        """BrowserNotReadyError has default message."""
        err = BrowserNotReadyError()
        assert "wake()" in str(err)
        assert err.recoverable is True

    def test_browser_not_ready_custom_message(self):
        """BrowserNotReadyError accepts custom message."""
        err = BrowserNotReadyError("Custom message")
        assert str(err) == "Custom message"

    def test_browser_unhealthy_default_message(self):
        """BrowserUnhealthyError has default message."""
        err = BrowserUnhealthyError()
        assert "unresponsive" in str(err).lower()
        assert err.recoverable is True

    def test_browser_unhealthy_custom_message(self):
        """BrowserUnhealthyError accepts custom message."""
        err = BrowserUnhealthyError("Browser crashed")
        assert str(err) == "Browser crashed"

    def test_browser_restart_failed_default_message(self):
        """BrowserRestartFailedError has default message."""
        err = BrowserRestartFailedError()
        assert "restart" in str(err).lower()
        assert err.recoverable is False

    def test_browser_restart_failed_custom_message(self):
        """BrowserRestartFailedError accepts custom message."""
        err = BrowserRestartFailedError("Out of memory")
        assert str(err) == "Out of memory"

    def test_element_not_found_with_selector(self):
        """ElementNotFoundError with selector."""
        err = ElementNotFoundError(selector="#my-button")
        assert "#my-button" in str(err)
        assert err.details["selector"] == "#my-button"
        assert err.recoverable is True

    def test_element_not_found_with_text(self):
        """ElementNotFoundError with text."""
        err = ElementNotFoundError(text="Click me")
        assert "Click me" in str(err)
        assert err.details["text"] == "Click me"

    def test_element_not_found_with_url(self):
        """ElementNotFoundError includes URL in details."""
        err = ElementNotFoundError(selector="a", url="https://example.com")
        assert err.details["url"] == "https://example.com"

    def test_element_not_found_no_args(self):
        """ElementNotFoundError with no arguments uses default message."""
        err = ElementNotFoundError()
        assert "Element not found" in str(err)
        assert err.recoverable is True

    def test_navigation_error(self):
        """NavigationError formats correctly."""
        err = NavigationError("https://example.com", reason="DNS failure")
        assert "https://example.com" in str(err)
        assert "DNS failure" in str(err)
        assert err.recoverable is True

    def test_download_error_basic(self):
        """DownloadError basic formatting."""
        err = DownloadError("https://example.com/file.pdf")
        assert "https://example.com/file.pdf" in str(err)

    def test_download_error_with_status(self):
        """DownloadError with HTTP status code."""
        err = DownloadError("https://example.com/file.pdf", status_code=404)
        assert "404" in str(err)
        assert err.details["status_code"] == 404

    def test_download_error_with_reason(self):
        """DownloadError with reason."""
        err = DownloadError("https://example.com/file.pdf", reason="File too large")
        assert "File too large" in str(err)

    def test_timeout_error(self):
        """TimeoutError formats correctly."""
        err = TimeoutError("Page load", 30.0)
        assert "Page load" in str(err)
        assert "30" in str(err)
        assert err.details["timeout"] == 30.0


# =============================================================================
# LLM Error Tests
# =============================================================================

class TestLLMErrors:
    """Tests for LLM-related exceptions."""

    def test_llm_error_inheritance(self):
        """LLMError inherits from BlackreachError."""
        err = LLMError("LLM error")
        assert isinstance(err, BlackreachError)

    def test_provider_error(self):
        """ProviderError formats correctly."""
        err = ProviderError("ollama", reason="Connection refused")
        assert "ollama" in str(err)
        assert "Connection refused" in str(err)
        assert err.recoverable is False

    def test_provider_not_installed(self):
        """ProviderNotInstalledError includes install instructions."""
        err = ProviderNotInstalledError("openai", "openai")
        assert "pip install openai" in str(err)
        assert err.details["package"] == "openai"

    def test_parse_error(self):
        """ParseError includes truncated raw response."""
        long_response = "x" * 1000
        err = ParseError(long_response, reason="Invalid JSON")
        assert "Invalid JSON" in str(err)
        assert len(err.details["raw_response"]) == 500  # Truncated
        assert err.recoverable is True

    def test_api_error(self):
        """APIError formats correctly."""
        err = APIError("openai", "authentication_error", "Invalid API key", 401)
        assert "openai" in str(err)
        assert "Invalid API key" in str(err)
        assert err.details["status_code"] == 401

    def test_rate_limit_error(self):
        """RateLimitError includes retry_after."""
        err = RateLimitError("anthropic", retry_after=60.0)
        assert "anthropic" in str(err)
        assert "60" in str(err)
        assert err.retry_after == 60.0

    def test_rate_limit_error_no_retry(self):
        """RateLimitError works without retry_after."""
        err = RateLimitError("openai")
        assert "openai" in str(err)
        assert err.retry_after is None


# =============================================================================
# Agent Error Tests
# =============================================================================

class TestAgentErrors:
    """Tests for agent-related exceptions."""

    def test_agent_error_inheritance(self):
        """AgentError inherits from BlackreachError."""
        err = AgentError("Agent error")
        assert isinstance(err, BlackreachError)

    def test_action_error(self):
        """ActionError formats correctly."""
        err = ActionError("click", "Element not visible", {"selector": "#btn"})
        assert "click" in str(err)
        assert "Element not visible" in str(err)
        assert err.details["args"]["selector"] == "#btn"
        assert err.recoverable is True

    def test_unknown_action_error(self):
        """UnknownActionError formats correctly."""
        err = UnknownActionError("invalid_action")
        assert "invalid_action" in str(err)
        assert "Unknown" in str(err)

    def test_invalid_action_args_error(self):
        """InvalidActionArgsError formats correctly."""
        err = InvalidActionArgsError("click", "Missing selector", {"text": None})
        assert "click" in str(err)
        assert "Missing selector" in str(err)

    def test_stuck_error_basic(self):
        """StuckError basic formatting."""
        err = StuckError()
        assert "stuck" in str(err).lower()
        assert err.recoverable is True

    def test_stuck_error_with_url(self):
        """StuckError with URL."""
        err = StuckError(url="https://example.com/page")
        assert "https://example.com/page" in str(err)

    def test_stuck_error_with_visits(self):
        """StuckError with consecutive visits."""
        err = StuckError(consecutive_visits=5)
        assert "5" in str(err)
        assert err.details["consecutive_visits"] == 5

    def test_max_steps_exceeded(self):
        """MaxStepsExceededError formats correctly."""
        err = MaxStepsExceededError(max_steps=50, current_step=51)
        assert "50" in str(err)
        assert "51" in str(err)
        assert err.recoverable is False


# =============================================================================
# Site Error Tests
# =============================================================================

class TestSiteErrors:
    """Tests for site-specific exceptions."""

    def test_site_error_inheritance(self):
        """SiteError inherits from BlackreachError."""
        err = SiteError("Site error")
        assert isinstance(err, BlackreachError)

    def test_captcha_error_basic(self):
        """CaptchaError basic formatting."""
        err = CaptchaError("https://example.com")
        assert "CAPTCHA" in str(err)
        assert err.details["url"] == "https://example.com"
        assert err.recoverable is True

    def test_captcha_error_with_type(self):
        """CaptchaError with captcha type."""
        err = CaptchaError("https://example.com", captcha_type="reCAPTCHA")
        assert "reCAPTCHA" in str(err)

    def test_login_required_error(self):
        """LoginRequiredError formats correctly."""
        err = LoginRequiredError("https://example.com/protected")
        assert "Login required" in str(err)
        assert err.recoverable is False

    def test_login_required_with_login_url(self):
        """LoginRequiredError includes login URL."""
        err = LoginRequiredError(
            "https://example.com/protected",
            login_url="https://example.com/login"
        )
        assert err.details["login_url"] == "https://example.com/login"

    def test_paywall_error(self):
        """PaywallError formats correctly."""
        err = PaywallError("https://example.com/premium")
        assert "Paywall" in str(err)
        assert err.recoverable is False

    def test_access_denied_error_basic(self):
        """AccessDeniedError basic formatting."""
        err = AccessDeniedError("https://example.com/admin")
        assert "Access denied" in str(err)
        assert err.recoverable is False

    def test_access_denied_with_status(self):
        """AccessDeniedError with HTTP status."""
        err = AccessDeniedError("https://example.com/admin", status_code=403)
        assert "403" in str(err)


# =============================================================================
# Config Error Tests
# =============================================================================

class TestConfigErrors:
    """Tests for configuration exceptions."""

    def test_config_error_basic(self):
        """ConfigError basic formatting."""
        err = ConfigError("Invalid configuration")
        assert "Invalid configuration" in str(err)
        assert err.recoverable is False

    def test_config_error_with_key(self):
        """ConfigError with config key."""
        err = ConfigError("Invalid value", config_key="timeout")
        assert err.details["config_key"] == "timeout"

    def test_invalid_config_error(self):
        """InvalidConfigError formats correctly."""
        err = InvalidConfigError("max_steps", -5, "positive integer")
        assert "max_steps" in str(err)
        assert "-5" in str(err)
        assert "positive integer" in str(err)


# =============================================================================
# Network Error Tests
# =============================================================================

class TestNetworkErrors:
    """Tests for network-related exceptions."""

    def test_network_error_basic(self):
        """NetworkError basic formatting."""
        err = NetworkError("Connection lost")
        assert "Connection lost" in str(err)
        assert err.recoverable is True

    def test_network_error_with_url(self):
        """NetworkError with URL."""
        err = NetworkError("Timeout", url="https://example.com")
        assert err.details["url"] == "https://example.com"

    def test_connection_error(self):
        """ConnectionError formats correctly."""
        err = ConnectionError("https://example.com", reason="ECONNREFUSED")
        assert "https://example.com" in str(err)
        assert "ECONNREFUSED" in str(err)

    def test_ssl_error(self):
        """SSLError formats correctly."""
        err = SSLError("https://expired-cert.example.com")
        assert "SSL" in str(err)
        assert "expired-cert.example.com" in str(err)


# =============================================================================
# Session Error Tests
# =============================================================================

class TestSessionErrors:
    """Tests for session-related exceptions."""

    def test_session_error_inheritance(self):
        """SessionError inherits from BlackreachError."""
        err = SessionError("Session error")
        assert isinstance(err, BlackreachError)

    def test_session_not_found(self):
        """SessionNotFoundError formats correctly."""
        err = SessionNotFoundError("abc123")
        assert "abc123" in str(err)
        assert err.details["session_id"] == "abc123"
        assert err.recoverable is False

    def test_session_corrupted(self):
        """SessionCorruptedError formats correctly."""
        err = SessionCorruptedError("abc123", reason="Invalid JSON")
        assert "abc123" in str(err)
        assert "Invalid JSON" in str(err)


# =============================================================================
# Hierarchy Tests
# =============================================================================

class TestExceptionHierarchy:
    """Tests for exception inheritance relationships."""

    def test_all_inherit_from_base(self):
        """All exceptions inherit from BlackreachError."""
        exceptions = [
            BrowserError("test"),
            BrowserNotReadyError(),
            BrowserUnhealthyError(),
            BrowserRestartFailedError(),
            ElementNotFoundError(selector="x"),
            NavigationError("url"),
            DownloadError("url"),
            TimeoutError("op", 1.0),
            LLMError("test"),
            ProviderError("p"),
            ParseError("raw"),
            APIError("p", "t", "m"),
            RateLimitError("p"),
            AgentError("test"),
            ActionError("a", "r"),
            StuckError(),
            MaxStepsExceededError(10, 11),
            SiteError("test"),
            CaptchaError("url"),
            LoginRequiredError("url"),
            PaywallError("url"),
            AccessDeniedError("url"),
            ConfigError("test"),
            InvalidConfigError("k", "v", "e"),
            NetworkError("test"),
            ConnectionError("url"),
            SSLError("url"),
            SessionError("test"),
            SessionNotFoundError("id"),
            SessionCorruptedError("id"),
        ]

        for exc in exceptions:
            assert isinstance(exc, BlackreachError), f"{type(exc).__name__} should inherit from BlackreachError"

    def test_browser_errors_inherit_from_browser_error(self):
        """Browser exceptions inherit from BrowserError."""
        exceptions = [
            BrowserNotReadyError(),
            BrowserUnhealthyError(),
            BrowserRestartFailedError(),
            ElementNotFoundError(selector="x"),
            NavigationError("url"),
            DownloadError("url"),
            TimeoutError("op", 1.0),
        ]

        for exc in exceptions:
            assert isinstance(exc, BrowserError)

    def test_llm_errors_inherit_from_llm_error(self):
        """LLM exceptions inherit from LLMError."""
        exceptions = [
            ProviderError("p"),
            ProviderNotInstalledError("p", "pkg"),
            ParseError("raw"),
            APIError("p", "t", "m"),
            RateLimitError("p"),
        ]

        for exc in exceptions:
            assert isinstance(exc, LLMError)

    def test_agent_errors_inherit_from_agent_error(self):
        """Agent exceptions inherit from AgentError."""
        exceptions = [
            ActionError("a", "r"),
            UnknownActionError("a"),
            InvalidActionArgsError("a", "r"),
            StuckError(),
            MaxStepsExceededError(10, 11),
        ]

        for exc in exceptions:
            assert isinstance(exc, AgentError)

    def test_site_errors_inherit_from_site_error(self):
        """Site exceptions inherit from SiteError."""
        exceptions = [
            CaptchaError("url"),
            LoginRequiredError("url"),
            PaywallError("url"),
            AccessDeniedError("url"),
        ]

        for exc in exceptions:
            assert isinstance(exc, SiteError)

    def test_can_catch_by_base_class(self):
        """Can catch multiple exception types with base class."""
        try:
            raise ElementNotFoundError(selector="#btn")
        except BrowserError as e:
            assert "#btn" in str(e)

        try:
            raise DownloadError("url")
        except BlackreachError as e:
            assert "url" in str(e)
