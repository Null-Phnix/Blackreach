# Blackreach Testing & Error Handling - Phase 3

## Overview

This document covers the test infrastructure and error handling improvements made as part of the Alpha → Beta transition (Package A: Foundation).

**Completed:** January 22, 2026
**Total Tests:** 284
**Milestones Completed:** 1 (Tests) and 3 (Error Handling)

---

## Test Infrastructure

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_memory.py       # 38 tests
├── test_observer.py     # 54 tests
├── test_llm.py          # 31 tests
├── test_browser.py      # 23 tests
├── test_agent_e2e.py    # 16 tests
├── test_exceptions.py   # 56 tests
├── test_detection.py    # 38 tests
└── test_resilience.py   # 28 tests
```

### Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["blackreach"]
```

### Key Fixtures (conftest.py)

- `temp_dir` - Temporary directory for test files
- `download_dir` - Download directory fixture
- `memory_db` - In-memory SQLite for testing
- `simple_html` - Basic HTML page
- `arxiv_search_html` - ArXiv search results mock
- `github_repo_html` - GitHub repo page mock
- `mock_llm_responses` - Sequence of LLM responses
- `mock_browser` - Mocked Hand instance

---

## Exception Hierarchy

### Base Exception

```python
class BlackreachError(Exception):
    """Base exception for all Blackreach errors."""

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        recoverable: bool = False
    ):
        self.message = message
        self.details = details or {}
        self.recoverable = recoverable
```

### Browser Errors

| Exception | When Raised | Recoverable |
|-----------|-------------|-------------|
| `BrowserNotReadyError` | Browser not initialized | Yes |
| `ElementNotFoundError` | Target element missing | Yes |
| `NavigationError` | Page navigation failed | Yes |
| `DownloadError` | File download failed | Yes |
| `TimeoutError` | Operation timed out | Yes |

### LLM Errors

| Exception | When Raised | Recoverable |
|-----------|-------------|-------------|
| `ProviderError` | Provider misconfigured | No |
| `ProviderNotInstalledError` | Package not installed | No |
| `ParseError` | Response parsing failed | Yes |
| `APIError` | API call failed | Yes |
| `RateLimitError` | Rate limit exceeded | Yes |

### Agent Errors

| Exception | When Raised | Recoverable |
|-----------|-------------|-------------|
| `ActionError` | Action execution failed | Yes |
| `UnknownActionError` | Unknown action type | No |
| `InvalidActionArgsError` | Invalid action arguments | No |
| `StuckError` | Agent stuck in loop | Yes |
| `MaxStepsExceededError` | Max steps reached | No |

### Site Errors

| Exception | When Raised | Recoverable |
|-----------|-------------|-------------|
| `CaptchaError` | CAPTCHA detected | Yes |
| `LoginRequiredError` | Login wall detected | No |
| `PaywallError` | Paywall detected | No |
| `AccessDeniedError` | Access denied (403) | No |

---

## Site Detection Module

### SiteDetector Class

Detects various site conditions that may block agent progress:

```python
from blackreach.detection import SiteDetector

detector = SiteDetector()

# Individual detection
captcha = detector.detect_captcha(html, url)
login = detector.detect_login(html, url)
paywall = detector.detect_paywall(html, url)
rate_limit = detector.detect_rate_limit(html, url, status_code)
access_denied = detector.detect_access_denied(html, url, status_code)

# Combined detection (returns list sorted by confidence)
results = detector.detect_all(html, url, status_code)

# Detect and raise appropriate exception
detector.detect_and_raise(html, url, status_code)
```

### Detection Patterns

**CAPTCHA Detection:**
- Script URLs: `recaptcha/api.js`, `hcaptcha.com`, `challenges.cloudflare.com`
- Elements: `data-sitekey`, `g-recaptcha`, `h-captcha`, `cf-turnstile`
- Text: "verify you're not a robot", "security check"

**Login Detection:**
- URL patterns: `/login`, `/signin`, `/auth`
- Form elements: `type="password"`, `autocomplete="current-password"`
- Text: "sign in to continue", "must be logged in"

**Paywall Detection:**
- Classes: `paywall`, `premium-wall`, `subscribe-wall`
- Text: "subscribe to read", "premium content", "unlock this article"
- Visual: Blurred content (`filter: blur`)

**Rate Limit Detection:**
- HTTP status: 429
- Text: "too many requests", "rate limit", "try again later"

---

## Circuit Breaker Pattern

### Purpose

Prevents cascading failures by "tripping" after repeated failures, allowing operations to fail fast instead of wasting time retrying.

### States

1. **CLOSED** - Normal operation, requests allowed
2. **OPEN** - Failing fast, requests blocked
3. **HALF_OPEN** - Testing recovery, limited requests allowed

### Usage

```python
from blackreach.resilience import CircuitBreaker, CircuitBreakerConfig

# Configuration
config = CircuitBreakerConfig(
    failure_threshold=5,      # Failures before tripping
    recovery_timeout=30.0,    # Seconds before testing recovery
    half_open_max_calls=1     # Calls allowed in half-open
)

# Create breaker
breaker = CircuitBreaker(config, name="api-calls")

# Use as context manager
try:
    with breaker:
        result = risky_operation()
except CircuitBreakerOpen as e:
    # Handle fail-fast case
    print(f"Circuit open, retry in {e.time_remaining}s")
```

### State Transitions

```
                 success
    ┌──────────────────────────────┐
    │                              │
    ▼           failure            │
 CLOSED ─────────────────────► OPEN
    ▲          threshold           │
    │                              │
    │         recovery             │
    │         timeout              ▼
    │                         HALF_OPEN
    │                              │
    └──────────────────────────────┘
              success
```

---

## Error Handling Audit

### Changes Made

Fixed bare `except:` blocks across the codebase to prevent catching `SystemExit` and `KeyboardInterrupt`:

**browser.py:**
- `get_html()` - Wait for load state fallbacks
- `get_title()` - Navigation retry logic
- `wait_for_navigation()` - Load state fallbacks

**cli.py:**
- Memory stats loading (2 locations)

**resilience.py:**
- `find_by_text()` element lookup

### Before/After

```python
# Before (catches everything including Ctrl+C)
try:
    self.page.wait_for_load_state("networkidle")
except:
    pass

# After (only catches exceptions, not interrupts)
try:
    self.page.wait_for_load_state("networkidle")
except Exception:
    pass  # Continue anyway - page may be usable
```

---

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v

# Run specific module
python -m pytest tests/test_memory.py

# Run with coverage
python -m pytest tests/ --cov=blackreach --cov-report=html
```

---

## Test Coverage Summary

| Module | Tests | Coverage Focus |
|--------|-------|----------------|
| memory.py | 38 | SessionMemory, PersistentMemory, dedup |
| observer.py | 54 | HTML parsing, element extraction, caching |
| llm.py | 31 | Config, response parsing, provider init |
| browser.py | 23 | Hash computation, state management, mocks |
| agent e2e | 16 | Config, actions, memory integration |
| exceptions.py | 56 | Hierarchy, messages, recoverable flags |
| detection.py | 38 | CAPTCHA, login, paywall, rate limit |
| resilience.py | 28 | Retry, circuit breaker states/transitions |

---

## Next Steps

With Package A (Foundation) complete, the remaining work for Beta:

1. **Milestone 2: Session Resume** - Save/restore session state
2. **Milestone 4: Documentation** - Consolidated docs, quickstart guide
3. **Milestone 5: Reliability** - Site-specific improvements
4. **Milestone 6: Config System** - YAML config file support
