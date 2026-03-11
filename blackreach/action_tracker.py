"""
Blackreach Action Tracker - Learn from action outcomes.

Tracks success/failure of actions to build confidence scores.
The agent uses this to make smarter decisions about which
actions to try and which to avoid.

Example usage:
    tracker = ActionTracker(memory)

    # Record outcomes
    tracker.record("click", "button.download", success=True, domain="archive.org")
    tracker.record("click", "a.slow-download", success=False, domain="libgen.li")

    # Get confidence for an action
    confidence = tracker.get_confidence("click", "button.download", domain="archive.org")
    # Returns 0.0-1.0 based on historical success rate

    # Get recommended actions for a domain
    recommendations = tracker.get_recommendations(domain="archive.org", action_type="click")
    # Returns list of selectors sorted by success rate
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import json


@dataclass
class ActionOutcome:
    """Record of an action's outcome."""
    action_type: str      # click, type, scroll, navigate, download
    target: str           # selector, URL, or input text
    domain: str           # Site domain where action occurred
    success: bool         # Whether action achieved intended result
    context: str = ""     # Additional context (page title, etc.)
    error: str = ""       # Error message if failed


@dataclass
class ActionStats:
    """Aggregated statistics for an action pattern."""
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[str] = None  # Timestamp
    last_failure: Optional[str] = None
    common_errors: Dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.5  # Unknown = neutral
        return self.success_count / self.total

    def record_success(self):
        self.success_count += 1
        self.last_success = datetime.now().isoformat()

    def record_failure(self, error: str = ""):
        self.failure_count += 1
        self.last_failure = datetime.now().isoformat()
        if error:
            self.common_errors[error] = self.common_errors.get(error, 0) + 1


