# Code Quality Findings - Blackreach Project

**Review Date:** 2026-01-24
**Reviewer:** Claude Opus 4.5
**Session Duration:** 8 hours

---

## Summary

This document contains code quality findings from a comprehensive review of the Blackreach codebase.

---

## Findings

### Finding #1: Long Function - Agent.run()
**Location:** blackreach/agent.py:~200-500
**Severity:** High
**Description:** The `run()` method in the Agent class is extremely long (approximately 300+ lines). This method handles the entire ReAct loop including observation, thinking, acting, error recovery, and session management. The function complexity makes it difficult to test, maintain, and understand.
**Recommendation:** Refactor into smaller, focused methods: `_observe_page()`, `_think_about_action()`, `_execute_action()`, `_handle_step_error()`, etc.

### Finding #2: Missing Type Hints - SessionMemory Methods
**Location:** blackreach/memory.py:42-66
**Severity:** Medium
**Description:** Several methods in `SessionMemory` class lack return type hints. Methods like `add_download()`, `add_visit()`, `add_action()`, and `add_failure()` don't specify return types.
**Recommendation:** Add `-> None` return type hints to all void methods for consistency and static type checking.

### Finding #3: Magic Numbers in EyesConfig
**Location:** blackreach/observer.py:22-37
**Severity:** Low
**Description:** The `EyesConfig` dataclass contains magic numbers (8000, 50, 20, 20, 100) without explanation of why these specific values were chosen.
**Recommendation:** Add comments explaining the rationale for these limits or extract them as named constants with descriptive names.

### Finding #4: Bare Exception Handling in FileLogHandler
**Location:** blackreach/logging.py:244-245
**Severity:** High
**Description:** The `emit()` method catches `Exception` and silently passes. While the comment mentions not letting logging failures crash the application, this hides all errors including programming bugs.
**Recommendation:** At minimum, log to stderr or a fallback mechanism. Consider catching only specific exceptions like `IOError` and `OSError`.

### Finding #5: Duplicate Code in Config Validation
**Location:** blackreach/config.py:353-468
**Severity:** Medium
**Description:** Multiple validation methods (`_validate_provider`, `_validate_agent_settings`, `_validate_paths`, etc.) have similar patterns of adding errors/warnings to a result object. There's duplication in the validation logic structure.
**Recommendation:** Create a base validation helper or decorator pattern to reduce repetition.

### Finding #6: Missing Docstring - LLMResponse.is_valid
**Location:** blackreach/llm.py:42-44
**Severity:** Low
**Description:** The `is_valid` property lacks a docstring explaining what constitutes a "valid" response and when this property should be used.
**Recommendation:** Add docstring explaining the validation logic and use cases.

### Finding #7: Inconsistent Error Handling in LLM.generate()
**Location:** blackreach/llm.py:141-158
**Severity:** Medium
**Description:** The `generate()` method has a try/except block that catches all exceptions, but only re-raises on the last attempt. Earlier failures are silently swallowed without logging.
**Recommendation:** Add logging for retry attempts to aid debugging. Consider raising custom exceptions that wrap the original error.

### Finding #8: God Class - Hand (Browser Controller)
**Location:** blackreach/browser.py:263-1562
**Severity:** High
**Description:** The `Hand` class is approximately 1300 lines and handles too many responsibilities: browser lifecycle, navigation, clicking, typing, scrolling, downloading, screenshots, stealth injection, proxy management, and challenge detection.
**Recommendation:** Split into focused classes: `BrowserLifecycle`, `NavigationController`, `InputController`, `DownloadManager`, `StealthInjector`.

### Finding #9: Hardcoded User Agents May Become Outdated
**Location:** blackreach/stealth.py:45-63
**Severity:** Medium
**Description:** User agent strings are hardcoded with specific version numbers (Chrome 133, Firefox 134). These will become outdated over time and may trigger bot detection.
**Recommendation:** Consider a mechanism to update user agents dynamically or fetch them from an external source. Add a comment noting when they were last updated.

### Finding #10: Missing Input Validation in ProxyConfig.from_url()
**Location:** blackreach/browser.py:93-126
**Severity:** Medium
**Description:** The `from_url()` class method doesn't validate the URL format before parsing. Malformed URLs could cause unexpected behavior.
**Recommendation:** Add URL validation and raise `InvalidConfigError` for malformed proxy URLs.

### Finding #11: Bare Exception in retry_with_backoff Decorator
**Location:** blackreach/resilience.py:51-53
**Severity:** Medium
**Description:** The decorator catches bare `Exception`, which may catch exceptions that shouldn't be retried (like `KeyboardInterrupt`, `SystemExit`, or programming errors).
**Recommendation:** Create a list of retryable exceptions or use a base class for network-related errors.

### Finding #12: Complex Nested Logic in _wait_for_dynamic_content
**Location:** blackreach/browser.py:827-1000
**Severity:** High
**Description:** This method spans ~170 lines with 7+ different strategies, multiple nested loops, and try/except blocks. The complexity makes it hard to understand the control flow.
**Recommendation:** Extract each strategy into a separate method with clear naming. Create a strategy pattern or chain of responsibility.

### Finding #13: Duplicate Pattern Lists in SiteDetector
**Location:** blackreach/detection.py:46-166
**Severity:** Medium
**Description:** The `SiteDetector` class has multiple lists of regex patterns that could be consolidated. Some patterns are duplicated between `CAPTCHA_PATTERNS` and `CHALLENGE_PATTERNS`.
**Recommendation:** Create a shared base set of patterns and compose the specific lists from common patterns.

### Finding #14: Missing Error Context in ElementNotFoundError
**Location:** blackreach/exceptions.py:72-96
**Severity:** Low
**Description:** When `ElementNotFoundError` is raised, it could include more context like the current page title or a snippet of the page content to aid debugging.
**Recommendation:** Add optional `page_context` parameter to provide debugging information.

### Finding #15: Long Parameter Lists in detect_rate_limit
**Location:** blackreach/detection.py:297
**Severity:** Low
**Description:** The `detect_rate_limit` method takes `html`, `url`, and `status_code` as separate parameters. This pattern repeats across multiple detection methods.
**Recommendation:** Create a `PageContext` dataclass to bundle these related parameters.

### Finding #16: Inconsistent Naming - LogLevel.WARN vs WARNING
**Location:** blackreach/logging.py:41
**Severity:** Low
**Description:** `LogLevel` has both `WARNING = 30` and `WARN = 30` as an alias. This inconsistency can lead to confusion about which to use.
**Recommendation:** Choose one naming convention and deprecate the other with a clear message.

### Finding #17: Missing Cleanup in PersistentMemory
**Location:** blackreach/memory.py:679-683
**Severity:** Medium
**Description:** The `__del__` method attempts cleanup but may fail silently. If the connection wasn't properly initialized, this could cause issues during garbage collection.
**Recommendation:** Add a guard to check `self._conn` exists before calling `close()`. Consider using `weakref.ref` for more reliable cleanup.

### Finding #18: Hardcoded Timeout Values Throughout
**Location:** blackreach/browser.py:709, 719, 725, etc.
**Severity:** Medium
**Description:** Timeout values (45000, 15000, 10000, etc.) are hardcoded throughout the codebase rather than being configurable.
**Recommendation:** Add timeout configuration to `AgentConfig` or `StealthConfig` to allow tuning for different network conditions.

### Finding #19: Missing Thread Safety in GlobalLogger
**Location:** blackreach/logging.py:669-740
**Severity:** Medium
**Description:** `GlobalLogger` is a singleton but the `_log()` method doesn't use locking when writing. Multiple threads could interleave log entries.
**Recommendation:** Add thread synchronization using the existing `_lock` pattern from `FileLogHandler`.

### Finding #20: Unused Import in logging.py
**Location:** blackreach/logging.py:537-538
**Severity:** Low
**Description:** The `time` module is imported at the end of the file (line 538) rather than at the top with other imports. This breaks the standard import order convention.
**Recommendation:** Move the import to the top of the file with other imports.

### Finding #21: Complex Conditional in Agent Action Parsing
**Location:** blackreach/llm.py:248-286
**Severity:** Medium
**Description:** The `parse_action()` method has complex string manipulation with multiple fallback cases. The JSON extraction logic uses a broad regex that may match unintended JSON objects.
**Recommendation:** Consider using a more robust parsing approach or a dedicated JSON extraction library. Add unit tests for edge cases.

### Finding #22: Missing Docstrings in CLI Commands
**Location:** blackreach/cli.py:379-417
**Severity:** Low
**Description:** Several CLI commands like `list_resumable()` have minimal docstrings that don't explain the command's purpose or options clearly.
**Recommendation:** Add detailed docstrings that describe what each command does, its options, and example usage.

### Finding #23: Potential Resource Leak in API.get_page()
**Location:** blackreach/api.py:199-225
**Severity:** Medium
**Description:** The `get_page()` method creates a browser but doesn't close it. If called multiple times without using the context manager, this could leak browser processes.
**Recommendation:** Either auto-close the browser after `get_page()` or clearly document that users must call `close()`.

### Finding #24: Dead Code - BatchProcessor.add()
**Location:** blackreach/api.py:278-282
**Severity:** Medium
**Description:** The `add()` method returns an index but doesn't actually add anything to a queue. The comment says "Goals are processed immediately in current implementation" but the method does nothing useful.
**Recommendation:** Either implement the queuing functionality or remove the method.

### Finding #25: Inconsistent Return Types in Detection Methods
**Location:** blackreach/detection.py:177-360
**Severity:** Low
**Description:** All detection methods return `DetectionResult` but set `indicators` to `None` by default, then the `__post_init__` converts it to an empty list. This is inconsistent.
**Recommendation:** Always initialize `indicators` as an empty list in the method body before populating it.

### Finding #26: Overly Broad URL Blocking
**Location:** blackreach/stealth.py:76-80
**Severity:** Medium
**Description:** The `BLOCKED_DOMAINS` list contains partial patterns like "analytics.", "tracking.", "pixel." which could inadvertently block legitimate domains.
**Recommendation:** Use full domain matching or more specific patterns to avoid false positives.

### Finding #27: Missing Validation in Cookie Consent Handling
**Location:** blackreach/resilience.py:617-673
**Severity:** Medium
**Description:** The `dismiss_cookie_banner()` method tries many selectors without validating that the clicked element was actually a consent button. It could accidentally click important buttons.
**Recommendation:** Add validation that the button text/context indicates consent, not other actions.

### Finding #28: Hardcoded File Extensions
**Location:** blackreach/observer.py:319-328
**Severity:** Low
**Description:** The `DOWNLOAD_EXTENSIONS` set contains hardcoded file extensions. New file types would require code changes.
**Recommendation:** Move to configuration or allow runtime extension of supported types.

### Finding #29: Complex Method - _extract_links
**Location:** blackreach/observer.py:352-432
**Severity:** Medium
**Description:** The `_extract_links()` method is ~80 lines with complex scoring logic, multiple conditions, and several responsibilities (extraction, filtering, scoring, sorting).
**Recommendation:** Split into `_extract_raw_links()`, `_score_link()`, `_filter_links()`, and `_sort_links()`.

### Finding #30: Missing Rate Limit Backoff in LLM
**Location:** blackreach/llm.py:141-158
**Severity:** High
**Description:** When an LLM API call fails due to rate limiting, the retry logic uses a simple delay multiplication. It doesn't specifically handle rate limit errors which often include `retry-after` headers.
**Recommendation:** Check for `RateLimitError` specifically and use the provider's suggested retry time.

### Finding #31: Inconsistent Exception Import Styles
**Location:** blackreach/detection.py:17-24
**Severity:** Low
**Description:** Imports exceptions using `from blackreach.exceptions import (...)` but only uses them in `detect_and_raise()`. The other detect methods return `DetectionResult` instead.
**Recommendation:** Remove unused exception imports or document why they're imported.

### Finding #32: Missing SSL Certificate Validation Option
**Location:** blackreach/browser.py:510
**Severity:** Medium
**Description:** `ignore_https_errors: True` is hardcoded. While this helps with some sites, it could hide security issues and should be configurable.
**Recommendation:** Add an option to `StealthConfig` to control SSL error handling.

### Finding #33: Duplicate Session Initialization Logic
**Location:** blackreach/cli.py:284-298, 330-346
**Severity:** Medium
**Description:** The session initialization code for LLM and Agent configuration is duplicated between the resume and regular run paths.
**Recommendation:** Extract into a helper function like `_create_session(provider, model, cfg)`.

### Finding #34: Missing Input Sanitization in Selector Generation
**Location:** blackreach/resilience.py:517-571
**Severity:** High
**Description:** The `generate_selectors()` method doesn't sanitize the description input before using it in CSS selectors. Special characters could cause issues.
**Recommendation:** Sanitize or escape special characters in the description before generating selectors.

### Finding #35: Long CLI Interactive Mode
**Location:** blackreach/cli.py:1325-1616
**Severity:** High
**Description:** The `interactive_mode()` function is ~290 lines handling all interactive commands in a single function with many if/elif branches.
**Recommendation:** Use a command registry pattern or dispatch table to separate command handlers.

### Finding #36: Inconsistent Error Messages
**Location:** Multiple files
**Severity:** Low
**Description:** Error messages vary in style. Some use "Error:" prefix, others don't. Some include the problematic value, others don't.
**Recommendation:** Create an error message style guide and apply consistently. Consider i18n support.

### Finding #37: Missing Type Hints in StealthConfig
**Location:** blackreach/stealth.py:18-41
**Severity:** Low
**Description:** The `StealthConfig` dataclass has type hints for most fields but the tuple type for `typing_speed` could be more specific.
**Recommendation:** Use `Tuple[float, float]` instead of just `Tuple`.

### Finding #38: Circular Import Risk
**Location:** blackreach/__init__.py:1-65
**Severity:** Medium
**Description:** The `__init__.py` imports from many modules, creating a potential for circular imports if any of those modules import from the package.
**Recommendation:** Use lazy imports or restructure to reduce import coupling.

### Finding #39: Missing Context Manager for Browser
**Location:** blackreach/browser.py:263
**Severity:** Medium
**Description:** The `Hand` class doesn't implement `__enter__` and `__exit__` methods despite having `wake()` and `sleep()` lifecycle methods.
**Recommendation:** Add context manager support for automatic cleanup: `with Hand() as browser: ...`

### Finding #40: Inconsistent Method Naming
**Location:** blackreach/logging.py:361, 432-441
**Severity:** Low
**Description:** `warn` is an alias for `warning`, and `log_error` exists alongside `error`. This creates ambiguity about which to use.
**Recommendation:** Deprecate aliases with clear migration guidance.

### Finding #41: Complex Regular Expressions Without Comments
**Location:** blackreach/detection.py:46-76
**Severity:** Medium
**Description:** The CAPTCHA_PATTERNS list contains complex regex patterns without comments explaining what each pattern matches.
**Recommendation:** Add comments for each pattern or group related patterns with explanatory headers.

### Finding #42: Missing Boundary Checks in Pagination
**Location:** blackreach/observer.py:532-605
**Severity:** Medium
**Description:** The `_extract_pagination()` method doesn't validate that extracted page numbers are reasonable (e.g., not negative or absurdly large).
**Recommendation:** Add validation for extracted page numbers and handle edge cases.

### Finding #43: Hardcoded Challenge Wait Time
**Location:** blackreach/browser.py:766
**Severity:** Medium
**Description:** The `_wait_for_challenge_resolution()` method has a hardcoded 30-second max wait time that isn't configurable.
**Recommendation:** Add to configuration or pass as parameter.

### Finding #44: Missing Logging in Critical Paths
**Location:** blackreach/browser.py:1302-1370
**Severity:** Medium
**Description:** The `download_file()` method doesn't log download attempts, successes, or failures. This makes debugging download issues difficult.
**Recommendation:** Add debug logging for download lifecycle events.

### Finding #45: Inconsistent Null Handling
**Location:** blackreach/api.py:88-129
**Severity:** Low
**Description:** The `browse()` method uses `on_progress` callback but doesn't validate it's callable before using. Passing a non-callable would cause runtime errors.
**Recommendation:** Add `if callable(on_progress)` check.

### Finding #46: Missing Retry for Direct HTTP Downloads
**Location:** blackreach/browser.py:1401-1447
**Severity:** Medium
**Description:** The `_fetch_file_directly()` method doesn't retry on transient failures like connection timeouts.
**Recommendation:** Wrap in retry logic or use a library with built-in retry support.

### Finding #47: Potential Memory Leak in Cache
**Location:** blackreach/observer.py:74, 132-135
**Severity:** Medium
**Description:** The Eyes class cache uses a simple size limit but doesn't implement LRU eviction. Old entries are never removed once the cache is full.
**Recommendation:** Implement proper LRU cache using `functools.lru_cache` or `collections.OrderedDict`.

### Finding #48: Missing Validation in set_api_key
**Location:** blackreach/config.py:221-228
**Severity:** Medium
**Description:** The `set_api_key()` method doesn't validate the key format before saving, potentially storing invalid keys.
**Recommendation:** Add basic format validation matching the patterns in `ConfigValidator.API_KEY_PATTERNS`.

### Finding #49: Inconsistent Path Handling
**Location:** blackreach/config.py:21-23
**Severity:** Low
**Description:** `CONFIG_DIR` and `CONFIG_FILE` use `Path.home()` but other parts of the codebase use `Path("./...")`. This inconsistency could cause confusion.
**Recommendation:** Document the convention clearly and apply consistently.

### Finding #50: Long Exception Hierarchy
**Location:** blackreach/exceptions.py:1-444
**Severity:** Low
**Description:** The exception hierarchy is well-organized but the file is 444 lines. Some exception classes are very similar and could be consolidated.
**Recommendation:** Consider whether all exception types are necessary. Some could be combined with different error codes.

### Finding #51: Missing Type Hints in detect_all Return
**Location:** blackreach/detection.py:516
**Severity:** Low
**Description:** The `detect_all()` method is missing proper type hints for the return value.
**Recommendation:** Add `-> List[DetectionResult]` return type hint (already done but verify completeness).

### Finding #52: Duplicate Download Extension Checks
**Location:** blackreach/browser.py:1379-1386, blackreach/observer.py:319-328
**Severity:** Medium
**Description:** File extension lists for downloads are duplicated between the browser module and observer module.
**Recommendation:** Centralize in a constants module and import where needed.

### Finding #53: Complex JavaScript String Embedding
**Location:** blackreach/stealth.py:198-275
**Severity:** High
**Description:** JavaScript code is embedded as multi-line strings in Python, making it hard to maintain, test, and syntax-check.
**Recommendation:** Move JavaScript to separate `.js` files and load them at runtime, or use a template system.

