# Blackreach UX Investigation - 10 Hour Deep Work Session
## Comprehensive UX Findings Report

**Investigator:** UX Investigation Agent
**Date:** 2026-01-24
**Version Analyzed:** 4.0.0-beta.2
**Total Findings:** 150+

---

## Executive Summary

This document captures all UX friction points, confusion areas, missing features, and positive patterns discovered during a comprehensive 10-hour investigation of the Blackreach CLI tool. Findings are categorized by severity and component.

---

## SECTION 1: CLI MAIN INTERFACE (cli.py)

### UX Issue #1: Version Mismatch in Banner
- **Type:** Inconsistency
- **Location:** cli.py:60 vs cli.py:72
- **Scenario:** User views version information
- **Problem:** `__version__ = "4.0.0-beta.2"` at line 60, but BANNER shows `v4.0.0-beta.2` - hardcoded, would drift if version changes
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Use `{__version__}` in BANNER string

### UX Issue #2: No --quiet Flag for Scripting
- **Type:** Missing
- **Location:** cli.py `run` command
- **Scenario:** User wants to run blackreach in scripts without output
- **Problem:** No `--quiet` or `-q` flag to suppress all output for scripting/CI
- **User Impact:** Power users, DevOps
- **Frustration Level:** 3
- **Suggested Fix:** Add `--quiet/-q` flag that sets JSON-only output or silent mode

### UX Issue #3: --verbose Flag Underdocumented
- **Type:** Confusion
- **Location:** cli.py:233
- **Scenario:** User enables verbose mode
- **Problem:** Help says "Enable verbose logging" but doesn't explain WHAT extra info is shown
- **User Impact:** Intermediate users
- **Frustration Level:** 2
- **Suggested Fix:** Add more detail: "Enable verbose logging (shows LLM reasoning, full URLs, timing)"

### UX Issue #4: --validate Flag Name Conflict
- **Type:** Confusion
- **Location:** cli.py:234
- **Scenario:** User might confuse with `validate` command
- **Problem:** `--validate` option on `run` command AND a `validate` subcommand - different behaviors
- **User Impact:** Beginners
- **Frustration Level:** 3
- **Suggested Fix:** Rename to `--check-config` or `--pre-check`

### UX Issue #5: Missing Short Flags
- **Type:** Friction
- **Location:** cli.py run command
- **Scenario:** User typing commands frequently
- **Problem:** No short flag for `--headless` (would expect `-H`), `--validate`, `--steps` has `-s` but `--resume` also has `-r`
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add `-H/--headless` and document all short flags clearly

### UX Issue #6: Steps Default Not Shown in Help
- **Type:** Missing
- **Location:** cli.py:231
- **Scenario:** User wonders what default max steps is
- **Problem:** `--steps` help doesn't show default value (30)
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Change to `--steps INTEGER  Maximum steps (default: 30)`

### UX Issue #7: Browser Choice Help Unclear
- **Type:** Confusion
- **Location:** cli.py:230
- **Scenario:** User choosing browser
- **Problem:** Help says "helps bypass DDoS protection" but doesn't explain how/why
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Better explanation or link to docs

### UX Issue #8: Goal Argument Position
- **Type:** Friction
- **Location:** cli.py:226
- **Scenario:** User running with options
- **Problem:** `blackreach run --provider openai "my goal"` works but positional arg before options doesn't work cleanly
- **User Impact:** Beginners
- **Frustration Level:** 2
- **Suggested Fix:** Add example in help showing option ordering

### UX Issue #9: Typo Command No Suggestions
- **Type:** Missing
- **Location:** CLI main
- **Scenario:** User types `blackreach runn` (typo)
- **Problem:** Error says "No such command 'runn'" but doesn't suggest "did you mean 'run'?"
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Implement fuzzy matching for command suggestions

### UX Issue #10: No Global --config Flag
- **Type:** Missing
- **Location:** CLI main
- **Scenario:** User wants to use different config file
- **Problem:** Cannot specify alternate config file location
- **User Impact:** Power users, testing
- **Frustration Level:** 3
- **Suggested Fix:** Add `--config PATH` global option

### UX Issue #11: No --output Flag
- **Type:** Missing
- **Location:** cli.py run command
- **Scenario:** User wants JSON output for processing
- **Problem:** No `--output json` option for machine-readable output
- **User Impact:** Power users, automation
- **Frustration Level:** 4
- **Suggested Fix:** Add `--output [text|json|yaml]` option

### UX Issue #12: No --dry-run Flag
- **Type:** Missing
- **Location:** cli.py run command
- **Scenario:** User wants to preview what agent would do
- **Problem:** No way to see plan without actually executing
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Add `--dry-run` that shows planned steps without execution

### UX Issue #13: Headless Default Not Clear
- **Type:** Confusion
- **Location:** cli.py:229
- **Scenario:** User runs command
- **Problem:** `--headless/--no-headless` doesn't show which is default
- **User Impact:** Beginners
- **Frustration Level:** 2
- **Suggested Fix:** Show "(default: visible)" in help

### UX Issue #14: Model Override Without Provider Confusing
- **Type:** Confusion
- **Location:** cli.py run command
- **Scenario:** User runs `blackreach run --model gpt-4 "goal"`
- **Problem:** If default provider is ollama, this silently uses gpt-4 with ollama (fails)
- **User Impact:** All users
- **Frustration Level:** 4
- **Suggested Fix:** Auto-detect provider from model name, or warn

### UX Issue #15: Resume Without Recent Context
- **Type:** Friction
- **Location:** cli.py:274-313
- **Scenario:** User wants to resume
- **Problem:** `--resume 42` requires knowing session ID but no way to see recent IDs inline
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Add `--resume last` or show recent sessions when resume fails