class ActionTracker:
    """
    Tracks action outcomes to build confidence scores.

    Confidence scoring:
    - 1.0 = Always succeeds
    - 0.5 = Unknown or 50/50
    - 0.0 = Always fails

    Uses hierarchical matching:
    1. Exact match (domain + action + target)
    2. Domain pattern match (domain + action type)
    3. Global pattern match (action type only)
    """

    # Selector normalization patterns
    RE_CLASS_ID = re.compile(r'[#.][\w-]+')
    RE_NTH_CHILD = re.compile(r':nth-child\(\d+\)')
    RE_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')
    RE_ELEMENT_TYPE = re.compile(r'^(\w+)')

    def __init__(self, persistent_memory=None):
        """
        Initialize tracker.

        Args:
            persistent_memory: Optional PersistentMemory for long-term storage
        """
        self.memory = persistent_memory

        # In-memory stats (fast access)
        # Key: (domain, action_type, normalized_target)
        self._stats: Dict[Tuple[str, str, str], ActionStats] = defaultdict(ActionStats)

        # Domain-level stats (action_type success on domain)
        # Key: (domain, action_type)
        self._domain_stats: Dict[Tuple[str, str], ActionStats] = defaultdict(ActionStats)

        # Global stats (action_type success anywhere)
        # Key: action_type
        self._global_stats: Dict[str, ActionStats] = defaultdict(ActionStats)

        # Selector patterns that worked well
        # Key: domain -> List of (selector_pattern, success_rate)
        self._good_selectors: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

        # Load from persistent memory if available
        if self.memory:
            self._load_from_memory()

    def _normalize_selector(self, selector: str) -> str:
        """
        Normalize selector for pattern matching.

        Removes specific text content, IDs, and nth-child indices
        to find patterns that generalize.

        Examples:
            "button:has-text('Download Now')" -> "button:has-text(*)"
            "#btn-123" -> "#*"
            "a.download:nth-child(3)" -> "a.download:nth-child(*)"
        """
        if not selector:
            return ""

        # Normalize quoted text
        normalized = self.RE_QUOTED.sub("'*'", selector)

        # Normalize nth-child
        normalized = self.RE_NTH_CHILD.sub(":nth-child(*)", normalized)

        return normalized.lower().strip()

    def _extract_selector_type(self, selector: str) -> str:
        """Extract the base element type from a selector."""
        if not selector:
            return "unknown"

        # Get first word (element type) - uses class-level pre-compiled pattern
        match = self.RE_ELEMENT_TYPE.match(selector)
        if match:
            return match.group(1).lower()

        # Check for class/id selectors
        if selector.startswith('.'):
            return "class"
        if selector.startswith('#'):
            return "id"

        return "unknown"

    def record(
        self,
        action_type: str,
        target: str,
        success: bool,
        domain: str = "",
        context: str = "",
        error: str = ""
    ) -> None:
        """
        Record an action outcome.

        Args:
            action_type: Type of action (click, type, scroll, navigate, download)
            target: Selector, URL, or text depending on action
            success: Whether the action achieved its goal
            domain: Site domain where action occurred
            context: Additional context
            error: Error message if failed
        """
        normalized_target = self._normalize_selector(target)

        # Update exact stats
        key = (domain, action_type, normalized_target)
        stats = self._stats[key]
        if success:
            stats.record_success()
        else:
            stats.record_failure(error)

        # Update domain stats
        domain_key = (domain, action_type)
        domain_stats = self._domain_stats[domain_key]
        if success:
            domain_stats.record_success()
        else:
            domain_stats.record_failure(error)

        # Update global stats
        global_stats = self._global_stats[action_type]
        if success:
            global_stats.record_success()
        else:
            global_stats.record_failure(error)

        # Track good selectors
        if success and action_type == "click":
            self._update_good_selectors(domain, target)

        # Persist to long-term memory
        if self.memory:
            self._save_to_memory(action_type, target, success, domain, error)

    def _update_good_selectors(self, domain: str, selector: str) -> None:
        """Update the list of selectors that work well on a domain."""
        normalized = self._normalize_selector(selector)
        selector_type = self._extract_selector_type(selector)

        # Get current stats for this selector pattern
        key = (domain, "click", normalized)
        stats = self._stats.get(key)

        if stats and stats.success_rate >= 0.7:
            # Add to good selectors if not already there
            existing = [s for s, _ in self._good_selectors[domain]]
            if normalized not in existing:
                self._good_selectors[domain].append((normalized, stats.success_rate))
                # Keep sorted by success rate
                self._good_selectors[domain].sort(key=lambda x: x[1], reverse=True)
                # Keep top 20
                self._good_selectors[domain] = self._good_selectors[domain][:20]

    def get_confidence(
        self,
        action_type: str,
        target: str,
        domain: str = ""
    ) -> float:
        """
        Get confidence score for an action.

        Returns:
            Float 0.0-1.0 representing expected success rate
        """
        normalized_target = self._normalize_selector(target)

        # Try exact match first
        key = (domain, action_type, normalized_target)
        if key in self._stats:
            stats = self._stats[key]
            if stats.total >= 3:  # Need enough data
                return stats.success_rate

        # Try domain-level stats
        domain_key = (domain, action_type)
        if domain_key in self._domain_stats:
            stats = self._domain_stats[domain_key]
            if stats.total >= 5:
                return stats.success_rate

        # Try global stats
        if action_type in self._global_stats:
            stats = self._global_stats[action_type]
            if stats.total >= 10:
                return stats.success_rate

        # Default confidence by action type
        defaults = {
            "navigate": 0.9,   # Usually works
            "click": 0.7,      # Often works
            "type": 0.8,       # Usually works
            "scroll": 0.9,     # Almost always works
            "download": 0.6,   # Can fail for many reasons
            "back": 0.95,      # Almost always works
            "wait": 0.95,      # Almost always works
        }
        return defaults.get(action_type, 0.5)

    def get_recommendations(
        self,
        domain: str,
        action_type: str = "click",
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Get recommended selectors/targets for a domain.

        Returns:
            List of (selector, confidence) tuples sorted by confidence
        """
        recommendations = []

        # Get all stats for this domain and action type
        for key, stats in self._stats.items():
            d, a, target = key
            if d == domain and a == action_type and stats.total >= 2:
                recommendations.append((target, stats.success_rate))

        # Sort by success rate
        recommendations.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        return recommendations[:limit]

    def get_good_selectors(self, domain: str) -> List[str]:
        """Get list of selectors that have worked well on a domain."""
        return [s for s, _ in self._good_selectors.get(domain, [])]

    def get_action_history(
        self,
        domain: str = "",
        action_type: str = "",
        limit: int = 20
    ) -> List[Dict]:
        """
        Get recent action history with stats.

        Returns list of dicts with action details and success rates.
        """
        results = []

        for key, stats in self._stats.items():
            d, a, target = key

            # Apply filters
            if domain and d != domain:
                continue
            if action_type and a != action_type:
                continue

            results.append({
                "domain": d,
                "action_type": a,
                "target": target,
                "success_count": stats.success_count,
                "failure_count": stats.failure_count,
                "success_rate": stats.success_rate,
                "total": stats.total,
            })

        # Sort by total attempts (most used first)
        results.sort(key=lambda x: x["total"], reverse=True)

        return results[:limit]

    def get_domain_summary(self, domain: str) -> Dict:
        """
        Get summary of action success rates for a domain.

        Returns:
            Dict with action type -> success rate mapping
        """
        summary = {}

        for (d, action_type), stats in self._domain_stats.items():
            if d == domain:
                summary[action_type] = {
                    "success_rate": stats.success_rate,
                    "total_actions": stats.total,
                    "successes": stats.success_count,
                    "failures": stats.failure_count,
                }

        return summary

    def should_avoid(self, action_type: str, target: str, domain: str = "") -> bool:
        """
        Check if an action should be avoided based on history.

        Returns True if:
        - Action has failed 3+ times with 0% success rate
        - Action has >80% failure rate with 5+ attempts
        """
        normalized_target = self._normalize_selector(target)
        key = (domain, action_type, normalized_target)

        if key in self._stats:
            stats = self._stats[key]
            # Strong signal to avoid
            if stats.total >= 3 and stats.success_rate == 0:
                return True
            if stats.total >= 5 and stats.success_rate < 0.2:
                return True

        return False

    def get_alternative_actions(
        self,
        action_type: str,
        failed_target: str,
        domain: str
    ) -> List[str]:
        """
        Suggest alternative targets after a failure.

        Returns list of alternative selectors to try.
        """
        alternatives = []
        failed_normalized = self._normalize_selector(failed_target)

        # Find similar actions that succeeded on this domain
        for key, stats in self._stats.items():
            d, a, target = key
            if d == domain and a == action_type and target != failed_normalized:
                if stats.success_rate >= 0.5 and stats.total >= 2:
                    alternatives.append((target, stats.success_rate))

        # Sort by success rate
        alternatives.sort(key=lambda x: x[1], reverse=True)

        return [target for target, _ in alternatives[:5]]

    def _load_from_memory(self) -> None:
        """Load action stats from persistent memory."""
        if not self.memory:
            return

        try:
            # Load from site_patterns table (repurpose for action tracking)
            patterns = self.memory.get_best_patterns("__action_tracker__", "stats", limit=1000)
            for pattern_json in patterns:
                try:
                    data = json.loads(pattern_json)
                    key = (data["domain"], data["action_type"], data["target"])
                    stats = ActionStats(
                        success_count=data.get("success_count", 0),
                        failure_count=data.get("failure_count", 0),
                    )
                    self._stats[key] = stats
                except (json.JSONDecodeError, KeyError):
                    continue
        except Exception:
            pass  # Memory not initialized yet

    def _save_to_memory(
        self,
        action_type: str,
        target: str,
        success: bool,
        domain: str,
        error: str = ""
    ) -> None:
        """Save action outcome to persistent memory."""
        if not self.memory:
            return

        # Record pattern for future retrieval
        normalized_target = self._normalize_selector(target)
        pattern_data = json.dumps({
            "domain": domain,
            "action_type": action_type,
            "target": normalized_target,
            "success_count": self._stats[(domain, action_type, normalized_target)].success_count,
            "failure_count": self._stats[(domain, action_type, normalized_target)].failure_count,
        })

        self.memory.record_pattern(
            domain="__action_tracker__",
            pattern_type="stats",
            pattern_data=pattern_data,
            success=success
        )

    def get_stats_summary(self) -> Dict:
        """Get overall tracking statistics."""
        total_actions = sum(s.total for s in self._stats.values())
        total_successes = sum(s.success_count for s in self._stats.values())

        # Get most problematic actions
        problem_actions = []
        for key, stats in self._stats.items():
            if stats.total >= 5 and stats.success_rate < 0.3:
                d, a, t = key
                problem_actions.append({
                    "domain": d,
                    "action": a,
                    "target": t,
                    "success_rate": stats.success_rate,
                    "failures": stats.failure_count,
                })

        problem_actions.sort(key=lambda x: x["success_rate"])

        return {
            "total_tracked_actions": total_actions,
            "total_successes": total_successes,
            "overall_success_rate": total_successes / total_actions if total_actions > 0 else 0,
            "unique_action_patterns": len(self._stats),
            "domains_tracked": len(set(k[0] for k in self._stats.keys())),
            "problem_actions": problem_actions[:10],
        }


# Convenience function for simple tracking
_global_tracker: Optional[ActionTracker] = None

def get_tracker(memory=None) -> ActionTracker:
    """Get or create the global action tracker."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ActionTracker(memory)
    return _global_tracker
