# Blackreach Roadmap: Alpha → Beta

**Current Version:** 0.2.0 (Alpha)
**Target Version:** 0.3.0 (Beta)
**Target Completion:** 75% of Beta features

---

## Beta Definition

A Beta release means:
- Core features work reliably (>90% success rate on supported sites)
- Test coverage exists for critical paths
- Users can pause and resume sessions
- Documentation is consolidated and usable
- Edge cases are handled gracefully

---

## Milestone 1: Test Foundation (Priority: Critical)

**Goal:** Establish test infrastructure and basic coverage

### Tasks
- [ ] 1.1 Create tests/ directory structure
- [ ] 1.2 Set up pytest configuration
- [ ] 1.3 Write unit tests for memory.py
- [ ] 1.4 Write unit tests for observer.py (element extraction)
- [ ] 1.5 Write unit tests for llm.py (response parsing)
- [ ] 1.6 Write integration tests for browser.py (downloads)
- [ ] 1.7 Write end-to-end test for simple goal
- [ ] 1.8 Add test fixtures for mock HTML pages

**Success Criteria:** `pytest` runs with >60% coverage on core modules

---

## Milestone 2: Session Resume (Priority: High)

**Goal:** Allow users to pause and resume interrupted sessions

### Tasks
- [ ] 2.1 Design session state schema (what needs saving)
- [ ] 2.2 Add session serialization to memory.py
- [ ] 2.3 Add `--resume` flag to CLI
- [ ] 2.4 Implement session restore in agent.py
- [ ] 2.5 Add `/pause` command to interactive mode
- [ ] 2.6 Handle partial downloads on resume
- [ ] 2.7 Test resume after crash/interrupt

**Success Criteria:** Can Ctrl+C a session and resume it later

---

## Milestone 3: Error Handling Improvements (Priority: High)

**Goal:** Graceful handling of all common failure modes

### Tasks
- [ ] 3.1 Audit all try/except blocks for proper handling
- [ ] 3.2 Add specific exception classes (BlackreachError hierarchy)
- [ ] 3.3 Implement CAPTCHA detection and user notification
- [ ] 3.4 Add rate limit detection and backoff
- [ ] 3.5 Handle network timeouts gracefully
- [ ] 3.6 Add login wall detection
- [ ] 3.7 Improve element-not-found recovery
- [ ] 3.8 Add max-failure circuit breaker

**Success Criteria:** Agent never crashes unexpectedly, always gives clear error

---

## Milestone 4: Documentation (Priority: Medium)

**Goal:** Consolidate docs into usable format

### Tasks
- [ ] 4.1 Write comprehensive README.md
- [ ] 4.2 Create QUICKSTART.md with examples
- [ ] 4.3 Document all CLI commands
- [ ] 4.4 Document configuration options
- [ ] 4.5 Create CONTRIBUTING.md
- [ ] 4.6 Add inline docstrings to public APIs
- [ ] 4.7 Consolidate learning/ into docs/

**Success Criteria:** New user can get started in <5 minutes

---

## Milestone 5: Reliability Improvements (Priority: Medium)

**Goal:** Increase success rate on supported sites

### Tasks
- [ ] 5.1 Improve ArXiv navigation (category pages)
- [ ] 5.2 Fix GitHub repo file browsing
- [ ] 5.3 Add support for pagination (search results)
- [ ] 5.4 Improve PDF detection heuristics
- [ ] 5.5 Handle JavaScript-heavy pages better
- [ ] 5.6 Add scroll-to-load detection
- [ ] 5.7 Improve link prioritization algorithm

**Success Criteria:** >90% success rate on ArXiv, GitHub, Wikipedia

---

## Milestone 6: Config System (Priority: Low)

**Goal:** Full configuration file support

### Tasks
- [ ] 6.1 Define config schema (YAML)
- [ ] 6.2 Implement config loading in config.py
- [ ] 6.3 Add config validation
- [ ] 6.4 Support per-site configs
- [ ] 6.5 Add `blackreach config` command
- [ ] 6.6 Document all config options

**Success Criteria:** All hardcoded values can be overridden via config

---

## Work Packages

### Package A: Foundation (Milestones 1 + 3)
- Tests + Error handling
- Estimated effort: 6-8 hours
- **This is the 75% Beta target**

### Package B: User Experience (Milestones 2 + 4)
- Resume + Docs
- Estimated effort: 4-6 hours

### Package C: Polish (Milestones 5 + 6)
- Reliability + Config
- Estimated effort: 4-6 hours

---

## Progress Tracking

| Milestone | Tasks | Done | Progress |
|-----------|-------|------|----------|
| 1. Tests | 8 | 6 | 75% |
| 2. Resume | 7 | 0 | 0% |
| 3. Errors | 8 | 0 | 0% |
| 4. Docs | 7 | 0 | 0% |
| 5. Reliability | 7 | 0 | 0% |
| 6. Config | 6 | 0 | 0% |
| **Total** | **43** | **6** | **14%** |

**75% Beta = Package A complete + 50% of Package B**

### Milestone 1 Detail
- [x] 1.1 Create tests/ directory structure
- [x] 1.2 Set up pytest configuration
- [x] 1.3 Write unit tests for memory.py (38 tests)
- [x] 1.4 Write unit tests for observer.py (54 tests)
- [x] 1.5 Write unit tests for llm.py (31 tests)
- [x] 1.6 Write integration tests for browser.py (23 tests)
- [ ] 1.7 Write end-to-end test for simple goal
- [ ] 1.8 Add test fixtures for mock HTML pages (partial - in conftest.py)

**Total: 146 tests passing**

---

## Session Log

Track autonomous work sessions here:

| Session | Date | Duration | Tasks Completed | Notes |
|---------|------|----------|-----------------|-------|
| 1 | - | - | - | - |

