"""
Blackreach Source Manager - Intelligent multi-source failover.

Manages content sources and provides automatic failover when sources fail:
- Tracks source health in real-time
- Prioritizes sources based on success rate
- Automatic failover to mirrors/alternatives
- Cool-down periods for failed sources

Example usage:
    manager = SourceManager()

    # Get best source for a content type
    source = manager.get_best_source("ebook")

    # Record source outcome
    manager.record_success("annas-archive.li")
    manager.record_failure("libgen.li", "rate_limited")

    # Get failover source
    next_source = manager.get_failover("annas-archive.li", "ebook")
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from collections import defaultdict

from blackreach.knowledge import CONTENT_SOURCES, ContentSource, find_best_sources


class SourceStatus(Enum):
    """Status of a content source."""
    HEALTHY = "healthy"           # Working normally
    DEGRADED = "degraded"         # Partial failures
    RATE_LIMITED = "rate_limited" # Too many requests
    BLOCKED = "blocked"           # IP/access blocked
    DOWN = "down"                 # Not responding
    UNKNOWN = "unknown"           # Not yet tested


@dataclass
class SourceHealth:
    """Health tracking for a single source."""
    status: SourceStatus = SourceStatus.UNKNOWN
    success_count: int = 0
    failure_count: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    last_error: str = ""
    cool_down_until: float = 0.0  # Timestamp when source can be tried again
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Unknown
        return self.success_count / total

    @property
    def is_available(self) -> bool:
        """Check if source can be used (not in cool-down)."""
        if self.status == SourceStatus.DOWN:
            return False
        return time.time() >= self.cool_down_until

    def record_success(self):
        self.success_count += 1
        self.last_success = time.time()
        self.consecutive_failures = 0
        self._update_status()

    def record_failure(self, error: str = ""):
        self.failure_count += 1
        self.last_failure = time.time()
        self.last_error = error
        self.consecutive_failures += 1
        self._update_status()
        self._apply_cooldown()

    def _update_status(self):
        """Update status based on recent performance."""
        if self.consecutive_failures >= 5:
            self.status = SourceStatus.DOWN
        elif self.consecutive_failures >= 3:
            if "rate" in self.last_error.lower():
                self.status = SourceStatus.RATE_LIMITED
            elif "block" in self.last_error.lower() or "403" in self.last_error:
                self.status = SourceStatus.BLOCKED
            else:
                self.status = SourceStatus.DEGRADED
        elif self.success_rate >= 0.7:
            self.status = SourceStatus.HEALTHY
        elif self.success_rate >= 0.3:
            self.status = SourceStatus.DEGRADED
        else:
            self.status = SourceStatus.DOWN

    def _apply_cooldown(self):
        """Apply cool-down period based on failure type."""
        base_cooldown = 30  # seconds

        if self.status == SourceStatus.RATE_LIMITED:
            cooldown = base_cooldown * 4  # 2 minutes for rate limiting
        elif self.status == SourceStatus.BLOCKED:
            cooldown = base_cooldown * 10  # 5 minutes for blocks
        elif self.status == SourceStatus.DOWN:
            cooldown = base_cooldown * 20  # 10 minutes for down
        else:
            cooldown = base_cooldown * self.consecutive_failures

        self.cool_down_until = time.time() + cooldown


class SourceManager:
    """
    Manages content sources with intelligent failover.

    Features:
    - Real-time health tracking
    - Automatic source prioritization
    - Failover to mirrors/alternatives
    - Cool-down periods for failed sources
    """

    def __init__(self):
        # Health tracking per domain
        self._health: Dict[str, SourceHealth] = defaultdict(SourceHealth)

        # Map domains to sources
        self._domain_to_source: Dict[str, ContentSource] = {}
        self._build_domain_map()

        # Track current session's used sources
        self._session_sources: Set[str] = set()

        # Failover history (avoid repeated failovers)
        self._failover_history: List[Tuple[str, str, float]] = []  # (from, to, timestamp)

    def _build_domain_map(self):
        """Build mapping from domain to source."""
        from urllib.parse import urlparse

        for source in CONTENT_SOURCES:
            domain = urlparse(source.url).netloc
            self._domain_to_source[domain] = source

            # Also map mirrors
            for mirror in source.mirrors:
                mirror_domain = urlparse(mirror).netloc
                self._domain_to_source[mirror_domain] = source

    def get_best_source(
        self,
        content_type: str,
        exclude_domains: Optional[Set[str]] = None
    ) -> Optional[ContentSource]:
        """
        Get the best available source for a content type.

        Args:
            content_type: Type of content (ebook, wallpaper, etc.)
            exclude_domains: Domains to exclude (already tried)

        Returns:
            Best available ContentSource or None
        """
        exclude_domains = exclude_domains or set()

        # Get candidate sources
        candidates = find_best_sources(content_type, max_sources=10)

        # Score each candidate
        scored = []
        for source in candidates:
            from urllib.parse import urlparse
            domain = urlparse(source.url).netloc

            # Skip excluded
            if domain in exclude_domains:
                continue

            # Get health info
            health = self._health[domain]

            # Skip unavailable
            if not health.is_available:
                continue

            # Calculate score
            # Base score from priority
            score = source.priority * 10

            # Adjust by success rate (0-50 points)
            score += health.success_rate * 50

            # Penalty for recent failures
            if health.consecutive_failures > 0:
                score -= health.consecutive_failures * 10

            # Bonus for recent success
            if health.last_success > 0:
                recency = time.time() - health.last_success
                if recency < 300:  # Within 5 minutes
                    score += 20

            # Penalty for rate limiting
            if health.status == SourceStatus.RATE_LIMITED:
                score -= 30
            elif health.status == SourceStatus.DEGRADED:
                score -= 15

            scored.append((source, score))

        if not scored:
            return None

        # Sort by score and return best
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def get_failover(
        self,
        failed_domain: str,
        content_type: str = ""
    ) -> Optional[Tuple[ContentSource, str]]:
        """
        Get a failover source after a failure.

        Args:
            failed_domain: Domain that failed
            content_type: Content type for finding alternatives

        Returns:
            Tuple of (ContentSource, URL) or None
        """
        # First, try mirrors of the same source
        source = self._domain_to_source.get(failed_domain)
        if source and source.mirrors:
            for mirror in source.mirrors:
                from urllib.parse import urlparse
                mirror_domain = urlparse(mirror).netloc

                health = self._health[mirror_domain]
                if health.is_available:
                    self._record_failover(failed_domain, mirror_domain)
                    return (source, mirror)

        # If no mirrors, find alternative source
        exclude = {failed_domain}
        # Also exclude recent failover targets to avoid loops
        for from_domain, to_domain, timestamp in self._failover_history[-5:]:
            if time.time() - timestamp < 300:  # Within 5 minutes
                exclude.add(to_domain)

        alt_source = self.get_best_source(content_type, exclude_domains=exclude)
        if alt_source:
            from urllib.parse import urlparse
            alt_domain = urlparse(alt_source.url).netloc
            self._record_failover(failed_domain, alt_domain)
            return (alt_source, alt_source.url)

        return None

    def _record_failover(self, from_domain: str, to_domain: str):
        """Record a failover event."""
        self._failover_history.append((from_domain, to_domain, time.time()))
        # Keep only recent history
        if len(self._failover_history) > 50:
            self._failover_history = self._failover_history[-50:]

    def record_success(self, domain: str):
        """Record successful interaction with a source."""
        self._health[domain].record_success()
        self._session_sources.add(domain)

    def record_failure(self, domain: str, error: str = ""):
        """Record failed interaction with a source."""
        self._health[domain].record_failure(error)
        self._session_sources.add(domain)

    def get_source_status(self, domain: str) -> SourceHealth:
        """Get health status for a domain."""
        return self._health[domain]

    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all tracked sources."""
        result = {}
        for domain, health in self._health.items():
            result[domain] = {
                "status": health.status.value,
                "success_rate": health.success_rate,
                "success_count": health.success_count,
                "failure_count": health.failure_count,
                "available": health.is_available,
                "last_error": health.last_error,
            }
        return result

    def get_healthy_sources(
        self,
        content_type: str = ""
    ) -> List[ContentSource]:
        """Get list of currently healthy sources."""
        healthy = []

        for source in CONTENT_SOURCES:
            # Filter by content type if specified
            if content_type and content_type not in source.content_types:
                continue

            from urllib.parse import urlparse
            domain = urlparse(source.url).netloc
            health = self._health[domain]

            if health.status in [SourceStatus.HEALTHY, SourceStatus.UNKNOWN]:
                healthy.append(source)

        return healthy

    def reset_source(self, domain: str):
        """Reset health tracking for a source (give it another chance)."""
        self._health[domain] = SourceHealth()

    def reset_all(self):
        """Reset all health tracking."""
        self._health.clear()
        self._session_sources.clear()
        self._failover_history.clear()

    def get_session_summary(self) -> Dict:
        """Get summary of sources used in current session."""
        summary = {
            "sources_used": len(self._session_sources),
            "failovers": len(self._failover_history),
            "by_status": defaultdict(int),
        }

        for domain in self._session_sources:
            health = self._health[domain]
            summary["by_status"][health.status.value] += 1

        summary["by_status"] = dict(summary["by_status"])
        return summary

    def suggest_sources_for_goal(
        self,
        goal: str,
        max_sources: int = 5
    ) -> List[Tuple[ContentSource, str, float]]:
        """
        Suggest sources for a goal, with health-adjusted scores.

        Returns:
            List of (source, url, score) tuples
        """
        # Get base suggestions from knowledge base
        base_sources = find_best_sources(goal, max_sources=max_sources * 2)

        suggestions = []
        for source in base_sources:
            from urllib.parse import urlparse
            domain = urlparse(source.url).netloc
            health = self._health[domain]

            if not health.is_available:
                continue

            # Calculate adjusted score
            base_score = source.priority
            health_modifier = health.success_rate

            # Penalize degraded/rate-limited
            if health.status == SourceStatus.RATE_LIMITED:
                health_modifier *= 0.5
            elif health.status == SourceStatus.DEGRADED:
                health_modifier *= 0.7

            final_score = base_score * (0.5 + 0.5 * health_modifier)

            # Determine best URL (primary or mirror)
            best_url = source.url
            if health.status != SourceStatus.HEALTHY and source.mirrors:
                # Check mirrors
                for mirror in source.mirrors:
                    m_domain = urlparse(mirror).netloc
                    m_health = self._health[m_domain]
                    if m_health.success_rate > health.success_rate:
                        best_url = mirror
                        break

            suggestions.append((source, best_url, final_score))

        # Sort by score
        suggestions.sort(key=lambda x: x[2], reverse=True)

        return suggestions[:max_sources]


# Global instance
_source_manager: Optional[SourceManager] = None


def get_source_manager() -> SourceManager:
    """Get or create the global source manager."""
    global _source_manager
    if _source_manager is None:
        _source_manager = SourceManager()
    return _source_manager