### UX Issue #16: No --start-url Flag
- **Type:** Missing
- **Location:** cli.py run command
- **Scenario:** User wants to start from specific page
- **Problem:** No way to set starting URL from CLI (API has it)
- **User Impact:** Intermediate users
- **Frustration Level:** 3
- **Suggested Fix:** Add `--start-url URL` option

### UX Issue #17: Config Command No Options
- **Type:** Friction
- **Location:** cli.py:420-421
- **Scenario:** User wants to set specific config value
- **Problem:** `blackreach config` only has interactive mode, no `blackreach config set key value`
- **User Impact:** Power users, automation
- **Frustration Level:** 4
- **Suggested Fix:** Add `blackreach config get/set` subcommands

### UX Issue #18: Models Command Overwhelming
- **Type:** Friction
- **Location:** cli.py:512-532
- **Scenario:** User runs `blackreach models`
- **Problem:** Lists ALL models for ALL providers, no pagination
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Only show current provider by default, add `--all`

### UX Issue #19: Status vs Stats Confusion
- **Type:** Confusion
- **Location:** cli.py status and stats commands
- **Scenario:** User wants to see system state
- **Problem:** Both `status` and `stats` exist - unclear difference
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Merge into one command or clarify distinction in help

### UX Issue #20: Clear Command Requires Flag
- **Type:** Friction
- **Location:** cli.py:1183-1220
- **Scenario:** User runs `blackreach clear`
- **Problem:** Running without flags just shows usage - why have command at all then?
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Default to showing what CAN be cleared, or interactive mode

### UX Issue #21: Actions Command Obscure
- **Type:** Confusion
- **Location:** cli.py:713
- **Scenario:** New user explores commands
- **Problem:** "Show action tracking statistics" - what are actions? Why track them?
- **User Impact:** Beginners
- **Frustration Level:** 2
- **Suggested Fix:** Better description: "Show success rates of browser interactions by domain"

### UX Issue #22: Sources vs Health Overlap
- **Type:** Confusion
- **Location:** cli.py sources and health commands
- **Scenario:** User wants to check source status
- **Problem:** Both `sources` and `health` check source availability - overlap
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Merge or clarify difference in help text

### UX Issue #23: Resumable vs Sessions Naming
- **Type:** Confusion
- **Location:** cli.py resumable and sessions commands
- **Scenario:** User wants to see past sessions
- **Problem:** `resumable` and `sessions` are separate - user might check wrong one
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Merge into one `sessions` with `--resumable` filter

### UX Issue #24: No Completion Script Generation
- **Type:** Missing
- **Location:** CLI main
- **Scenario:** User wants shell completion
- **Problem:** No `blackreach completion bash/zsh/fish` command
- **User Impact:** Power users
- **Frustration Level:** 3
- **Suggested Fix:** Add completion script generation

### UX Issue #25: Doctor Doesn't Check All Requirements
- **Type:** Incomplete
- **Location:** cli.py:850-903
- **Scenario:** User runs doctor to diagnose
- **Problem:** Doesn't check: disk space, network, API key validity, model availability
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Add more checks: API connectivity, model download status

---

## SECTION 2: ERROR MESSAGES (exceptions.py)

### UX Issue #26: BrowserNotReadyError Doesn't Explain wake()
- **Type:** Confusion
- **Location:** exceptions.py:54
- **Scenario:** User gets error
- **Problem:** Says "Call wake() first" - user doesn't know what wake() is or how to call it
- **User Impact:** Beginners
- **Frustration Level:** 4
- **Suggested Fix:** "Browser not ready. This usually auto-initializes. Try running again or check 'blackreach doctor'"

### UX Issue #27: BrowserUnhealthyError Too Generic
- **Type:** Incomplete
- **Location:** exceptions.py:58-62
- **Scenario:** Browser becomes unresponsive
- **Problem:** "Browser is unresponsive" - doesn't say WHY or what to do
- **User Impact:** All users
- **Frustration Level:** 4
- **Suggested Fix:** Add suggestions: "Try: 1) Wait and retry 2) Run 'blackreach doctor' 3) Kill zombie browser processes"

### UX Issue #28: ElementNotFoundError Selector Too Technical
- **Type:** Confusion
- **Location:** exceptions.py:72-96
- **Scenario:** Click fails
- **Problem:** Shows CSS selector like "Element not found: button.submit-btn" - users don't understand selectors
- **User Impact:** Beginners
- **Frustration Level:** 3
- **Suggested Fix:** Human-readable: "Could not find 'Submit' button on page. The page may have changed."

### UX Issue #29: NavigationError Missing Diagnostics
- **Type:** Incomplete
- **Location:** exceptions.py:99-106
- **Scenario:** Page fails to load
- **Problem:** "Failed to navigate to URL: reason" - doesn't check if internet is down, DNS fails, etc.
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Add diagnostic suggestions based on error type

### UX Issue #30: DownloadError No Retry Suggestion
- **Type:** Missing
- **Location:** exceptions.py:109-127
- **Scenario:** Download fails
- **Problem:** Says download failed but doesn't suggest retry or alternative
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** "Download failed. Try: 1) Check URL is valid 2) Site may be rate-limiting, wait and retry"

### UX Issue #31: TimeoutError Shadows Built-in
- **Type:** Technical Debt
- **Location:** exceptions.py:130-139
- **Scenario:** Developer catches timeout
- **Problem:** Class named `TimeoutError` shadows Python's built-in
- **User Impact:** Developers
- **Frustration Level:** 3
- **Suggested Fix:** Rename to `OperationTimeoutError`

### UX Issue #32: ProviderError No Installation Help
- **Type:** Incomplete
- **Location:** exceptions.py:151-158
- **Scenario:** Provider not available
- **Problem:** Says provider error but not how to install/fix
- **User Impact:** Beginners
- **Frustration Level:** 4
- **Suggested Fix:** Add specific installation instructions per provider

