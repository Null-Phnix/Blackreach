"""
Unit tests for blackreach/nav_context.py

Tests navigation context, breadcrumb tracking, and backtrack functionality.
"""

import pytest
from datetime import datetime
from blackreach.nav_context import (
    PageValue,
    Breadcrumb,
    NavigationPath,
    DomainKnowledge,
    NavigationContext,
)


class TestPageValue:
    """Tests for PageValue enum."""

    def test_all_values_exist(self):
        """All expected page values should exist."""
        assert PageValue.EXCELLENT.value == "excellent"
        assert PageValue.GOOD.value == "good"
        assert PageValue.NEUTRAL.value == "neutral"
        assert PageValue.LOW.value == "low"
        assert PageValue.DEAD_END.value == "dead_end"


class TestBreadcrumb:
    """Tests for Breadcrumb dataclass."""

    def test_breadcrumb_creation(self):
        """Breadcrumb should store all fields correctly."""
        now = datetime.now()
        crumb = Breadcrumb(
            url="https://example.com/page",
            title="Test Page",
            timestamp=now,
            value=PageValue.GOOD,
            content_summary="Test content summary",
            links_found=10,
            depth=2,
            from_action="click"
        )
        assert crumb.url == "https://example.com/page"
        assert crumb.title == "Test Page"
        assert crumb.timestamp == now
        assert crumb.value == PageValue.GOOD
        assert crumb.links_found == 10
        assert crumb.depth == 2
        assert crumb.from_action == "click"


class TestNavigationPath:
    """Tests for NavigationPath dataclass."""

    def test_empty_path(self):
        """Empty path should have sensible defaults."""
        path = NavigationPath()
        assert path.breadcrumbs == []
        assert path.successful_endpoints == []
        assert len(path.dead_ends) == 0
        assert path.current_depth == 0
        assert path.current_url is None

    def test_add_breadcrumb(self):
        """Should add breadcrumb to path."""
        path = NavigationPath()
        crumb = Breadcrumb(
            url="https://example.com",
            title="Home",
            timestamp=datetime.now(),
            value=PageValue.NEUTRAL,
            content_summary="Homepage",
            links_found=50,
            depth=1,
            from_action="navigate"
        )
        path.add_breadcrumb(crumb)

        assert path.current_depth == 1
        assert path.current_url == "https://example.com"
        assert len(path.breadcrumbs) == 1

    def test_add_dead_end(self):
        """Dead end should be tracked."""
        path = NavigationPath()
        crumb = Breadcrumb(
            url="https://example.com/dead",
            title="Dead End",
            timestamp=datetime.now(),
            value=PageValue.DEAD_END,
            content_summary="No links",
            links_found=0,
            depth=2,
            from_action="click"
        )
        path.add_breadcrumb(crumb)

        assert "https://example.com/dead" in path.dead_ends

    def test_add_successful_endpoint(self):
        """Successful endpoints should be tracked."""
        path = NavigationPath()
        crumb = Breadcrumb(
            url="https://example.com/download",
            title="Download Page",
            timestamp=datetime.now(),
            value=PageValue.EXCELLENT,
            content_summary="Found download",
            links_found=5,
            depth=3,
            from_action="click"
        )
        path.add_breadcrumb(crumb)

        assert "https://example.com/download" in path.successful_endpoints

    def test_backtrack_options(self):
        """Should return valid backtrack options."""
        path = NavigationPath()

        # Add some breadcrumbs
        for i, url in enumerate(["page1", "page2", "page3", "page4"]):
            crumb = Breadcrumb(
                url=f"https://example.com/{url}",
                title=f"Page {i+1}",
                timestamp=datetime.now(),
                value=PageValue.NEUTRAL,
                content_summary="",
                links_found=10,
                depth=i+1,
                from_action="click"
            )
            path.add_breadcrumb(crumb)

        options = path.get_backtrack_options(steps=3)

        # Should not include current page
        assert len(options) == 3
        assert all(opt.url != "https://example.com/page4" for opt in options)

    def test_backtrack_excludes_dead_ends(self):
        """Backtrack options should exclude dead ends."""
        path = NavigationPath()

        # Add breadcrumbs including a dead end
        crumb1 = Breadcrumb(
            url="https://example.com/good",
            title="Good Page",
            timestamp=datetime.now(),
            value=PageValue.GOOD,
            content_summary="",
            links_found=10,
            depth=1,
            from_action="navigate"
        )
        crumb2 = Breadcrumb(
            url="https://example.com/dead",
            title="Dead End",
            timestamp=datetime.now(),
            value=PageValue.DEAD_END,
            content_summary="",
            links_found=0,
            depth=2,
            from_action="click"
        )
        crumb3 = Breadcrumb(
            url="https://example.com/current",
            title="Current",
            timestamp=datetime.now(),
            value=PageValue.NEUTRAL,
            content_summary="",
            links_found=5,
            depth=3,
            from_action="click"
        )

        path.add_breadcrumb(crumb1)
        path.add_breadcrumb(crumb2)
        path.add_breadcrumb(crumb3)

        options = path.get_backtrack_options()

        # Should not include dead end or current page
        urls = [opt.url for opt in options]
        assert "https://example.com/dead" not in urls
        assert "https://example.com/current" not in urls
        assert "https://example.com/good" in urls


