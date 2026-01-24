"""
Timeout Management System (v2.6.0)

Provides adaptive timeout management:
- Per-domain and per-action timeout learning
- Adaptive timeouts based on historical data
- Graceful timeout handling with fallbacks
- Timeout budget tracking
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""
    default_timeout: float = 30.0       # Default timeout in seconds
    min_timeout: float = 5.0            # Minimum timeout
    max_timeout: float = 120.0          # Maximum timeout
    adaptive: bool = True               # Enable adaptive timeouts
    buffer_factor: float = 1.5          # Multiplier for predicted time
    sample_size: int = 10               # Number of samples for prediction


@dataclass
class ActionTiming:
    """Timing data for an action."""
    duration: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TimeoutStats:
    """Statistics about timeouts for a domain/action."""
    total_attempts: int = 0
    timeouts: int = 0
    avg_duration: float = 0.0
    max_duration: float = 0.0
    predicted_timeout: float = 30.0


class TimeoutManager:
    """Manages adaptive timeouts for operations."""

    def __init__(self, config: Optional[TimeoutConfig] = None):
        self.config = config or TimeoutConfig()

        # Track timings per domain and action type
        # domain -> action -> list of timings
        self.timings: Dict[str, Dict[str, List[ActionTiming]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Per-action default timeouts
        self.action_defaults: Dict[str, float] = {
            "navigate": 30.0,
            "click": 10.0,
            "type": 5.0,
            "scroll": 3.0,
            "download": 120.0,
            "wait": 60.0,
        }

        # Track active operations for timeout tracking
        self._active: Dict[str, datetime] = {}

    def get_timeout(self, action: str, domain: str = "") -> float:
        """Get the recommended timeout for an action."""
        if not self.config.adaptive:
            return self._get_default(action)

        # Check if we have historical data
        if domain and domain in self.timings:
            action_timings = self.timings[domain].get(action, [])
            if len(action_timings) >= 3:
                return self._predict_timeout(action_timings)

        # Fall back to action default
        return self._get_default(action)

    def _get_default(self, action: str) -> float:
        """Get default timeout for an action."""
        return self.action_defaults.get(action, self.config.default_timeout)

    def _predict_timeout(self, timings: List[ActionTiming]) -> float:
        """Predict timeout based on historical data."""
        # Get recent successful timings
        recent = timings[-self.config.sample_size:]
        successful = [t.duration for t in recent if t.success]

        if not successful:
            # All recent attempts failed, increase timeout
            return min(
                self.config.max_timeout,
                self.config.default_timeout * 2
            )

        # Use 95th percentile with buffer
        if len(successful) >= 3:
            sorted_durations = sorted(successful)
            idx = int(len(sorted_durations) * 0.95)
            p95 = sorted_durations[min(idx, len(sorted_durations) - 1)]
        else:
            p95 = max(successful)

        predicted = p95 * self.config.buffer_factor

        # Clamp to min/max
        return max(
            self.config.min_timeout,
            min(self.config.max_timeout, predicted)
        )

    def start_timing(self, action: str, domain: str = "") -> str:
        """Start timing an operation. Returns timing key."""
        key = f"{domain}:{action}:{datetime.now().isoformat()}"
        self._active[key] = datetime.now()
        return key

    def end_timing(
        self,
        timing_key: str,
        success: bool,
        action: str,
        domain: str = ""
    ) -> float:
        """End timing and record the result. Returns duration."""
        if timing_key not in self._active:
            return 0.0

        start_time = self._active.pop(timing_key)
        duration = (datetime.now() - start_time).total_seconds()

        # Record timing
        self.timings[domain][action].append(ActionTiming(
            duration=duration,
            success=success
        ))

        # Trim old data
        max_samples = self.config.sample_size * 2
        if len(self.timings[domain][action]) > max_samples:
            self.timings[domain][action] = self.timings[domain][action][-max_samples:]

        return duration

    def record_timeout(self, action: str, domain: str = ""):
        """Record that an operation timed out."""
        # Record as a failed timing at max timeout
        self.timings[domain][action].append(ActionTiming(
            duration=self.config.max_timeout,
            success=False
        ))

    def get_stats(self, domain: str = "", action: str = "") -> TimeoutStats:
        """Get timeout statistics."""
        if domain and action:
            timings = self.timings.get(domain, {}).get(action, [])
        elif domain:
            # Aggregate all actions for domain
            timings = []
            for action_timings in self.timings.get(domain, {}).values():
                timings.extend(action_timings)
        elif action:
            # Aggregate action across domains
            timings = []
            for domain_timings in self.timings.values():
                timings.extend(domain_timings.get(action, []))
        else:
            # All timings
            timings = []
            for domain_timings in self.timings.values():
                for action_timings in domain_timings.values():
                    timings.extend(action_timings)

        if not timings:
            return TimeoutStats()

        durations = [t.duration for t in timings]
        timeout_count = sum(1 for t in timings if not t.success)

        return TimeoutStats(
            total_attempts=len(timings),
            timeouts=timeout_count,
            avg_duration=statistics.mean(durations) if durations else 0,
            max_duration=max(durations) if durations else 0,
            predicted_timeout=self._predict_timeout(timings) if len(timings) >= 3 else self.config.default_timeout
        )

    def suggest_timeout_adjustment(self, domain: str, action: str) -> Tuple[float, str]:
        """Suggest timeout adjustment based on recent performance."""
        stats = self.get_stats(domain, action)

        if stats.total_attempts < 3:
            return (self._get_default(action), "Not enough data")

        timeout_rate = stats.timeouts / stats.total_attempts

        if timeout_rate > 0.5:
            # More than half timing out - increase timeout
            new_timeout = min(
                self.config.max_timeout,
                stats.predicted_timeout * 1.5
            )
            return (new_timeout, f"High timeout rate ({timeout_rate:.0%}), increasing timeout")

        elif timeout_rate < 0.1 and stats.predicted_timeout > self.config.min_timeout * 2:
            # Very few timeouts and currently generous - can reduce
            new_timeout = max(
                self.config.min_timeout,
                stats.predicted_timeout * 0.8
            )
            return (new_timeout, f"Low timeout rate ({timeout_rate:.0%}), can reduce timeout")

        return (stats.predicted_timeout, "Timeout is appropriate")

    def export_data(self) -> Dict:
        """Export timing data for persistence."""
        return {
            domain: {
                action: [
                    {
                        "duration": t.duration,
                        "success": t.success,
                        "timestamp": t.timestamp.isoformat()
                    }
                    for t in timings
                ]
                for action, timings in actions.items()
            }
            for domain, actions in self.timings.items()
        }

    def import_data(self, data: Dict):
        """Import previously saved timing data."""
        for domain, actions in data.items():
            for action, timings in actions.items():
                for t in timings:
                    self.timings[domain][action].append(ActionTiming(
                        duration=t["duration"],
                        success=t["success"],
                        timestamp=datetime.fromisoformat(t["timestamp"])
                    ))


# Global timeout manager instance
_timeout_manager: Optional[TimeoutManager] = None


def get_timeout_manager() -> TimeoutManager:
    """Get the global timeout manager instance."""
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = TimeoutManager()
    return _timeout_manager


def reset_timeout_manager():
    """Reset the global timeout manager."""
    global _timeout_manager
    _timeout_manager = None