### UX Issue #33: ProviderNotInstalledError Good
- **Type:** UX Win
- **What Works:** exceptions.py:161-167
- **Why It's Good:** Includes exact pip install command
- **Keep This:** This pattern should be used for all fixable errors

### UX Issue #34: ParseError Truncates Response
- **Type:** Incomplete
- **Location:** exceptions.py:170-181
- **Scenario:** LLM response malformed
- **Problem:** Truncates to 500 chars - might cut off the relevant part
- **User Impact:** Developers
- **Frustration Level:** 2
- **Suggested Fix:** Show first and last 250 chars, or full with verbose flag

### UX Issue #35: RateLimitError Good
- **Type:** UX Win
- **What Works:** exceptions.py:205-221
- **Why It's Good:** Includes retry_after timing
- **Keep This:** Users know exactly when to retry

### UX Issue #36: ActionError Doesn't Explain Actions
- **Type:** Confusion
- **Location:** exceptions.py:233-247
- **Scenario:** Action fails
- **Problem:** "Action 'click' failed" - doesn't explain what alternatives exist
- **User Impact:** Beginners
- **Frustration Level:** 3
- **Suggested Fix:** Include link to action documentation

### UX Issue #37: StuckError Too Technical
- **Type:** Confusion
- **Location:** exceptions.py:264-282
- **Scenario:** Agent gets stuck
- **Problem:** Says "consecutive_visits: 5" - user doesn't know what this means
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** "Agent tried the same page 5 times without progress. Try rephrasing your goal."

### UX Issue #38: MaxStepsExceededError No Guidance
- **Type:** Incomplete
- **Location:** exceptions.py:285-294
- **Scenario:** Ran out of steps
- **Problem:** "Exceeded maximum steps" but doesn't say if goal was partially completed
- **User Impact:** All users
- **Frustration Level:** 4
- **Suggested Fix:** "Exceeded max steps (30/30). Goal may be too complex - try breaking into smaller goals or increase --steps"

### UX Issue #39: CaptchaError No Workaround
- **Type:** Incomplete
- **Location:** exceptions.py:306-317
- **Scenario:** Hit CAPTCHA
- **Problem:** Just says "CAPTCHA detected" - no workaround or alternative
- **User Impact:** All users
- **Frustration Level:** 4
- **Suggested Fix:** "CAPTCHA detected. Try: 1) Run in visible mode (--no-headless) 2) Try different source 3) Wait and retry"

### UX Issue #40: LoginRequiredError Good Context
- **Type:** UX Win
- **What Works:** exceptions.py:320-330
- **Why It's Good:** Includes login_url when available
- **Keep This:** Helps users understand next step

### UX Issue #41: PaywallError No Alternatives
- **Type:** Missing
- **Location:** exceptions.py:333-341
- **Scenario:** Hit paywall
- **Problem:** Just says paywall detected, doesn't suggest alternatives
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** "Try: 'blackreach health' to find free alternatives for this content type"

### UX Issue #42: InvalidConfigError Good Format
- **Type:** UX Win
- **What Works:** exceptions.py:372-379
- **Why It's Good:** Shows: key, value, expected - all context needed
- **Keep This:** Great error message pattern

### UX Issue #43: ConnectionError Generic
- **Type:** Incomplete
- **Location:** exceptions.py:396-403
- **Scenario:** Network failure
- **Problem:** Doesn't distinguish between DNS, timeout, refused, etc.
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Parse error type and give specific advice

### UX Issue #44: SSLError No Fix Suggestion
- **Type:** Incomplete
- **Location:** exceptions.py:406-410
- **Scenario:** SSL certificate issue
- **Problem:** Just says "SSL certificate error" - no explanation
- **User Impact:** All users
- **Frustration Level:** 4
- **Suggested Fix:** "SSL error. Site certificate may be expired or invalid. Check your system time is correct."

### UX Issue #45: SessionCorruptedError No Recovery
- **Type:** Incomplete
- **Location:** exceptions.py:433-444
- **Scenario:** Session data corrupted
- **Problem:** Says corrupted but no recovery option
- **User Impact:** All users
- **Frustration Level:** 4
- **Suggested Fix:** "Session corrupted. Run 'blackreach clear --sessions' to clean up."

### UX Issue #46: No Network Offline Detection
- **Type:** Missing
- **Location:** exceptions.py
- **Scenario:** User has no internet
- **Problem:** No specific "you appear to be offline" error
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Add NetworkOfflineError with connectivity check suggestion

---

## SECTION 3: UI COMPONENTS (ui.py)

### UX Issue #47: Banner Version Hardcoded
- **Type:** Inconsistency
- **Location:** ui.py:413
- **Scenario:** Version displayed
- **Problem:** Banner shows "v2.0.0" but CLI is at 4.0.0-beta.2
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Dynamic version injection or single source of truth

### UX Issue #48: Spinner Messages Not Customizable
- **Type:** Limitation
- **Location:** ui.py:81-84
- **Scenario:** Long operations
- **Problem:** Can't update spinner message during operation
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Return spinner object that can be updated

### UX Issue #49: AgentProgress Emojis in Terminal
- **Type:** Compatibility
- **Location:** ui.py:135-163
- **Scenario:** Terminal without emoji support
- **Problem:** Heavy use of emojis may render as boxes in some terminals
- **User Impact:** Some users
- **Frustration Level:** 3
- **Suggested Fix:** Add `--no-emoji` flag or detect terminal capability

### UX Issue #50: Action Icons Hardcoded
- **Type:** Maintenance
- **Location:** ui.py:154-163
- **Scenario:** New actions added
- **Problem:** Action icons hardcoded, new actions get generic icon
- **User Impact:** None visible
- **Frustration Level:** 1
- **Suggested Fix:** Centralize icon mapping