### Finding #54: Missing Error Handling in Stealth Script Injection
**Location:** blackreach/browser.py:610-616
**Severity:** Medium
**Description:** If stealth script injection fails, no error is raised or logged. The browser continues without stealth.
**Recommendation:** Log warnings if script injection fails and consider retrying.

### Finding #55: Inconsistent Parameter Order
**Location:** blackreach/detection.py:177, 221, 264, 297, 336
**Severity:** Low
**Description:** Detection methods have inconsistent parameter order. Some have `html, url`, others have `html, url, status_code`.
**Recommendation:** Standardize parameter order across all detection methods.

### Finding #56: Missing Default for max_steps in validate_for_run
**Location:** blackreach/config.py:470-515
**Severity:** Low
**Description:** The `validate_for_run()` method checks `config.max_steps < 1` but doesn't check the upper bound like `_validate_agent_settings()` does.
**Recommendation:** Add consistent validation for both bounds.

### Finding #57: Unclear Magic String in _get_selector
**Location:** blackreach/observer.py:664-694
**Severity:** Low
**Description:** The selector generation uses magic strings like `:has-text(...)` which are Playwright-specific without documentation.
**Recommendation:** Add comment noting these are Playwright pseudo-selectors.

### Finding #58: Missing Async Support in API
**Location:** blackreach/api.py:14
**Severity:** Medium
**Description:** The API module imports `asyncio` but doesn't provide async versions of the public methods.
**Recommendation:** Either implement async versions or remove the unused import.

### Finding #59: Hardcoded Retry Count
**Location:** blackreach/llm.py:26
**Severity:** Low
**Description:** `max_retries: int = 3` is hardcoded in `LLMConfig`. The optimal retry count varies by use case.
**Recommendation:** Document the default and explain when to adjust.

### Finding #60: Missing Cleanup in CircuitBreaker
**Location:** blackreach/resilience.py:77-177
**Severity:** Low
**Description:** The `CircuitBreaker` class doesn't have a way to persist state across restarts. A long-running issue could be forgotten on restart.
**Recommendation:** Consider optional persistence for production use.

### Finding #61: Complex Fuzzy Matching Logic
**Location:** blackreach/resilience.py:410-459
**Severity:** Medium
**Description:** The `find_fuzzy()` method iterates all visible elements which can be slow on large pages. There's no early exit optimization.
**Recommendation:** Add maximum element count check and early exit when a perfect match is found.

### Finding #62: Missing Input Validation in BrowseResult
**Location:** blackreach/api.py:17-27
**Severity:** Low
**Description:** `BrowseResult` dataclass doesn't validate that `pages_visited` and `steps_taken` are non-negative.
**Recommendation:** Add `__post_init__` validation for invariants.

### Finding #63: Inconsistent List Initialization
**Location:** blackreach/api.py:17-27
**Severity:** Low
**Description:** `BrowseResult` uses `field(default_factory=list)` for some fields but not for the parent classes' similar patterns.
**Recommendation:** Apply consistent patterns across all dataclasses.

### Finding #64: Missing Documentation for CONTENT_SOURCES
**Location:** blackreach/knowledge.py (referenced in __init__.py)
**Severity:** Medium
**Description:** `CONTENT_SOURCES` is exported but likely lacks documentation about its structure and how to extend it.
**Recommendation:** Add comprehensive documentation for the knowledge base format.

### Finding #65: Overly Permissive URL Pattern Matching
**Location:** blackreach/observer.py:331-342
**Severity:** Medium
**Description:** `DOWNLOAD_PATH_PATTERNS` includes very generic patterns like `/file/` which could match non-download URLs.
**Recommendation:** Make patterns more specific or require multiple indicators.

### Finding #66: Missing Timeout Parameter in SmartSelector.find
**Location:** blackreach/resilience.py:198-223
**Severity:** Low
**Description:** The `find()` method uses class-level timeout but doesn't allow per-call timeout override.
**Recommendation:** Add optional timeout parameter for flexibility.

### Finding #67: Complex Control Flow in dismiss_cookie_banner
**Location:** blackreach/resilience.py:617-673
**Severity:** Medium
**Description:** The method has multiple nested loops and try/except blocks making it hard to follow.
**Recommendation:** Refactor into smaller helper methods with clear responsibilities.

### Finding #68: Missing Docstring for CircuitBreakerOpen
**Location:** blackreach/resilience.py:179-185
**Severity:** Low
**Description:** The exception class has a message but no docstring explaining when it's raised.
**Recommendation:** Add docstring with usage examples.

### Finding #69: Inconsistent Version Strings
**Location:** blackreach/__init__.py:66, blackreach/cli.py:60
**Severity:** Low
**Description:** Version is defined in multiple places (`__version__` in `__init__.py` and `cli.py`).
**Recommendation:** Define in one place and import elsewhere.

### Finding #70: Hardcoded Chunk Sizes
**Location:** blackreach/browser.py:1489
**Severity:** Low
**Description:** File hash computation uses hardcoded 8192 byte chunks.
**Recommendation:** Extract as constant with explanation of the choice.

### Finding #71: Missing Type Annotation for _cache
**Location:** blackreach/observer.py:73
**Severity:** Low
**Description:** `self._cache: Dict[str, dict] = {}` uses generic `dict` instead of typed Dict.
**Recommendation:** Use `Dict[str, ParseResult]` or similar specific type.

### Finding #72: Unclear Method Purpose - force_render
**Location:** blackreach/browser.py:1002-1045
**Severity:** Medium
**Description:** The `force_render()` method name doesn't clearly indicate what triggers it's trying to force.
**Recommendation:** Rename to `trigger_lazy_load()` or `force_spa_render()` to be more descriptive.

### Finding #73: Missing Bounds Check in scroll
**Location:** blackreach/browser.py:1194-1211
**Severity:** Low
**Description:** The `scroll()` method accepts any `amount` value without validation that it's positive.
**Recommendation:** Add validation for `amount > 0`.

### Finding #74: Inconsistent Boolean Parameter Handling
**Location:** blackreach/browser.py:1067-1069
**Severity:** Low
**Description:** `human = human if human is not None else ...` pattern is repeated multiple times. Could use a helper.
**Recommendation:** Extract to a helper method like `_resolve_human_mode(human)`.

### Finding #75: Complex Download Handling Logic
**Location:** blackreach/browser.py:1312-1370
**Severity:** Medium
**Description:** The `download_file()` method handles both URL and selector-based downloads with different logic paths.
**Recommendation:** Split into `download_from_url()` and `download_via_selector()`.

### Finding #76: Missing Error Type in ProviderNotInstalledError
**Location:** blackreach/exceptions.py:161-167
**Severity:** Low
**Description:** The exception stores `package` in details but doesn't provide a method to retrieve it easily.
**Recommendation:** Add a property `required_package` for easy access.

### Finding #77: Redundant Condition Check
**Location:** blackreach/memory.py:44-47
**Severity:** Low
**Description:** In `add_download()`, `url` is checked separately from being added to the list. The condition could be simplified.
**Recommendation:** Combine the check: `if url and url not in self.downloaded_urls: self.downloaded_urls.append(url)`

### Finding #78: Missing Validation for provider_type
**Location:** blackreach/llm.py:60-75
**Severity:** Medium
**Description:** `_init_client()` sets `_provider_type` but if initialization fails, the type might be in an inconsistent state.
**Recommendation:** Set `_provider_type` only after successful initialization.

### Finding #79: Long Method - _call_google
**Location:** blackreach/llm.py:215-232
**Severity:** Low
**Description:** The `_call_google()` method creates a complex nested structure inline. This is harder to read than alternatives.
**Recommendation:** Build the request object in steps for clarity.

### Finding #80: Implicit Dependency on BeautifulSoup Parser
**Location:** blackreach/observer.py:100
**Severity:** Low
**Description:** Uses `html.parser` but `lxml` was commented out. The choice should be documented with performance implications.
**Recommendation:** Add comment explaining parser choice and when to change.

### Finding #81: Missing Max Retries in force_render
**Location:** blackreach/browser.py:1002-1045
**Severity:** Low
**Description:** The method doesn't limit how many times render forcing can be attempted.
**Recommendation:** Add retry limit parameter.

### Finding #82: Unclear Purpose of SiteHandlerExecutor
**Location:** blackreach/agent.py:38 (import)
**Severity:** Low
**Description:** `SiteHandlerExecutor` is imported but its role in the architecture isn't clear from context.
**Recommendation:** Add documentation explaining the handler pattern.

### Finding #83: Inconsistent Use of Optional
**Location:** blackreach/llm.py:18-29
**Severity:** Low
**Description:** `LLMConfig` uses `Optional[str]` for some fields but not others that could be None.
**Recommendation:** Review and apply Optional consistently.

### Finding #84: Complex State Management in ProxyRotator
**Location:** blackreach/browser.py:134-261
**Severity:** Medium
**Description:** `ProxyRotator` maintains multiple internal states (`_proxies`, `_health`, `_domain_sticky`, `_current_index`) that can become inconsistent.
**Recommendation:** Consider using a more immutable approach or add state validation methods.

### Finding #85: Missing Lock in ProxyRotator
**Location:** blackreach/browser.py:174-212
**Severity:** High
**Description:** `ProxyRotator.get_next()` modifies shared state without thread synchronization. Concurrent calls could cause race conditions.
**Recommendation:** Add thread lock for state modifications.

### Finding #86: Hardcoded GPU Layers
**Location:** blackreach/llm.py:29
**Severity:** Low
**Description:** `num_gpu_layers: int = 999` is a magic number meaning "all layers".
**Recommendation:** Define as a constant with a clear name like `GPU_ALL_LAYERS = -1` or document the 999 convention.

### Finding #87: Missing Validation in cleanup_old_logs
**Location:** blackreach/logging.py:562-570
**Severity:** Low
**Description:** `keep_days` parameter isn't validated. Negative values would keep nothing.
**Recommendation:** Add validation: `if keep_days < 0: raise ValueError(...)`.

### Finding #88: Complex Selector Building in find_input
**Location:** blackreach/resilience.py:283-315
**Severity:** Low
**Description:** Multiple selector strings are built conditionally. A builder pattern would be cleaner.
**Recommendation:** Create a `SelectorBuilder` helper class.

### Finding #89: Missing Type Hints in get_stats
**Location:** blackreach/memory.py:465-491
**Severity:** Low
**Description:** The `get_stats()` method returns a Dict but doesn't specify the value types.
**Recommendation:** Add proper type hint: `Dict[str, Union[int, str]]`.

### Finding #90: Inconsistent Method Return Types
**Location:** blackreach/browser.py:697-764
**Severity:** Low
**Description:** `goto()` returns a dict with several fields but the structure isn't documented or typed.
**Recommendation:** Create a `NavigationResult` dataclass for the return type.

### Finding #91: Missing Error Context in API browse
**Location:** blackreach/api.py:124-129
**Severity:** Medium
**Description:** When an exception occurs, only `str(e)` is captured in errors. Stack traces and exception types are lost.
**Recommendation:** Capture more error context for debugging.

### Finding #92: Duplicate Pattern Matching
**Location:** blackreach/detection.py:428-513
**Severity:** Medium
**Description:** `detect_download_landing()` has patterns that overlap with those in the observer module.
**Recommendation:** Centralize download-related patterns in one location.

### Finding #93: Complex Constructor in Hand
**Location:** blackreach/browser.py:275-336
**Severity:** Medium
**Description:** The `Hand` class constructor initializes many optional components, making it hard to understand the minimal vs full initialization.
**Recommendation:** Use builder pattern or factory method for complex initialization.

### Finding #94: Missing Timeout in is_healthy
**Location:** blackreach/browser.py:346-363
**Severity:** Low
**Description:** The health check accesses `page.url` and `page.title()` without timeouts. A hung browser could block indefinitely.
**Recommendation:** Add timeouts to health check operations.

### Finding #95: Undocumented Return Values
**Location:** blackreach/browser.py:1047-1063
**Severity:** Low
**Description:** Methods like `back()`, `forward()`, `refresh()` return dicts but the structure isn't documented.
**Recommendation:** Create typed return classes or document the dict structure.

### Finding #96: Inconsistent List/Set Usage
**Location:** blackreach/observer.py:354-355
**Severity:** Low
**Description:** `seen_hrefs` is a `Set[str]` but similar tracking in other methods uses lists.
**Recommendation:** Consistently use sets for membership checking.

### Finding #97: Missing Rate Limiting in Batch Operations
**Location:** blackreach/api.py:284-310
**Severity:** Medium
**Description:** `BatchProcessor.run_all()` runs goals sequentially without rate limiting between requests.
**Recommendation:** Add optional delay between operations to avoid overwhelming targets.

### Finding #98: Complex JSON Building in Session State
**Location:** blackreach/memory.py:578-610
**Severity:** Low
**Description:** The `save_session_state()` method does JSON serialization inline. Error handling is minimal.
**Recommendation:** Add try/except around JSON serialization with meaningful errors.

### Finding #99: Missing Database Migration Support
**Location:** blackreach/memory.py:126-219
**Severity:** Medium
**Description:** Database schema changes require manual migration. The `_init_db()` method doesn't handle schema evolution.
**Recommendation:** Add schema versioning and migration support.

### Finding #100: Inconsistent Exception Raising
**Location:** blackreach/config.py:227-228, 237, 246
**Severity:** Low
**Description:** Some methods raise `InvalidConfigError` while others might silently fail or return None.
**Recommendation:** Document expected behavior consistently and apply uniform error handling.

### Finding #101: Magic String in _clean_text
**Location:** blackreach/observer.py:696-702
**Severity:** Low
**Description:** The regex pattern `r'\s+'` is used without explanation of what whitespace normalization is applied.
**Recommendation:** Add comment explaining the normalization rules.

### Finding #102: Missing Validation in find_by_aria
**Location:** blackreach/resilience.py:373-394
**Severity:** Low
**Description:** The method doesn't validate that at least one of `label`, `role`, or `described_by` is provided.
**Recommendation:** Add validation: at least one parameter must be non-None.

### Finding #103: Complex Command Dispatch in CLI
**Location:** blackreach/cli.py:1368-1596
**Severity:** High
**Description:** Interactive mode uses a long chain of if/elif for command dispatch. This is hard to extend and maintain.
**Recommendation:** Use a command registry dictionary mapping commands to handler functions.

### Finding #104: Missing Docstrings in Browser Lifecycle
**Location:** blackreach/browser.py:365-386
**Severity:** Low
**Description:** `ensure_awake()` and `restart()` lack complete docstrings explaining their behavior and side effects.
**Recommendation:** Add comprehensive docstrings with usage examples.

### Finding #105: Unclear Error Recovery Strategy
**Location:** blackreach/browser.py:371-385
**Severity:** Medium
**Description:** The `ensure_awake()` method silently swallows sleep errors. The caller can't distinguish between "was already awake" and "recovered from error".
**Recommendation:** Return a status enum indicating what happened.

### Finding #106: Inconsistent Console Output
**Location:** blackreach/browser.py:715, 787, 824
**Severity:** Low
**Description:** Direct `print()` statements are mixed with the logging system. Some messages go to console, others to logs.
**Recommendation:** Use the logging system consistently for all output.

### Finding #107: Missing Validation in CircuitBreakerConfig
**Location:** blackreach/resilience.py:70-75
**Severity:** Low
**Description:** Configuration values aren't validated. Negative thresholds or timeouts would cause unexpected behavior.
**Recommendation:** Add `__post_init__` validation.

### Finding #108: Complex Frame Iteration
**Location:** blackreach/resilience.py:648-664
**Severity:** Low
**Description:** Cookie banner dismissal iterates all frames which can be slow on pages with many iframes.
**Recommendation:** Limit iteration to relevant frames or add early exit.

### Finding #109: Missing Cleanup on Script Error
**Location:** blackreach/browser.py:852-881
**Severity:** Low
**Description:** If the framework hydration JavaScript throws, no cleanup is performed.
**Recommendation:** Add finally block for cleanup or use safer evaluation.

### Finding #110: Hardcoded Patterns for Known Sites
**Location:** blackreach/observer.py:331-342
**Severity:** Medium
**Description:** Site-specific patterns like "Anna's Archive" and "LibGen" are hardcoded.
**Recommendation:** Move to a configurable site registry.

### Finding #111: Missing Thread Safety in Session Memory
**Location:** blackreach/memory.py:27-96
**Severity:** Medium
**Description:** `SessionMemory` is modified by multiple methods without synchronization, but may be accessed from callbacks.
**Recommendation:** Add thread safety or document single-threaded requirement.

### Finding #112: Complex Constructor in SessionLogger
**Location:** blackreach/logging.py:266-306
**Severity:** Medium
**Description:** The constructor does too much: creates directory, creates file, initializes handlers, and writes initial entry.
**Recommendation:** Split into initialization phases with separate methods.

### Finding #113: Undocumented Event Names
**Location:** blackreach/logging.py:389-469
**Severity:** Medium
**Description:** Event names like "step_start", "observe", "think", "act" are used but not documented as a schema.
**Recommendation:** Create an event schema documentation or enum.

### Finding #114: Missing Timeout in timed_operation
**Location:** blackreach/logging.py:475-509
**Severity:** Low
**Description:** The context manager doesn't have a timeout option. Long operations could run indefinitely.
**Recommendation:** Add optional timeout parameter.

### Finding #115: Complex Size Formatting Logic
**Location:** blackreach/cli.py:1067-1072, 1089-1095
**Severity:** Low
**Description:** File size formatting logic is duplicated in multiple places.
**Recommendation:** Use a shared utility function for size formatting.

### Finding #116: Missing Input Validation in click
**Location:** blackreach/browser.py:1067-1101
**Severity:** Low
**Description:** The `click()` method doesn't validate that `selector` is not empty.
**Recommendation:** Add validation: `if not selector: raise ValueError(...)`.

### Finding #117: Inconsistent Use of Constants
**Location:** blackreach/observer.py:52-56
**Severity:** Low
**Description:** `REMOVE_TAGS` is a set but `MAIN_CONTENT_TAGS` is also a set while being used differently.
**Recommendation:** Document the different uses or unify the pattern.

### Finding #118: Missing Error Handling in _extract_pagination
**Location:** blackreach/observer.py:532-605
**Severity:** Low
**Description:** Integer conversion of page numbers can fail but there's no error handling.
**Recommendation:** Add try/except around int() conversions.

### Finding #119: Unclear Purpose of debug_html
**Location:** blackreach/observer.py:138-176
**Severity:** Low
**Description:** The `debug_html()` method returns debugging info but it's not clear when to use it.
**Recommendation:** Add docstring explaining the use case and when to call.

