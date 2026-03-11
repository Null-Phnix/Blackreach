# Cycle 4: Fix test isolation bug in ErrorRecovery singleton causing test timeouts

Started: 2026-01-25T13:23:06.197586

## Summary
Successfully fixed the test isolation bug that caused `test_handle_tracks_error_counts_by_category` to timeout when run with the full test suite. The root cause was global singleton state accumulation across tests. Additionally fixed a secondary issue where browser integration tests were timing out due to excessive content-waiting delays.

## Changes Made

### 1. Added reset function to ErrorRecovery singleton
**File:** `blackreach/error_recovery.py:481-485`

Added `reset_global_recovery()` function to allow tests to reset the global singleton state:
```python
def reset_global_recovery() -> None:
    """Reset the global error recovery instance (for testing)."""
    global _global_recovery
    _global_recovery = None
```

### 2. Created autouse fixture for global state reset
**File:** `tests/conftest.py:793-847`

Added an `autouse=True` fixture that automatically resets all singleton global state before and after each test:
- `reset_global_state()` - autouse fixture that runs for every test
- `_reset_all_singletons()` - helper that resets:
  - ErrorRecovery (`reset_global_recovery`)
  - RateLimiter (`reset_rate_limiter`)
  - TimeoutManager (`reset_timeout_manager`)
  - ParallelManager (`reset_parallel_manager`)

### 3. Added convenience fixtures for fresh singleton instances
**File:** `tests/conftest.py:850-873`

Added explicit fixtures for tests that need guaranteed fresh instances:
- `fresh_error_recovery` - provides a clean ErrorRecovery instance
- `fresh_rate_limiter` - provides a clean RateLimiter instance
- `fresh_timeout_manager` - provides a clean TimeoutManager instance

### 4. Fixed browser integration test timeouts
**File:** `tests/test_integration.py` (multiple locations)

Updated all `browser.goto()` calls in navigation and interaction tests to use `wait_for_content=False` for mock server pages, reducing test execution time from timeouts to passing:

- Lines 140, 148, 155, 162, 165, 170, 171, 180, 181, 191 (TestBrowserNavigation)
- Lines 219, 228, 235, 245, 253, 264, 274, 284, 294 (TestElementInteraction)
- Lines 311, 320, 329, 339 (TestPageInformation)
- Lines 356, 367 (TestScreenshot)
- Lines 438, 454 (TestErrorHandling)
- Lines 477, 487, 498, 511, 521, 533, 543, 552 (TestDebugTools)
- Lines 585, 623 (TestResultTracker, TestErrorCapturingWrapper)
- Lines 665 (TestDynamicContent)
- Lines 681, 690 (TestStealthMode)
- Lines 716, 727, 739, 751, 762 (TestExecuteCommand)
- Lines 876, 883, 894 (TestMockServer)

## Singletons Reviewed

| Module | Global Variable | Get Function | Reset Function |
|--------|-----------------|--------------|----------------|
| error_recovery.py | `_global_recovery` | `get_recovery()` | `reset_global_recovery()` (added) |
| rate_limiter.py | `_rate_limiter` | `get_rate_limiter()` | `reset_rate_limiter()` (existed) |
| timeout_manager.py | `_timeout_manager` | `get_timeout_manager()` | `reset_timeout_manager()` (existed) |
| parallel_ops.py | `_parallel_manager` | `get_parallel_manager()` | `reset_parallel_manager()` (existed) |
| resilience.py | N/A (CircuitBreaker is instance-based) | N/A | N/A |

## Tests
- Ran: 2492
- Passed: 2492
- Warnings: 3 (unrelated to our changes)
- Fixed:
  - `test_handle_tracks_error_counts_by_category` (singleton isolation)
  - `test_goto_handles_different_pages` (browser timeout)
  - All other browser integration tests that could have timed out

## Root Cause Analysis

### ErrorRecovery Timeout Issue
The `ErrorRecovery` class tracks `_consecutive_errors` which influences retry delays:
1. Each call to `handle()` increments `_consecutive_errors`
2. In `categorize()`, when `_consecutive_errors >= 3`, retry delay is doubled
3. In `_apply_strategy()`, `time.sleep()` is called with the calculated delay
4. Without isolation, previous test runs accumulate errors in the global singleton
5. Eventually delays exceed the 30-second test timeout

### Browser Navigation Timeout Issue
The `Hand.goto()` method has extensive content-waiting logic:
1. `wait_for_content=True` (default) triggers `_wait_for_dynamic_content()`
2. This method has multiple `time.sleep()` calls totaling up to 15+ seconds per navigation
3. Tests navigating multiple pages compounded these delays
4. Solution: Use `wait_for_content=False` for simple mock server pages

## Notes for Next Session
1. All singleton isolation issues are now fixed with autouse fixtures
2. Consider adding `wait_for_content=False` as default for test browser fixture
3. The `CircuitBreaker` class in `resilience.py` is instance-based, not a global singleton, so it doesn't need special reset handling
4. Monitor for any new singleton patterns added in future development


Completed: 2026-01-25T15:53:06.216350