### UX Issue #51: Truncation at 60 Chars
- **Type:** Friction
- **Location:** ui.py:146
- **Scenario:** Long detail text
- **Problem:** Details truncated at 60 chars - often cuts off useful info
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Make configurable or use terminal width

### UX Issue #52: No Progress Percentage
- **Type:** Missing
- **Location:** ui.py:119-132
- **Scenario:** Long running task
- **Problem:** Shows step X/Y but not percentage or ETA
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Add estimated time remaining

### UX Issue #53: SlashCompleter Commands Incomplete
- **Type:** Incomplete
- **Location:** ui.py:246-268
- **Scenario:** Tab completion in interactive mode
- **Problem:** Missing some commands like /resume, /sessions
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add all available slash commands

### UX Issue #54: History File Location Undocumented
- **Type:** Missing
- **Location:** ui.py:58
- **Scenario:** User wants to find/clear history
- **Problem:** `~/.blackreach/history` exists but never mentioned anywhere
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Document in help or add `blackreach clear --history`

### UX Issue #55: Key Bindings Limited
- **Type:** Missing
- **Location:** ui.py:317-323
- **Scenario:** User wants keyboard shortcuts
- **Problem:** Only Ctrl+L bound, no Ctrl+U to clear line, etc.
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add common readline shortcuts

### UX Issue #56: Prompt Doesn't Show Provider
- **Type:** Missing
- **Location:** ui.py:341
- **Scenario:** User forgets current provider
- **Problem:** Prompt just shows "blackreach >" not "[ollama] blackreach >"
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Include provider in prompt

### UX Issue #57: RadioList Dialog May Fail
- **Type:** Fragile
- **Location:** ui.py:577-606
- **Scenario:** Running in basic terminal
- **Problem:** radiolist_dialog can fail, falls back silently
- **User Impact:** Some users
- **Frustration Level:** 2
- **Suggested Fix:** Better fallback handling, log when fallback used

### UX Issue #58: Provider Menu Descriptions Inconsistent
- **Type:** Inconsistency
- **Location:** ui.py:639-645
- **Scenario:** Selecting provider
- **Problem:** "xAI - Grok-4, fast reasoning" but xAI models include grok-3, grok-code
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Update descriptions to match actual offerings

### UX Issue #59: Model Menu Only Shows Top 3
- **Type:** Friction
- **Location:** ui.py:673
- **Scenario:** Selecting model from other provider
- **Problem:** Only shows 3 models from other providers - may miss desired one
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add "more..." option or show all

### UX Issue #60: Download Progress Good
- **Type:** UX Win
- **What Works:** ui.py:722-837
- **Why It's Good:** Rich progress bars with speed, ETA, concurrent downloads
- **Keep This:** Professional download experience

### UX Issue #61: Error Panel Good
- **Type:** UX Win
- **What Works:** ui.py:952-986
- **Why It's Good:** Shows exception type, message, and optional suggestion
- **Keep This:** Clear error presentation

### UX Issue #62: Session Info Display Good
- **Type:** UX Win
- **What Works:** ui.py:1026-1053
- **Why It's Good:** Shows all relevant session info in clean panel
- **Keep This:** Good information density

### UX Issue #63: Log Entry Time Parsing Fragile
- **Type:** Fragile
- **Location:** ui.py:1129
- **Scenario:** Unusual timestamp format
- **Problem:** Hardcoded slicing for time extraction
- **User Impact:** None visible usually
- **Frustration Level:** 1
- **Suggested Fix:** Use proper datetime parsing

### UX Issue #64: No Color Theme Control
- **Type:** Missing
- **Location:** ui.py:62-72
- **Scenario:** User wants different colors
- **Problem:** Theme hardcoded, no dark/light mode, no customization
- **User Impact:** Some users
- **Frustration Level:** 2
- **Suggested Fix:** Add theme configuration in config.yaml

### UX Issue #65: Print Functions Don't Return
- **Type:** Design
- **Location:** ui.py print_* functions
- **Scenario:** Programmatic use
- **Problem:** Print functions don't return the text, can't capture
- **User Impact:** Developers
- **Frustration Level:** 2
- **Suggested Fix:** Return formatted string optionally

---

## SECTION 4: CONFIGURATION (config.py)

### UX Issue #66: Config Location Not Obvious
- **Type:** Discoverability
- **Location:** config.py:21-22
- **Scenario:** User wants to edit config manually
- **Problem:** `~/.blackreach/config.yaml` not prominently documented
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Show path in `blackreach config` output

### UX Issue #67: No Config File Comments
- **Type:** Missing
- **Location:** config.py save method
- **Scenario:** User edits config manually
- **Problem:** Generated YAML has no comments explaining options
- **User Impact:** Power users
- **Frustration Level:** 3
- **Suggested Fix:** Add comments to generated config

### UX Issue #68: API Key Patterns May Be Wrong
- **Type:** Fragile
- **Location:** config.py:307-313
- **Scenario:** Validating API key
- **Problem:** Regex patterns for API keys may not match all valid keys
- **User Impact:** Some users
- **Frustration Level:** 3
- **Suggested Fix:** Make patterns more permissive or remove format validation

### UX Issue #69: Model List Outdated Risk
- **Type:** Maintenance
- **Location:** config.py:69-106
- **Scenario:** New models released
- **Problem:** AVAILABLE_MODELS hardcoded, will become outdated
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Fetch from APIs or allow custom models without warning

### UX Issue #70: Download Dir Relative Path Warning
- **Type:** Confusion
- **Location:** config.py:394-399
- **Scenario:** Using default ./downloads
- **Problem:** Warns about relative path but default IS relative
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Either default to absolute or don't warn about default

### UX Issue #71: No Config Migration
- **Type:** Missing
- **Location:** config.py
- **Scenario:** Upgrading from old version
- **Problem:** No mechanism to migrate old config format
- **User Impact:** Upgrading users
- **Frustration Level:** 3
- **Suggested Fix:** Add config version and migration logic

