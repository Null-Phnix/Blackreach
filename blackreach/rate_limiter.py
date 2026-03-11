"""
Rate Limit Handling System (v3.0.0)

Provides intelligent rate limit management:
- Per-domain rate tracking
- Automatic backoff on rate limits
- Request throttling to prevent hits
- Rate limit detection and response
- Adaptive throttling based on server responses
- Response time monitoring for proactive adjustment
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
import time
import re
import statistics


class ServerResponseType(Enum):
    """Classification of server responses for adaptive throttling."""
    SUCCESS = "success"
    SLOW = "slow"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    BLOCKED = "blocked"


@dataclass
class ResponseMetrics:
    """Metrics for a single response."""
    timestamp: datetime
    response_time: float  # seconds
    status_code: Optional[int] = None
    response_type: ServerResponseType = ServerResponseType.SUCCESS


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting behavior."""
    default_requests_per_minute: float = 30.0
    min_request_interval: float = 0.5       # Minimum seconds between requests
    backoff_multiplier: float = 2.0         # Multiplier after rate limit hit
    max_backoff: float = 300.0              # Maximum backoff (5 minutes)
    recovery_time: float = 60.0             # Time before reducing backoff

    # Adaptive throttling settings
    adaptive_throttling: bool = True        # Enable adaptive throttling
    slow_response_threshold: float = 3.0    # Seconds - responses slower than this trigger throttling
    target_response_time: float = 1.0       # Ideal response time to aim for
    throttle_increase_factor: float = 1.5   # Slow down factor when responses are slow
    throttle_decrease_factor: float = 0.9   # Speed up factor when responses are fast
    min_interval_adaptive: float = 0.2      # Minimum interval for adaptive throttling
    max_interval_adaptive: float = 10.0     # Maximum interval for adaptive throttling
    response_window: int = 10               # Number of recent responses to consider


@dataclass
class DomainState:
    """Rate limit state for a domain."""
    requests: List[datetime] = field(default_factory=list)
    rate_limit_hits: int = 0
    last_rate_limit: Optional[datetime] = None
    current_backoff: float = 0.0
    custom_limit: Optional[float] = None    # Custom requests/minute if detected

    # Adaptive throttling state
    response_metrics: List[ResponseMetrics] = field(default_factory=list)
    adaptive_interval: Optional[float] = None  # Current adaptive interval
    consecutive_successes: int = 0
    consecutive_slow: int = 0


# Common rate limit response patterns
RATE_LIMIT_PATTERNS = [
    re.compile(r'rate\s*limit', re.I),
    re.compile(r'too\s*many\s*requests', re.I),
    re.compile(r'429', re.I),
    re.compile(r'slow\s*down', re.I),
    re.compile(r'throttl', re.I),
    re.compile(r'request\s*quota', re.I),
    re.compile(r'retry\s*after', re.I),
]

# P0-PERF: Pre-compiled patterns for wait time extraction
_RE_RETRY_AFTER = re.compile(r'retry[- ]after[:\s]+(\d+)', re.I)
_RE_WAIT_SECONDS = re.compile(r'wait\s+(\d+)\s*(?:seconds?|secs?|s\b)', re.I)
_RE_WAIT_MINUTES = re.compile(r'(\d+)\s*(?:minutes?|mins?|m\b)', re.I)


