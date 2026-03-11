"""
Context-Aware Navigation System (v2.1.0)

Tracks navigation history, remembers where good content was found,
and provides intelligent back-navigation with breadcrumb support.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
import hashlib
import re
from urllib.parse import urlparse, urljoin


class PageValue(Enum):
    """Classification of page value for navigation decisions."""
    EXCELLENT = "excellent"      # Found exactly what we needed
    GOOD = "good"                # Useful content, worth revisiting
    NEUTRAL = "neutral"          # Neither helpful nor harmful
    LOW = "low"                  # Not useful, avoid in future
    DEAD_END = "dead_end"        # No useful links, backtrack


@dataclass
class Breadcrumb:
    """A single navigation breadcrumb."""
    url: str
    title: str
    timestamp: datetime
    value: PageValue
    content_summary: str
    links_found: int
    depth: int
    from_action: str  # What action led here


@dataclass
class NavigationPath:
    """Represents a navigation path through sites."""
    breadcrumbs: List[Breadcrumb] = field(default_factory=list)
    successful_endpoints: List[str] = field(default_factory=list)
    dead_ends: Set[str] = field(default_factory=set)

    def add_breadcrumb(self, crumb: Breadcrumb):
        """Add a breadcrumb to the path."""
        self.breadcrumbs.append(crumb)
        if crumb.value == PageValue.DEAD_END:
            self.dead_ends.add(crumb.url)
        elif crumb.value in (PageValue.EXCELLENT, PageValue.GOOD):
            self.successful_endpoints.append(crumb.url)

    @property
    def current_depth(self) -> int:
        """Get current navigation depth."""
        return len(self.breadcrumbs)

    @property
    def current_url(self) -> Optional[str]:
        """Get current URL."""
        return self.breadcrumbs[-1].url if self.breadcrumbs else None

    def get_backtrack_options(self, steps: int = 3) -> List[Breadcrumb]:
        """Get options for backtracking."""
        if len(self.breadcrumbs) < 2:
            return []
        # Get last N breadcrumbs that aren't dead ends
        options = []
        for crumb in reversed(self.breadcrumbs[:-1]):
            if crumb.url not in self.dead_ends:
                options.append(crumb)
                if len(options) >= steps:
                    break
        return options


@dataclass
class DomainKnowledge:
    """Accumulated knowledge about a specific domain."""
    domain: str
    visits: int = 0
    successes: int = 0
    failures: int = 0
    successful_paths: List[List[str]] = field(default_factory=list)
    content_locations: Dict[str, List[str]] = field(default_factory=dict)  # content_type -> urls
    navigation_patterns: Dict[str, str] = field(default_factory=dict)  # pattern -> description
    best_entry_points: List[str] = field(default_factory=list)
    pages_to_avoid: Set[str] = field(default_factory=set)
    last_visit: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this domain."""
        if self.visits == 0:
            return 0.5  # Default for no data
        return self.successes / self.visits

    def record_content_location(self, content_type: str, url: str):
        """Record where specific content types are found."""
        if content_type not in self.content_locations:
            self.content_locations[content_type] = []
        if url not in self.content_locations[content_type]:
            self.content_locations[content_type].append(url)

    def get_content_locations(self, content_type: str) -> List[str]:
        """Get known locations for specific content type."""
        return self.content_locations.get(content_type, [])