### Finding #120: Complex Scoring Logic
**Location:** blackreach/observer.py:369-428
**Severity:** Medium
**Description:** Link scoring uses magic numbers (100, 75, 50, 25, 15, 30, 20, 40, 50) without explanation.
**Recommendation:** Extract to named constants with documentation explaining the scoring rationale.

### Finding #121: Missing Validation in type() Method
**Location:** blackreach/browser.py:1103-1181
**Severity:** Low
**Description:** The `type()` method doesn't validate that `text` is not None or empty.
**Recommendation:** Add validation for the text parameter.

### Finding #122: Inconsistent Return Dict Structure
**Location:** blackreach/browser.py
**Severity:** Medium
**Description:** Action methods return dicts with varying structures. Some have "action" key, some have more fields.
**Recommendation:** Define a consistent `ActionResult` type for all action methods.

### Finding #123: Missing Cleanup in get_pending_downloads
**Location:** blackreach/browser.py:1457-1459
**Severity:** Low
**Description:** Returns a copy of pending downloads but doesn't clear old completed downloads.
**Recommendation:** Add method to clear old entries or implement auto-cleanup.

### Finding #124: Complex Content Verification
**Location:** blackreach/browser.py:938-978
**Severity:** Medium
**Description:** Content verification JavaScript is a large inline string with complex logic.
**Recommendation:** Move to external JavaScript file and test separately.

### Finding #125: Missing Documentation for Public API
**Location:** blackreach/api.py
**Severity:** Medium
**Description:** The public API functions (`browse()`, `download()`, `search()`, `get_page()`) have minimal documentation.
**Recommendation:** Add comprehensive docstrings with examples and error handling guidance.

### Finding #126: Bare Exception Handler in import_history
**Location:** blackreach/download_history.py:441-442
**Severity:** Medium
**Description:** The `import_history()` method catches bare `Exception` and continues with a simple `continue` statement. This hides potentially important errors during import, making debugging difficult.
**Recommendation:** Log the exception with entry details, or collect errors and return them. Consider raising for critical failures.

### Finding #127: SQL Injection Risk with f-string in search_history
**Location:** blackreach/download_history.py:298-299
**Severity:** High
**Description:** The `search_history()` method constructs SQL query using f-string: `f"SELECT * FROM download_history WHERE {where_clause}"`. While the where_clause is built from parameterized conditions, this pattern is fragile and could lead to SQL injection if modified carelessly.
**Recommendation:** Use a query builder pattern or ensure the where_clause construction is always parameterized. Add explicit documentation about the security model.

### Finding #128: Missing Connection Context Manager Pattern
**Location:** blackreach/download_history.py:114-116
**Severity:** Low
**Description:** The `_get_connection()` method returns a raw connection. Callers use `with self._get_connection() as conn:` but rely on implicit behavior rather than explicit resource management.
**Recommendation:** Consider implementing a context manager wrapper that ensures proper cleanup, or document the expected usage pattern.

### Finding #129: Thread Lock Not Used Consistently
**Location:** blackreach/download_history.py:134, 155-169
**Severity:** Medium
**Description:** `add_entry()` uses `self._lock` for thread safety, but read-only methods like `check_url_exists()`, `check_hash_exists()`, and `get_recent_downloads()` don't use the lock. This could lead to inconsistent reads during concurrent writes.
**Recommendation:** Either document the thread-safety guarantees or protect all methods that access the database.

### Finding #130: Global Mutable State Pattern
**Location:** blackreach/download_history.py:448-456
**Severity:** Medium
**Description:** Uses global `_download_history` variable with `get_download_history()` function. This singleton pattern makes testing difficult and can cause issues in multi-threaded contexts.
**Recommendation:** Consider dependency injection or a factory pattern that allows for easier testing and configuration.

### Finding #131: Hardcoded Database Path
**Location:** blackreach/download_history.py:80-81
**Severity:** Low
**Description:** Default database path is hardcoded to `~/.blackreach/download_history.db`. This makes it difficult to run multiple instances or customize storage location without code changes.
**Recommendation:** Allow configuration via environment variable or config file as well.

### Finding #132: Missing Index on downloaded_at Column
**Location:** blackreach/download_history.py:107-111
**Severity:** Low
**Description:** Creates indexes on url, md5, sha256, and filename, but not on `downloaded_at` which is used in `ORDER BY` clauses and date range queries in `search_history()` and `get_statistics()`.
**Recommendation:** Add index: `CREATE INDEX IF NOT EXISTS idx_downloaded_at ON download_history(downloaded_at)`.

### Finding #133: Duplicate Global Instance Pattern
**Location:** blackreach/rate_limiter.py:434-449
**Severity:** Low
**Description:** Same global singleton pattern with `_rate_limiter` and `get_rate_limiter()` as seen in download_history.py. This pattern is repeated across multiple modules.
**Recommendation:** Create a shared factory or registry for managing these singletons consistently.

### Finding #134: Hardcoded Known Rate Limits
**Location:** blackreach/rate_limiter.py:97-103
**Severity:** Medium
**Description:** The `known_limits` dictionary contains hardcoded rate limits for specific domains (arxiv.org: 15, scholar.google.com: 10, etc.). These may become outdated and can't be configured externally.
**Recommendation:** Load known limits from configuration file and/or allow runtime updates.

### Finding #135: Mutable Default in dataclass
**Location:** blackreach/rate_limiter.py:64, 71
**Severity:** Medium
**Description:** `DomainState` dataclass uses `field(default_factory=list)` for `requests` and `response_metrics`, which is correct, but the class itself is stored in a `defaultdict(DomainState)`. Each access creates a new DomainState, potentially causing memory growth.
**Recommendation:** Document the expected lifecycle of DomainState objects and consider periodic cleanup of old domains.

### Finding #136: Time-based Logic May Drift
**Location:** blackreach/rate_limiter.py:126-133
**Severity:** Low
**Description:** Request tracking uses `datetime.now()` comparisons with `timedelta(minutes=1)`. On systems with clock drift or NTP adjustments, this could behave unexpectedly.
**Recommendation:** Consider using monotonic time (`time.monotonic()`) for relative time comparisons.

### Finding #137: Complex Method - _update_adaptive_interval
**Location:** blackreach/rate_limiter.py:309-358
**Severity:** Medium
**Description:** The `_update_adaptive_interval()` method has 50 lines with multiple conditionals for different response types. The logic is difficult to follow and test.
**Recommendation:** Extract each response type handler into a separate method or use a strategy pattern.

### Finding #138: Magic Numbers in Throttling Logic
**Location:** blackreach/rate_limiter.py:325, 347, 349
**Severity:** Low
**Description:** Uses magic numbers like `3` (consecutive successes threshold), `** 2` (rate limit slowdown factor), without named constants.
**Recommendation:** Extract to named constants: `CONSECUTIVE_SUCCESS_THRESHOLD = 3`, etc.

### Finding #139: Incomplete Error Classification
**Location:** blackreach/rate_limiter.py:292-307
**Severity:** Low
**Description:** `_classify_response()` treats all 4xx errors (except 403) as generic errors. Some 4xx codes like 401 (Unauthorized) or 404 (Not Found) may warrant different handling.
**Recommendation:** Add specific handling for common 4xx codes or document why they're treated uniformly.

### Finding #140: Statistics Method Returns Raw Data
**Location:** blackreach/rate_limiter.py:375-403
**Severity:** Low
**Description:** `get_response_stats()` calculates statistics inline. For domains with many responses, this could be slow.
**Recommendation:** Consider caching statistics or computing incrementally.

### Finding #141: Complex Regex Patterns Without Comments
**Location:** blackreach/captcha_detect.py:59-142
**Severity:** Medium
**Description:** The `CAPTCHA_PATTERNS` dictionary contains numerous complex regex patterns without comments explaining what they match or why specific patterns were chosen.
**Recommendation:** Add inline comments for each pattern explaining what it matches and potential false positives.

### Finding #142: Duplicate Sitekey Patterns
**Location:** blackreach/captcha_detect.py:271-277
**Severity:** Low
**Description:** The `_extract_sitekey()` method defines sitekey patterns that partially duplicate patterns in `CAPTCHA_PATTERNS`. Changes in one place may not be reflected in the other.
**Recommendation:** Share patterns between detection and extraction, or document the relationship.

### Finding #143: Confidence Boost Logic Issues
**Location:** blackreach/captcha_detect.py:217-223
**Severity:** Medium
**Description:** The confidence boosting logic only boosts if the same provider matches again: `if best_match and best_match[0] == provider`. However, the loop iterates through all providers, so `best_match` could be from a different provider, causing the boost to never trigger.
**Recommendation:** Track matches per provider separately, then boost confidence based on multiple pattern matches for the same provider.

### Finding #144: Missing Thread Safety in Singleton
**Location:** blackreach/captcha_detect.py:383-391
**Severity:** Low
**Description:** The `get_captcha_detector()` function creates a singleton without thread safety. In multi-threaded code, multiple instances could be created.
**Recommendation:** Add threading lock or use lazy initialization pattern with double-checked locking.

### Finding #145: Low Confidence Thresholds for Generic Patterns
**Location:** blackreach/captcha_detect.py:145-159
**Severity:** Low
**Description:** Generic CAPTCHA patterns have low confidence values (0.4-0.6) which may cause false positives. Patterns like "security.*check" (0.4) could match many non-CAPTCHA pages.
**Recommendation:** Consider requiring multiple generic patterns to match before reporting, or raise the threshold.

### Finding #146: Selectors May Not Match Modern Sites
**Location:** blackreach/captcha_detect.py:287-324
**Severity:** Low
**Description:** The `_get_selectors()` method returns hardcoded CSS selectors for CAPTCHA elements. These may not match dynamically generated or obfuscated class names used by modern CAPTCHA implementations.
**Recommendation:** Add documentation about selector reliability and consider using more robust detection strategies.

### Finding #147: Unused Return Value Pattern
**Location:** blackreach/captcha_detect.py:354-379
**Severity:** Low
**Description:** `get_bypass_suggestions()` returns a list of suggestions, but these are generic text strings that may not be actionable programmatically.
**Recommendation:** Consider returning structured data (e.g., action types) that can be acted upon, or document that these are for display purposes only.

### Finding #148: Long Method - extract_metadata
**Location:** blackreach/metadata_extract.py (estimated line 200-400)
**Severity:** Medium
**Description:** The main extraction method likely handles multiple file types in a single method, making it long and complex.
**Recommendation:** Delegate to type-specific extractors early in the method to keep it concise.

### Finding #149: Missing Dependency Checks
**Location:** blackreach/metadata_extract.py
**Severity:** Medium
**Description:** The module uses optional dependencies (pypdf, PIL/Pillow, ebooklib) but may not gracefully handle their absence in all code paths.
**Recommendation:** Check for optional dependencies at import time and provide clear error messages when required functionality is unavailable.

### Finding #150: File Handle Management in Extraction
**Location:** blackreach/metadata_extract.py
**Severity:** Medium
**Description:** When extracting metadata from files, there's risk of file handles not being properly closed if exceptions occur during extraction.
**Recommendation:** Ensure all file operations use context managers (`with` statements) consistently.

### Finding #151: Hash Computation Loads Entire File
**Location:** blackreach/metadata_extract.py (hash computation section)
**Severity:** Medium
**Description:** Computing MD5/SHA256 hashes typically requires reading the entire file into memory, which could be problematic for very large files (multi-GB).
**Recommendation:** Use chunked reading for hash computation: read file in blocks and update hash incrementally.

### Finding #152: Magic Byte Detection May Conflict
**Location:** blackreach/metadata_extract.py
**Severity:** Low
**Description:** Magic byte detection for file types may conflict with file extension detection. The precedence and behavior when they disagree should be documented.
**Recommendation:** Document the detection strategy and how conflicts are resolved.

### Finding #153: Exception Handling in PDF Extraction
**Location:** blackreach/metadata_extract.py
**Severity:** Medium
**Description:** PDF extraction may fail for various reasons (encrypted, corrupted, unsupported features). The error handling and fallback behavior should be comprehensive.
**Recommendation:** Add specific exception handling for common PDF issues and provide meaningful error messages.

### Finding #154: EPUB Metadata Extraction Incomplete
**Location:** blackreach/metadata_extract.py
**Severity:** Low
**Description:** EPUB files can contain rich metadata (series info, subjects, rights, etc.) that may not be fully extracted.
**Recommendation:** Document which EPUB metadata fields are extracted and which are ignored.

### Finding #155: Image EXIF Handling May Expose Privacy Data
**Location:** blackreach/metadata_extract.py
**Severity:** Medium
**Description:** Image metadata extraction may include GPS coordinates, camera serial numbers, and other privacy-sensitive EXIF data without warning.
**Recommendation:** Add option to sanitize/filter privacy-sensitive metadata and document what data is extracted.

### Finding #156: Import Inside Method - ActionStats
**Location:** blackreach/action_tracker.py:63, 69
**Severity:** Low
**Description:** `from datetime import datetime` is imported inside `record_success()` and `record_failure()` methods instead of at module level. This is inefficient and unconventional.
**Recommendation:** Move import to module level with other imports.

### Finding #157: Global Singleton Without Thread Safety
**Location:** blackreach/action_tracker.py:498-505
**Severity:** Medium
**Description:** The `_global_tracker` singleton and `get_tracker()` function have no thread safety. Concurrent access could create multiple instances.
**Recommendation:** Add threading lock or use lazy initialization with double-checked locking.

### Finding #158: Mutable Default in defaultdict
**Location:** blackreach/action_tracker.py:105-117
**Severity:** Low
**Description:** Using `defaultdict(ActionStats)` creates new ActionStats objects on any key access. This could lead to unbounded memory growth if many unique keys are accessed.
**Recommendation:** Document the expected lifecycle and consider periodic cleanup of stale entries.

### Finding #159: Silent Exception in _load_from_memory
**Location:** blackreach/action_tracker.py:435-436
**Severity:** Medium
**Description:** `_load_from_memory()` catches all exceptions and silently passes. This hides initialization failures that could affect behavior.
**Recommendation:** Log exceptions at debug level or re-raise after logging.

### Finding #160: Bare Exception in _load_from_memory Inner Loop
**Location:** blackreach/action_tracker.py:433-434
**Severity:** Low
**Description:** Inner try/except catches `json.JSONDecodeError` and `KeyError` but uses bare `except` with continue. Other exceptions are silently swallowed.
**Recommendation:** Be explicit about caught exceptions or log unexpected ones.

### Finding #161: Magic Numbers in Thresholds
**Location:** blackreach/stuck_detector.py:89-93
**Severity:** Low
**Description:** Class-level constants `URL_REPEAT_THRESHOLD = 3`, `CONTENT_REPEAT_THRESHOLD = 3`, etc. are defined but the rationale for these specific values is not documented.
**Recommendation:** Add comments explaining why these thresholds were chosen.

### Finding #162: Import Inside Function - compute_content_hash
**Location:** blackreach/stuck_detector.py:456
**Severity:** Low
**Description:** `import re` is called inside `compute_content_hash()` function at module level, but re is already imported at the top of the module.
**Recommendation:** Remove the redundant import inside the function.

### Finding #163: MD5 Used for Content Hashing
**Location:** blackreach/stuck_detector.py:474
**Severity:** Low
**Description:** `hashlib.md5()` is used for content hashing. While not a security concern here, MD5 is deprecated for cryptographic use.
**Recommendation:** Document that this is non-cryptographic use or consider using xxhash for better performance.

### Finding #164: Potential Infinite Loop in get_backtrack_url
**Location:** blackreach/stuck_detector.py:390-394
**Severity:** Low
**Description:** `get_backtrack_url()` pops from breadcrumbs, but if repeatedly called without progress, will eventually return None. No indication is given to caller about exhausted backtrack options.
**Recommendation:** Return a tuple with (url, remaining_breadcrumbs) or similar to indicate exhaustion.

### Finding #165: Complex Nested Conditional in _check_action_loop
**Location:** blackreach/stuck_detector.py:278-288
**Severity:** Medium
**Description:** The action loop pattern detection uses a complex condition checking if `last_6[0] == last_6[2] == last_6[4]` and similar. This is hard to read and maintain.
**Recommendation:** Extract into a helper method like `_is_alternating_pattern(sequence, pattern_length)`.

### Finding #166: Bare Exception in Custom Handler Call
**Location:** blackreach/error_recovery.py:311-314
**Severity:** Medium
**Description:** Custom handler exceptions are caught and silently pass, falling through to default handling. This hides errors in user-provided handlers.
**Recommendation:** Log the exception before falling through, or re-raise to let caller handle.

### Finding #167: Blocking Sleep in _apply_strategy
**Location:** blackreach/error_recovery.py:338, 349
**Severity:** Medium
**Description:** `time.sleep()` is called directly in recovery strategies, blocking the entire thread. This could be problematic in async contexts.
**Recommendation:** Consider making this async-compatible or documenting the blocking behavior.

### Finding #168: Empty stats Dict Access May Raise
**Location:** blackreach/error_recovery.py:415-416
**Severity:** Low
**Description:** `get_stats()` calls `max(self._error_counts.items(), ...)` which will raise `ValueError` if dict is empty, even though there's a check for `if self._error_counts`.
**Recommendation:** The conditional check is there but the logic is on same line - add explicit empty check.

### Finding #169: Repeated urlparse Calls
**Location:** blackreach/source_manager.py:177-179, 243-244, 261, 314-315, 365, 388-389
**Severity:** Low
**Description:** `from urllib.parse import urlparse` and then `urlparse()` is called repeatedly inside methods. The import is done inside the method multiple times.
**Recommendation:** Move import to module level and cache parsed URLs where possible.

### Finding #170: Magic Numbers in Scoring
**Location:** blackreach/source_manager.py:194-214
**Severity:** Medium
**Description:** `get_best_source()` uses magic numbers for scoring: `* 10`, `* 50`, `- 10`, `+ 20`, `- 30`, `- 15`. The scoring rationale is undocumented.
**Recommendation:** Extract to named constants with documentation explaining the scoring model.

### Finding #171: Unbounded Failover History
**Location:** blackreach/source_manager.py:267-272
**Severity:** Low
**Description:** `_failover_history` grows to 50 entries then trims to 50. The trim happens only when > 50, so it oscillates between 50-51 entries.
**Recommendation:** Use `collections.deque(maxlen=50)` for cleaner bounded history.

### Finding #172: No Default Return Type Annotation
**Location:** blackreach/source_manager.py:284-286
**Severity:** Low
**Description:** `get_source_status()` returns `self._health[domain]` which uses defaultdict, so it always returns a SourceHealth. The return type hint is missing.
**Recommendation:** Add `-> SourceHealth` return type hint.

