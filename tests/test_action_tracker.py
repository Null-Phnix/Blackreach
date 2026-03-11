"""
Unit tests for blackreach/action_tracker.py

Tests action outcome tracking and confidence scoring.
"""

import pytest
from blackreach.action_tracker import (
    ActionOutcome,
    ActionStats,
    ActionTracker,
    get_tracker,
)


class TestActionOutcome:
    """Tests for ActionOutcome dataclass."""

    def test_creation(self):
        """ActionOutcome stores all fields."""
        outcome = ActionOutcome(
            action_type="click",
            target="button.download",
            domain="example.com",
            success=True,
            context="Download page",
            error=""
        )
        assert outcome.action_type == "click"
        assert outcome.target == "button.download"
        assert outcome.domain == "example.com"
        assert outcome.success is True
        assert outcome.context == "Download page"
        assert outcome.error == ""

    def test_failed_outcome(self):
        """ActionOutcome can represent failures."""
        outcome = ActionOutcome(
            action_type="click",
            target="button.broken",
            domain="example.com",
            success=False,
            error="Element not found"
        )
        assert outcome.success is False
        assert outcome.error == "Element not found"


class TestActionStats:
    """Tests for ActionStats dataclass."""

    def test_default_values(self):
        """ActionStats has correct defaults."""
        stats = ActionStats()
        assert stats.success_count == 0
        assert stats.failure_count == 0
        assert stats.last_success is None
        assert stats.last_failure is None
        assert stats.common_errors == {}

    def test_total_property(self):
        """Total should sum successes and failures."""
        stats = ActionStats(success_count=5, failure_count=3)
        assert stats.total == 8

    def test_success_rate_unknown(self):
        """Success rate should be 0.5 for unknown actions."""
        stats = ActionStats()
        assert stats.success_rate == 0.5

    def test_success_rate_all_success(self):
        """Success rate should be 1.0 for all successes."""
        stats = ActionStats(success_count=10, failure_count=0)
        assert stats.success_rate == 1.0

    def test_success_rate_all_failure(self):
        """Success rate should be 0.0 for all failures."""
        stats = ActionStats(success_count=0, failure_count=10)
        assert stats.success_rate == 0.0

    def test_success_rate_mixed(self):
        """Success rate should calculate correctly."""
        stats = ActionStats(success_count=7, failure_count=3)
        assert stats.success_rate == 0.7

    def test_record_success(self):
        """Recording success should update stats."""
        stats = ActionStats()
        stats.record_success()

        assert stats.success_count == 1
        assert stats.last_success is not None

    def test_record_failure(self):
        """Recording failure should update stats."""
        stats = ActionStats()
        stats.record_failure("Timeout error")

        assert stats.failure_count == 1
        assert stats.last_failure is not None
        assert "Timeout error" in stats.common_errors

    def test_record_failure_tracks_common_errors(self):
        """Recording failures should track common errors."""
        stats = ActionStats()
        stats.record_failure("Error A")
        stats.record_failure("Error A")
        stats.record_failure("Error B")

        assert stats.common_errors["Error A"] == 2
        assert stats.common_errors["Error B"] == 1


