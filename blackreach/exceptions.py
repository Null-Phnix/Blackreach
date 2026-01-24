"""
Blackreach exception hierarchy.

All custom exceptions inherit from BlackreachError for easy catching.
Specific exception types allow for granular error handling.
"""

from typing import Optional, Any


# =============================================================================
# Base Exception
# =============================================================================

class BlackreachError(Exception):
    """Base exception for all Blackreach errors.

    Attributes:
        message: Human-readable error description
        details: Optional dict with additional context
        recoverable: Whether the error can potentially be recovered from
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        recoverable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.recoverable = recoverable

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


# =============================================================================
# Browser Errors
# =============================================================================

class BrowserError(BlackreachError):
    """Base class for browser-related errors."""
    pass


class BrowserNotReadyError(BrowserError):
    """Browser not initialized or not awake."""

    def __init__(self, message: str = "Browser is not ready. Call wake() first."):
        super().__init__(message, recoverable=True)


class BrowserUnhealthyError(BrowserError):
    """Browser is unresponsive or in an unhealthy state."""

    def __init__(self, message: str = "Browser is unresponsive."):
        super().__init__(message, recoverable=True)


class BrowserRestartFailedError(BrowserError):
    """Browser failed to restart after becoming unresponsive."""

    def __init__(self, message: str = "Failed to restart browser."):
        super().__init__(message, recoverable=False)


class ElementNotFoundError(BrowserError):
    """Target element could not be found on the page."""

    def __init__(
        self,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        url: Optional[str] = None
    ):
        details = {}
        if selector:
            details["selector"] = selector
        if text:
            details["text"] = text
        if url:
            details["url"] = url

        if selector:
            message = f"Element not found: {selector}"
        elif text:
            message = f"Element with text not found: {text}"
        else:
            message = "Element not found"

        super().__init__(message, details=details, recoverable=True)


class NavigationError(BrowserError):
    """Failed to navigate to a page."""

    def __init__(self, url: str, reason: Optional[str] = None):
        message = f"Failed to navigate to {url}"
        if reason:
            message += f": {reason}"
        super().__init__(message, details={"url": url}, recoverable=True)


class DownloadError(BrowserError):
    """Failed to download a file."""

    def __init__(
        self,
        url: str,
        reason: Optional[str] = None,
        status_code: Optional[int] = None
    ):
        details = {"url": url}
        message = f"Failed to download {url}"

        if status_code:
            details["status_code"] = status_code
            message += f" (HTTP {status_code})"
        if reason:
            message += f": {reason}"

        super().__init__(message, details=details, recoverable=True)


class TimeoutError(BrowserError):
    """Operation timed out."""

    def __init__(self, operation: str, timeout_seconds: float):
        message = f"{operation} timed out after {timeout_seconds}s"
        super().__init__(
            message,
            details={"operation": operation, "timeout": timeout_seconds},
            recoverable=True
        )


# =============================================================================
# LLM Errors
# =============================================================================

class LLMError(BlackreachError):
    """Base class for LLM-related errors."""
    pass


class ProviderError(LLMError):
    """Error with LLM provider configuration or availability."""

    def __init__(self, provider: str, reason: Optional[str] = None):
        message = f"LLM provider error: {provider}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, details={"provider": provider}, recoverable=False)


class ProviderNotInstalledError(ProviderError):
    """Required provider package is not installed."""

    def __init__(self, provider: str, package: str):
        message = f"Provider '{provider}' requires package '{package}'. Install with: pip install {package}"
        super().__init__(provider, message)
        self.details["package"] = package


class ParseError(LLMError):
    """Failed to parse LLM response."""

    def __init__(self, raw_response: str, reason: Optional[str] = None):
        message = "Failed to parse LLM response"
        if reason:
            message += f": {reason}"
        super().__init__(
            message,
            details={"raw_response": raw_response[:500]},  # Truncate for safety
            recoverable=True
        )


class APIError(LLMError):
    """Error from LLM API call."""

    def __init__(
        self,
        provider: str,
        error_type: str,
        message: str,
        status_code: Optional[int] = None
    ):
        details = {"provider": provider, "error_type": error_type}
        if status_code:
            details["status_code"] = status_code

        super().__init__(
            f"LLM API error ({provider}): {message}",
            details=details,
            recoverable=True
        )


class RateLimitError(APIError):
    """Rate limit exceeded on LLM API."""

    def __init__(
        self,
        provider: str,
        retry_after: Optional[float] = None
    ):
        details = {"provider": provider}
        message = f"Rate limit exceeded for {provider}"

        if retry_after:
            details["retry_after"] = retry_after
            message += f". Retry after {retry_after}s"

        super().__init__(provider, "rate_limit", message)
        self.retry_after = retry_after


# =============================================================================
# Agent Errors
# =============================================================================

class AgentError(BlackreachError):
    """Base class for agent-related errors."""
    pass


class ActionError(AgentError):
    """Error executing an action."""

    def __init__(
        self,
        action: str,
        reason: str,
        args: Optional[dict] = None
    ):
        details = {"action": action}
        if args:
            details["args"] = args

        message = f"Action '{action}' failed: {reason}"
        super().__init__(message, details=details, recoverable=True)


class UnknownActionError(ActionError):
    """Unknown action type."""

    def __init__(self, action: str):
        super().__init__(action, f"Unknown action type: {action}")


class InvalidActionArgsError(ActionError):
    """Action has invalid or missing arguments."""

    def __init__(self, action: str, reason: str, args: Optional[dict] = None):
        super().__init__(action, reason, args)


class StuckError(AgentError):
    """Agent appears to be stuck in a loop."""

    def __init__(
        self,
        url: Optional[str] = None,
        consecutive_visits: int = 0
    ):
        details = {"consecutive_visits": consecutive_visits}
        if url:
            details["url"] = url

        message = "Agent appears to be stuck"
        if url:
            message += f" on {url}"
        if consecutive_visits:
            message += f" ({consecutive_visits} consecutive visits)"

        super().__init__(message, details=details, recoverable=True)


class MaxStepsExceededError(AgentError):
    """Agent exceeded maximum allowed steps."""

    def __init__(self, max_steps: int, current_step: int):
        message = f"Exceeded maximum steps ({current_step}/{max_steps})"
        super().__init__(
            message,
            details={"max_steps": max_steps, "current_step": current_step},
            recoverable=False
        )


# =============================================================================
# Site/Content Errors
# =============================================================================

class SiteError(BlackreachError):
    """Base class for site-specific errors."""
    pass


class CaptchaError(SiteError):
    """CAPTCHA detected on the page."""

    def __init__(self, url: str, captcha_type: Optional[str] = None):
        details = {"url": url}
        message = "CAPTCHA detected"

        if captcha_type:
            details["captcha_type"] = captcha_type
            message += f" ({captcha_type})"

        super().__init__(message, details=details, recoverable=True)


class LoginRequiredError(SiteError):
    """Login wall detected."""

    def __init__(self, url: str, login_url: Optional[str] = None):
        details = {"url": url}
        message = "Login required to access this content"

        if login_url:
            details["login_url"] = login_url

        super().__init__(message, details=details, recoverable=False)


class PaywallError(SiteError):
    """Paywall detected."""

    def __init__(self, url: str):
        super().__init__(
            "Paywall detected - content requires subscription",
            details={"url": url},
            recoverable=False
        )


class AccessDeniedError(SiteError):
    """Access denied (403 or similar)."""

    def __init__(self, url: str, status_code: Optional[int] = None):
        details = {"url": url}
        message = "Access denied"

        if status_code:
            details["status_code"] = status_code
            message += f" (HTTP {status_code})"

        super().__init__(message, details=details, recoverable=False)


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigError(BlackreachError):
    """Configuration-related error."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, details=details, recoverable=False)