class NavigationContext:
    """
    Context-aware navigation system that remembers where good content
    was found and provides intelligent navigation suggestions.
    """

    def __init__(self, persistent_memory=None):
        self.persistent_memory = persistent_memory
        self.current_path = NavigationPath()
        self.domain_knowledge: Dict[str, DomainKnowledge] = {}
        self.content_type_patterns = self._init_content_patterns()
        self.valuable_selectors: Dict[str, Set[str]] = {}  # domain -> selectors that led to good content

    def _init_content_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Initialize patterns for detecting content types."""
        return {
            "documentation": [
                re.compile(r'\b(docs?|documentation|guide|tutorial|reference)\b', re.I),
                re.compile(r'\b(api|manual|handbook)\b', re.I),
            ],
            "download": [
                re.compile(r'\b(download|release|binary|installer)\b', re.I),
                re.compile(r'\.(exe|zip|tar|dmg|pkg|deb|rpm|msi)$', re.I),
            ],
            "pricing": [
                re.compile(r'\b(pricing|plans?|subscription|cost)\b', re.I),
                re.compile(r'\$\d+|\d+\s*(?:USD|EUR|GBP)', re.I),
            ],
            "contact": [
                re.compile(r'\b(contact|support|help|email)\b', re.I),
                re.compile(r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I),
            ],
            "login": [
                re.compile(r'\b(login|sign\s*in|log\s*in|authenticate)\b', re.I),
            ],
            "search_results": [
                re.compile(r'\b(results?|found|showing)\s+\d+', re.I),
                re.compile(r'search.*results?', re.I),
            ],
            "article": [
                re.compile(r'\b(article|blog|post|news|story)\b', re.I),
                re.compile(r'published|author|written\s+by', re.I),
            ],
            "product": [
                re.compile(r'\b(product|item|buy|cart|add\s+to\s+cart)\b', re.I),
                re.compile(r'\$[\d,.]+', re.I),
            ],
        }

    def detect_content_type(self, url: str, title: str, content: str) -> List[str]:
        """Detect what types of content are on the page."""
        detected = []
        combined_text = f"{url} {title} {content[:2000]}"

        for content_type, patterns in self.content_type_patterns.items():
            for pattern in patterns:
                if pattern.search(combined_text):
                    detected.append(content_type)
                    break

        return detected if detected else ["general"]

    def record_navigation(
        self,
        url: str,
        title: str,
        content_preview: str,
        links_found: int,
        from_action: str,
        value: PageValue = PageValue.NEUTRAL
    ) -> Breadcrumb:
        """Record a navigation step."""
        domain = urlparse(url).netloc

        # Create breadcrumb
        crumb = Breadcrumb(
            url=url,
            title=title,
            timestamp=datetime.now(),
            value=value,
            content_summary=content_preview[:500],
            links_found=links_found,
            depth=self.current_path.current_depth + 1,
            from_action=from_action
        )

        self.current_path.add_breadcrumb(crumb)

        # Update domain knowledge
        if domain not in self.domain_knowledge:
            self.domain_knowledge[domain] = DomainKnowledge(domain=domain)

        dk = self.domain_knowledge[domain]
        dk.visits += 1
        dk.last_visit = datetime.now()

        # Record content locations
        content_types = self.detect_content_type(url, title, content_preview)
        for ct in content_types:
            dk.record_content_location(ct, url)

        # Track successful paths
        if value in (PageValue.EXCELLENT, PageValue.GOOD):
            path_urls = [c.url for c in self.current_path.breadcrumbs]
            if path_urls not in dk.successful_paths:
                dk.successful_paths.append(path_urls)
            # Mark as good entry point if it's near the start
            if crumb.depth <= 2 and url not in dk.best_entry_points:
                dk.best_entry_points.append(url)
        elif value == PageValue.DEAD_END:
            dk.pages_to_avoid.add(url)

        return crumb

    def mark_page_value(self, url: str, value: PageValue):
        """Update the value classification of a page."""
        for crumb in self.current_path.breadcrumbs:
            if crumb.url == url:
                crumb.value = value
                break

        domain = urlparse(url).netloc
        if domain in self.domain_knowledge:
            if value == PageValue.DEAD_END:
                self.domain_knowledge[domain].pages_to_avoid.add(url)
            elif value in (PageValue.EXCELLENT, PageValue.GOOD):
                if url in self.domain_knowledge[domain].pages_to_avoid:
                    self.domain_knowledge[domain].pages_to_avoid.discard(url)

    # =========================================================================
    # API compatibility methods for simpler interface
    # =========================================================================

    @property
    def path(self) -> NavigationPath:
        """Alias for current_path for API compatibility."""
        return self.current_path

    def visit(
        self,
        url: str,
        title: str,
        links_found: int = 0,
        from_action: str = "",
        content_preview: str = "",
        value: PageValue = PageValue.NEUTRAL
    ) -> Breadcrumb:
        """Convenience method for record_navigation."""
        return self.record_navigation(
            url=url,
            title=title,
            content_preview=content_preview,
            links_found=links_found,
            from_action=from_action,
            value=value
        )

    def mark_value(self, value: PageValue) -> None:
        """Mark the current (last visited) page with a value."""
        if self.current_path.breadcrumbs:
            current_url = self.current_path.breadcrumbs[-1].url
            self.mark_page_value(current_url, value)

    def record_valuable_selector(self, domain: str, selector: str):
        """Record a selector that led to valuable content."""
        if domain not in self.valuable_selectors:
            self.valuable_selectors[domain] = set()
        self.valuable_selectors[domain].add(selector)

    def get_navigation_suggestion(
        self,
        current_url: str,
        goal: str,
        available_links: List[Dict]
    ) -> Tuple[str, str, float]:
        """
        Suggest the best navigation action based on context.

        Returns: (action, target, confidence)
        """
        domain = urlparse(current_url).netloc
        dk = self.domain_knowledge.get(domain)

        # Check if we should backtrack
        if self._should_backtrack():
            backtrack_options = self.current_path.get_backtrack_options()
            if backtrack_options:
                best = backtrack_options[0]
                return "navigate", best.url, 0.8

        # Check domain knowledge for known good locations
        if dk:
            goal_lower = goal.lower()
            for content_type in self.content_type_patterns.keys():
                if content_type in goal_lower:
                    known_locations = dk.get_content_locations(content_type)
                    for loc in known_locations:
                        if loc != current_url and loc not in self.current_path.dead_ends:
                            return "navigate", loc, 0.85

        # Score available links
        scored_links = self._score_links(available_links, goal, domain)
        if scored_links:
            best_link = scored_links[0]
            if best_link[1] > 0.5:
                return "click", best_link[0], best_link[1]

        # Default: explore the first promising link
        if available_links:
            return "click", available_links[0].get("text", ""), 0.3

        return "backtrack", "", 0.5

    def _should_backtrack(self) -> bool:
        """Determine if we should backtrack based on navigation history."""
        if self.current_path.current_depth < 3:
            return False

        # Check if recent pages have been low value
        recent = self.current_path.breadcrumbs[-3:]
        low_value_count = sum(
            1 for c in recent
            if c.value in (PageValue.LOW, PageValue.DEAD_END)
        )
        return low_value_count >= 2

    def _score_links(
        self,
        links: List[Dict],
        goal: str,
        domain: str
    ) -> List[Tuple[str, float]]:
        """Score links based on relevance to goal and domain knowledge."""
        scored = []
        goal_words = set(goal.lower().split())
        dk = self.domain_knowledge.get(domain)

        for link in links:
            text = link.get("text", "").lower()
            href = link.get("href", "").lower()
            score = 0.0

            # Word overlap with goal
            link_words = set(text.split())
            overlap = len(goal_words & link_words)
            score += overlap * 0.2

            # Avoid known dead ends
            if dk and href in dk.pages_to_avoid:
                score -= 0.5

            # Prefer known good selectors
            selector = link.get("selector", "")
            if dk and selector in self.valuable_selectors.get(domain, set()):
                score += 0.3

            # Penalty for already visited
            if href in [c.url for c in self.current_path.breadcrumbs]:
                score -= 0.4

            scored.append((text, min(1.0, max(0.0, score))))

        return sorted(scored, key=lambda x: x[1], reverse=True)

    def get_backtrack_url(self, steps: int = 1) -> Optional[str]:
        """Get URL to backtrack to."""
        options = self.current_path.get_backtrack_options(steps)
        if options:
            return options[min(steps - 1, len(options) - 1)].url
        return None

    def get_path_summary(self) -> str:
        """Get a summary of the current navigation path."""
        if not self.current_path.breadcrumbs:
            return "No navigation history"

        lines = ["Navigation Path:"]
        for i, crumb in enumerate(self.current_path.breadcrumbs):
            prefix = "  " * i + "├─" if i < len(self.current_path.breadcrumbs) - 1 else "  " * i + "└─"
            value_icon = {
                PageValue.EXCELLENT: "★",
                PageValue.GOOD: "✓",
                PageValue.NEUTRAL: "○",
                PageValue.LOW: "⊖",
                PageValue.DEAD_END: "✗"
            }.get(crumb.value, "?")
            lines.append(f"{prefix} {value_icon} {crumb.title[:40]} ({crumb.url[:50]})")

        return "\n".join(lines)

    def get_domain_summary(self, domain: str) -> Optional[str]:
        """Get summary of knowledge about a domain."""
        dk = self.domain_knowledge.get(domain)
        if not dk:
            return None

        lines = [f"Domain: {domain}"]
        lines.append(f"  Visits: {dk.visits}")
        lines.append(f"  Successful paths: {len(dk.successful_paths)}")
        lines.append(f"  Entry points: {len(dk.best_entry_points)}")
        lines.append(f"  Pages to avoid: {len(dk.pages_to_avoid)}")

        if dk.content_locations:
            lines.append("  Content locations:")
            for ct, urls in dk.content_locations.items():
                lines.append(f"    {ct}: {len(urls)} known locations")

        return "\n".join(lines)

    def reset_session(self):
        """Reset current session path (keeps domain knowledge)."""
        self.current_path = NavigationPath()

    def export_knowledge(self) -> Dict:
        """Export accumulated navigation knowledge."""
        return {
            "domains": {
                domain: {
                    "visits": dk.visits,
                    "successful_paths": dk.successful_paths,
                    "content_locations": dk.content_locations,
                    "best_entry_points": dk.best_entry_points,
                    "pages_to_avoid": list(dk.pages_to_avoid),
                }
                for domain, dk in self.domain_knowledge.items()
            },
            "valuable_selectors": {
                domain: list(selectors)
                for domain, selectors in self.valuable_selectors.items()
            }
        }

    def import_knowledge(self, data: Dict):
        """Import previously exported navigation knowledge."""
        for domain, info in data.get("domains", {}).items():
            dk = DomainKnowledge(domain=domain)
            dk.visits = info.get("visits", 0)
            dk.successful_paths = info.get("successful_paths", [])
            dk.content_locations = info.get("content_locations", {})
            dk.best_entry_points = info.get("best_entry_points", [])
            dk.pages_to_avoid = set(info.get("pages_to_avoid", []))
            self.domain_knowledge[domain] = dk

        for domain, selectors in data.get("valuable_selectors", {}).items():
            self.valuable_selectors[domain] = set(selectors)


# Global instance
_nav_context: Optional[NavigationContext] = None


def get_nav_context(persistent_memory=None) -> NavigationContext:
    """Get the global navigation context instance."""
    global _nav_context
    if _nav_context is None:
        _nav_context = NavigationContext(persistent_memory)
    return _nav_context


def reset_nav_context():
    """Reset the global navigation context."""
    global _nav_context
    _nav_context = None