class RateLimiter:
    """Manages rate limiting across domains."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.domains: Dict[str, DomainState] = defaultdict(DomainState)

        # Known rate limits for specific domains
        self.known_limits: Dict[str, float] = {
            "arxiv.org": 15.0,           # arXiv is strict
            "scholar.google.com": 10.0,   # Google Scholar very strict
            "google.com": 20.0,
            "github.com": 60.0,
            "api.github.com": 30.0,
        }

    def can_request(self, domain: str) -> Tuple[bool, float]:
        """
        Check if we can make a request to this domain.

        Returns: (can_request, wait_time_if_not)
        """
        state = self.domains[domain]
        now = datetime.now()

        # Check if in backoff period
        if state.last_rate_limit:
            elapsed = (now - state.last_rate_limit).total_seconds()
            if elapsed < state.current_backoff:
                wait_time = state.current_backoff - elapsed
                return (False, wait_time)

        # Get rate limit for domain
        rate_limit = self._get_rate_limit(domain)
        interval = 60.0 / rate_limit  # Seconds between requests

        # Clean old requests (keep last minute)
        cutoff = now - timedelta(minutes=1)
        state.requests = [r for r in state.requests if r > cutoff]

        # Check if we've hit the limit
        if len(state.requests) >= rate_limit:
            # Calculate wait time until oldest request expires
            oldest = min(state.requests)
            wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()
            return (False, max(0, wait_time))

        # Check minimum interval
        if state.requests:
            last_request = max(state.requests)
            elapsed = (now - last_request).total_seconds()
            if elapsed < self.config.min_request_interval:
                wait_time = self.config.min_request_interval - elapsed
                return (False, wait_time)

        return (True, 0)

    def record_request(self, domain: str):
        """Record that a request was made."""
        self.domains[domain].requests.append(datetime.now())

    def record_rate_limit(self, domain: str, response: str = ""):
        """Record that we hit a rate limit."""
        state = self.domains[domain]
        state.rate_limit_hits += 1
        state.last_rate_limit = datetime.now()

        # Increase backoff exponentially
        if state.current_backoff < self.config.min_request_interval:
            state.current_backoff = self.config.min_request_interval
        else:
            state.current_backoff = min(
                state.current_backoff * self.config.backoff_multiplier,
                self.config.max_backoff
            )

        # Try to detect specific wait time from response
        wait_time = self._extract_wait_time(response)
        if wait_time:
            state.current_backoff = max(state.current_backoff, wait_time)

    def record_success(self, domain: str, response_time: float = 0.0, status_code: Optional[int] = None):
        """Record a successful request (reduce backoff over time).

        Args:
            domain: The domain the request was made to
            response_time: How long the request took in seconds
            status_code: HTTP status code of the response
        """
        state = self.domains[domain]
        now = datetime.now()

        # Record response metrics for adaptive throttling
        if self.config.adaptive_throttling:
            response_type = self._classify_response(response_time, status_code)
            metrics = ResponseMetrics(
                timestamp=now,
                response_time=response_time,
                status_code=status_code,
                response_type=response_type
            )
            state.response_metrics.append(metrics)

            # Keep only recent metrics
            cutoff = now - timedelta(minutes=5)
            state.response_metrics = [m for m in state.response_metrics if m.timestamp > cutoff]

            # Update adaptive interval based on response
            self._update_adaptive_interval(domain, response_type, response_time)

        # If we've had success for a while, reduce backoff
        if state.last_rate_limit:
            elapsed = (now - state.last_rate_limit).total_seconds()
            if elapsed > self.config.recovery_time:
                state.current_backoff = max(
                    0,
                    state.current_backoff / self.config.backoff_multiplier
                )

    def is_rate_limit_error(self, error: str) -> bool:
        """Check if an error indicates rate limiting."""
        for pattern in RATE_LIMIT_PATTERNS:
            if pattern.search(error):
                return True
        return False

    def _get_rate_limit(self, domain: str) -> float:
        """Get the rate limit for a domain."""
        # Check for known limits
        for known_domain, limit in self.known_limits.items():
            if known_domain in domain:
                return limit

        # Check for custom detected limit
        state = self.domains[domain]
        if state.custom_limit:
            return state.custom_limit

        return self.config.default_requests_per_minute

    def _extract_wait_time(self, response: str) -> Optional[float]:
        """Try to extract wait time from a rate limit response."""
        # Look for "Retry-After: X" style (uses pre-compiled pattern)
        match = _RE_RETRY_AFTER.search(response)
        if match:
            return float(match.group(1))

        # Look for "wait X seconds" style (uses pre-compiled pattern)
        match = _RE_WAIT_SECONDS.search(response)
        if match:
            return float(match.group(1))

        # Look for "X minutes" style (uses pre-compiled pattern)
        match = _RE_WAIT_MINUTES.search(response)
        if match:
            return float(match.group(1)) * 60

        return None

    def wait_if_needed(self, domain: str) -> float:
        """Wait if rate limited. Returns actual wait time."""
        can_request, wait_time = self.can_request(domain)
        if not can_request and wait_time > 0:
            time.sleep(wait_time)
            return wait_time
        return 0

    def get_stats(self, domain: str = "") -> Dict:
        """Get rate limit statistics."""
        if domain:
            state = self.domains[domain]
            return {
                "domain": domain,
                "requests_last_minute": len(state.requests),
                "rate_limit_hits": state.rate_limit_hits,
                "current_backoff": state.current_backoff,
                "rate_limit": self._get_rate_limit(domain)
            }

        # Aggregate stats
        total_requests = sum(len(s.requests) for s in self.domains.values())
        total_hits = sum(s.rate_limit_hits for s in self.domains.values())

        return {
            "domains_tracked": len(self.domains),
            "total_requests_last_minute": total_requests,
            "total_rate_limit_hits": total_hits,
            "domains_in_backoff": sum(
                1 for s in self.domains.values()
                if s.current_backoff > 0 and s.last_rate_limit and
                (datetime.now() - s.last_rate_limit).total_seconds() < s.current_backoff
            )
        }

    def set_domain_limit(self, domain: str, requests_per_minute: float):
        """Set a custom rate limit for a domain."""
        self.domains[domain].custom_limit = requests_per_minute

    def reset_domain(self, domain: str):
        """Reset rate limit state for a domain."""
        if domain in self.domains:
            del self.domains[domain]

    def _classify_response(self, response_time: float, status_code: Optional[int]) -> ServerResponseType:
        """Classify a response for adaptive throttling."""
        if status_code:
            if status_code == 429:
                return ServerResponseType.RATE_LIMITED
            elif status_code == 403 or status_code == 503:
                return ServerResponseType.BLOCKED
            elif status_code >= 500:
                return ServerResponseType.ERROR
            elif status_code >= 400:
                return ServerResponseType.ERROR

        if response_time > self.config.slow_response_threshold:
            return ServerResponseType.SLOW

        return ServerResponseType.SUCCESS

    def _update_adaptive_interval(self, domain: str, response_type: ServerResponseType, response_time: float):
        """Update the adaptive interval based on server response."""
        if not self.config.adaptive_throttling:
            return

        state = self.domains[domain]

        # Initialize adaptive interval if needed
        if state.adaptive_interval is None:
            state.adaptive_interval = self.config.min_request_interval

        if response_type == ServerResponseType.SUCCESS:
            state.consecutive_successes += 1
            state.consecutive_slow = 0

            # Speed up if we have consistent fast responses
            if state.consecutive_successes >= 3:
                if response_time < self.config.target_response_time:
                    state.adaptive_interval = max(
                        self.config.min_interval_adaptive,
                        state.adaptive_interval * self.config.throttle_decrease_factor
                    )

        elif response_type == ServerResponseType.SLOW:
            state.consecutive_slow += 1
            state.consecutive_successes = 0

            # Slow down on slow responses
            state.adaptive_interval = min(
                self.config.max_interval_adaptive,
                state.adaptive_interval * self.config.throttle_increase_factor
            )

        elif response_type in (ServerResponseType.RATE_LIMITED, ServerResponseType.BLOCKED):
            state.consecutive_successes = 0
            state.consecutive_slow = 0

            # Significant slowdown on rate limit or block
            state.adaptive_interval = min(
                self.config.max_interval_adaptive,
                state.adaptive_interval * (self.config.throttle_increase_factor ** 2)
            )

        elif response_type == ServerResponseType.ERROR:
            state.consecutive_successes = 0
            # Moderate slowdown on errors
            state.adaptive_interval = min(
                self.config.max_interval_adaptive,
                state.adaptive_interval * self.config.throttle_increase_factor
            )

    def get_adaptive_interval(self, domain: str) -> float:
        """Get the current adaptive interval for a domain.

        Returns the adaptive interval if adaptive throttling is enabled,
        otherwise returns the minimum request interval.
        """
        if not self.config.adaptive_throttling:
            return self.config.min_request_interval

        state = self.domains[domain]
        if state.adaptive_interval is not None:
            return state.adaptive_interval

        return self.config.min_request_interval

    def get_response_stats(self, domain: str) -> Dict:
        """Get response statistics for a domain."""
        state = self.domains[domain]

        if not state.response_metrics:
            return {
                "domain": domain,
                "total_responses": 0,
                "avg_response_time": 0,
                "slow_responses": 0,
                "rate_limited": 0,
                "adaptive_interval": state.adaptive_interval
            }

        response_times = [m.response_time for m in state.response_metrics]
        slow_count = sum(1 for m in state.response_metrics if m.response_type == ServerResponseType.SLOW)
        rate_limited_count = sum(1 for m in state.response_metrics if m.response_type == ServerResponseType.RATE_LIMITED)

        return {
            "domain": domain,
            "total_responses": len(state.response_metrics),
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "median_response_time": statistics.median(response_times) if response_times else 0,
            "slow_responses": slow_count,
            "rate_limited": rate_limited_count,
            "adaptive_interval": state.adaptive_interval,
            "consecutive_successes": state.consecutive_successes,
            "consecutive_slow": state.consecutive_slow
        }

    def should_throttle(self, domain: str) -> Tuple[bool, float]:
        """Check if we should throttle based on recent response patterns.

        Returns:
            Tuple of (should_throttle, recommended_wait_time)
        """
        state = self.domains[domain]

        # Check recent metrics for warning signs
        recent_metrics = state.response_metrics[-self.config.response_window:] if state.response_metrics else []

        if not recent_metrics:
            return (False, 0)

        # Count problematic responses
        slow_count = sum(1 for m in recent_metrics if m.response_type == ServerResponseType.SLOW)
        error_count = sum(1 for m in recent_metrics if m.response_type in (ServerResponseType.ERROR, ServerResponseType.RATE_LIMITED, ServerResponseType.BLOCKED))

        total = len(recent_metrics)

        # If more than 30% slow or any errors, suggest throttling
        if error_count > 0:
            return (True, state.adaptive_interval or self.config.min_request_interval * 2)
        elif slow_count / total > 0.3:
            return (True, state.adaptive_interval or self.config.min_request_interval * 1.5)

        return (False, 0)


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def reset_rate_limiter():
    """Reset the global rate limiter."""
    global _rate_limiter
    _rate_limiter = None