class TestActionTracker:
    """Tests for ActionTracker class."""

    def test_init(self):
        """ActionTracker initializes correctly."""
        tracker = ActionTracker()
        assert tracker is not None

    def test_normalize_selector_basic(self):
        """Should normalize basic selectors."""
        tracker = ActionTracker()

        # Should lowercase
        assert tracker._normalize_selector("BUTTON") == "button"

        # Should strip whitespace
        assert tracker._normalize_selector("  button  ") == "button"

    def test_normalize_selector_quoted_text(self):
        """Should normalize quoted text."""
        tracker = ActionTracker()

        normalized = tracker._normalize_selector("button:has-text('Download')")
        assert "'*'" in normalized

    def test_normalize_selector_nth_child(self):
        """Should normalize nth-child selectors."""
        tracker = ActionTracker()

        normalized = tracker._normalize_selector("a:nth-child(5)")
        assert ":nth-child(*)" in normalized

    def test_extract_selector_type(self):
        """Should extract element type from selector."""
        tracker = ActionTracker()

        assert tracker._extract_selector_type("button.download") == "button"
        assert tracker._extract_selector_type("a.link") == "a"
        assert tracker._extract_selector_type(".class-name") == "class"
        assert tracker._extract_selector_type("#element-id") == "id"

    def test_record_success(self):
        """Should record successful action."""
        tracker = ActionTracker()
        tracker.record("click", "button.download", success=True, domain="example.com")

        stats = tracker._stats[("example.com", "click", "button.download")]
        assert stats.success_count == 1

    def test_record_failure(self):
        """Should record failed action."""
        tracker = ActionTracker()
        tracker.record(
            "click", "button.broken",
            success=False, domain="example.com",
            error="Element not found"
        )

        stats = tracker._stats[("example.com", "click", "button.broken")]
        assert stats.failure_count == 1
        assert "Element not found" in stats.common_errors

    def test_record_updates_domain_stats(self):
        """Should update domain-level stats."""
        tracker = ActionTracker()
        tracker.record("click", "button.a", success=True, domain="example.com")
        tracker.record("click", "button.b", success=True, domain="example.com")

        domain_stats = tracker._domain_stats[("example.com", "click")]
        assert domain_stats.success_count == 2

    def test_record_updates_global_stats(self):
        """Should update global stats."""
        tracker = ActionTracker()
        tracker.record("click", "button.a", success=True, domain="example.com")
        tracker.record("click", "button.b", success=True, domain="other.com")

        global_stats = tracker._global_stats["click"]
        assert global_stats.success_count == 2


class TestActionTrackerConfidence:
    """Tests for confidence scoring."""

    def test_get_confidence_exact_match(self):
        """Should use exact match stats when available."""
        tracker = ActionTracker()

        # Record enough data for exact match
        for _ in range(5):
            tracker.record("click", "button.download", success=True, domain="example.com")

        confidence = tracker.get_confidence("click", "button.download", domain="example.com")
        assert confidence == 1.0

    def test_get_confidence_domain_fallback(self):
        """Should fall back to domain stats."""
        tracker = ActionTracker()

        # Record domain-level data
        for _ in range(10):
            tracker.record("click", "button.a", success=True, domain="example.com")

        # Query for unknown target on same domain
        confidence = tracker.get_confidence("click", "button.unknown", domain="example.com")
        assert confidence == 1.0

    def test_get_confidence_global_fallback(self):
        """Should fall back to global stats."""
        tracker = ActionTracker()

        # Record global data
        for _ in range(15):
            tracker.record("click", "button.a", success=True, domain="site1.com")

        # Query for unknown domain
        confidence = tracker.get_confidence("click", "button.unknown", domain="unknown.com")
        assert confidence == 1.0

    def test_get_confidence_defaults(self):
        """Should return default confidence for unknown actions."""
        tracker = ActionTracker()

        # Default for navigate should be high
        assert tracker.get_confidence("navigate", "http://example.com") == 0.9

        # Default for scroll should be high
        assert tracker.get_confidence("scroll", "down") == 0.9

        # Default for download should be lower
        assert tracker.get_confidence("download", "file.pdf") == 0.6

        # Default for unknown action type
        assert tracker.get_confidence("unknown_action", "target") == 0.5


class TestActionTrackerRecommendations:
    """Tests for getting recommendations."""

    def test_get_recommendations(self):
        """Should return recommendations sorted by success rate."""
        tracker = ActionTracker()

        # Record some actions
        for _ in range(5):
            tracker.record("click", "button.good", success=True, domain="example.com")

        for _ in range(3):
            tracker.record("click", "button.bad", success=False, domain="example.com")
            tracker.record("click", "button.bad", success=True, domain="example.com")

        recommendations = tracker.get_recommendations("example.com", "click")

        # Good button should be first
        assert len(recommendations) > 0
        assert recommendations[0][0] == "button.good"
        assert recommendations[0][1] == 1.0

    def test_get_good_selectors(self):
        """Should return selectors with high success rate."""
        tracker = ActionTracker()

        # Record many successes for a selector
        for _ in range(10):
            tracker.record("click", "button.download", success=True, domain="example.com")

        good = tracker.get_good_selectors("example.com")
        assert "button.download" in good


