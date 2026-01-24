"""
Rate Limit Handling System (v2.7.0)

Provides intelligent rate limit management:
- Per-domain rate tracking
- Automatic backoff on rate limits
- Request throttling to prevent hits
- Rate limit detection and response
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import time
import re


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting behavior."""
    default_requests_per_minute: float = 30.0
    min_request_interval: float = 0.5       # Minimum seconds between requests
    backoff_multiplier: float = 2.0         # Multiplier after rate limit hit
    max_backoff: float = 300.0              # Maximum backoff (5 minutes)
    recovery_time: float = 60.0             # Time before reducing backoff


@dataclass
class DomainState:
    """Rate limit state for a domain."""
    requests: List[datetime] = field(default_factory=list)
    rate_limit_hits: int = 0
    last_rate_limit: Optional[datetime] = None
    current_backoff: float = 0.0
    custom_limit: Optional[float] = None    # Custom requests/minute if detected


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

    def record_success(self, domain: str):
        """Record a successful request (reduce backoff over time)."""
        state = self.domains[domain]
        now = datetime.now()

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
        # Look for "Retry-After: X" style
        match = re.search(r'retry[- ]after[:\s]+(\d+)', response, re.I)
        if match:
            return float(match.group(1))

        # Look for "wait X seconds" style
        match = re.search(r'wait\s+(\d+)\s*(?:seconds?|secs?|s\b)', response, re.I)
        if match:
            return float(match.group(1))

        # Look for "X minutes" style
        match = re.search(r'(\d+)\s*(?:minutes?|mins?|m\b)', response, re.I)
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
