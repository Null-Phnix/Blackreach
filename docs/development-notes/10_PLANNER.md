# Planner Module

This document explains the Planner module for breaking complex goals into subtasks.

---

## What This Does (ELI5)

Imagine you ask someone to "download 5 papers about transformers from arxiv."

A simple approach would be to start clicking around randomly hoping to find papers. But a smarter approach is to first make a plan:

1. Go to arxiv.org
2. Search for "transformers"
3. Download paper 1
4. Download paper 2
5. ... etc.

The Planner module does exactly this - it takes a complex goal and breaks it into simple, actionable steps that the agent can execute one by one.

---

## Why It's Built This Way

### Simple vs Complex Goals

Not every goal needs planning:

| Simple (no planning) | Complex (needs planning) |
|---------------------|--------------------------|
| "go to wikipedia" | "download 5 papers" |
| "search for cats" | "find all images on this page" |
| "click the login button" | "fill the form then submit" |

Simple goals can be handled directly by the ReAct loop. Complex goals need to be broken down first.

### How We Detect Complexity

The planner looks for keywords that indicate complexity:

**Complex indicators:**
- Numbers > 1 ("download 5", "find 10")
- "all", "each", "every" (iteration needed)
- "download", "papers", "files", "images" (multi-step tasks)
- "then", "after that" (sequential steps)

**Simple indicators:**
- "go to", "navigate to" (single navigation)
- "search for" (single search)
- "click", "open" (single action)

---

## The Code Explained

### Goal Classification

```python
def is_simple_goal(self, goal: str) -> bool:
    # Check for complex indicators
    complex_indicators = ["download", "all", "each", "papers", "files"]
    for indicator in complex_indicators:
        if indicator in goal.lower():
            return False  # Complex!

    # Check for numbers > 1
    numbers = re.findall(r'\b([2-9]|[1-9]\d+)\b', goal)
    if numbers:
        return False  # Multiple items = complex

    # Check for simple patterns
    if goal.lower().startswith("go to"):
        return True  # Simple navigation

    # Default: simple if short
    return len(goal.split()) < 10
```

### Plan Generation

```python
PLAN_PROMPT = """You are a task planner for a web browser agent.

GOAL: {goal}

Break this goal into concrete, actionable subtasks.
Each subtask should be completable in 1-5 browser actions.

OUTPUT FORMAT (JSON):
{
    "subtasks": [
        {"description": "Go to arxiv.org", "expected_outcome": "On homepage"},
        ...
    ]
}
"""
```

### Data Structures

```python
@dataclass
class Subtask:
    description: str      # What to do
    expected_outcome: str # How to know it's done
    optional: bool = False

@dataclass
class Plan:
    goal: str
    subtasks: List[Subtask]
    estimated_steps: int
```

---

## Example Plans

### Goal: "download 3 papers about transformers from arxiv"

```
Plan:
  1. Navigate to https://arxiv.org/
     → arXiv homepage is loaded

  2. Search for 'transformer neural network'
     → Search results display papers about transformers

  3. Click [PDF] link next to first paper
     → PDF download initiated

  4. Click [PDF] link next to second paper
     → PDF download initiated

  5. Click [PDF] link next to third paper
     → PDF download initiated

Estimated steps: ~15
```

### Goal: "find 10 wallpapers of anime characters"

```
Plan:
  1. Navigate to a wallpaper site (e.g., wallhaven.cc)
     → On wallpaper site

  2. Search for "anime characters"
     → Search results showing anime wallpapers

  3-12. Download wallpaper N (repeated 10 times)
     → Wallpaper downloaded

Estimated steps: ~30
```

---

## How to Use

### Preview a Plan

```bash
# In the interactive CLI
/plan download 5 papers about transformers from arxiv
```

This shows what the agent would do without actually doing it.

### Simple Goal (No Plan)

```bash
/plan search for cats
# Output: Goal is simple - will run directly without planning
```

---

## Current Limitations

1. **Plans don't auto-execute** - Currently the planner just generates plans. The agent doesn't automatically execute them step by step.

2. **No plan persistence** - Plans aren't saved. If you run a complex goal, it doesn't remember the plan.

3. **No progress tracking** - If a step fails, the planner doesn't know to retry or adjust.

### Future Improvements

1. **Plan execution mode** - Run each subtask and track progress
2. **Adaptive planning** - Adjust plan based on what's found
3. **Checkpoint resume** - Save progress and resume later
4. **Parallel subtasks** - Run independent tasks concurrently

---

## Code Location

| What | Where |
|------|-------|
| Planner class | blackreach/planner.py |
| /plan command | blackreach/cli.py |
| Plan prompt | planner.py PLAN_PROMPT |

---

## Key Concepts

1. **Simple vs Complex** - Not all goals need planning
2. **Subtasks** - Break complex goals into 1-5 action steps
3. **Expected Outcomes** - Know when a step is "done"
4. **Estimation** - Guess total steps needed

---

## Testing

```python
from blackreach.planner import Planner

planner = Planner()

# Test classification
print(planner.is_simple_goal("go to wikipedia"))  # True
print(planner.is_simple_goal("download 5 papers"))  # False

# Generate a plan
plan = planner.plan("download 5 papers about transformers")
print(planner.format_plan(plan))
```
