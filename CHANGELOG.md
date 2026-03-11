# Changelog

All notable changes to Blackreach are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [5.0.0-beta.1] - 2026-03-02

### Added

- **Full agent rearchitecture (v5)**: Rewrote the core ReAct loop for reliability and maintainability
- **DOM Walker**: Replaced HTML parser approach with live Playwright DOM extraction (`dom_walker.py`). Assigns numeric `[N]` IDs to interactive elements so the LLM can reference them precisely
- **Fallback search engine chain**: Agent now tries Bing → DuckDuckGo → Brave in sequence when one search engine blocks or returns poor results; replaces the previous hardcoded Google-only behavior
- **Challenge page detection**: Improved handling of DDoS-Guard, Cloudflare "checking your browser", and similar interstitial pages; agent waits for auto-resolution instead of immediately failing
- **LLM reasoning improvements**: Expanded text coverage sent to the LLM, improved prompt structure for better action extraction
- **Production hardening sprint**: Fixed 6 high-priority bugs including race conditions in parallel operations, resource leaks in browser teardown, and logic errors in stuck detection
- **Exception narrowing**: Narrowed ~50 bare `except Exception:` blocks to specific exception types (`PlaywrightError`, `BrowserError`, `OSError`, `ValueError`, etc.) across all modules
- **Named constants**: Extracted 18+ magic numbers in `browser.py` and `agent.py` into descriptive named constants
- **Import cleanup**: Removed duplicate imports and trivially-restating inline comments across the codebase

### Changed

- `AgentConfig.start_url` now defaults to Bing (more reliable in headless mode than Google)
- Challenge wait logic improved: page navigation during challenge detection is now handled gracefully
- `STEP_PAUSE_SECONDS`, `CHALLENGE_WAIT_SECONDS`, `RENDER_WAIT_SECONDS`, and other timing values are now named constants in `agent.py`

### Fixed

- Fixed race condition in `parallel_ops.py` where task cancellation could leave the thread pool in a bad state
- Fixed browser resource leak when `Hand.close()` raised an exception during teardown
- Fixed stuck detection false-positives when the agent legitimately revisited a search results page
- Fixed `download_history.import_history()` swallowing all exceptions silently (now logs the error)
- Fixed challenge page detection when a Playwright navigation exception fires mid-check

---

## [4.2.0-beta.2] - 2026-02-15

### Added

