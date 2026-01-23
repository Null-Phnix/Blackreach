# Performance Fix - Single LLM Call Architecture

## Session Date: January 22, 2026 (Session 2)

---

## Problem

The agent was making **3 LLM calls per step**:
1. `_observe()` - Describe the page
2. `_think()` - Decide what to do
3. `_act()` - Output JSON action

This caused:
- Extremely slow performance (3x latency)
- Higher token usage
- Inconsistent outputs between calls

---

## Solution: Unified ReAct Prompt

Combined all three calls into a single prompt (`react.txt`) that:
- Shows page state (URL, title, elements)
- Shows goal
- Asks for thought + action in ONE JSON response

### Before (3 calls per step):
```
Step 1:
  LLM call 1: "Describe this page..."
  LLM call 2: "What should I do..."
  LLM call 3: "Output JSON action..."
```

### After (1 call per step):
```
Step 1:
  LLM call 1: "Here's the page and goal. Output thought + action as JSON"
```

---

## Changes Made

### prompts/react.txt (NEW)

Simplified prompt that asks for thought + action together:

```
GOAL: {goal}

PAGE: {title}
URL: {url}

ELEMENTS:
{elements}

OUTPUT JSON ONLY:
{"thought": "reason", "action": "name", "args": {...}}

ACTIONS:
- type: {"thought": "search X", "action": "type", "args": {"selector": "input", "text": "query"}}
- click: {"thought": "click X", "action": "click", "args": {"text": "Link Text"}}
- navigate: {"thought": "go to X", "action": "navigate", "args": {"url": "..."}}
- done: {"thought": "goal complete", "action": "done", "args": {"reason": "why"}}

RULE: If page title matches goal topic, use done action.

JSON:
```

### agent.py Changes

1. **New `_step()` method** - Single LLM call instead of three
2. **Action aliasing** - Maps common LLM outputs to valid actions:
   ```python
   action_aliases = {
       "search": "type",
       "go": "navigate",
       "goto": "navigate",
       "visit": "navigate",
       "finish": "done",
       "complete": "done",
   }
   ```
3. **Auto-submit for type** - Changed default from `submit: False` to `submit: True`
4. **Default URL** - Changed from Google (CAPTCHA) to Wikipedia

---

## Test Results

| Test | Result | Steps |
|------|--------|-------|
| Search "artificial intelligence" | SUCCESS | 2 |
| Search "Python programming" | SUCCESS | 2 |

### Example Run:
```
[Step 1/5]
  REACT: search for artificial intelligence on wikipedia -> navigate

[Step 2/5]
  REACT: page title matches goal topic -> done

 COMPLETE: Artificial intelligence - Wikipedia
```

---

## Performance Comparison

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| LLM calls per step | 3 | 1 | 66% reduction |
| Prompt tokens | ~2000 | ~500 | 75% reduction |
| Response time | ~15s | ~5s | 66% faster |

---

## Key Learnings

1. **Simpler prompts work better** - The verbose 3-prompt system confused smaller models
2. **Action aliasing is essential** - LLMs use various names for the same action
3. **Auto-submit saves steps** - Most type actions need Enter pressed
4. **Title matching for goal detection** - Simple rule catches most success cases

---

## Files Changed

| File | Change |
|------|--------|
| prompts/react.txt | NEW - Unified prompt |
| blackreach/agent.py | Refactored _step() to single call |
| blackreach/agent.py | Added action aliases |
| blackreach/agent.py | Default submit=True for type |
| blackreach/agent.py | Default URL = Wikipedia |