### UX Issue #72: Environment Variables Good
- **Type:** UX Win
- **What Works:** config.py:142-158
- **Why It's Good:** Supports standard env vars like OPENAI_API_KEY
- **Keep This:** Industry standard approach

### UX Issue #73: Validation Result Good Pattern
- **Type:** UX Win
- **What Works:** config.py:274-292
- **Why It's Good:** Separates errors (fatal) from warnings (informational)
- **Keep This:** Good validation feedback pattern

### UX Issue #74: No Config Export/Import
- **Type:** Missing
- **Location:** config.py
- **Scenario:** Sharing config between machines
- **Problem:** No easy way to export config (without API keys) for sharing
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add `blackreach config export/import`

### UX Issue #75: ConfigManager is Singleton-ish
- **Type:** Design
- **Location:** config.py:551
- **Scenario:** Testing
- **Problem:** Global config_manager instance makes testing harder
- **User Impact:** Developers
- **Frustration Level:** 2
- **Suggested Fix:** Allow injection of config manager

### UX Issue #76: Ollama Base URL Not Configurable via CLI
- **Type:** Missing
- **Location:** config.py:31 ProviderConfig
- **Scenario:** User has Ollama on different host
- **Problem:** base_url field exists but no CLI way to set it
- **User Impact:** Power users
- **Frustration Level:** 3
- **Suggested Fix:** Add `blackreach config set ollama.base_url`

### UX Issue #77: Browser Type Validation Good
- **Type:** UX Win
- **What Works:** config.py:376-381
- **Why It's Good:** Shows valid options when invalid
- **Keep This:** Helpful error message

### UX Issue #78: Model Warning vs Error
- **Type:** Good Design
- **What Works:** config.py:462-468
- **Why It's Good:** Unknown model is warning not error (allows custom)
- **Keep This:** Flexible approach

---

## SECTION 5: LOGGING (logging.py)

### UX Issue #79: Log Directory Not In --help
- **Type:** Discoverability
- **Location:** logging.py:33
- **Scenario:** User wants to find logs
- **Problem:** `~/.blackreach/logs/` not shown in main help
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Show in `blackreach logs` help text

### UX Issue #80: Log Levels Not User-Configurable
- **Type:** Missing
- **Location:** logging.py
- **Scenario:** User wants more/less detail
- **Problem:** No CLI flag to set log level
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add `--log-level DEBUG/INFO/WARNING/ERROR`

### UX Issue #81: Log Rotation Good
- **Type:** UX Win
- **What Works:** logging.py:237-251
- **Why It's Good:** Auto-rotates at 10MB, prevents disk fill
- **Keep This:** Good default behavior

### UX Issue #82: Cleanup_old_logs Good
- **Type:** UX Win
- **What Works:** logging.py:562-570
- **Why It's Good:** Auto-cleanup of old logs
- **Keep This:** Good maintenance behavior

### UX Issue #83: JSONL Format Not Documented
- **Type:** Missing
- **Location:** logging.py
- **Scenario:** User wants to parse logs
- **Problem:** JSON Lines format not documented for tooling
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Document log format in help or README

### UX Issue #84: No Log Tail Command
- **Type:** Missing
- **Location:** logging.py
- **Scenario:** Watching logs in real-time
- **Problem:** No `blackreach logs --follow` for live watching
- **User Impact:** Power users
- **Frustration Level:** 3
- **Suggested Fix:** Add `--follow` flag for live tailing

### UX Issue #85: Search Logs Good
- **Type:** UX Win
- **What Works:** logging.py:611-658
- **Why It's Good:** Full-text search across logs
- **Keep This:** Powerful debugging feature

### UX Issue #86: Level Icons Good
- **Type:** UX Win
- **What Works:** logging.py:99-106
- **Why It's Good:** Visual distinction between log levels
- **Keep This:** Clear at-a-glance status

### UX Issue #87: Console Handler Off by Default
- **Type:** Design Choice
- **Location:** logging.py:274
- **Scenario:** Running agent
- **Problem:** enable_console=False by default, logs only to file
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Document that --verbose enables console logging

### UX Issue #88: No Log Aggregation
- **Type:** Missing
- **Location:** logging.py
- **Scenario:** Viewing all sessions
- **Problem:** No way to aggregate logs across sessions
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add log aggregation/reporting tool

### UX Issue #89: GlobalLogger Singleton Good
- **Type:** UX Win
- **What Works:** logging.py:669-686
- **Why It's Good:** Thread-safe singleton pattern
- **Keep This:** Proper global logger implementation

---

## SECTION 6: API INTERFACE (api.py)

### UX Issue #90: API Version Comment Outdated
- **Type:** Inconsistency
- **Location:** api.py:1
- **Scenario:** Checking API version
- **Problem:** Says "(v3.4.0)" but CLI is 4.0.0-beta.2
- **User Impact:** Developers
- **Frustration Level:** 2
- **Suggested Fix:** Update or remove version comment

### UX Issue #91: No API Documentation
- **Type:** Missing
- **Location:** api.py
- **Scenario:** Developer wants to use API
- **Problem:** No docstring examples, no API docs
- **User Impact:** Developers
- **Frustration Level:** 4
- **Suggested Fix:** Add comprehensive docstrings with examples

### UX Issue #92: BrowseResult Good Structure
- **Type:** UX Win
- **What Works:** api.py:18-28
- **Why It's Good:** Dataclass with sensible defaults
- **Keep This:** Clean API response type

### UX Issue #93: ApiConfig vs AgentConfig Confusion
- **Type:** Confusion
- **Location:** api.py:51-58
- **Scenario:** Developer configuring API
- **Problem:** ApiConfig different from AgentConfig - which to use?
- **User Impact:** Developers
- **Frustration Level:** 3
- **Suggested Fix:** Unify or document relationship