### Finding #173: Circular Import Risk
**Location:** blackreach/source_manager.py:30
**Severity:** Low
**Description:** `from blackreach.knowledge import CONTENT_SOURCES, ContentSource, find_best_sources` at module level. If knowledge.py imports from source_manager, there would be a circular import.
**Recommendation:** Document module dependencies or use lazy imports if needed.

### Finding #174: Complex Goal Pattern Matching
**Location:** blackreach/goal_engine.py:206-238
**Severity:** Medium
**Description:** `GOAL_PATTERNS` dict contains regex patterns for goal detection, but some patterns may overlap or conflict. For example, "get" appears in both DOWNLOAD and EXTRACT patterns.
**Recommendation:** Add priority ordering or document which pattern wins in case of multiple matches.

### Finding #175: Hardcoded Word-to-Number Mapping
**Location:** blackreach/goal_engine.py:272-280
**Severity:** Low
**Description:** `word_numbers` dict is hardcoded with "one" through "ten" plus informal terms. Missing common variations like "dozen", "couple", etc.
**Recommendation:** Extend the mapping or use a library like `word2number`.

### Finding #176: ID Generation Uses MD5
**Location:** blackreach/goal_engine.py:253-254
**Severity:** Low
**Description:** `_generate_id()` uses MD5 hash truncated to 12 characters. While not a security issue, collision probability increases with truncation.
**Recommendation:** Consider using UUID4 for guaranteed uniqueness.

### Finding #177: Estimated Steps Calculation is Naive
**Location:** blackreach/goal_engine.py:311
**Severity:** Low
**Description:** `estimated_steps=sum(3 for _ in subtasks)` assumes every subtask takes 3 steps. This is a constant regardless of task complexity.
**Recommendation:** Calculate estimates based on task type and complexity.

### Finding #178: Double Update in update_progress
**Location:** blackreach/goal_engine.py:491-493
**Severity:** Low
**Description:** When status is COMPLETED, both `subtask.status = status` and `subtask.mark_complete(result)` are called. `mark_complete()` also sets status, so it's set twice.
**Recommendation:** Remove the explicit status assignment when calling mark_complete().

### Finding #179: Replan Creates Unbounded Subtasks
**Location:** blackreach/goal_engine.py:498-529
**Severity:** Medium
**Description:** `replan()` adds new subtasks to the decomposition without limit. Repeated failures could cause unbounded growth of subtasks.
**Recommendation:** Add a maximum number of alternative subtasks or replan attempts.

### Finding #180: Global Engine Instance Pattern Repeated
**Location:** blackreach/goal_engine.py:579-588
**Severity:** Low
**Description:** Same `_goal_engine` / `get_goal_engine()` singleton pattern as seen in multiple other modules. This pattern is repeated across the codebase.
**Recommendation:** Create a common pattern or registry for managing these singletons.

### Finding #181: Silent Exception in Cache Serialization
**Location:** blackreach/cache.py:203-204
**Severity:** Medium
**Description:** `_save_to_disk()` catches all exceptions and passes silently. Users have no way to know if cache persistence failed.
**Recommendation:** Log serialization failures or expose a callback for error handling.

### Finding #182: Silent Exception in Cache Loading
**Location:** blackreach/cache.py:224-225
**Severity:** Medium
**Description:** `_load_from_disk()` catches all exceptions and passes silently. Corrupted cache files won't be reported.
**Recommendation:** Log load failures and consider creating a backup before overwriting corrupted caches.

### Finding #183: MD5 for Cache Keys
**Location:** blackreach/cache.py:264, 296
**Severity:** Low
**Description:** `_url_key()` and `_query_key()` use MD5 for generating cache keys. While not a security issue here, it adds unnecessary complexity.
**Recommendation:** Consider using a simpler hash or just using the URL/query string directly if within size limits.

### Finding #184: Default TTL Not Configurable Per Entry Type
**Location:** blackreach/cache.py:49
**Severity:** Low
**Description:** `default_ttl_seconds` is a single value for all cache types. Different content types may benefit from different TTLs.
**Recommendation:** Allow TTL configuration per cache type or make it more configurable.

### Finding #185: CacheEntry Generic Type Not Enforced at Runtime
**Location:** blackreach/cache.py:26-35
**Severity:** Low
**Description:** `CacheEntry[T]` uses Generic typing but there's no runtime type checking. Any value can be stored regardless of type parameter.
**Recommendation:** Document this limitation or add optional runtime type validation.

### Finding #186: PageCache Stores Two Copies
**Location:** blackreach/cache.py:240-246
**Severity:** Medium
**Description:** `cache_page()` stores HTML in `_html_cache` and optionally parsed content in `_parsed_cache`. If both are stored, memory usage doubles for pages.
**Recommendation:** Consider storing only one and computing the other on demand, or document the memory implications.

### Finding #187: Multiple Global Cache Instances
**Location:** blackreach/cache.py:304-321
**Severity:** Low
**Description:** Two separate global instances (`_page_cache`, `_result_cache`) with separate getter functions. This pattern is repeated.
**Recommendation:** Consider a cache registry pattern or unify the initialization approach.

### Finding #188: Sequential Batch Processing in ParallelFetcher
**Location:** blackreach/parallel_ops.py:145-149
**Severity:** Medium
**Description:** Despite being called "ParallelFetcher", `fetch_pages()` processes URLs sequentially within batches using a simple for loop. The parallelism is only batch-level.
**Recommendation:** Use ThreadPoolExecutor or asyncio for true parallel execution within batches.

### Finding #189: Import Inside Method - ParallelFetcher
**Location:** blackreach/parallel_ops.py:170
**Severity:** Low
**Description:** `from urllib.parse import urlparse` is imported inside `_fetch_single()` method instead of at module level.
**Recommendation:** Move import to module level for consistency and slight performance improvement.

### Finding #190: Import Inside Method - ParallelDownloader
**Location:** blackreach/parallel_ops.py:319-320
**Severity:** Low
**Description:** `from urllib.parse import urlparse` and `from pathlib import Path` are imported inside `_download_single()` method.
**Recommendation:** Move imports to module level.

### Finding #191: Hardcoded Download Timeout
**Location:** blackreach/parallel_ops.py:340
**Severity:** Low
**Description:** `expect_download(timeout=60000)` has a hardcoded 60-second timeout. Large files or slow connections may need more time.
**Recommendation:** Make timeout configurable or use the timeout_manager for consistency.

### Finding #192: Missing Error Logging in ParallelSearcher
**Location:** blackreach/parallel_ops.py:431-432
**Severity:** Low
**Description:** When search fails, exception is caught but not logged. The error is silently swallowed and empty results returned.
**Recommendation:** Log the exception for debugging purposes.

### Finding #193: Import Inside Method - ParallelSearcher
**Location:** blackreach/parallel_ops.py:409, 438
**Severity:** Low
**Description:** `from urllib.parse import quote` and `from bs4 import BeautifulSoup` are imported inside methods.
**Recommendation:** Move imports to module level.

### Finding #194: Generic Link Extraction Logic
**Location:** blackreach/parallel_ops.py:443-463
**Severity:** Medium
**Description:** `_extract_search_results()` uses a generic approach to extract links. This won't work well with JavaScript-rendered search results or sites with different structures.
**Recommendation:** Add source-specific extractors or document limitations of generic extraction.

### Finding #195: Hardcoded Result Limit
**Location:** blackreach/parallel_ops.py:462
**Severity:** Low
**Description:** `if len(results) >= 20: break` limits results to 20 with no configuration option.
**Recommendation:** Make the limit configurable.

### Finding #196: Lazy Initialization Without Thread Safety
**Location:** blackreach/parallel_ops.py:497-530
**Severity:** Medium
**Description:** `ParallelOperationManager` lazily initializes `_fetcher`, `_downloader`, `_searcher` in properties without thread safety. Concurrent access could create multiple instances.
**Recommendation:** Add locking around lazy initialization or initialize in `__init__`.

### Finding #197: Global Manager Requires browser_context
**Location:** blackreach/parallel_ops.py:558-571
**Severity:** Low
**Description:** `get_parallel_manager()` returns None if called without browser_context and manager doesn't exist. This could cause `AttributeError` if caller doesn't check.
**Recommendation:** Raise a clear exception or document the None return case prominently.

### Finding #198: Sequential Download Processing Despite "Parallel" Name
**Location:** blackreach/parallel_ops.py:289-305
**Severity:** Medium
**Description:** `download_files()` also processes sequentially within batches, despite the class being named `ParallelDownloader`.
**Recommendation:** Implement true parallel processing with thread pool or rename to clarify actual behavior.

### Finding #199: No Cleanup on Exception in Tab Operations
**Location:** blackreach/parallel_ops.py:186-210, 325-358
**Severity:** Medium
**Description:** If an exception occurs during fetch/download, the tab may not be properly released. The `release_tab` call is inside the try block, not in a finally.
**Recommendation:** Move `release_tab` to a finally block to ensure cleanup.

### Finding #200: Timestamp-Based ID Generation
**Location:** blackreach/parallel_ops.py:103-107, 249-253
**Severity:** Low
**Description:** Task IDs are generated with `int(time.time())`. If many tasks are created in the same second, IDs could collide (though counter helps).
**Recommendation:** Use UUID or more robust unique ID generation.

### Finding #201: Database Connections Not Properly Managed
**Location:** blackreach/session_manager.py:93-135, 144-155
**Severity:** Medium
**Description:** `_init_db()` and `create_session()` create SQLite connections but don't use context managers. If an exception occurs, connections may leak.
**Recommendation:** Use `with sqlite3.connect(self.db_path) as conn:` for automatic cleanup.

### Finding #202: No Connection Pooling
**Location:** blackreach/session_manager.py
**Severity:** Medium
**Description:** Every database operation creates a new SQLite connection. This is inefficient and could cause issues with concurrent access.
**Recommendation:** Consider a connection pool or at minimum caching a single connection.

### Finding #203: Set Serialization May Lose Data
**Location:** blackreach/session_manager.py:187-189
**Severity:** Low
**Description:** `successful_selectors` contains Sets which are converted to lists for JSON serialization. Sets are inherently unordered, so ordering may vary on reload.
**Recommendation:** Sort the list before serialization for deterministic output.

### Finding #204: Silent Failures in save_session
**Location:** blackreach/session_manager.py:171-175
**Severity:** Low
**Description:** `save_session()` returns early if no session, but doesn't indicate to caller that nothing was saved.
**Recommendation:** Return a boolean indicating success or raise an exception.

### Finding #205: Learning Data Not Auto-Saved
**Location:** blackreach/session_manager.py:460-469
**Severity:** Medium
**Description:** `record_successful_pattern()` updates in-memory learning data but doesn't persist it. Data loss occurs if `save_learning_data()` isn't called explicitly.
**Recommendation:** Auto-save periodically or on significant updates, or document the requirement to call save_learning_data().

### Finding #206: No Error Handling in _load_learning_data
**Location:** blackreach/session_manager.py:417-437
**Severity:** Low
**Description:** `_load_learning_data()` doesn't handle JSON parsing errors. Corrupted data would crash the application.
**Recommendation:** Add try/except around JSON parsing with appropriate error handling.

### Finding #207: Session Manager Global Has Default Path
**Location:** blackreach/session_manager.py:480-486
**Severity:** Low
**Description:** `get_session_manager()` defaults to `"./memory.db"` which creates database in current working directory. This may vary depending on where the script is run from.
**Recommendation:** Use a more predictable default path like `~/.blackreach/sessions.db`.

### Finding #208: Missing Index on sessions.last_update
**Location:** blackreach/session_manager.py:97-110
**Severity:** Low
**Description:** The `sessions` table queries by `last_update` for resumable sessions but no index exists on this column.
**Recommendation:** Add index: `CREATE INDEX IF NOT EXISTS idx_sessions_update ON sessions(last_update)`.

### Finding #209: Hardcoded Action Defaults
**Location:** blackreach/timeout_manager.py:60-67
**Severity:** Low
**Description:** `action_defaults` dict contains hardcoded timeout values. These can't be configured without code changes.
**Recommendation:** Load defaults from config or allow runtime override.

### Finding #210: Nested defaultdict Lambda
**Location:** blackreach/timeout_manager.py:55-57
**Severity:** Low
**Description:** `defaultdict(lambda: defaultdict(list))` works but is harder to pickle/serialize and can be confusing to debug.
**Recommendation:** Consider a regular dict with explicit initialization in get/set methods.

### Finding #211: Timing Key Format May Collide
**Location:** blackreach/timeout_manager.py:121
**Severity:** Low
**Description:** `key = f"{domain}:{action}:{datetime.now().isoformat()}"` includes isoformat timestamp. If two operations start in same millisecond, keys could collide.
**Recommendation:** Add a counter or UUID component to ensure uniqueness.

### Finding #212: record_timeout Uses max_timeout as Duration
**Location:** blackreach/timeout_manager.py:152-158
**Severity:** Low
**Description:** `record_timeout()` records a failed timing at `max_timeout`, but the actual timeout used may have been different (e.g., action-specific).
**Recommendation:** Accept the actual timeout value as a parameter.

### Finding #213: Statistics Calculated on Every Call
**Location:** blackreach/timeout_manager.py:160-193
**Severity:** Low
**Description:** `get_stats()` recalculates statistics from raw data on every call. For domains with many timings, this could be slow.
**Recommendation:** Cache computed statistics or compute incrementally.

### Finding #214: Complex Aggregation Logic
**Location:** blackreach/timeout_manager.py:162-179
**Severity:** Medium
**Description:** `get_stats()` has complex branching for different filter combinations (domain+action, domain only, action only, all). The logic is repetitive.
**Recommendation:** Refactor into a helper method that collects relevant timings based on filters.

### Finding #215: No Thread Safety in TimeoutManager
**Location:** blackreach/timeout_manager.py
**Severity:** Medium
**Description:** `TimeoutManager` modifies `timings` and `_active` dicts without thread safety. Concurrent timing operations could cause data corruption.
**Recommendation:** Add threading locks around mutable state access.

### Finding #216: Export/Import Don't Preserve All State
**Location:** blackreach/timeout_manager.py:222-248
**Severity:** Low
**Description:** `export_data()` and `import_data()` only handle timing data, not the configuration or active timings.
**Recommendation:** Document what is and isn't persisted, or include all relevant state.

### Finding #217: Global Timeout Manager Pattern
**Location:** blackreach/timeout_manager.py:251-260
**Severity:** Low
**Description:** Same `_timeout_manager` / `get_timeout_manager()` pattern repeated. No thread safety in initialization.
**Recommendation:** Use double-checked locking or initialize at import time.

### Finding #218: reset_timeout_manager Doesn't Clean Active Timings
**Location:** blackreach/timeout_manager.py:263-266
**Severity:** Low
**Description:** `reset_timeout_manager()` sets the global to None but doesn't clean up `_active` timings in the old instance. Could cause memory leaks if timings are never ended.
**Recommendation:** Call cleanup on the old manager before resetting.

### Finding #219: predict_timeout Edge Case with Empty Successful
**Location:** blackreach/timeout_manager.py:96-101
**Severity:** Low
**Description:** When all recent attempts failed, `_predict_timeout()` returns `default_timeout * 2`. But if this is called repeatedly, it doesn't continue increasing.
**Recommendation:** Consider exponential backoff for repeated failures.

### Finding #220: 95th Percentile Calculation May Be Inaccurate
**Location:** blackreach/timeout_manager.py:104-109
**Severity:** Low
**Description:** The 95th percentile calculation uses index-based selection which may not be accurate for small sample sizes (< 20 samples).
**Recommendation:** Use `statistics.quantiles()` with method='inclusive' for better accuracy, or document the approximation.

### Finding #221: Planner Always Creates New LLM Instance
**Location:** blackreach/planner.py:77-78
**Severity:** Low
**Description:** `Planner.__init__` always creates a new LLM instance even if one exists elsewhere. This prevents sharing LLM connections across components.
**Recommendation:** Accept an optional LLM instance in the constructor to allow sharing.

### Finding #222: is_simple_goal Has Overlapping Patterns
**Location:** blackreach/planner.py:95-118
**Severity:** Low
**Description:** The `is_simple_goal()` method checks both "simple_indicators" and "complex_indicators" but some words like "download" might appear in simple goals too (e.g., "download this page").
**Recommendation:** Use more contextual pattern matching rather than individual keyword checks.

### Finding #223: Plan Fallback Creates Single Task
**Location:** blackreach/planner.py:160-168
**Severity:** Low
**Description:** When JSON parsing fails, the fallback creates a single subtask with generic text. This loses any partial information that might have been extracted.
**Recommendation:** Attempt to extract partial subtasks from malformed JSON before falling back.

### Finding #224: maybe_plan Creates Planner Each Call
**Location:** blackreach/planner.py:213-216
**Severity:** Low
**Description:** The `maybe_plan()` convenience function creates a new Planner instance on every call, wasting resources.
**Recommendation:** Cache the planner instance or use a module-level singleton.

### Finding #225: NavigationContext Missing Thread Safety
**Location:** blackreach/nav_context.py:102-113
**Severity:** Medium
**Description:** `NavigationContext` modifies `domain_knowledge` and `valuable_selectors` dicts without thread safety, but these may be accessed from callbacks.
**Recommendation:** Add thread lock or document single-threaded usage requirement.

### Finding #226: DomainKnowledge successful_paths Unbounded
**Location:** blackreach/nav_context.py:83
**Severity:** Low
**Description:** `successful_paths` list grows without limit as successful navigations are recorded. Long-running sessions could accumulate many paths.
**Recommendation:** Limit to most recent N paths or implement LRU eviction.

### Finding #227: Breadcrumb depth Calculated Incorrectly
**Location:** blackreach/nav_context.py:184
**Severity:** Low
**Description:** `depth=self.current_path.current_depth + 1` adds 1 to the current depth, but if adding the first breadcrumb, depth would be 1, not 0.
**Recommendation:** Verify depth calculation is intentional or adjust to 0-based indexing.

### Finding #228: Missing Validation for links Parameter
**Location:** blackreach/nav_context.py:294-299
**Severity:** Low
**Description:** `_score_links()` doesn't validate that links have required keys ('text', 'href'). Missing keys would cause silent failures.
**Recommendation:** Add validation or use `.get()` with defaults consistently.

### Finding #229: Global nav_context Has No Thread Safety
**Location:** blackreach/nav_context.py:415-424
**Severity:** Medium
**Description:** The `_nav_context` singleton pattern doesn't use thread-safe initialization. Race conditions possible in concurrent access.
**Recommendation:** Add threading lock or use module-level initialization.

