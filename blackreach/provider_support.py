"""Shared provider settings and safe transport-error classification.

Never include SDK exception text or response bodies in user-visible errors: they
can contain request data, credentials, and provider-generated content.
"""
import math
from typing import Any

from blackreach.exceptions import ProviderError

REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


def settings_errors(settings: Any) -> list[str]:
    """Validate request bounds without reading credentials or contacting a service."""
    errors = []
    for name, low, high in [("max_tokens", 1, 131072), ("max_retries", 1, 10)]:
        value = getattr(settings, name)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            errors.append(f"{name} must be an integer between {low} and {high}")
    for name, low, high in [("timeout_seconds", 1, 600), ("retry_delay", 0, 60)]:
        value = getattr(settings, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            errors.append(f"{name} must be a finite number between {low} and {high}")
    if not isinstance(settings.api_mode, str) or settings.api_mode not in {"auto", "chat", "responses"}:
        errors.append("api_mode must be auto, chat, or responses")
    if not isinstance(settings.reasoning_effort, str) or settings.reasoning_effort not in REASONING_EFFORTS:
        errors.append("reasoning_effort must be none, minimal, low, medium, high, xhigh, or max")
    if settings.api_mode == "responses" and settings.provider.lower() != "openai":
        errors.append("api_mode=responses requires provider=openai")
    return errors


def provider_error(provider: str, code: str, reason: str, *, retryable: bool = False, status_code: int | None = None) -> ProviderError:
    error = ProviderError(provider, reason)
    error.details["code"] = code
    if status_code is not None:
        error.details["status_code"] = status_code
    # This flag is for the adapter's bounded retry loop. Final errors always have
    # recoverable=False so the browser agent cannot repeat exhausted requests.
    error.retryable = retryable
    return error


def classify_error(provider: str, exc: Exception) -> ProviderError:
    """Classify SDK/HTTP failures using safe metadata only; unknowns do not retry."""
    if isinstance(exc, ProviderError):
        return exc
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        status = getattr(exc, "code", None)  # Google ApiError
    status = status if isinstance(status, int) else None
    code = getattr(exc, "code", None)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error_body = body.get("error", body)
        if isinstance(error_body, dict):
            code = error_body.get("code", code)
    name = type(exc).__name__.lower()
    if isinstance(code, str) and code in {"insufficient_quota", "billing_hard_limit_reached", "billing_not_active", "usage_limit_reached"}:
        return provider_error(provider, "quota", "Provider quota or billing limit reached. Check account billing and limits.", status_code=status)
    if status == 401 or "authentication" in name:
        return provider_error(provider, "authentication", "Authentication failed. Check the selected provider's API key.", status_code=status)
    if status == 403 or "permissiondenied" in name:
        return provider_error(provider, "permission", "Access denied. Check project permissions and model access.", status_code=status)
    if status == 404 or code == "model_not_found" or "notfound" in name:
        return provider_error(provider, "model_not_found", "Model or endpoint unavailable. Check the model ID, base URL, and account access.", status_code=status)
    if status == 429 or "ratelimit" in name:
        return provider_error(provider, "rate_limit", "Provider rate limit reached. Wait before retrying or lower request frequency.", retryable=True, status_code=status)
    if status in {408, 504} or isinstance(exc, TimeoutError) or "timeout" in name:
        return provider_error(provider, "timeout", "Provider request timed out. Check connectivity or increase timeout_seconds.", retryable=True, status_code=status)
    if status in {409, 500, 502, 503, 529} or (status is not None and status >= 500):
        return provider_error(provider, "unavailable", "Provider temporarily unavailable. Retry later.", retryable=True, status_code=status)
    if status is not None and status >= 400:
        return provider_error(provider, "invalid_request", "Provider rejected the request. Check model, API mode, and request settings.", status_code=status)
    if isinstance(exc, ConnectionError) or name in {"apiconnectionerror", "connecterror", "connectionerror", "readerror", "remoteprotocolerror"}:
        return provider_error(provider, "connection", "Could not connect to the provider. Check connectivity and base URL.", retryable=True)
    return provider_error(provider, "provider_failure", "Provider request failed. Check the selected provider and request settings.")


def is_reasoning_model(model: str) -> bool:
    """Recognize model families, including snapshots, without altering custom IDs."""
    model = model.lower()
    return model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")) and "-chat" not in model