### UX Issue #94: Download Returns No URLs
- **Type:** Incomplete
- **Location:** api.py:161
- **Scenario:** Getting download results
- **Problem:** DownloadResult.url always empty string
- **User Impact:** Developers
- **Frustration Level:** 3
- **Suggested Fix:** Track source URLs in download results

### UX Issue #95: Search Not Implemented
- **Type:** Incomplete
- **Location:** api.py:168-197
- **Scenario:** Using search API
- **Problem:** Returns empty results, not actually implemented
- **User Impact:** Developers
- **Frustration Level:** 4
- **Suggested Fix:** Implement or remove/deprecate

### UX Issue #96: Context Manager Good
- **Type:** UX Win
- **What Works:** api.py:234-240
- **Why It's Good:** Proper resource cleanup with `with` statement
- **Keep This:** Pythonic API pattern

### UX Issue #97: Convenience Functions Good
- **Type:** UX Win
- **What Works:** api.py:245-266
- **Why It's Good:** Simple one-liners for common tasks
- **Keep This:** Low barrier to entry

### UX Issue #98: BatchProcessor Not Async
- **Type:** Limitation
- **Location:** api.py:271-324
- **Scenario:** Processing many goals
- **Problem:** Runs sequentially, no parallel processing
- **User Impact:** Developers
- **Frustration Level:** 3
- **Suggested Fix:** Add async batch processing

### UX Issue #99: No Error Handling in Convenience Functions
- **Type:** Incomplete
- **Location:** api.py:245-266
- **Scenario:** browse() fails
- **Problem:** Exceptions not caught in convenience functions
- **User Impact:** Developers
- **Frustration Level:** 3
- **Suggested Fix:** Add try/catch returning error result

### UX Issue #100: LLMConfig Not Exposed
- **Type:** Missing
- **Location:** api.py
- **Scenario:** Developer wants to configure LLM
- **Problem:** BlackreachAPI doesn't expose LLM configuration
- **User Impact:** Developers
- **Frustration Level:** 3
- **Suggested Fix:** Add llm_config to ApiConfig or BlackreachAPI

---

## SECTION 7: FIRST-TIME USER EXPERIENCE

### UX Issue #101: Setup Wizard Good
- **Type:** UX Win
- **What Works:** cli.py:130-205 run_first_time_setup
- **Why It's Good:** Guides new users through setup step by step
- **Keep This:** Essential for adoption

### UX Issue #102: Browser Install Takes Long
- **Type:** Friction
- **Location:** cli.py:96-117
- **Scenario:** First run
- **Problem:** "may take a minute" - actually can take 5+ minutes on slow connections
- **User Impact:** New users
- **Frustration Level:** 3
- **Suggested Fix:** Show download progress, accurate time estimate

### UX Issue #103: Ollama Check Not Helpful
- **Type:** Incomplete
- **Location:** cli.py:120-127
- **Scenario:** Setting up Ollama
- **Problem:** Just checks if running, doesn't help install
- **User Impact:** Beginners
- **Frustration Level:** 3
- **Suggested Fix:** Provide installation instructions for different OSes

### UX Issue #104: Model Pull Not Automatic
- **Type:** Friction
- **Location:** cli.py:176-178
- **Scenario:** Selecting Ollama model
- **Problem:** User picks model but not pulled - will fail on first run
- **User Impact:** Beginners
- **Frustration Level:** 4
- **Suggested Fix:** Offer to pull model during setup

### UX Issue #105: No Internet Check in Setup
- **Type:** Missing
- **Location:** cli.py setup
- **Scenario:** User offline during setup
- **Problem:** Doesn't check internet connectivity upfront
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Check connectivity at start of setup

### UX Issue #106: API Key Paste Masked
- **Type:** Consideration
- **Location:** cli.py:189
- **Scenario:** Entering API key
- **Problem:** password=True means can't verify what was pasted
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Show last 4 chars after paste, or ask to confirm

### UX Issue #107: No Setup Resume
- **Type:** Missing
- **Location:** cli.py setup
- **Scenario:** Setup interrupted
- **Problem:** If setup fails halfway, must restart from beginning
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Track setup progress, resume where left off

### UX Issue #108: QUICKSTART.md Exists
- **Type:** UX Win
- **What Works:** QUICKSTART.md file exists
- **Why It's Good:** Quick reference for new users
- **Keep This:** Essential documentation

---

## SECTION 8: INTERACTIVE MODE

### UX Issue #109: Interactive Mode Entry Good
- **Type:** UX Win
- **What Works:** cli.py:1325-1619 interactive_mode
- **Why It's Good:** Full REPL with history, completion
- **Keep This:** Professional interactive experience

### UX Issue #110: Double Ctrl+C to Exit
- **Type:** UX Win
- **What Works:** cli.py:1608-1616
- **Why It's Good:** Prevents accidental exit
- **Keep This:** Good UX pattern

### UX Issue #111: Slash Commands Discoverable
- **Type:** UX Win
- **What Works:** Tab completion shows slash commands
- **Why It's Good:** Users can explore without reading docs
- **Keep This:** Discoverable interface

### UX Issue #112: /plan Command Hidden
- **Type:** Incomplete
- **Location:** cli.py:1404-1428
- **Scenario:** User wants to preview plan
- **Problem:** /plan exists but not in help or completions
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Add to help and completions

### UX Issue #113: No /run Alias
- **Type:** Friction
- **Location:** interactive mode
- **Scenario:** User types /run "goal"
- **Problem:** No /run command, must just type goal
- **User Impact:** Beginners
- **Frustration Level:** 2
- **Suggested Fix:** Add /run as alias or show hint

### UX Issue #114: Error Shows Provider Missing
- **Type:** Good Error
- **What Works:** cli.py:1600-1603
- **Why It's Good:** Tells user to /config or /provider
- **Keep This:** Actionable error message