### Finding #230: QueryFormulator Stores Queries Unbounded
**Location:** blackreach/search_intel.py:91-92
**Severity:** Low
**Description:** `successful_queries` and `failed_queries` dicts grow without limit. Many searches could cause memory issues.
**Recommendation:** Limit the number of stored queries per subject or implement LRU eviction.

### Finding #231: STOP_WORDS May Remove Important Terms
**Location:** blackreach/search_intel.py:60-68
**Severity:** Low
**Description:** STOP_WORDS includes "download" which might be an important search term in some contexts. Removing it could change search intent.
**Recommendation:** Make stop words context-aware or configurable.

### Finding #232: get_proven_query Returns First Without Ranking
**Location:** blackreach/search_intel.py:245-249
**Severity:** Low
**Description:** `get_proven_query()` returns the first successful query without considering recency or success rate.
**Recommendation:** Sort by success metrics before returning.

### Finding #233: SearchSession Mutates alternatives List
**Location:** blackreach/search_intel.py:451
**Severity:** Low
**Description:** `get_next_query()` calls `pop(0)` on `alternatives`, mutating the original SearchQuery object.
**Recommendation:** Make a copy of alternatives or track consumption separately.

### Finding #234: TRUSTED_DOMAINS Contains Partial Matches
**Location:** blackreach/search_intel.py:278-290
**Severity:** Low
**Description:** Trusted domain patterns like "annas-archive" don't have domain extension, could match unintended URLs.
**Recommendation:** Use full domain patterns with TLD.

### Finding #235: RetryPolicy Uses Lambda Default
**Location:** blackreach/retry_strategy.py:37-42
**Severity:** Low
**Description:** `retry_on_errors` and `skip_on_errors` use `field(default_factory=lambda: [...])` which is evaluated each time. A frozen list would be more efficient.
**Recommendation:** Define default lists as module-level constants.

### Finding #236: with_retry Doesn't Handle All RetryDecisions
**Location:** blackreach/retry_strategy.py:349
**Severity:** Low
**Description:** The `with_retry()` function handles WAIT_AND_RETRY, SKIP, ABORT, CHANGE_APPROACH but doesn't handle RETRY decision type separately.
**Recommendation:** Either document this behavior or add explicit RETRY handling.

### Finding #237: ErrorClassifier Patterns Not Case Insensitive
**Location:** blackreach/retry_strategy.py:293
**Severity:** Low
**Description:** `classify()` converts error to lowercase, but patterns are already lowercase. This works but isn't explicit about case handling.
**Recommendation:** Document or make patterns explicitly case-insensitive in comments.

### Finding #238: calculate_wait Can Return Near-Zero Values
**Location:** blackreach/retry_strategy.py:205
**Severity:** Low
**Description:** `max(0, wait)` could return very small values if jitter makes wait negative before capping. This might cause rapid retries.
**Recommendation:** Add minimum wait floor: `max(min_wait, wait)`.

### Finding #239: TabManager Uses Async Lock Conditionally
**Location:** blackreach/multi_tab.py:59
**Severity:** Medium
**Description:** `self._lock = asyncio.Lock() if asyncio else None` - the check `if asyncio` is always truthy since asyncio is imported. The intended check is unclear.
**Recommendation:** Clarify the condition or remove the conditional.

### Finding #240: TabManager Doesn't Use Lock
**Location:** blackreach/multi_tab.py:59, 71-88
**Severity:** Medium
**Description:** `_lock` is created but never used in methods like `get_tab()`. Concurrent tab operations could cause issues.
**Recommendation:** Use `async with self._lock:` in async methods that modify state.

### Finding #241: SyncTabManager Duplicate Code
**Location:** blackreach/multi_tab.py:181-293
**Severity:** Medium
**Description:** `SyncTabManager` duplicates much of `TabManager`'s logic. Changes must be made in two places.
**Recommendation:** Use composition or a shared base implementation.

### Finding #242: close_tab Deletes While Potentially Iterating
**Location:** blackreach/multi_tab.py:124-125
**Severity:** Low
**Description:** `close_tab()` deletes from `self.tabs` dict. If called during iteration (e.g., from cleanup), this could cause issues.
**Recommendation:** Use `self.tabs.pop(tab_id, None)` pattern.

### Finding #243: navigate_in_tab Doesn't Wait for Load
**Location:** blackreach/multi_tab.py:276
**Severity:** Medium
**Description:** `tab.page.goto(url)` doesn't specify wait conditions. Navigation might not be complete when method returns.
**Recommendation:** Add `wait_until` parameter or timeout configuration.

### Finding #244: TaskScheduler Uses PriorityQueue Incorrectly
**Location:** blackreach/task_scheduler.py:172-173
**Severity:** Medium
**Description:** When getting from `PriorityQueue`, the task status may have changed. The check `if task.status == TaskStatus.READY` could skip tasks or re-process them.
**Recommendation:** Remove tasks from queue when status changes, or validate more carefully.

### Finding #245: Task Dependencies Not Validated
**Location:** blackreach/task_scheduler.py:121
**Severity:** Low
**Description:** `dependencies` list isn't validated to ensure referenced task IDs exist. Invalid dependencies would cause tasks to remain blocked forever.
**Recommendation:** Validate dependencies exist when adding task.

### Finding #246: wait_all Uses Busy Loop
**Location:** blackreach/task_scheduler.py:291-300
**Severity:** Low
**Description:** `wait_all()` uses `time.sleep(0.5)` in a loop. This wastes CPU cycles and has 500ms latency.
**Recommendation:** Use `threading.Event` for efficient waiting.

### Finding #247: Task __lt__ Uses Two Comparisons
**Location:** blackreach/task_scheduler.py:58-62
**Severity:** Low
**Description:** `Task.__lt__` compares priority then `created_at`. If both are equal, result is undefined (depends on datetime comparison stability).
**Recommendation:** Add a third tiebreaker (e.g., task_id) for stable sorting.

### Finding #248: ContentVerifier placeholder_patterns Lower Case Issue
**Location:** blackreach/content_verify.py:91-102, 253-254
**Severity:** Low
**Description:** `placeholder_patterns` are defined as bytes, then `.lower()` is called on each. But bytes `.lower()` only works for ASCII.
**Recommendation:** Use pre-lowercased patterns or handle encoding properly.

### Finding #249: verify_file Reads Entire File Into Memory
**Location:** blackreach/content_verify.py:146-147
**Severity:** Medium
**Description:** `f.read()` loads the entire file into memory. For large files (multi-GB), this could cause memory issues.
**Recommendation:** For large files, use streaming verification or limit initial read size.

### Finding #250: _verify_epub Doesn't Close ZipFile on All Paths
**Location:** blackreach/content_verify.py:366
**Severity:** Low
**Description:** `zf.close()` is called at line 366, but if any return statement before that is hit, the ZipFile isn't closed.
**Recommendation:** Use `with zipfile.ZipFile(...) as zf:` context manager.

### Finding #251: Magic Signatures Dict Order Dependent
**Location:** blackreach/content_verify.py:60-73
**Severity:** Low
**Description:** `MAGIC_SIGNATURES` iteration order determines which type matches first. `PK\x03\x04` (ZIP) would match before EPUB check in `detect_type`.
**Recommendation:** Document matching order or use ordered matching explicitly.

### Finding #252: get_verifier Creates New Instance on None
**Location:** blackreach/content_verify.py:670-675
**Severity:** Low
**Description:** Same global singleton pattern as elsewhere. No thread safety on initialization.
**Recommendation:** Add thread-safe initialization.

### Finding #253: DebugTools _cleanup_old_snapshots Deletes Files
**Location:** blackreach/debug_tools.py:219-222
**Severity:** Medium
**Description:** Old snapshots are automatically deleted including their files. This could be unexpected behavior - users might want to keep all debug output.
**Recommendation:** Make file deletion optional/configurable.

### Finding #254: capture_snapshot Catches Broad Exception
**Location:** blackreach/debug_tools.py:180-185
**Severity:** Low
**Description:** Page info extraction catches all exceptions and silently passes. Debugging issues with page info retrieval would be difficult.
**Recommendation:** Log exceptions at debug level.

### Finding #255: ErrorCapturingWrapper Uses __getattr__ Magic
**Location:** blackreach/debug_tools.py:399-415
**Severity:** Low
**Description:** The `__getattr__` implementation creates wrapper functions on every attribute access. This adds overhead and could mask errors.
**Recommendation:** Cache wrapped methods or document the performance implications.

### Finding #256: DownloadQueue Generates Non-Unique IDs
**Location:** blackreach/download_queue.py:137-140
**Severity:** Low
**Description:** ID format `f"dl_{self._counter}_{datetime.now().strftime('%H%M%S')}"` only includes time to seconds. Multiple calls in same second get same timestamp.
**Recommendation:** Include milliseconds or use UUID.

### Finding #257: DownloadQueue._get_history Returns None
**Location:** blackreach/download_queue.py:127-135
**Severity:** Low
**Description:** Method returns `None` if history is disabled or import fails. Callers must check for None before use.
**Recommendation:** Consider returning a null object pattern or raising exception.

### Finding #258: complete Method Has Many Responsibilities
**Location:** blackreach/download_queue.py:276-360
**Severity:** Medium
**Description:** `complete()` method handles hash assignment, verification, status updates, callback invocation, and history recording - 85 lines with multiple concerns.
**Recommendation:** Split into `_verify_checksums()`, `_update_status()`, `_record_history()` methods.

### Finding #259: wait_all Imports time Inside Method
**Location:** blackreach/download_queue.py:512
**Severity:** Low
**Description:** `import time` inside `wait_all()` method instead of at module level.
**Recommendation:** Move import to module level.

### Finding #260: CookieManager Uses Fixed Salt
**Location:** blackreach/cookie_manager.py:181-182
**Severity:** Medium
**Description:** Encryption uses fixed salt `b"blackreach_cookie_salt_v1"`. This reduces security as all installations use same salt.
**Recommendation:** Generate and store per-installation salt, or document the security implications.

### Finding #261: Machine ID Fallback Uses Hostname
**Location:** blackreach/cookie_manager.py:218-223
**Severity:** Medium
**Description:** If machine ID can't be obtained, falls back to hostname+username. This is predictable and provides weak key derivation.
**Recommendation:** Add additional entropy sources or warn user about reduced security.

### Finding #262: CookieEncryption No Error Handling on Decrypt
**Location:** blackreach/cookie_manager.py:243-244
**Severity:** Medium
**Description:** `decrypt()` doesn't catch InvalidToken exception. Corrupted or tampered data would crash the application.
**Recommendation:** Handle `cryptography.fernet.InvalidToken` and provide meaningful error.

### Finding #263: load_profile Prints Error Directly
**Location:** blackreach/cookie_manager.py:374
**Severity:** Low
**Description:** Uses `print()` for error output instead of logging system. Inconsistent with rest of codebase.
**Recommendation:** Use logging module for error output.

### Finding #264: Cookie same_site Validation Missing
**Location:** blackreach/cookie_manager.py:38
**Severity:** Low
**Description:** `same_site` defaults to "Lax" but no validation ensures it's one of the valid values (Strict, Lax, None).
**Recommendation:** Add validation in `__post_init__` or property setter.

### Finding #265: DownloadProgressTracker Add Download Auto-Starts
**Location:** blackreach/progress.py:160-165
**Severity:** Low
**Description:** `add_download()` calls `self.start()` if progress is None. This implicit side effect could be unexpected.
**Recommendation:** Document the auto-start behavior or require explicit start.

### Finding #266: DownloadInfo eta_seconds Division by Zero Risk
**Location:** blackreach/progress.py:82-87
**Severity:** Low
**Description:** `eta_seconds` divides by `self.speed` which could be 0.0. The check `if self.speed <= 0` handles this but `<= 0` is redundant for speed.
**Recommendation:** Use `if self.speed == 0` or document why `< 0` is checked.

### Finding #267: track_downloads Function Creates Closure Over url
**Location:** blackreach/progress.py:437-438
**Severity:** Medium
**Description:** The `progress_callback` closure captures `url` from the enclosing loop. In Python, this can cause issues with late binding if used asynchronously.
**Recommendation:** Capture url as default argument: `def progress_callback(downloaded, total=None, url=url):`.

### Finding #268: TaskProgressTracker complete Doesn't Verify State
**Location:** blackreach/progress.py:395-402
**Severity:** Low
**Description:** `complete()` doesn't verify that progress was started or that _task_id exists before updating.
**Recommendation:** Add state validation.

### Finding #269: Theme Uses Class Attributes Not Instance
**Location:** blackreach/ui.py:62-70
**Severity:** Low
**Description:** `Theme` dataclass uses class-level attributes without `=` assignment making them class attributes, not instance attributes.
**Recommendation:** Use `field(default=...)` for proper dataclass behavior.

### Finding #270: HISTORY_FILE Created Without Checking
**Location:** blackreach/ui.py:58, 299-300
**Severity:** Low
**Description:** `HISTORY_FILE` path is used but only the parent directory is created. If the file doesn't exist, FileHistory may fail.
**Recommendation:** Verify FileHistory handles missing file or create empty file.

### Finding #271: InteractivePrompt Catches Broad Exceptions
**Location:** blackreach/ui.py:343-348, 604
**Severity:** Low
**Description:** Multiple places catch `Exception` and return default values. This hides errors that might be important.
**Recommendation:** Catch specific exceptions or log the errors.

### Finding #272: show_menu Falls Back Silently
**Location:** blackreach/ui.py:604-606
**Severity:** Low
**Description:** If `radiolist_dialog` fails, falls back to `show_simple_menu` without logging why the primary method failed.
**Recommendation:** Log the failure reason for debugging.

### Finding #273: UI Console Created Multiple Times
**Location:** blackreach/ui.py:37, 55
**Severity:** Low
**Description:** `console = Console()` is created at module level, but `DownloadProgressUI` also accepts console parameter with its own default.
**Recommendation:** Share the module-level console consistently.

### Finding #274: AgentProgress _step_shown Never Cleared
**Location:** blackreach/ui.py:103
**Severity:** Low
**Description:** `_step_shown` set tracks which steps have been displayed but is only cleared in `start()`. If reused across multiple runs, it would accumulate.
**Recommendation:** Clear in `complete()` as well or document single-use pattern.

### Finding #275: MultiDownloadProgress _live Not Checked in _refresh
**Location:** blackreach/progress.py:931-934 (ui.py similar)
**Severity:** Low
**Description:** `_refresh()` checks `if self._live` but doesn't handle the case where live display was stopped mid-operation.
**Recommendation:** Add more robust state checking.

### Finding #276: SiteHandler domains As Class Attribute
**Location:** blackreach/site_handlers.py:48-52
**Severity:** Medium
**Description:** `domains` and `url_patterns` are defined as class attributes with empty defaults. Subclasses override these but the pattern is error-prone - forgetting to override would silently fail matching.
**Recommendation:** Use abstract property or raise NotImplementedError for subclasses that don't set domains.

### Finding #277: get_handler_for_url Creates New Instance Each Call
**Location:** blackreach/site_handlers.py:876-881
**Severity:** Low
**Description:** `get_handler_for_url()` creates a new handler instance on every call. For frequent calls, this wastes resources.
**Recommendation:** Cache handler instances or use singleton pattern per handler type.

### Finding #278: SiteHandlerExecutor Uses time.sleep
**Location:** blackreach/site_handlers.py:928, 938, 944, 953
**Severity:** Low
**Description:** `time.sleep()` blocks the entire thread. In async contexts, this could be problematic.
**Recommendation:** Consider async sleep or document blocking behavior.

### Finding #279: execute_actions Accesses page.locator Directly
**Location:** blackreach/site_handlers.py:924-926
**Severity:** Medium
**Description:** `execute_actions()` directly accesses `self.hand.page.locator()` and `loc.first.click()`, bypassing Hand's abstraction layer and error handling.
**Recommendation:** Use Hand's click() method instead of direct Playwright API calls.

### Finding #280: SiteAction target Used for Multiple Purposes
**Location:** blackreach/site_handlers.py:28
**Severity:** Low
**Description:** `target` field contains selectors for click, URLs for navigate, direction strings for scroll - overloaded meaning makes code harder to understand.
**Recommendation:** Create typed action subclasses or use a discriminated union pattern.

### Finding #281: type Action Extracts Query From Description
**Location:** blackreach/site_handlers.py:936
**Severity:** Medium
**Description:** `action.description.split(": ")[-1]` extracts text to type from the description string. This is fragile - if description format changes, typing breaks.
**Recommendation:** Add a dedicated `value` field to SiteAction for type operations.

### Finding #282: Handler domains Use Partial Strings
**Location:** blackreach/site_handlers.py:94, 175, 264, 304
**Severity:** Medium
**Description:** Domain matching uses `if d in domain` which matches partial strings. "annas-archive" would match "fake-annas-archive.com".
**Recommendation:** Use proper domain suffix matching or full domain comparison.

### Finding #283: Duplicate Search Action Patterns
**Location:** blackreach/site_handlers.py (multiple methods)
**Severity:** Medium
**Description:** Every handler's `get_search_actions()` follows the same pattern: type in input, click submit. This is duplicated ~15 times with only selector differences.
**Recommendation:** Create a base implementation that subclasses can customize selectors for.

### Finding #284: Missing Handler for Common Sites
**Location:** blackreach/site_handlers.py:855-873
**Severity:** Low
**Description:** `SITE_HANDLERS` registry is missing handlers for common sites like Twitter/X, LinkedIn, Medium, etc. that users might navigate to.
**Recommendation:** Add stubs for more common sites or make handler matching more graceful.

### Finding #285: HandlerResult actions_taken Contains Mutable Default
**Location:** blackreach/site_handlers.py:39
**Severity:** Low
**Description:** Uses `field(default_factory=list)` which is correct, but the class doesn't prevent mutation of the list after creation.
**Recommendation:** Consider returning a tuple or frozen list for immutability.

### Finding #286: AnnasArchiveHandler domains Has Inconsistent Entries
**Location:** blackreach/site_handlers.py:94
**Severity:** Low
**Description:** `domains = ["annas-archive", "anna's archive"]` - the apostrophe version won't appear in URLs but is listed anyway.
**Recommendation:** Remove the apostrophe version or document its purpose.

### Finding #287: Wait Action Uses String to Float Conversion
**Location:** blackreach/site_handlers.py:947
**Severity:** Low
**Description:** `time.sleep(float(action.target))` converts target to float. Invalid strings would crash with ValueError.
**Recommendation:** Add validation or try/except around the conversion.