class TestNavigationContext:
    """Tests for NavigationContext class."""

    def test_init(self):
        """NavigationContext initializes correctly."""
        ctx = NavigationContext()
        assert ctx is not None

    def test_visit_page(self):
        """Should track page visit."""
        ctx = NavigationContext()
        ctx.visit(
            url="https://example.com",
            title="Home",
            links_found=50,
            from_action="navigate"
        )

        assert ctx.path.current_url == "https://example.com"
        assert ctx.path.current_depth == 1

    def test_mark_page_value(self):
        """Should update page value."""
        ctx = NavigationContext()
        ctx.visit(
            url="https://example.com",
            title="Home",
            links_found=50,
            from_action="navigate"
        )
        ctx.mark_value(PageValue.EXCELLENT)

        # Last breadcrumb should have updated value
        assert ctx.path.breadcrumbs[-1].value == PageValue.EXCELLENT


class TestDomainKnowledge:
    """Tests for DomainKnowledge dataclass."""

    def test_domain_knowledge_defaults(self):
        """DomainKnowledge has correct defaults."""
        dk = DomainKnowledge(domain="example.com")
        assert dk.domain == "example.com"
        assert dk.visits == 0
        assert dk.successes == 0
        assert dk.failures == 0

    def test_success_rate_no_visits(self):
        """Success rate should be 0.5 for no visits."""
        dk = DomainKnowledge(domain="example.com")
        assert dk.success_rate == 0.5

    def test_success_rate_with_visits(self):
        """Success rate should calculate correctly."""
        dk = DomainKnowledge(domain="example.com")
        dk.successes = 8
        dk.visits = 10
        assert dk.success_rate == 0.8


class TestNavigationContextAPICompatibility:
    """Tests for API compatibility methods."""

    def test_path_property_is_alias(self):
        """path property should be alias for current_path."""
        ctx = NavigationContext()
        ctx.visit(
            url="https://example.com",
            title="Home",
            links_found=50,
            from_action="navigate"
        )

        assert ctx.path is ctx.current_path

    def test_visit_is_convenience_for_record_navigation(self):
        """visit() should be a convenience method for record_navigation."""
        ctx = NavigationContext()
        crumb = ctx.visit(
            url="https://example.com",
            title="Home",
            links_found=50,
            from_action="navigate"
        )

        assert crumb is not None
        assert crumb.url == "https://example.com"
        assert crumb.title == "Home"
        assert crumb.links_found == 50

    def test_mark_value_updates_current_page(self):
        """mark_value() should update the current (last visited) page."""
        ctx = NavigationContext()
        ctx.visit(url="https://example.com/page1", title="Page 1", links_found=10)
        ctx.visit(url="https://example.com/page2", title="Page 2", links_found=20)

        ctx.mark_value(PageValue.EXCELLENT)

        # Should update the last visited page (page2)
        assert ctx.path.breadcrumbs[-1].value == PageValue.EXCELLENT
        # First page should still have its original value
        assert ctx.path.breadcrumbs[0].value == PageValue.NEUTRAL

    def test_mark_value_no_breadcrumbs_does_not_crash(self):
        """mark_value() should not crash when there are no breadcrumbs."""
        ctx = NavigationContext()
        # Should not raise
        ctx.mark_value(PageValue.EXCELLENT)

    def test_visit_accepts_all_parameters(self):
        """visit() should accept all optional parameters."""
        ctx = NavigationContext()
        crumb = ctx.visit(
            url="https://example.com",
            title="Home",
            links_found=50,
            from_action="navigate",
            content_preview="Some content preview",
            value=PageValue.GOOD
        )

        assert crumb.value == PageValue.GOOD


class TestDomainKnowledgeAPICompatibility:
    """Tests for DomainKnowledge API compatibility properties."""

    def test_successes_attribute(self):
        """DomainKnowledge should have successes attribute."""
        dk = DomainKnowledge(domain="example.com")
        assert hasattr(dk, 'successes')
        assert dk.successes == 0
        dk.successes = 5
        assert dk.successes == 5

    def test_failures_attribute(self):
        """DomainKnowledge should have failures attribute."""
        dk = DomainKnowledge(domain="example.com")
        assert hasattr(dk, 'failures')
        assert dk.failures == 0
        dk.failures = 3
        assert dk.failures == 3

    def test_success_rate_property(self):
        """success_rate property should calculate correctly."""
        dk = DomainKnowledge(domain="example.com")

        # No visits - default rate
        assert dk.success_rate == 0.5

        # All successes
        dk.visits = 10
        dk.successes = 10
        assert dk.success_rate == 1.0

        # Mixed results
        dk.successes = 7
        assert dk.success_rate == 0.7

        # All failures
        dk.successes = 0
        assert dk.success_rate == 0.0