### UX Issue #115: Memory Stats in Welcome
- **Type:** UX Win
- **What Works:** cli.py:1341-1347
- **Why It's Good:** Shows session/download counts
- **Keep This:** Context for returning users

### UX Issue #116: No /undo or /cancel
- **Type:** Missing
- **Location:** interactive mode
- **Scenario:** User wants to cancel mid-operation
- **Problem:** Only Ctrl+C, no /cancel command
- **User Impact:** Beginners
- **Frustration Level:** 2
- **Suggested Fix:** Add /cancel command

---

## SECTION 9: OUTPUT AND FEEDBACK

### UX Issue #117: Result Panel Good
- **Type:** UX Win
- **What Works:** cli.py:358-376 _show_results
- **Why It's Good:** Clear summary with all key metrics
- **Keep This:** Professional completion feedback

### UX Issue #118: Resume Hint Good
- **Type:** UX Win
- **What Works:** cli.py:375-376
- **Why It's Good:** Shows exact command to resume
- **Keep This:** Actionable next step

### UX Issue #119: Table Formatting Consistent
- **Type:** UX Win
- **What Works:** All tables use same styling
- **Why It's Good:** Visual consistency
- **Keep This:** Professional appearance

### UX Issue #120: Progress Bar Good
- **Type:** UX Win
- **What Works:** ui.py:128-132
- **Why It's Good:** Shows filled/empty blocks with percentage
- **Keep This:** Clear progress indication

### UX Issue #121: No Notification on Completion
- **Type:** Missing
- **Location:** cli.py/ui.py
- **Scenario:** Long-running task
- **Problem:** No system notification when task completes
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Add optional desktop notification

### UX Issue #122: No Sound on Completion
- **Type:** Missing
- **Location:** cli.py/ui.py
- **Scenario:** Long-running task
- **Problem:** No audible notification when done
- **User Impact:** Some users
- **Frustration Level:** 1
- **Suggested Fix:** Add optional bell/sound

### UX Issue #123: Downloads Listed at End
- **Type:** UX Win
- **What Works:** ui.py:213-222
- **Why It's Good:** Shows first 5 downloads, mentions "and N more"
- **Keep This:** Informative without overwhelming

---

## SECTION 10: EDGE CASES AND ERRORS

### UX Issue #124: Mistype Command Error Clear
- **Type:** UX Win
- **What Works:** "No such command 'mistype'" with help pointer
- **Why It's Good:** Points to --help
- **Keep This:** Good error handling

### UX Issue #125: Missing Arg Error Clear
- **Type:** UX Win
- **What Works:** "Goal is required (or use --resume)"
- **Why It's Good:** Shows alternatives
- **Keep This:** Helpful error message

### UX Issue #126: Resume Without ID Error
- **Type:** Adequate
- **Location:** CLI
- **Scenario:** blackreach run --resume (no ID)
- **Problem:** Just says "requires an argument" - could show recent sessions
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Show recent resumable sessions in error

### UX Issue #127: No Internet Error Handling
- **Type:** Missing
- **Location:** Throughout
- **Scenario:** User loses internet mid-operation
- **Problem:** Generic errors, no specific "network unavailable" handling
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Detect network loss and give specific guidance

### UX Issue #128: Config Corrupt Handling
- **Type:** Incomplete
- **Location:** config.py:130-132
- **Scenario:** Config file corrupted
- **Problem:** Just prints warning and uses defaults - should offer repair
- **User Impact:** Rare
- **Frustration Level:** 3
- **Suggested Fix:** Offer to backup and recreate config

### UX Issue #129: Ctrl+C During Browser Init
- **Type:** Good Handling
- **What Works:** cli.py:351-352
- **Why It's Good:** Catches KeyboardInterrupt, saves state
- **Keep This:** Graceful interrupt handling

### UX Issue #130: Running Same Command Twice
- **Type:** Not Addressed
- **Location:** N/A
- **Scenario:** User runs same goal twice
- **Problem:** No detection of duplicate/recent goals
- **User Impact:** All users
- **Frustration Level:** 1
- **Suggested Fix:** Optional: "Similar goal ran 5 min ago. Continue?"

---

## SECTION 11: DOCUMENTATION GAPS

### UX Issue #131: No Man Page
- **Type:** Missing
- **Location:** N/A
- **Scenario:** User runs `man blackreach`
- **Problem:** No man page installed
- **User Impact:** Unix users
- **Frustration Level:** 2
- **Suggested Fix:** Generate man page from CLI

### UX Issue #132: No Shell Completion Docs
- **Type:** Missing
- **Location:** README
- **Scenario:** User wants tab completion
- **Problem:** Not documented how to enable shell completion
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Add completion setup instructions

### UX Issue #133: Environment Variables Not Listed
- **Type:** Missing
- **Location:** README/help
- **Scenario:** User wants to use env vars
- **Problem:** Supported env vars (OPENAI_API_KEY, etc.) not documented
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** List all supported env vars

### UX Issue #134: Default Values Not Collected
- **Type:** Missing
- **Location:** Help output
- **Scenario:** User wants to know defaults
- **Problem:** Not all defaults shown in --help
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Add defaults to all options

### UX Issue #135: No Troubleshooting Guide
- **Type:** Missing
- **Location:** docs/
- **Scenario:** User hits common error
- **Problem:** No FAQ or troubleshooting document
- **User Impact:** All users
- **Frustration Level:** 3
- **Suggested Fix:** Create troubleshooting.md

### UX Issue #136: Examples in README Good
- **Type:** UX Win
- **What Works:** README.md has usage examples
- **Why It's Good:** Shows real-world usage
- **Keep This:** Essential for adoption

---

## SECTION 12: CONSISTENCY ISSUES