### Finding #288: execute_actions Error Handling Inconsistent
**Location:** blackreach/site_handlers.py:920-958
**Severity:** Medium
**Description:** Some actions catch exceptions and check `action.optional`, but the handling isn't uniform. Some paths set `last_error` but don't break, others do.
**Recommendation:** Standardize error handling across all action types.

### Finding #289: SITE_HANDLERS Uses Class Types Not Instances
**Location:** blackreach/site_handlers.py:855
**Severity:** Low
**Description:** Registry stores handler classes not instances, requiring instantiation on each lookup. This wastes resources.
**Recommendation:** Pre-instantiate handlers or use lazy singleton pattern.

### Finding #290: AbstractMethod Implementations Not Validated
**Location:** blackreach/site_handlers.py:72-80
**Severity:** Low
**Description:** `get_download_actions` and `get_search_actions` are abstract, but handlers can return empty lists without indicating why. This makes debugging difficult.
**Recommendation:** Add logging when returning empty action lists, or use Optional return with reason.

### Finding #291: SourceHealth success_rate Returns 0.5 for Unknown
**Location:** blackreach/source_manager.py:56-60
**Severity:** Low
**Description:** When no requests have been made, `success_rate` returns 0.5. This could artificially inflate unknown sources vs those with actual 40% success rate.
**Recommendation:** Return a distinct value (None or NaN) for unknown, or document the 0.5 assumption.

### Finding #292: SourceManager Uses defaultdict Without Thread Safety
**Location:** blackreach/source_manager.py:130
**Severity:** Medium
**Description:** `self._health` uses `defaultdict(SourceHealth)` which creates new objects on access. Concurrent access could cause race conditions.
**Recommendation:** Add threading lock around health dictionary access.

### Finding #293: Multiple urlparse Imports Inside Methods
**Location:** blackreach/source_manager.py:144, 178, 243, 261, 314, 365
**Severity:** Low
**Description:** `from urllib.parse import urlparse` is imported multiple times inside different methods instead of once at module level.
**Recommendation:** Move to module-level import.

### Finding #294: _failover_history Trimming Uses List Slice
**Location:** blackreach/source_manager.py:271-272
**Severity:** Low
**Description:** Uses list slicing to trim failover history. This creates a new list on every call when over 50 items.
**Recommendation:** Use `collections.deque(maxlen=50)` for automatic size limiting.

### Finding #295: get_best_source Has Complex Scoring Logic
**Location:** blackreach/source_manager.py:155-222
**Severity:** Medium
**Description:** The scoring logic in `get_best_source()` has many magic numbers (10, 50, 10, 20, 30, 15) with unclear origins. Hard to tune or understand.
**Recommendation:** Extract scoring weights to constants or configuration.

### Finding #296: suggest_sources_for_goal Duplicates Scoring Logic
**Location:** blackreach/source_manager.py:348-399
**Severity:** Medium
**Description:** `suggest_sources_for_goal()` has similar but different scoring logic as `get_best_source()`. Duplication could lead to inconsistencies.
**Recommendation:** Extract shared scoring logic to a common method.

### Finding #297: SourceHealth _apply_cooldown Uses Hardcoded Values
**Location:** blackreach/source_manager.py:101-114
**Severity:** Low
**Description:** Cool-down periods (30, 120, 300, 600 seconds) are hardcoded. Not configurable for different environments.
**Recommendation:** Make cool-down periods configurable.

### Finding #298: SessionManager Opens New Connection Per Operation
**Location:** blackreach/session_manager.py:93, 144, 177, 215, 284, 314, 346, 419, 441
**Severity:** Medium
**Description:** Every database operation opens and closes a new SQLite connection. This is inefficient and could cause lock contention.
**Recommendation:** Use connection pooling or a persistent connection with proper thread safety.

### Finding #299: SessionState successful_selectors Uses Set
**Location:** blackreach/session_manager.py:66
**Severity:** Low
**Description:** `successful_selectors: Dict[str, Set[str]]` uses Set which isn't JSON-serializable. Conversion to/from list is done manually.
**Recommendation:** Use frozenset or document the serialization requirement.

### Finding #300: create_snapshot ID Not Truly Unique
**Location:** blackreach/session_manager.py:267
**Severity:** Low
**Description:** Snapshot ID format `snap_{session_id}_{step}_{HHMMSS}` could collide if multiple snapshots created in same second.
**Recommendation:** Add milliseconds or use UUID.

### Finding #301: Learning Data Keys Are Stringly Typed
**Location:** blackreach/session_manager.py:428-435
**Severity:** Low
**Description:** Learning data keys ("domain_knowledge", "successful_queries", etc.) are string constants used in multiple places. Typo would cause silent failure.
**Recommendation:** Use an enum or constants for learning data keys.

### Finding #302: _load_learning_data Silently Ignores Unknown Keys
**Location:** blackreach/session_manager.py:424-435
**Severity:** Low
**Description:** If a new learning data key is added to the database, `_load_learning_data()` would silently ignore it.
**Recommendation:** Log a warning for unrecognized keys.

### Finding #303: visited_urls Grows Without Limit
**Location:** blackreach/session_manager.py:386-387
**Severity:** Low
**Description:** `visited_urls` list appends every unique URL without limit. Long sessions could have very large state.
**Recommendation:** Limit to most recent N URLs or use a deque.

### Finding #304: actions_taken Stores Full Dict for Each Action
**Location:** blackreach/session_manager.py:389-390
**Severity:** Low
**Description:** Each action is stored as a full Dict. Hundreds of actions could make session state very large.
**Recommendation:** Store summarized actions or limit history length.

### Finding #305: No Index on sessions.last_update
**Location:** blackreach/session_manager.py:97-110
**Severity:** Low
**Description:** The sessions table is queried with `ORDER BY last_update DESC` but no index exists on this column.
**Recommendation:** Add index on last_update for efficient queries.

### Finding #306: get_resumable_sessions Returns Raw Dict
**Location:** blackreach/session_manager.py:344-368
**Severity:** Low
**Description:** Returns list of raw dicts instead of typed objects. Type safety is lost for callers.
**Recommendation:** Return list of SessionSummary dataclass or similar.

### Finding #307: JSON Serialization Catches No Exceptions
**Location:** blackreach/session_manager.py:206, 296
**Severity:** Low
**Description:** `json.dumps()` calls don't catch serialization errors. Non-serializable data would crash.
**Recommendation:** Add try/except with fallback or validation.

### Finding #308: SessionSnapshot Duplicates SessionState Fields
**Location:** blackreach/session_manager.py:30-42, 46-69
**Severity:** Low
**Description:** `SessionSnapshot` and `SessionState` share many fields (downloads, visited_urls, actions_taken, failures). Code duplication.
**Recommendation:** Use composition or inheritance to share common fields.

### Finding #309: complete_session Doesn't Save Learning Data
**Location:** blackreach/session_manager.py:398-404
**Severity:** Low
**Description:** `complete_session()` saves session but doesn't call `save_learning_data()`. Learning data might be lost.
**Recommendation:** Also save learning data on session completion.

### Finding #310: record_successful_pattern Uses Nested Dict Creation
**Location:** blackreach/session_manager.py:460-469
**Severity:** Low
**Description:** Three levels of conditional dict/list creation. Could use `defaultdict` for cleaner code.
**Recommendation:** Use `defaultdict(lambda: defaultdict(list))` pattern.

### Finding #311: LLM generate Returns Empty String on Exhausted Retries
**Location:** blackreach/llm.py:158
**Severity:** Medium
**Description:** After exhausting retries, `generate()` returns empty string `""` but doesn't log or indicate failure clearly. Callers might not realize the LLM call failed.
**Recommendation:** Raise an exception or return a sentinel value that callers can check.

### Finding #312: LLM _call_google Concatenates System and User Prompts
**Location:** blackreach/llm.py:219
**Severity:** Low
**Description:** `full_prompt = f"{system_prompt}\n\n{user_message}"` loses the semantic distinction between system and user prompts. This differs from other providers.
**Recommendation:** Use Gemini's system instruction feature if available.

### Finding #313: parse_action Uses Greedy Regex
**Location:** blackreach/llm.py:248
**Severity:** Low
**Description:** `re.search(r'\{[\s\S]*\}', cleaned)` uses greedy matching. If response contains multiple JSON objects, it might match the wrong one.
**Recommendation:** Use non-greedy `\{[\s\S]*?\}` or parse more carefully.

### Finding #314: LLMResponse done Logic Is Complex
**Location:** blackreach/llm.py:263-269
**Severity:** Low
**Description:** `done` can be set from `data.get("done")` or from `action == "done"`. The double check with fallback reason extraction is convoluted.
**Recommendation:** Simplify by normalizing the response structure.

### Finding #315: LLM Config Defaults Include GPU Settings
**Location:** blackreach/llm.py:28-29
**Severity:** Low
**Description:** `use_gpu: bool = True` and `num_gpu_layers: int = 999` are Ollama-specific but defined in general config used by all providers.
**Recommendation:** Move provider-specific settings to sub-configs or document they're ignored for non-Ollama.

### Finding #316: _init_client Uses String Matching for Providers
**Location:** blackreach/llm.py:62-75
**Severity:** Low
**Description:** Provider type is matched with string comparison instead of enum. Typos would silently fall through.
**Recommendation:** Use an enum for provider types with explicit handling.

### Finding #317: LLM Retry Delay Uses Linear Backoff
**Location:** blackreach/llm.py:155
**Severity:** Low
**Description:** `retry_delay * (attempt + 1)` is linear backoff. Exponential backoff is typically more effective for rate limiting.
**Recommendation:** Use exponential backoff: `retry_delay * (2 ** attempt)`.

### Finding #318: DownloadHistory Uses Context Manager Incorrectly
**Location:** blackreach/download_history.py:91, 135, 161, etc.
**Severity:** Low
**Description:** `with self._get_connection() as conn` doesn't automatically close the connection - SQLite connections don't work as context managers for closing.
**Recommendation:** Explicitly close connections or use `contextlib.closing()`.

### Finding #319: DownloadHistory Has Threading Lock But Connection Per Call
**Location:** blackreach/download_history.py:86, 114-116
**Severity:** Low
**Description:** `_lock` is used for write operations but each operation creates a new connection anyway. The lock provides limited benefit.
**Recommendation:** Use a shared connection with proper locking or connection pool.

### Finding #320: HistoryEntry from_row Has Implicit Column Ordering
**Location:** blackreach/download_history.py:46-59
**Severity:** Medium
**Description:** `from_row()` uses positional indexing `row[0]`, `row[1]`, etc. If column order changes in schema, this would silently break.
**Recommendation:** Use named columns via `sqlite3.Row` or explicit column selection.

### Finding #321: export_history Hardcodes Limit 10000
**Location:** blackreach/download_history.py:391
**Severity:** Low
**Description:** `get_recent_downloads(limit=10000)` hardcodes export limit. Users might have more than 10000 entries.
**Recommendation:** Make limit configurable or paginate export.

### Finding #322: import_history Silently Ignores Errors
**Location:** blackreach/download_history.py:441-442
**Severity:** Medium
**Description:** `except Exception: continue` silently ignores any import error. User won't know which entries failed.
**Recommendation:** Collect and report errors, or at minimum log them.

### Finding #323: search_history Uses String Interpolation in SQL
**Location:** blackreach/download_history.py:298-299
**Severity:** Low
**Description:** `f"SELECT * FROM download_history WHERE {where_clause}"` uses f-string for SQL. While `where_clause` is controlled, it's still an anti-pattern.
**Recommendation:** Build query using parameterization throughout.

### Finding #324: check_hash_exists Doesn't Normalize Hash Case
**Location:** blackreach/download_history.py:182-198
**Severity:** Low
**Description:** Hash comparison is case-sensitive. Same hash in different cases (a1b2 vs A1B2) would not match.
**Recommendation:** Normalize to lowercase before comparison.

### Finding #325: DuplicateInfo duplicate_type Is Stringly Typed
**Location:** blackreach/download_history.py:66
**Severity:** Low
**Description:** `duplicate_type: str` accepts arbitrary strings. Should be an enum ('url', 'hash', 'none').
**Recommendation:** Use an enum for type safety.

### Finding #326: get_statistics Returns Mixed Types
**Location:** blackreach/download_history.py:343-351
**Severity:** Low
**Description:** Returns dict with `total_size_bytes` (int) and `total_size_mb` (float rounded). Mixed precision handling.
**Recommendation:** Keep raw values, let callers format.

### Finding #327: Global _download_history Not Thread Safe
**Location:** blackreach/download_history.py:448-456
**Severity:** Medium
**Description:** `get_download_history()` checks and sets `_download_history` without locking. Race condition in concurrent initialization.
**Recommendation:** Add lock around singleton creation.

### Finding #328: DownloadHistory db_path Accepts None
**Location:** blackreach/download_history.py:74-81
**Severity:** Low
**Description:** If `db_path` is None, defaults to user home directory. This may not be appropriate for all contexts (e.g., tests).
**Recommendation:** Make default explicit in config rather than __init__.

### Finding #329: TimeoutError Shadows Built-in
**Location:** blackreach/exceptions.py:130
**Severity:** Medium
**Description:** `class TimeoutError(BrowserError)` shadows Python's built-in `TimeoutError`. This could cause confusion and unexpected behavior.
**Recommendation:** Rename to `BrowserTimeoutError` or `OperationTimeoutError`.

### Finding #330: ConnectionError Shadows Built-in
**Location:** blackreach/exceptions.py:396
**Severity:** Medium
**Description:** `class ConnectionError(NetworkError)` shadows Python's built-in `ConnectionError`. Same issue as TimeoutError.
**Recommendation:** Rename to `NetworkConnectionError` or `BlackreachConnectionError`.

### Finding #331: Exception Hierarchy Is Deep But Inconsistent
**Location:** blackreach/exceptions.py:46-444
**Severity:** Low
**Description:** Some exceptions have 3 levels of inheritance (e.g., `RateLimitError` -> `APIError` -> `LLMError` -> `BlackreachError`) while others have fewer. Inconsistent depth.
**Recommendation:** Document the hierarchy or flatten where not needed.

### Finding #332: ProviderNotInstalledError Calls Parent with Message as Reason
**Location:** blackreach/exceptions.py:164-167
**Severity:** Low
**Description:** `super().__init__(provider, message)` passes the full message as `reason` to `ProviderError`, which then reformats it. Double messaging.
**Recommendation:** Just set fields directly without calling parent's formatting.

### Finding #333: ParseError Truncates raw_response
**Location:** blackreach/exceptions.py:179
**Severity:** Low
**Description:** `raw_response[:500]` truncates to 500 chars but doesn't indicate truncation occurred. Debugging could be confusing.
**Recommendation:** Add `"... (truncated)"` suffix when truncating.

### Finding #334: Exception Details Not Immutable
**Location:** blackreach/exceptions.py:32
**Severity:** Low
**Description:** `self.details = details or {}` creates a mutable dict. Callers could modify exception details after creation.
**Recommendation:** Use `types.MappingProxyType` or document mutability.

### Finding #335: TimeoutManager Uses Nested defaultdict
**Location:** blackreach/timeout_manager.py:55-57
**Severity:** Low
**Description:** `defaultdict(lambda: defaultdict(list))` is correct but makes type hints and IDE support difficult.
**Recommendation:** Use explicit initialization or TypedDict for structure.

### Finding #336: TimeoutManager _active Dict Grows Unbounded
**Location:** blackreach/timeout_manager.py:70
**Severity:** Low
**Description:** `_active` dict stores start times for operations. If `end_timing()` is never called (e.g., due to crash), entries accumulate.
**Recommendation:** Add periodic cleanup or max size limit.

### Finding #337: start_timing Key Uses datetime.now().isoformat()
**Location:** blackreach/timeout_manager.py:121
**Severity:** Low
**Description:** The timing key includes isoformat which may not be unique if called multiple times per millisecond. Similar issue as other ID generation.
**Recommendation:** Add microseconds or random component.

### Finding #338: end_timing Requires Caller to Pass action and domain Again
**Location:** blackreach/timeout_manager.py:125-131
**Severity:** Low
**Description:** `end_timing(timing_key, success, action, domain)` requires action and domain even though they're encoded in timing_key. Could mismatch.
**Recommendation:** Parse action/domain from key or store in _active dict.

### Finding #339: Timing Data Trimming Creates New List
**Location:** blackreach/timeout_manager.py:147-148
**Severity:** Low
**Description:** `self.timings[domain][action] = self.timings[domain][action][-max_samples:]` creates new list. Use deque instead.
**Recommendation:** Use `collections.deque(maxlen=max_samples)`.

### Finding #340: get_stats Has Quadruple Nested Loop
**Location:** blackreach/timeout_manager.py:176-179
**Severity:** Low
**Description:** When aggregating all timings, code loops through `timings.values()` then `domain_timings.values()` then `extend`. Could be slow with lots of data.
**Recommendation:** Cache aggregated stats or use more efficient data structure.

### Finding #341: suggest_timeout_adjustment Magic Numbers
**Location:** blackreach/timeout_manager.py:195-220
**Severity:** Low
**Description:** Uses magic numbers (0.5, 0.1, 1.5, 0.8) for timeout rate thresholds and adjustment factors without explanation.
**Recommendation:** Define as constants with documentation.

### Finding #342: import_data Doesn't Validate Data
**Location:** blackreach/timeout_manager.py:239-248
**Severity:** Low
**Description:** `import_data()` assumes correct structure. Missing keys or wrong types would cause KeyError or TypeError.
**Recommendation:** Add validation or try/except with logging.

### Finding #343: Global _timeout_manager Not Thread Safe
**Location:** blackreach/timeout_manager.py:252-260
**Severity:** Medium
**Description:** Same pattern as other modules - singleton creation without locking. Race condition in multi-threaded usage.
**Recommendation:** Add lock around initialization.

### Finding #344: reset_timeout_manager Only Clears Reference
**Location:** blackreach/timeout_manager.py:263-266
**Severity:** Low
**Description:** `_timeout_manager = None` clears the global but doesn't clean up any state in the old instance. If any code holds a reference, old data persists.
**Recommendation:** Call cleanup method on old instance or document behavior.

### Finding #345: TimeoutConfig buffer_factor Default 1.5
**Location:** blackreach/timeout_manager.py:25
**Severity:** Low
**Description:** 1.5x buffer factor is arbitrary. No documentation on why this value was chosen or how to tune it.
**Recommendation:** Add documentation for the buffer factor choice.

### Finding #346: CONTENT_SOURCES Is Mutable Global List
**Location:** blackreach/knowledge.py:28-476
**Severity:** Low
**Description:** `CONTENT_SOURCES` is a mutable list defined at module level. Any code could accidentally modify it.
**Recommendation:** Use a tuple or freeze the list after creation.