class TestActionTrackerHistory:
    """Tests for action history."""

    def test_get_action_history(self):
        """Should return action history."""
        tracker = ActionTracker()

        tracker.record("click", "button.a", success=True, domain="example.com")
        tracker.record("click", "button.b", success=False, domain="example.com")

        history = tracker.get_action_history(domain="example.com")

        assert len(history) == 2
        assert all("domain" in h for h in history)
        assert all("success_rate" in h for h in history)

    def test_get_action_history_filter_domain(self):
        """Should filter by domain."""
        tracker = ActionTracker()

        tracker.record("click", "button.a", success=True, domain="site1.com")
        tracker.record("click", "button.b", success=True, domain="site2.com")

        history = tracker.get_action_history(domain="site1.com")

        assert len(history) == 1
        assert history[0]["domain"] == "site1.com"

    def test_get_action_history_filter_action_type(self):
        """Should filter by action type."""
        tracker = ActionTracker()

        tracker.record("click", "button.a", success=True, domain="example.com")
        tracker.record("type", "input.text", success=True, domain="example.com")

        history = tracker.get_action_history(action_type="click")

        assert len(history) == 1
        assert history[0]["action_type"] == "click"


class TestActionTrackerDomainSummary:
    """Tests for domain summary."""

    def test_get_domain_summary(self):
        """Should return summary for domain."""
        tracker = ActionTracker()

        for _ in range(5):
            tracker.record("click", "button", success=True, domain="example.com")
        for _ in range(3):
            tracker.record("navigate", "page", success=True, domain="example.com")
        tracker.record("download", "file", success=False, domain="example.com")

        summary = tracker.get_domain_summary("example.com")

        assert "click" in summary
        assert summary["click"]["success_rate"] == 1.0
        assert summary["navigate"]["total_actions"] == 3


class TestActionTrackerAvoidance:
    """Tests for action avoidance logic."""

    def test_should_avoid_always_fails(self):
        """Should avoid actions that always fail."""
        tracker = ActionTracker()

        for _ in range(3):
            tracker.record("click", "button.broken", success=False, domain="example.com")

        assert tracker.should_avoid("click", "button.broken", "example.com") is True

    def test_should_avoid_high_failure_rate(self):
        """Should avoid actions with high failure rate."""
        tracker = ActionTracker()

        # 0 success, 5 failures = 100% failure, clearly <20% success
        for _ in range(5):
            tracker.record("click", "button.bad", success=False, domain="example.com")

        assert tracker.should_avoid("click", "button.bad", "example.com") is True

    def test_should_not_avoid_successful(self):
        """Should not avoid successful actions."""
        tracker = ActionTracker()

        for _ in range(5):
            tracker.record("click", "button.good", success=True, domain="example.com")

        assert tracker.should_avoid("click", "button.good", "example.com") is False


class TestActionTrackerAlternatives:
    """Tests for alternative action suggestions."""

    def test_get_alternative_actions(self):
        """Should suggest alternatives after failure."""
        tracker = ActionTracker()

        # Record a successful alternative
        for _ in range(5):
            tracker.record("click", "button.alternative", success=True, domain="example.com")

        # Record failure for original
        tracker.record("click", "button.original", success=False, domain="example.com")

        alternatives = tracker.get_alternative_actions("click", "button.original", "example.com")

        assert "button.alternative" in alternatives


class TestActionTrackerStatsSummary:
    """Tests for overall statistics."""

    def test_get_stats_summary(self):
        """Should return overall statistics."""
        tracker = ActionTracker()

        for _ in range(10):
            tracker.record("click", "button.good", success=True, domain="site1.com")
        for _ in range(5):
            tracker.record("click", "button.bad", success=False, domain="site2.com")

        summary = tracker.get_stats_summary()

        assert summary["total_tracked_actions"] == 15
        assert summary["total_successes"] == 10
        assert summary["overall_success_rate"] == 10 / 15
        assert summary["domains_tracked"] == 2

    def test_stats_summary_identifies_problems(self):
        """Should identify problematic actions."""
        tracker = ActionTracker()

        # Create a problematic action (5+ failures with <30% success)
        for _ in range(5):
            tracker.record("click", "button.problem", success=False, domain="example.com")
        tracker.record("click", "button.problem", success=True, domain="example.com")

        summary = tracker.get_stats_summary()

        assert len(summary["problem_actions"]) > 0
        problem = summary["problem_actions"][0]
        assert problem["target"] == "button.problem"


class TestGlobalTracker:
    """Tests for global tracker instance."""

    def test_get_tracker(self):
        """Should return global tracker instance."""
        tracker1 = get_tracker()
        tracker2 = get_tracker()

        assert tracker1 is tracker2