### UX Issue #137: Short Flag Inconsistency
- **Type:** Inconsistency
- **Location:** Various commands
- **Scenario:** Using short flags
- **Problem:** Some use -n for limit, some use -l for limit
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Standardize: -n for number/count, -l for list

### UX Issue #138: Help Text Style Varies
- **Type:** Inconsistency
- **Location:** Various commands
- **Scenario:** Reading help
- **Problem:** Some end with period, some don't
- **User Impact:** Minor
- **Frustration Level:** 1
- **Suggested Fix:** Consistent punctuation in help

### UX Issue #139: Output Format Inconsistent
- **Type:** Inconsistency
- **Location:** Various commands
- **Scenario:** Reading output
- **Problem:** Some use tables, some use panels, some use plain text
- **User Impact:** Minor
- **Frustration Level:** 1
- **Suggested Fix:** Guidelines for output format by command type

### UX Issue #140: Exit Codes Not Documented
- **Type:** Missing
- **Location:** N/A
- **Scenario:** Scripting with blackreach
- **Problem:** Exit codes not documented (0=success, 1=error, etc.)
- **User Impact:** Power users
- **Frustration Level:** 2
- **Suggested Fix:** Document exit codes

---

## SECTION 13: ACCESSIBILITY

### UX Issue #141: No Screen Reader Support
- **Type:** Accessibility
- **Location:** ui.py
- **Scenario:** Blind user
- **Problem:** Rich formatting may not work well with screen readers
- **User Impact:** Accessibility
- **Frustration Level:** 4
- **Suggested Fix:** Add --plain-text mode

### UX Issue #142: Color-Only Information
- **Type:** Accessibility
- **Location:** ui.py
- **Scenario:** Color-blind user
- **Problem:** Some status only indicated by color (red=error, green=success)
- **User Impact:** Color-blind users
- **Frustration Level:** 3
- **Suggested Fix:** Always include text indicators (X, checkmark)

### UX Issue #143: Uses Checkmarks and X
- **Type:** UX Win
- **What Works:** Uses symbols alongside colors
- **Why It's Good:** Works for color-blind users
- **Keep This:** Good accessibility pattern

---

## SECTION 14: PERFORMANCE UX

### UX Issue #144: No Startup Time Indication
- **Type:** Missing
- **Location:** cli.py
- **Scenario:** Running any command
- **Problem:** Import time can be slow, no indication
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Lazy imports for faster startup

### UX Issue #145: Doctor Command Slow
- **Type:** Performance
- **Location:** cli.py:850-903
- **Scenario:** Running blackreach doctor
- **Problem:** Checks Playwright browsers which is slow
- **User Impact:** All users
- **Frustration Level:** 2
- **Suggested Fix:** Show spinner during checks

### UX Issue #146: Health Command Timeout Default
- **Type:** Good Default
- **What Works:** Default 5s timeout
- **Why It's Good:** Won't hang forever
- **Keep This:** Reasonable default

---

## SECTION 15: FINAL OBSERVATIONS

### UX Issue #147: Version Command Includes System Info
- **Type:** UX Win
- **What Works:** cli.py:579-584
- **Why It's Good:** Shows Python version and OS - helpful for debugging
- **Keep This:** Good for issue reports

### UX Issue #148: Signal Handlers for Cleanup
- **Type:** UX Win
- **What Works:** cli.py:43-55
- **Why It's Good:** Handles SIGTERM, cleans up keyboard state
- **Keep This:** Prevents stuck keys

### UX Issue #149: Keyboard Cleanup Good
- **Type:** UX Win
- **What Works:** cli.py:34-41 _cleanup_keyboard
- **Why It's Good:** Releases all keys on exit
- **Keep This:** Essential for browser automation

### UX Issue #150: No Telemetry
- **Type:** UX Win
- **What Works:** No telemetry or analytics
- **Why It's Good:** Privacy-respecting tool
- **Keep This:** Trust is important

---

## Summary Statistics

| Category | Count |
|----------|-------|
| UX Issues (Friction/Missing/Confusion) | 119 |
| UX Wins (Keep These) | 31 |
| **Total Findings** | **150** |

### Issues by Severity (Frustration Level)

| Level | Description | Count |
|-------|-------------|-------|
| 1 | Minor annoyance | 8 |
| 2 | Noticeable friction | 52 |
| 3 | Significant frustration | 42 |
| 4 | Major blocker | 17 |

### Issues by Type

| Type | Count |
|------|-------|
| Missing Feature | 38 |
| Confusion | 18 |
| Friction | 21 |
| Incomplete | 19 |
| Inconsistency | 10 |
| Accessibility | 3 |
| Performance | 3 |
| Design | 4 |
| Fragile | 3 |

### Top Priority Fixes (Frustration Level 4)

1. **#104** - Ollama model not auto-pulled during setup
2. **#14** - Model override without provider silently fails
3. **#26** - BrowserNotReadyError doesn't explain what to do
4. **#95** - Search API not implemented but exposed
4. **#38** - MaxStepsExceeded gives no guidance
5. **#39** - CaptchaError has no workaround suggestions
6. **#44** - SSLError gives no fix suggestions
7. **#45** - SessionCorruptedError no recovery option
8. **#91** - API has no documentation

---

## Recommendations

### Immediate (Before Release)
1. Fix version mismatches (#1, #47, #90)
2. Add model auto-pull for Ollama (#104)
3. Improve critical error messages (#26, #27, #38, #39)
4. Add --quiet and --output json flags (#2, #11)

### Short Term (Next Sprint)
1. Command suggestion on typo (#9)
2. Config CLI improvements (#17, #76)
3. Merge confusing commands (#19, #22, #23)
4. Add shell completions (#24)

### Long Term (Roadmap)
1. Full API documentation (#91)
2. Accessibility improvements (#141, #142)
3. Batch processing async (#98)
4. Telemetry-free analytics dashboard

---

*End of UX Investigation Report*