### Finding #347: ContentSource mirrors Empty List Default
**Location:** blackreach/knowledge.py:23
**Severity:** Low
**Description:** Many ContentSource entries explicitly set `mirrors=[]` even though `field(default_factory=list)` already provides empty list. Redundant.
**Recommendation:** Remove redundant empty list assignments.

### Finding #348: detect_content_type Re-compiles Regex Each Call
**Location:** blackreach/knowledge.py:489-514
**Severity:** Medium
**Description:** `re.search(pattern, goal_lower)` compiles regex patterns on every function call. With many patterns, this is inefficient.
**Recommendation:** Pre-compile patterns at module level.

### Finding #349: extract_subject Re-compiles Many Regex Patterns
**Location:** blackreach/knowledge.py:543-572
**Severity:** Medium
**Description:** Similar to detect_content_type, many regex patterns are re-compiled on every call.
**Recommendation:** Pre-compile all regex patterns at module level.

### Finding #350: find_best_sources Uses Magic Numbers
**Location:** blackreach/knowledge.py:597, 606, 609
**Severity:** Low
**Description:** Scoring uses magic numbers (10, 20, 15) without explanation.
**Recommendation:** Document or extract to constants.

### Finding #351: check_url_reachable Broad Exception Catch
**Location:** blackreach/knowledge.py:707
**Severity:** Low
**Description:** Catches `Exception` in addition to specific urllib errors. Could hide unexpected errors.
**Recommendation:** Remove generic Exception catch or log it.

### Finding #352: check_url_reachable Imports Inside Function
**Location:** blackreach/knowledge.py:697-698
**Severity:** Low
**Description:** `import urllib.request` and `import urllib.error` are inside the function body.
**Recommendation:** Move to module level imports.

### Finding #353: get_working_url Checks URLs Sequentially
**Location:** blackreach/knowledge.py:718-720
**Severity:** Low
**Description:** URLs are checked one at a time. For sources with many mirrors, this could be slow.
**Recommendation:** Consider parallel checking with ThreadPoolExecutor.

### Finding #354: check_sources_health Blocks on Network Calls
**Location:** blackreach/knowledge.py:749-771
**Severity:** Medium
**Description:** Health check iterates through all sources sequentially, making blocking network calls. Very slow with many sources.
**Recommendation:** Use async or parallel requests.

### Finding #355: ContentSource priority Field Undocumented Range
**Location:** blackreach/knowledge.py:21
**Severity:** Low
**Description:** `priority: int = 5` with comment "1-10" but no validation. Sources could have invalid priority values.
**Recommendation:** Add validation or use Literal type.

### Finding #356: reason_about_goal Returns Dict Not Dataclass
**Location:** blackreach/knowledge.py:621-664
**Severity:** Low
**Description:** Returns a plain dict with many keys. A dataclass would provide better type safety and documentation.
**Recommendation:** Create a `GoalReasoning` dataclass for the return type.

### Finding #357: get_smart_start Returns Tuple Without Named Fields
**Location:** blackreach/knowledge.py:668-679
**Severity:** Low
**Description:** Returns `(url, reasoning, search_query)` tuple. Easy to mix up the order when unpacking.
**Recommendation:** Return a NamedTuple or dataclass.

### Finding #358: Empty mirrors Lists Still Checked
**Location:** blackreach/knowledge.py:766-771
**Severity:** Low
**Description:** `if not is_reachable and source.mirrors:` checks mirrors, but many sources explicitly have empty mirrors lists.
**Recommendation:** Skip mirror checking when mirrors is empty.

### Finding #359: CONTENT_SOURCES Contains Stale URLs
**Location:** blackreach/knowledge.py:38, 66, 76
**Severity:** Low
**Description:** Comments like "Mirrors are unreliable, removed" suggest the knowledge base may have outdated information.
**Recommendation:** Add version/last-updated timestamp or periodic validation.

### Finding #360: detect_content_type Special Case Logic
**Location:** blackreach/knowledge.py:517-527
**Severity:** Low
**Description:** Special handling for "ebook" vs "book" and "pdf" type inference is hardcoded logic that's hard to maintain.
**Recommendation:** Extract to a separate type refinement function.

### Finding #361: LRUCache _save_to_disk Silently Ignores Errors
**Location:** blackreach/cache.py:203-204
**Severity:** Low
**Description:** `except Exception: pass` swallows all errors during disk persistence. Data loss could go unnoticed.
**Recommendation:** Log the error before ignoring.

### Finding #362: LRUCache _load_from_disk Silently Ignores Errors
**Location:** blackreach/cache.py:224-225
**Severity:** Low
**Description:** Same issue as _save_to_disk - all errors are silently ignored.
**Recommendation:** Log the error before ignoring.

### Finding #363: PageCache Uses MD5 for URL Keys
**Location:** blackreach/cache.py:264
**Severity:** Low
**Description:** `hashlib.md5(url.encode()).hexdigest()` uses MD5 for cache keys. MD5 has known collision vulnerabilities.
**Recommendation:** Use SHA256 or faster non-cryptographic hash like xxhash.

### Finding #364: ResultCache Uses MD5 for Query Keys
**Location:** blackreach/cache.py:296
**Severity:** Low
**Description:** Same MD5 usage for query keys.
**Recommendation:** Use SHA256 or faster non-cryptographic hash.

### Finding #365: CacheEntry size_bytes Default 0
**Location:** blackreach/cache.py:34
**Severity:** Low
**Description:** `size_bytes: int = 0` defaults to 0 even when value is provided. Size tracking may be inaccurate.
**Recommendation:** Calculate size automatically if not provided.

### Finding #366: Global Cache Instances Not Thread Safe
**Location:** blackreach/cache.py:308-321
**Severity:** Medium
**Description:** `get_page_cache()` and `get_result_cache()` check and set globals without locking. Race condition in initialization.
**Recommendation:** Add lock around singleton creation.

### Finding #367: _evict_one Iterates All Entries to Find Expired
**Location:** blackreach/cache.py:152-156
**Severity:** Low
**Description:** Eviction first tries to find any expired entry by iterating the entire cache. This is O(n) when it could track expiration more efficiently.
**Recommendation:** Use a min-heap or sorted structure for expiration tracking.

### Finding #368: CacheConfig max_size_bytes Not Enforced in PageCache
**Location:** blackreach/cache.py:243
**Severity:** Low
**Description:** `size_bytes=len(html.encode())` calculates size but doesn't check if it exceeds max_size_bytes before caching.
**Recommendation:** Add validation that entry doesn't exceed max cache size.

### Finding #369: _should_evict Doesn't Account for Entry Being Replaced
**Location:** blackreach/cache.py:141-147
**Severity:** Low
**Description:** When replacing an existing key, the old size isn't considered when deciding whether to evict.
**Recommendation:** Factor in the size delta when key already exists.

### Finding #370: OrderedDict Iteration Order Changes in Python 3.7+
**Location:** blackreach/cache.py:59
**Severity:** Low
**Description:** `OrderedDict` preserves insertion order but regular `dict` does too in Python 3.7+. The choice of OrderedDict isn't strictly necessary.
**Recommendation:** Document why OrderedDict is used (for `move_to_end` method) or use regular dict.

### Finding #371: ParallelFetcher Not Actually Parallel
**Location:** blackreach/parallel_ops.py:140-149
**Severity:** High
**Description:** The `fetch_pages` method processes URLs in a loop without using threads or async. Despite the class name "ParallelFetcher", it fetches sequentially within each batch.
**Recommendation:** Use ThreadPoolExecutor.map() or asyncio.gather() to actually fetch pages in parallel.

### Finding #372: ParallelDownloader Not Actually Parallel
**Location:** blackreach/parallel_ops.py:289-305
**Severity:** High
**Description:** Same issue as ParallelFetcher - the download loop processes files sequentially, not in parallel.
**Recommendation:** Use concurrent.futures for actual parallelism.

### Finding #373: ParallelSearcher Sequential Processing
**Location:** blackreach/parallel_ops.py:413-433
**Severity:** High
**Description:** Search sources are queried one at a time despite being named "ParallelSearcher".
**Recommendation:** Use actual parallel execution.

### Finding #374: Global Parallel Manager Not Thread Safe
**Location:** blackreach/parallel_ops.py:558-571
**Severity:** Medium
**Description:** `get_parallel_manager()` checks and sets global without locking, risking race conditions.
**Recommendation:** Add threading.Lock for singleton initialization.

### Finding #375: _fetch_single Import Inside Method
**Location:** blackreach/parallel_ops.py:170
**Severity:** Low
**Description:** `from urllib.parse import urlparse` is inside the method body, called for every fetch.
**Recommendation:** Move to module level.

### Finding #376: _download_single Import Inside Method
**Location:** blackreach/parallel_ops.py:319-320
**Severity:** Low
**Description:** `from urllib.parse import urlparse` and `from pathlib import Path` inside method body.
**Recommendation:** Move to module level.

### Finding #377: search_multiple_sources Import Inside Method
**Location:** blackreach/parallel_ops.py:409
**Severity:** Low
**Description:** `from urllib.parse import quote` inside method.
**Recommendation:** Move to module level.

### Finding #378: _extract_search_results Import Inside Method
**Location:** blackreach/parallel_ops.py:438
**Severity:** Low
**Description:** `from bs4 import BeautifulSoup` inside method - expensive import on every call.
**Recommendation:** Move to module level.

### Finding #379: TaskScheduler _generate_id Not Thread Safe
**Location:** blackreach/task_scheduler.py:99-102
**Severity:** Medium
**Description:** Counter increment without lock protection despite class having a `_lock` attribute.
**Recommendation:** Use the existing lock when incrementing counter.

### Finding #380: PriorityQueue get_nowait May Fail
**Location:** blackreach/task_scheduler.py:173
**Severity:** Low
**Description:** Using `queue.get_nowait()` in a loop. If another thread takes an item between empty() check and get_nowait(), exception occurs.
**Recommendation:** Use proper queue synchronization.

### Finding #381: wait_all Busy-Waits with Fixed Sleep
**Location:** blackreach/task_scheduler.py:291-299
**Severity:** Low
**Description:** Polls with `time.sleep(0.5)` instead of using event-based synchronization.
**Recommendation:** Use threading.Event for completion signaling.

### Finding #382: Global Scheduler Not Thread Safe
**Location:** blackreach/task_scheduler.py:307-312
**Severity:** Medium
**Description:** `get_scheduler()` singleton initialization without lock.
**Recommendation:** Add lock protection.

