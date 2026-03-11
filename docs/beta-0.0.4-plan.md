# Blackreach Beta 0.0.4 Plan

## Current State (v0.3.0)
- 1003 tests, 66% coverage
- 10 modules at 100% coverage
- Core agent loop working
- Multi-provider LLM support (Ollama, OpenAI, Anthropic, Google, xAI)
- Persistent memory system
- Stealth mode
- Session resume capability

## Code Quality Issues to Address
From code review:
1. `_step()` method too long (470 lines)
2. Magic numbers without documentation
3. Complex branching in `_execute_action()`
4. Dual memory system needs documentation

## Beta 0.0.4 Feature Candidates

### Tier 1: Code Quality (Essential)
- [ ] Refactor `_step()` into smaller methods
- [ ] Extract action handlers into classes
- [ ] Document magic numbers as constants
- [ ] Add architecture documentation

### Tier 2: Stability Improvements
- [ ] Better error messages for common failures
- [ ] Improved stuck detection
- [ ] Enhanced logging for debugging
- [ ] Retry strategies for flaky elements

### Tier 3: New Features
- [ ] Multi-tab support
- [ ] Form filling capabilities
- [ ] Screenshot on each step (optional)
- [ ] Action history visualization
- [ ] Export session logs to JSON

### Tier 4: Performance
- [ ] Faster page parsing
- [ ] Parallel element detection
- [ ] Caching improvements
- [ ] Memory usage optimization

## Recommended 0.0.4 Focus

Given the code review findings, 0.0.4 should prioritize:

1. **Code Refactoring** - Make code maintainable
   - Split `_step()` into observe/think/act
   - Create ActionHandler classes
   - Document constants

2. **Stability** - Reduce friction
   - Better error messages
   - Improved debugging logs
   - More robust stuck detection

3. **Developer Experience** - Enable contributions
   - Architecture documentation
   - API documentation
   - Example scripts

## Timeline Estimate
- Refactoring: 8-12 hours
- Stability improvements: 4-6 hours
- Documentation: 4-6 hours
- Testing: 4-6 hours

Total: ~20-30 hours of focused work

## Success Metrics
- [ ] No method over 200 lines
- [ ] All magic numbers documented
- [ ] 70%+ test coverage
- [ ] Architecture doc complete
- [ ] 3+ example scripts