class InvalidConfigError(ConfigError):
    """Invalid configuration value."""

    def __init__(self, key: str, value: Any, expected: str):
        message = f"Invalid config value for '{key}': got {value!r}, expected {expected}"
        super().__init__(message, config_key=key)
        self.details["value"] = str(value)
        self.details["expected"] = expected


# =============================================================================
# Network Errors
# =============================================================================

class NetworkError(BlackreachError):
    """Network-related error."""

    def __init__(self, message: str, url: Optional[str] = None):
        details = {}
        if url:
            details["url"] = url
        super().__init__(message, details=details, recoverable=True)


class ConnectionError(NetworkError):
    """Failed to connect to server."""

    def __init__(self, url: str, reason: Optional[str] = None):
        message = f"Failed to connect to {url}"
        if reason:
            message += f": {reason}"
        super().__init__(message, url=url)


class SSLError(NetworkError):
    """SSL/TLS certificate error."""

    def __init__(self, url: str):
        super().__init__(f"SSL certificate error for {url}", url=url)


# =============================================================================
# Session Errors
# =============================================================================

class SessionError(BlackreachError):
    """Session management error."""
    pass


class SessionNotFoundError(SessionError):
    """Session not found for resume."""

    def __init__(self, session_id: str):
        super().__init__(
            f"Session not found: {session_id}",
            details={"session_id": session_id},
            recoverable=False
        )


class SessionCorruptedError(SessionError):
    """Session data is corrupted."""

    def __init__(self, session_id: str, reason: Optional[str] = None):
        message = f"Session data corrupted: {session_id}"
        if reason:
            message += f" - {reason}"
        super().__init__(
            message,
            details={"session_id": session_id},
            recoverable=False
        )
