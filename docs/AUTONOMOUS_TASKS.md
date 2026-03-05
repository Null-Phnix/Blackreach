# Blackreach Autonomous Improvement Session

## Context
Read these files first to understand current state:
- `learning/08_DEBUGGING_REPORT.md` - Recent fixes and known issues
- `learning/07_SESSION_LOG.md` - Session history
- `learning/test_results.md` - Test results

## Priority 1: Fix Remaining Issues

### Issue A: LLM Picks Same Link Repeatedly
**Problem:** Even with "ALREADY VISITED" context, model picks same link ~30% of time
**Suggested Fix:** Remove already-visited links from element list entirely before sending to LLM
**Files:** `blackreach/agent.py` - `_format_elements()` and `_step()`

### Issue B: Download Timeouts for Inline Files
**Problem:** Browser displays some files inline instead of downloading
**Suggested Fix:** Detect file type from URL and use HTTP fetch directly for images/PDFs
**Files:** `blackreach/browser.py` - `download_file()`, `download_link()`

## Priority 2: Code Cleanup

### Dead Code Removal
- Search for unused imports
- Search for commented-out code blocks
- Search for unused functions/methods
- Run: `grep -r "# TODO\|# FIXME\|# XXX\|# HACK" blackreach/`

### Type Hints
- Add type hints to all public methods
- Focus on: `agent.py`, `browser.py`, `llm.py`

### Docstrings
- Ensure all public methods have docstrings
- Follow Google style docstrings

## Priority 3: Error Handling

### Improve Error Messages
- Replace generic exceptions with specific ones
- Add context to error messages (URL, selector, action)
- Log errors to session logger

### Add Retry Logic
- Retry failed downloads (network issues)
- Retry failed navigation (page load timeout)
- Max 3 retries with exponential backoff

## Priority 4: Testing

### Run Full Test Suite Again
After fixes, run all 10 tests from `learning/test_results.md`:
1. Wallpapers (wallhaven)
2. ArXiv papers
3. GitHub files
4. PyTorch docs
5. Gutenberg ebooks
6. CSV data files
7. Multi-step research
8. JavaScript sites
9. MIT OCW PDFs
10. Edge cases

### Add Unit Tests
Create `tests/` directory with:
- `test_agent.py` - Action parsing, URL resolution
- `test_browser.py` - Download handling
- `test_observer.py` - Element extraction

## Priority 5: Performance

### Profile LLM Calls
- Measure token usage per step
- Optimize prompt length
- Consider caching repeated prompts

### Reduce Memory Usage
- Clear page cache between steps
- Limit session memory size
- Add garbage collection hints

## How to Run This Session

Start Claude Code and say:
```
Read AUTONOMOUS_TASKS.md and work through the tasks autonomously.
Start with Priority 1, then move to Priority 2, etc.
Document all changes in learning/09_SESSION_LOG.md.
Run tests after each major fix to verify nothing broke.
Don't stop until you've completed at least Priority 1 and 2.
```

## Success Criteria
- [ ] LLM no longer picks same link repeatedly
- [ ] All inline file downloads work
- [ ] No dead code or unused imports
- [ ] All public methods have type hints
- [ ] Test pass rate >= 80%