- **Site type detection** (`detection.py`): Classifies sites as STATIC / SPA / HYBRID / SEARCH_ENGINE for adaptive timeout tuning
- **Download landing page detection**: Recognizes file-hosting interstitial pages (MediaFire, Mega, Anna's Archive, LibGen) and instructs the agent to click through
- **Search block detection**: Detects when Google or DuckDuckGo is blocking automated queries and triggers fallback
- **Advanced Cloudflare bypass**: Improved stealth mode and timing to reduce Cloudflare challenge triggers

### Changed

- Parallel operations manager now handles `concurrent.futures` task boundaries with broad exception catches (intentional — documented)
- `SiteCharacteristics` dataclass added to `detection.py`; `get_site_characteristics()` function now consulted before every page load

---

## [4.0.0-beta.1] - 2026-01-30

### Added

- **Caching system** (`cache.py`): LRU cache with TTL eviction for page HTML and parsed elements; `PageCache` and `ResultCache`
- **API interface** (`api.py`): `browse()`, `download()`, `search()` convenience functions for programmatic use
- **Parallel operations** (`parallel_ops.py`): `ParallelFetcher`, `ParallelDownloader`, `ParallelSearcher` for concurrent work
- **Task scheduler** (`task_scheduler.py`): Priority queue for multi-task agent workflows
- **Download queue** (`download_queue.py`): Persistent queue with priority levels for bulk downloads
- **Progress tracking** (`progress.py`): `DownloadProgressTracker` and `TaskProgressTracker` with live callbacks

### Changed

- Config system (`config.py`) restored to stable schema; `ProviderConfig` dataclass now used for all provider settings
- AVAILABLE_MODELS dict centralizes all supported model names

---

## [3.3.0] - 2026-01-22

### Added

- **Session resume** (`session_manager.py`): Pause with Ctrl+C, resume with `blackreach run --resume <id>`; auto-saves session state to SQLite
- **Rate limiter** (`rate_limiter.py`): Per-domain token bucket; respects `Retry-After` headers
- **Timeout manager** (`timeout_manager.py`): Adaptive per-site timeouts based on observed load times
- **Retry strategy** (`retry_strategy.py`): Configurable backoff with jitter; `RetryManager` used throughout the agent loop
- **Multi-tab manager** (`multi_tab.py`): `SyncTabManager` for coordinated multi-tab browsing

---

## [3.0.0] - 2026-01-22

### Added

- **Content verification** (`content_verify.py`): MD5 + SHA256 checksums for every downloaded file; `IntegrityVerifier` for post-download validation
- **Search intelligence** (`search_intel.py`): Query rewriting, result scoring, source ranking across multiple search engines
- **Navigation context** (`nav_context.py`): `NavigationContext` tracks page value scores to guide the agent toward high-value pages
- **Site handlers** (`site_handlers.py`): Site-specific navigation hints for arXiv, GitHub, Wikipedia, LibGen, Anna's Archive
- **Download history** (`download_history.py`): SQLite-backed deduplication by URL and file hash

---

## [2.0.0] - 2026-01-22

### Added

- **Goal decomposition engine** (`goal_engine.py`): Breaks complex goals into subtasks; tracks subtask completion
- **Stuck detection** (`stuck_detector.py`): Detects page loops and repeated failures; triggers alternate strategies
- **Error recovery** (`error_recovery.py`): Categorizes errors and selects recovery strategies (retry, skip, alternate source)
- **Action tracker** (`action_tracker.py`): Records action outcomes and learns which selectors succeed on each site
- **Source manager** (`source_manager.py`): Manages multi-source failover; tracks which sources succeeded per query type
- **Exception hierarchy** (`exceptions.py`): ~25 specific exception classes (`CaptchaError`, `LoginRequiredError`, `PaywallError`, `RateLimitError`, `DownloadError`, etc.)

---

## [1.5.0] - 2026-01-22

### Added

- **Memory system** (`memory.py`): `SessionMemory` (RAM) + `PersistentMemory` (SQLite); agent learns from past sessions
- **Stealth mode** (`stealth.py`): Randomized viewport, user-agent rotation, human-like timing to reduce bot detection
- **Resilience** (`resilience.py`): Circuit breaker with configurable failure thresholds
- **Knowledge base** (`knowledge.py`): Curated list of content sources by category; `reason_about_goal()` selects the best starting point
- **Cookie manager** (`cookie_manager.py`): Profile-based cookie storage; restores session cookies across runs
- **Metadata extraction** (`metadata_extract.py`): Extracts PDF, EPUB, and image metadata post-download

### Changed

- Agent now uses full ReAct loop: Observe → Think → Act with step-by-step logging

---

## [0.5.0] - 2026-01-20

### Added

- Initial release of Blackreach
- Playwright-based browser automation via `Hand` class
- Basic DOM parsing via `Eyes` (BeautifulSoup)
- LLM integration supporting Ollama, OpenAI, Anthropic, Google, xAI (`llm.py`)
- CLI interface (`cli.py`) with `blackreach run`, `blackreach config`, `blackreach history`
- Configuration system (`config.py`) with YAML file and optional keyring for API keys
- Download detection and file saving
- Basic test suite (297 tests)

---

[Unreleased]: https://github.com/phnix/blackreach/compare/v5.0.0-beta.1...HEAD
[5.0.0-beta.1]: https://github.com/phnix/blackreach/compare/v4.2.0-beta.2...v5.0.0-beta.1
[4.2.0-beta.2]: https://github.com/phnix/blackreach/compare/v4.0.0-beta.1...v4.2.0-beta.2
[4.0.0-beta.1]: https://github.com/phnix/blackreach/compare/v3.3.0...v4.0.0-beta.1
[3.3.0]: https://github.com/phnix/blackreach/compare/v3.0.0...v3.3.0
[3.0.0]: https://github.com/phnix/blackreach/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/phnix/blackreach/compare/v1.5.0...v2.0.0
[1.5.0]: https://github.com/phnix/blackreach/compare/v0.5.0...v1.5.0
[0.5.0]: https://github.com/phnix/blackreach/releases/tag/v0.5.0
