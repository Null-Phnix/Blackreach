# Priority Issues from User Testing

**Generated:** 2026-01-26
**Source:** Automated user testing found these issues

## Critical Issues to Fix

### 1. Timeout Issues on Common Sites
**Affected:** Wikipedia, GitHub, Google
**Symptom:** Operations timeout at 120-180s
**Likely Cause:**
- Wait logic too aggressive
- Content detection timing issues
- May need adaptive timeouts based on site

**Files to investigate:**
- `blackreach/browser.py` - goto(), wait_for_content logic
- `blackreach/agent.py` - step timeouts
- `blackreach/stuck_detector.py` - stuck detection thresholds

### 2. Image Search Failing (Unsplash)
**Symptom:** Exit code 1
**Likely Cause:**
- Unsplash site structure changed
- Image download logic failing
- Site handler may need update

**Files to investigate:**
- `blackreach/site_handlers.py` - Unsplash handler
- `blackreach/browser.py` - image download logic
- `blackreach/observer.py` - image link detection

### 3. Session Resume Not Working
**Symptom:** Interrupt/resume flow fails
**Likely Cause:**
- State not being saved properly on interrupt
- Resume not restoring state correctly
- Session ID handling issues

**Files to investigate:**
- `blackreach/agent.py` - save_state(), resume()
- `blackreach/memory.py` - session persistence
- `blackreach/cli.py` - --resume flag handling

### 4. Form Interaction (Google Search)
**Symptom:** Timeout on simple search
**Likely Cause:**
- Google's dynamic loading
- Form submission timing
- May need different approach for Google

**Files to investigate:**
- `blackreach/browser.py` - type(), click() methods
- `blackreach/site_handlers.py` - Google handler
- `blackreach/agent.py` - form interaction logic

## What Worked Well
- ArXiv paper downloads (47.9s) ✓
- Multi-page pagination (230.8s) ✓
- Error recovery from 500 errors (158.0s) ✓

## Recommended Priority Order
1. Fix timeout issues (affects multiple scenarios)
2. Fix session resume (core feature)
3. Fix form interaction (common use case)
4. Fix image search (specific to Unsplash)