### Finding #383: TabManager asyncio.Lock May Fail
**Location:** blackreach/multi_tab.py:59
**Severity:** Medium
**Description:** `self._lock = asyncio.Lock() if asyncio else None` - asyncio is always truthy (it's a module). The lock is created but never used.
**Recommendation:** Fix condition or use the lock in async methods.

### Finding #384: SyncTabManager Missing Thread Safety
**Location:** blackreach/multi_tab.py:181-294
**Severity:** Medium
**Description:** `SyncTabManager` has no locking despite being used by parallel operations. Tab pool operations could race.
**Recommendation:** Add threading.Lock for tab management operations.

### Finding #385: TabInfo Uses Generic Any for Page
**Location:** blackreach/multi_tab.py:32
**Severity:** Low
**Description:** `page: Any  # Playwright Page object` loses type safety.
**Recommendation:** Import and use proper Playwright Page type.

### Finding #386: SessionManager Database Connection Per Operation
**Location:** blackreach/session_manager.py:143-155, 171-211
**Severity:** Medium
**Description:** Each method opens and closes its own database connection. High overhead and no connection pooling.
**Recommendation:** Use connection pooling or context manager pattern.

### Finding #387: SessionState Uses Mutable Default in Dataclass
**Location:** blackreach/session_manager.py:59-69
**Severity:** Low
**Description:** `successful_selectors: Dict[str, Set[str]] = field(default_factory=dict)` - the Set inside Dict requires careful handling during serialization.
**Recommendation:** Document serialization requirements or simplify structure.

### Finding #388: save_session No Error Handling
**Location:** blackreach/session_manager.py:171-211
**Severity:** Low
**Description:** Database write operations don't handle SQLite errors or connection failures.
**Recommendation:** Add try/except with proper error handling.

### Finding #389: record_successful_pattern Unbounded List Growth
**Location:** blackreach/session_manager.py:460-469
**Severity:** Low
**Description:** Patterns are appended without limit. Long-running usage could accumulate huge lists.
**Recommendation:** Add maximum pattern count per type.

### Finding #390: Global Session Manager Path Hardcoded
**Location:** blackreach/session_manager.py:484
**Severity:** Low
**Description:** `db_path = db_path or Path("./memory.db")` uses current directory instead of user config directory.
**Recommendation:** Use platform-appropriate path like ~/.blackreach/memory.db.

### Finding #391: TimeoutManager Uses statistics Without Guard
**Location:** blackreach/timeout_manager.py:190
**Severity:** Low
**Description:** `statistics.mean(durations)` will raise StatisticsError on empty list, though guarded above.
**Recommendation:** Add explicit check for clarity.

### Finding #392: ActionTiming Timestamp Default Evaluated at Import
**Location:** blackreach/timeout_manager.py:34
**Severity:** Low
**Description:** `timestamp: datetime = field(default_factory=datetime.now)` - correct usage, but the pattern elsewhere may not be.
**Recommendation:** Audit all datetime defaults in dataclasses.

### Finding #393: export_data Creates Deeply Nested Dict
**Location:** blackreach/timeout_manager.py:222-237
**Severity:** Low
**Description:** Three levels of dictionary comprehension makes the code hard to read.
**Recommendation:** Refactor into explicit loops for clarity.

### Finding #394: RetryBudget window_start Default Evaluated Once
**Location:** blackreach/retry_strategy.py:63
**Severity:** Low
**Description:** `window_start: datetime = field(default_factory=datetime.now)` - creates one timestamp at instance creation, which is correct but should be documented.
**Recommendation:** Add comment explaining the timestamp semantics.

### Finding #395: ErrorClassifier Pattern Matching is O(n*m)
**Location:** blackreach/retry_strategy.py:291-298
**Severity:** Low
**Description:** For each error, iterates all categories and all patterns. Could be slow with many errors.
**Recommendation:** Pre-compile patterns into a single regex or use more efficient matching.

### Finding #396: with_retry Last Exception May Be None
**Location:** blackreach/retry_strategy.py:352-354
**Severity:** Low
**Description:** If `func()` never raises, `last_error` remains None. Raising None would cause confusing error.
**Recommendation:** Add guard or ensure exception always assigned in except block.

### Finding #397: CLI Interactive Mode 1700+ Lines
**Location:** blackreach/cli.py:1-1709
**Severity:** High
**Description:** The CLI module is extremely long with many responsibilities including setup, commands, and interactive mode.
**Recommendation:** Split into separate modules: cli_commands.py, cli_setup.py, cli_interactive.py.

### Finding #398: Global _active_agent State
**Location:** blackreach/cli.py:32, 241, 298, etc.
**Severity:** Medium
**Description:** Uses global mutable state for active agent reference. Not thread-safe.
**Recommendation:** Use context managers or class-based state management.

### Finding #399: signal.signal SIGINT May Fail Silently
**Location:** blackreach/cli.py:52-55
**Severity:** Low
**Description:** Catches ValueError on SIGINT registration but doesn't log it.
**Recommendation:** At least log a debug message about signal registration failure.

### Finding #400: check_playwright_browsers Subprocess with capture_output
**Location:** blackreach/cli.py:86-92
**Severity:** Low
**Description:** Uses subprocess without timeout. Could hang indefinitely if playwright command freezes.
**Recommendation:** Add timeout parameter.

### Finding #401: install_playwright_browsers No Timeout
**Location:** blackreach/cli.py:106-109
**Severity:** Medium
**Description:** `subprocess.run` without timeout during browser installation. Could hang forever.
**Recommendation:** Add reasonable timeout (e.g., 300 seconds).

### Finding #402: check_ollama_running Broad Exception Catch
**Location:** blackreach/cli.py:126-127
**Severity:** Low
**Description:** `except Exception:` catches everything including import errors.
**Recommendation:** Catch specific exceptions.

### Finding #403: run Command Long Parameter List
**Location:** blackreach/cli.py:225-235
**Severity:** Low
**Description:** Function signature has 9 parameters - hard to maintain and call correctly.
**Recommendation:** Use a config dataclass to group related options.

### Finding #404: interactive_mode Complex Control Flow
**Location:** blackreach/cli.py:1325-1620
**Severity:** High
**Description:** Nearly 300 lines of if/elif chain handling slash commands. Very hard to maintain.
**Recommendation:** Use command pattern with registered handlers.

### Finding #405: provider_map Dict Created on Every Choice
**Location:** blackreach/cli.py:158
**Severity:** Low
**Description:** Dictionary created inline on each call to run_first_time_setup.
**Recommendation:** Define as module constant.

### Finding #406: Datetime Import Inside Function
**Location:** blackreach/cli.py:1037, 1078, 1104, 1293
**Severity:** Low
**Description:** `from datetime import datetime` imported inside multiple functions.
**Recommendation:** Move to module level.

### Finding #407: downloads Command Repeated Size Formatting Logic
**Location:** blackreach/cli.py:1066-1072, 1088-1094
**Severity:** Low
**Description:** Size formatting (KB/MB/GB) logic is duplicated.
**Recommendation:** Extract to helper function.

### Finding #408: sessions Command Repeated Duration Formatting
**Location:** blackreach/cli.py:1146-1161
**Severity:** Low
**Description:** Duration formatting logic is inline and complex.
**Recommendation:** Extract to helper function.

### Finding #409: CookieEncryption Fixed Salt
**Location:** blackreach/cookie_manager.py:182
**Severity:** Medium
**Description:** `salt = b"blackreach_cookie_salt_v1"` - using fixed salt for all password-based encryption reduces security.
**Recommendation:** Generate random salt and store with encrypted data.

### Finding #410: CookieEncryption Machine ID Fallback Weak
**Location:** blackreach/cookie_manager.py:218-223
**Severity:** Medium
**Description:** Fallback to hostname + username is easily guessable and not unique across machines.
**Recommendation:** Consider more robust machine identification or warn user.

### Finding #411: CookieManager print() for Errors
**Location:** blackreach/cookie_manager.py:374
**Severity:** Low
**Description:** `print(f"Error loading cookie profile '{name}': {e}")` instead of using logging.
**Recommendation:** Use logger.error().

### Finding #412: CookieProfile Linear Search for Cookies
**Location:** blackreach/cookie_manager.py:122-127, 129-139
**Severity:** Low
**Description:** Cookie lookup and domain matching iterate through all cookies. Could be slow with many cookies.
**Recommendation:** Index cookies by domain for O(1) lookup.

### Finding #413: import_netscape Silently Skips Malformed Lines
**Location:** blackreach/cookie_manager.py:510-517
**Severity:** Low
**Description:** Lines with fewer than 7 parts are silently skipped without logging.
**Recommendation:** Log skipped lines for debugging.

### Finding #414: get_cookie_manager Not Thread Safe
**Location:** blackreach/cookie_manager.py:556-569
**Severity:** Medium
**Description:** Global singleton initialization without locking.
**Recommendation:** Add threading.Lock.

### Finding #415: CookieManager stores password in memory
**Location:** blackreach/cookie_manager.py:279-280
**Severity:** Low
**Description:** If password is provided, it's used to create Fernet but could be extractable from memory.
**Recommendation:** Document security implications or use secure memory handling.

### Finding #416: browser.py restart() Swallows All Exceptions
**Location:** blackreach/browser.py:404-422
**Severity:** Medium
**Description:** Multiple `except Exception: pass` blocks hide errors during restart.
**Recommendation:** Log errors before ignoring.

### Finding #417: browser.py _wait_for_challenge_resolution Import Inside Loop
**Location:** blackreach/browser.py:776
**Severity:** Low
**Description:** `import random` inside the method that may be called frequently.
**Recommendation:** Move to module level.

### Finding #418: goto() Magic Numbers for Timeouts
**Location:** blackreach/browser.py:709, 719, 725, 735, 741, 746
**Severity:** Low
**Description:** Multiple hardcoded timeout values (45000, 15000, 10000, etc.) without explanation.
**Recommendation:** Extract to named constants or configuration.

### Finding #419: _wait_for_dynamic_content 8 Nested Strategies
**Location:** blackreach/browser.py:827-1000
**Severity:** High
**Description:** Already documented as Finding #12, but worth noting again - this single method has 7+ different strategies with multiple nested loops and try/except.
**Recommendation:** Extract each strategy to separate method.

### Finding #420: execute() Large Switch Statement
**Location:** blackreach/browser.py:1524-1561
**Severity:** Medium
**Description:** 15 if/elif branches for action routing. Hard to extend and maintain.
**Recommendation:** Use command pattern with action handlers.

### Finding #421: error_recovery.py Global Singleton Without Thread Safety
**Location:** blackreach/error_recovery.py:468-476
**Severity:** Medium
**Description:** `_global_recovery` singleton is accessed without locking, allowing race conditions in concurrent use.
**Recommendation:** Use threading.Lock or a thread-local pattern.

### Finding #422: ErrorRecovery Uses time.sleep() in Recovery Logic
**Location:** blackreach/error_recovery.py:338, 349
**Severity:** Medium
**Description:** `_apply_strategy()` calls `time.sleep()` directly within the method. This blocks the entire thread and prevents async usage.
**Recommendation:** Return the delay duration instead, let caller decide how to wait.

### Finding #423: error_recovery.py Unbounded Error History Growth
**Location:** blackreach/error_recovery.py:203-205
**Severity:** Low
**Description:** `_error_counts` and `_recovery_success` dicts grow unbounded as different error categories are encountered.
**Recommendation:** Add a max size or use LRU eviction.

### Finding #424: search_intel.py Global Singleton Without Thread Safety
**Location:** blackreach/search_intel.py:479-487
**Severity:** Medium
**Description:** `_search_intel` global singleton has no thread protection.
**Recommendation:** Add thread-safe initialization.

### Finding #425: search_intel.py pop() Mutates Query Alternatives
**Location:** blackreach/search_intel.py:451
**Severity:** Medium
**Description:** `get_next_query()` uses `pop(0)` which mutates the original SearchQuery object, making the method non-idempotent.
**Recommendation:** Track consumed alternatives separately or use a different data structure.

### Finding #426: search_intel.py Unbounded Session List Growth
**Location:** blackreach/search_intel.py:370, 392
**Severity:** Low
**Description:** `sessions` list grows unbounded as searches are performed. No cleanup mechanism.
**Recommendation:** Add maximum session limit or TTL-based cleanup.

### Finding #427: planner.py Creates New LLM Instance Per Call
**Location:** blackreach/planner.py:77-78, 215-216
**Severity:** Medium
**Description:** `Planner.__init__` and `maybe_plan()` create new LLM instances. LLM initialization may be expensive.
**Recommendation:** Cache/reuse LLM instances or use dependency injection.

### Finding #428: planner.py Fallback Plan Has Magic Number 20
**Location:** blackreach/planner.py:161-168, 188-195
**Severity:** Low
**Description:** When JSON parsing fails, `estimated_steps=20` is hardcoded without explanation.
**Recommendation:** Document why 20 is the fallback or make configurable.

### Finding #429: planner.py Simplified Goal Detection Logic
**Location:** blackreach/planner.py:94-137
**Severity:** Low
**Description:** `is_simple_goal()` uses basic substring matching that may be inaccurate. "download" marks all goals as complex even for single items.
**Recommendation:** Consider more sophisticated NLP or pattern matching.

### Finding #430: resilience.py CircuitBreaker Uses time.time() for State
**Location:** blackreach/resilience.py:114
**Severity:** Low
**Description:** State transitions happen in `state` property getter via side effects when checking recovery timeout.
**Recommendation:** Property getters should not have side effects. Use explicit state transition methods.

### Finding #431: resilience.py SmartSelector._try_selector Division Bug
**Location:** blackreach/resilience.py:239
**Severity:** Medium
**Description:** `timeout=self.timeout / len([selector])` always divides by 1 since `[selector]` creates a single-element list. This appears to be a bug.
**Recommendation:** Fix to use the actual selector count from the parent call.

### Finding #432: resilience.py CircuitBreakerOpen Import Location
**Location:** blackreach/resilience.py:179-185
**Severity:** Low
**Description:** `CircuitBreakerOpen` exception is defined after `CircuitBreaker` class. If referenced before class definition, causes NameError.
**Recommendation:** Move exception definition before the class that uses it.

### Finding #433: resilience.py Multiple Bare Exception Catches
**Location:** blackreach/resilience.py:220, 270, 280, 453, 458
**Severity:** Medium
**Description:** Multiple `except Exception` catches that swallow errors silently.
**Recommendation:** Catch specific exceptions and log others.

### Finding #434: resilience.py find_fuzzy Performance Issue
**Location:** blackreach/resilience.py:425-459
**Severity:** Medium
**Description:** `find_fuzzy()` iterates all visible elements and computes SequenceMatcher ratio for each. O(n*m) complexity can be slow.
**Recommendation:** Add early termination or use more efficient fuzzy matching (e.g., rapidfuzz library).

### Finding #435: resilience.py WaitConditions.wait_for_ajax Incomplete
**Location:** blackreach/resilience.py:758-784
**Severity:** Low
**Description:** JavaScript code creates new variables but the pending counter is never actually used. Logic appears incomplete.
**Recommendation:** Complete the AJAX tracking logic or remove dead code.

### Finding #436: detection.py Long Class with 500+ Lines
**Location:** blackreach/detection.py:40-586
**Severity:** Medium
**Description:** `SiteDetector` class is over 500 lines with many detection methods that share similar patterns.
**Recommendation:** Extract pattern matching to helper methods; consider strategy pattern.

### Finding #437: detection.py Duplicated Pattern Matching Logic
**Location:** blackreach/detection.py:177-219, 221-262, 264-295
**Severity:** Medium
**Description:** Each `detect_*` method has nearly identical structure: set indicators=[], confidence=0.0, check patterns, cap confidence.
**Recommendation:** Create a generic pattern detector method.

### Finding #438: detection.py Only Returns First 3 Matches
**Location:** blackreach/detection.py:191, 235, 271, etc.
**Severity:** Low
**Description:** `matches[:3]` limits pattern matches to 3 without explanation.
**Recommendation:** Document rationale or make configurable.

### Finding #439: stealth.py Large JavaScript Strings
**Location:** blackreach/stealth.py:206-275, 285-343, etc.
**Severity:** Medium
**Description:** Multiple large inline JavaScript strings (50-100+ lines each) for spoofing. Hard to maintain and test.
**Recommendation:** Move JavaScript to external files or use template strings.

### Finding #440: stealth.py Random Values Computed at Runtime
**Location:** blackreach/stealth.py:255-266, 282-283
**Severity:** Low
**Description:** Random values for hardwareConcurrency, deviceMemory, noise_seed are computed when scripts are generated. Each call returns different scripts.
**Recommendation:** Document this behavior or make deterministic with seed.

### Finding #441: stealth.py Hardcoded GPU Configurations
**Location:** blackreach/stealth.py:351-357
**Severity:** Low
**Description:** `gpu_configs` list is hardcoded with specific GPU models that may become outdated.
**Recommendation:** Move to configuration file for easier updates.

### Finding #442: knowledge.py Global CONTENT_SOURCES List is 475+ Lines
**Location:** blackreach/knowledge.py:28-476
**Severity:** Medium
**Description:** Large static data structure defined inline makes the module hard to read. Mix of code and data.
**Recommendation:** Move to JSON/YAML configuration file.

### Finding #443: knowledge.py check_url_reachable Has Import Inside Function
**Location:** blackreach/knowledge.py:697-698
**Severity:** Low
**Description:** `import urllib.request` and `import urllib.error` inside function body.
**Recommendation:** Move imports to module level.

### Finding #444: knowledge.py Synchronous URL Checking
**Location:** blackreach/knowledge.py:692-708
**Severity:** Medium
**Description:** `check_url_reachable()` is synchronous. When `check_sources_health()` is called, it checks sources sequentially, which is slow.
**Recommendation:** Use concurrent.futures for parallel health checks.

### Finding #445: knowledge.py Potential Blocking in get_healthy_sources
**Location:** blackreach/knowledge.py:776-794
**Severity:** Medium
**Description:** Calls `check_sources_health()` synchronously for all sources. Could block for 10+ seconds with many sources.
**Recommendation:** Add async version or cache health status.

### Finding #446: nav_context.py Global Singleton Without Thread Safety
**Location:** blackreach/nav_context.py:416-424
**Severity:** Medium
**Description:** `_nav_context` global has no thread protection.
**Recommendation:** Add thread-safe initialization.

### Finding #447: nav_context.py Unused hashlib Import
**Location:** blackreach/nav_context.py:12
**Severity:** Low
**Description:** `hashlib` is imported but never used in the module.
**Recommendation:** Remove unused import.

### Finding #448: nav_context.py DomainKnowledge Growing Without Bounds
**Location:** blackreach/nav_context.py:79-99
**Severity:** Low
**Description:** Lists like `successful_paths`, `content_locations`, `best_entry_points` can grow unbounded.
**Recommendation:** Add maximum size limits.

### Finding #449: source_manager.py Import Inside Methods
**Location:** blackreach/source_manager.py:144, 178-179, 243, 261, 314, 364, 388
**Severity:** Low
**Description:** `from urllib.parse import urlparse` is imported inside multiple methods instead of at module level.
**Recommendation:** Move to module-level import.

### Finding #450: source_manager.py Global Singleton Without Thread Safety
**Location:** blackreach/source_manager.py:403-411
**Severity:** Medium
**Description:** `_source_manager` singleton has no thread protection.
**Recommendation:** Add thread-safe initialization.

### Finding #451: source_manager.py Manual List Trimming
**Location:** blackreach/source_manager.py:271-272
**Severity:** Low
**Description:** `_failover_history` is manually trimmed with slicing when > 50 items.
**Recommendation:** Use collections.deque(maxlen=50).

### Finding #452: action_tracker.py Import Inside Methods (datetime)
**Location:** blackreach/action_tracker.py:63-64, 68-69
**Severity:** Low
**Description:** `from datetime import datetime` is imported inside `record_success()` and `record_failure()` methods.
**Recommendation:** Move to module-level import.

### Finding #453: action_tracker.py Global Singleton Without Thread Safety
**Location:** blackreach/action_tracker.py:498-505
**Severity:** Medium
**Description:** `_global_tracker` singleton has no thread protection.
**Recommendation:** Add thread-safe initialization.

### Finding #454: action_tracker.py Silently Catches All Exceptions
**Location:** blackreach/action_tracker.py:435-436
**Severity:** Medium
**Description:** `_load_from_memory()` catches all exceptions with `pass`, hiding potential bugs.
**Recommendation:** Log the exception before ignoring.

### Finding #455: cache.py Thread Lock Not Used for All Operations
**Location:** blackreach/cache.py:162-170
**Severity:** Medium
**Description:** `cleanup_expired()` uses lock but `_evict_one()` is called from `set()` which already holds lock - no issue there. But `_save_to_disk()` doesn't use lock.
**Recommendation:** Ensure all cache mutations use lock consistently.

### Finding #456: cache.py MD5 for Cache Keys
**Location:** blackreach/cache.py:264, 296
**Severity:** Low
**Description:** Uses MD5 for generating cache keys. While not cryptographic, modern alternatives like xxhash are faster.
**Recommendation:** Consider faster non-cryptographic hash for cache keys.

### Finding #457: cache.py _save_to_disk() Silently Catches All Exceptions
**Location:** blackreach/cache.py:203-204
**Severity:** Medium
**Description:** Serialization errors are silently ignored, potentially losing cache state.
**Recommendation:** Log errors or notify caller.

### Finding #458: cache.py Global Singletons Without Thread Safety
**Location:** blackreach/cache.py:304-321
**Severity:** Medium
**Description:** Both `_page_cache` and `_result_cache` singletons have no thread protection.
**Recommendation:** Add thread-safe initialization with locks.

### Finding #459: Pervasive Singleton Anti-Pattern Across Codebase
**Location:** Multiple files (error_recovery.py, search_intel.py, nav_context.py, source_manager.py, action_tracker.py, cache.py, stuck_detector.py, goal_engine.py)
**Severity:** High
**Description:** 10+ modules use global singleton pattern with `_global_*` variables and `get_*()` functions. None are thread-safe. Creates hidden dependencies and makes testing difficult.
**Recommendation:** Implement a dependency injection container or service locator pattern with proper lifecycle management.

### Finding #460: Consistent Pattern of Missing Thread Safety
**Location:** All singleton modules
**Severity:** High
**Description:** Pattern of `if _global_var is None: _global_var = Class()` is a TOCTTOU race condition. Multiple threads can create separate instances.
**Recommendation:** Use `threading.Lock()` around initialization or use `functools.lru_cache(maxsize=1)` decorator.

---

## Statistics

- **Total Findings:** 460
- **Critical:** 0
- **High:** 16
- **Medium:** 172
- **Low:** 272

## Recommendations Summary

### High Priority (Architecture/Design)
1. **Refactor large functions** - Break down the Agent.run(), Hand class, and CLI interactive mode into smaller, testable units
2. **Unify singleton pattern** - Create a common factory or registry for the 15+ global singletons scattered across modules
3. **Add thread safety** - Review and protect shared state in singletons, caches, and managers; many modules have race conditions
4. **Fix "parallel" operations** - ParallelFetcher and ParallelDownloader don't actually run in parallel within batches; use ThreadPoolExecutor

### Medium Priority (Code Quality)
5. **Add missing type hints** - Ensure all public methods have complete type annotations
6. **Centralize configuration** - Move hardcoded values (timeouts, patterns, extensions, magic numbers) to configuration files
7. **Improve error handling** - Replace bare exception catches with specific exception types; log errors before swallowing
8. **Move imports to module level** - Many modules have imports inside methods (urlparse, datetime, etc.)
9. **Extract JavaScript** - Move inline JavaScript to separate files for maintainability and testing
10. **Database connection management** - Use context managers and connection pooling for SQLite operations

### Low Priority (Consistency/Cleanup)
11. **Consistent patterns** - Apply uniform naming, error handling, and return types across the codebase
12. **Use deque for bounded collections** - Replace list trimming patterns with collections.deque(maxlen=N)
13. **Document magic numbers** - Add comments explaining thresholds, scoring weights, and constants
14. **Add database indexes** - Several tables query by columns without indexes (downloaded_at, last_update)
15. **Replace MD5 with modern alternatives** - Use UUID for IDs, consider xxhash for non-cryptographic hashing

### Files Requiring Most Attention
- `browser.py` (Hand class - 1300+ lines, multiple responsibilities)
- `agent.py` (Agent.run() - 300+ lines)
- `cli.py` (interactive mode complexity)
- `parallel_ops.py` (misleading name, lacks true parallelism)
- Multiple managers (session_manager, timeout_manager, source_manager) - thread safety issues

- **Total Findings:** 420
- **Critical:** 0
- **High:** 14
- **Medium:** 156
- **Low:** 250

## Recommendations Summary

### High Priority (Architecture/Design)
1. **Refactor large functions** - Break down the Agent.run(), Hand class, and CLI interactive mode into smaller, testable units
2. **Unify singleton pattern** - Create a common factory or registry for the 15+ global singletons scattered across modules
3. **Add thread safety** - Review and protect shared state in singletons, caches, and managers; many modules have race conditions
4. **Fix "parallel" operations** - ParallelFetcher and ParallelDownloader don't actually run in parallel within batches; use ThreadPoolExecutor

### Medium Priority (Code Quality)
5. **Add missing type hints** - Ensure all public methods have complete type annotations
6. **Centralize configuration** - Move hardcoded values (timeouts, patterns, extensions, magic numbers) to configuration files
7. **Improve error handling** - Replace bare exception catches with specific exception types; log errors before swallowing
8. **Move imports to module level** - Many modules have imports inside methods (urlparse, datetime, etc.)
9. **Extract JavaScript** - Move inline JavaScript to separate files for maintainability and testing
10. **Database connection management** - Use context managers and connection pooling for SQLite operations

### Low Priority (Consistency/Cleanup)
11. **Consistent patterns** - Apply uniform naming, error handling, and return types across the codebase
12. **Use deque for bounded collections** - Replace list trimming patterns with collections.deque(maxlen=N)
13. **Document magic numbers** - Add comments explaining thresholds, scoring weights, and constants
14. **Add database indexes** - Several tables query by columns without indexes (downloaded_at, last_update)
15. **Replace MD5 with modern alternatives** - Use UUID for IDs, consider xxhash for non-cryptographic hashing

### Files Requiring Most Attention
- `browser.py` (Hand class - 1300+ lines, multiple responsibilities)
- `agent.py` (Agent.run() - 300+ lines)
- `cli.py` (interactive mode complexity)
- `parallel_ops.py` (misleading name, lacks true parallelism)
- Multiple managers (session_manager, timeout_manager, source_manager) - thread safety issues

