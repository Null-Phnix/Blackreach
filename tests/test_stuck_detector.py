"""
Unit tests for blackreach/stuck_detector.py

Tests stuck state detection and recovery strategy suggestions.
"""

import pytest
import time
from blackreach.stuck_detector import (
    StuckDetector,
    StuckReason,
    RecoveryStrategy,
    Observation,
    StuckState,
    compute_content_hash,
)


class TestStuckReason:
    """Tests for StuckReason enum."""

    def test_all_reasons_exist(self):
        """All expected stuck reasons should exist."""
        assert StuckReason.URL_LOOP.value == "url_loop"
        assert StuckReason.CONTENT_LOOP.value == "content_loop"
        assert StuckReason.ACTION_LOOP.value == "action_loop"
        assert StuckReason.NO_PROGRESS.value == "no_progress"
        assert StuckReason.CHALLENGE_BLOCKED.value == "challenge_blocked"
        assert StuckReason.DEAD_END.value == "dead_end"
        assert StuckReason.NOT_STUCK.value == "not_stuck"


class TestRecoveryStrategy:
    """Tests for RecoveryStrategy enum."""

    def test_all_strategies_exist(self):
        """All expected recovery strategies should exist."""
        assert RecoveryStrategy.GO_BACK.value == "go_back"
        assert RecoveryStrategy.TRY_ALTERNATE_SOURCE.value == "alternate"
        assert RecoveryStrategy.REFORMULATE_SEARCH.value == "reformulate"
        assert RecoveryStrategy.SCROLL_AND_EXPLORE.value == "scroll"
        assert RecoveryStrategy.WAIT_AND_RETRY.value == "wait"
        assert RecoveryStrategy.SWITCH_BROWSER.value == "switch_browser"
        assert RecoveryStrategy.GIVE_UP.value == "give_up"


class TestObservation:
    """Tests for Observation dataclass."""

    def test_observation_creation(self):
        """Observation should store all fields correctly."""
        obs = Observation(
            url="https://example.com",
            content_hash="abc123",
            action="click",
            action_target="button.submit",
            download_count=0,
            step_number=1
        )
        assert obs.url == "https://example.com"
        assert obs.content_hash == "abc123"
        assert obs.action == "click"
        assert obs.action_target == "button.submit"
        assert obs.download_count == 0
        assert obs.step_number == 1

    def test_observation_timestamp_default(self):
        """Observation timestamp defaults to 0."""
        obs = Observation(
            url="https://example.com",
            content_hash="abc123",
            action="click",
            action_target="button",
            download_count=0,
            step_number=1
        )
        assert obs.timestamp == 0.0


class TestStuckState:
    """Tests for StuckState dataclass."""

    def test_stuck_state_creation(self):
        """StuckState should store all fields correctly."""
        state = StuckState(
            is_stuck=True,
            reason=StuckReason.URL_LOOP,
            confidence=0.95,
            details="Visited same URL 3 times"
        )
        assert state.is_stuck is True
        assert state.reason == StuckReason.URL_LOOP
        assert state.confidence == 0.95
        assert state.details == "Visited same URL 3 times"

    def test_stuck_state_defaults(self):
        """StuckState should have correct defaults."""
        state = StuckState(
            is_stuck=False,
            reason=StuckReason.NOT_STUCK,
            confidence=0.0,
            details=""
        )
        assert state.stuck_since_step == 0
        assert state.steps_stuck == 0


class TestStuckDetector:
    """Tests for StuckDetector class."""

    def test_init(self):
        """StuckDetector initializes correctly."""
        detector = StuckDetector()
        assert detector is not None

    def test_not_stuck_initially(self):
        """Detector should not report stuck on fresh start."""
        detector = StuckDetector()
        assert not detector.is_stuck()

    def test_detect_url_loop(self):
        """Detector should detect URL loops."""
        detector = StuckDetector()

        # Visit same URL multiple times
        for i in range(5):
            detector.observe(
                url="https://example.com/same-page",
                content_hash=f"hash_{i}",  # Different content
                action="click",
                download_count=0
            )

        # Should be stuck due to URL loop
        assert detector.is_stuck()
        state = detector.get_stuck_state()
        assert state.reason == StuckReason.URL_LOOP

    def test_detect_content_loop(self):
        """Detector should detect content loops (same content, different URLs)."""
        detector = StuckDetector()

        # Visit different URLs but same content
        for i in range(5):
            detector.observe(
                url=f"https://example.com/page-{i}",
                content_hash="same_hash_always",  # Same content
                action="click",
                download_count=0
            )

        # Should be stuck due to content loop
        assert detector.is_stuck()
        state = detector.get_stuck_state()
        assert state.reason == StuckReason.CONTENT_LOOP

    def test_detect_action_loop(self):
        """Detector should detect action loops."""
        detector = StuckDetector()

        # Repeat same action pattern
        for i in range(10):
            detector.observe(
                url=f"https://example.com/page-{i % 2}",
                content_hash=f"hash_{i % 2}",
                action="click",
                action_target="button.same",
                download_count=0
            )

        # Should be stuck due to action loop
        assert detector.is_stuck()

    def test_no_stuck_with_progress(self):
        """Detector should not report stuck when making progress."""
        detector = StuckDetector()

        # Make steady progress with downloads
        for i in range(5):
            detector.observe(
                url=f"https://example.com/page-{i}",
                content_hash=f"hash_{i}",
                action="download",
                download_count=i + 1  # Increasing downloads
            )

        # Should NOT be stuck - we're making progress
        assert not detector.is_stuck()

    def test_reset_clears_history(self):
        """Reset should clear detection history."""
        detector = StuckDetector()

        # Get stuck
        for i in range(5):
            detector.observe(
                url="https://example.com/same",
                content_hash="same",
                action="click",
                download_count=0
            )

        assert detector.is_stuck()

        # Reset
        detector.reset()

        # Should no longer be stuck
        assert not detector.is_stuck()

    def test_suggest_strategy_for_url_loop(self):
        """Suggest appropriate strategy for URL loop."""
        detector = StuckDetector()

        for i in range(5):
            detector.observe(
                url="https://example.com/same",
                content_hash=f"hash_{i}",
                action="click",
                download_count=0
            )

        strategy, _ = detector.suggest_strategy()
        # GO_BACK or TRY_ALTERNATE_SOURCE are appropriate
        assert strategy in [
            RecoveryStrategy.GO_BACK,
            RecoveryStrategy.TRY_ALTERNATE_SOURCE,
            RecoveryStrategy.REFORMULATE_SEARCH
        ]


class TestContentHashFunction:
    """Tests for compute_content_hash function."""

    def test_same_content_same_hash(self):
        """Same content should produce same hash."""
        html = "<html><body><p>Hello World</p></body></html>"
        hash1 = compute_content_hash(html)
        hash2 = compute_content_hash(html)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content should produce different hash."""
        html1 = "<html><body><p>Hello World</p></body></html>"
        html2 = "<html><body><p>Goodbye World</p></body></html>"
        hash1 = compute_content_hash(html1)
        hash2 = compute_content_hash(html2)
        assert hash1 != hash2

    def test_ignores_timestamps(self):
        """Hash should ignore common dynamic elements like timestamps."""
        html1 = "<html><body><p>Content</p><span>2024-01-15</span></body></html>"
        html2 = "<html><body><p>Content</p><span>2024-01-16</span></body></html>"
        hash1 = compute_content_hash(html1)
        hash2 = compute_content_hash(html2)
        # Hashes should be same since only date differs
        assert hash1 == hash2

    def test_ignores_scripts(self):
        """Hash should ignore script content."""
        html1 = "<html><body><p>Content</p><script>var x = 1;</script></body></html>"
        html2 = "<html><body><p>Content</p><script>var x = 2;</script></body></html>"
        hash1 = compute_content_hash(html1)
        hash2 = compute_content_hash(html2)
        assert hash1 == hash2

    def test_ignores_styles(self):
        """Hash should ignore style content."""
        html1 = "<html><body><p>Content</p><style>.x { color: red; }</style></body></html>"
        html2 = "<html><body><p>Content</p><style>.x { color: blue; }</style></body></html>"
        hash1 = compute_content_hash(html1)
        hash2 = compute_content_hash(html2)
        assert hash1 == hash2


class TestStuckDetectorThresholds:
    """Tests for detection threshold behavior."""

    def test_url_threshold_configurable(self):
        """URL repeat threshold should be configurable."""
        detector = StuckDetector()

        # Default threshold is 5
        for i in range(4):
            detector.observe(
                url="https://example.com/same",
                content_hash=f"hash_{i}",
                action="click",
                download_count=0
            )

        # 4 visits should not trigger stuck
        assert not detector.is_stuck()

        # 5th visit should trigger
        detector.observe(
            url="https://example.com/same",
            content_hash="hash_4",
            action="click",
            download_count=0
        )
        assert detector.is_stuck()


class TestStuckDetectorEdgeCases:
    """Tests for edge cases in stuck detection."""

    def test_empty_url(self):
        """Should handle empty URL gracefully."""
        detector = StuckDetector()
        detector.observe(
            url="",
            content_hash="hash",
            action="click",
            download_count=0
        )
        # Should not crash

    def test_empty_content_hash(self):
        """Should handle empty content hash gracefully."""
        detector = StuckDetector()
        detector.observe(
            url="https://example.com",
            content_hash="",
            action="click",
            download_count=0
        )
        # Should not crash

    def test_high_step_numbers(self):
        """Should handle high step numbers."""
        detector = StuckDetector()
        detector.observe(
            url="https://example.com",
            content_hash="hash",
            action="click",
            download_count=0,
            step_number=999999
        )
        # Should not crash


class TestStuckDetectorAPICompatibility:
    """Tests for API compatibility methods."""

    def test_get_stuck_state_is_alias_for_check(self):
        """get_stuck_state should be an alias for check."""
        detector = StuckDetector()

        # Initially not stuck
        state1 = detector.get_stuck_state()
        state2 = detector.check()

        # Both should indicate not stuck
        assert state1.is_stuck == state2.is_stuck
        assert state1.reason == state2.reason

    def test_get_stuck_state_after_stuck(self):
        """get_stuck_state should return correct state when stuck."""
        detector = StuckDetector()

        # Get stuck
        for i in range(5):
            detector.observe(
                url="https://example.com/same",
                content_hash=f"hash_{i}",
                action="click",
                download_count=0
            )

        state = detector.get_stuck_state()
        assert state.is_stuck is True
        assert state.reason == StuckReason.URL_LOOP

    def test_get_stuck_state_returns_stuck_state_object(self):
        """get_stuck_state should return a StuckState object."""
        detector = StuckDetector()
        state = detector.get_stuck_state()

        assert isinstance(state, StuckState)
        assert hasattr(state, 'is_stuck')
        assert hasattr(state, 'reason')
        assert hasattr(state, 'confidence')
        assert hasattr(state, 'details')

    def test_check_and_get_stuck_state_equivalent(self):
        """check() and get_stuck_state() should return equivalent results."""
        detector = StuckDetector()

        # Add some observations
        detector.observe(
            url="https://example.com/page1",
            content_hash="hash1",
            action="click",
            download_count=0
        )
        detector.observe(
            url="https://example.com/page2",
            content_hash="hash2",
            action="click",
            download_count=0
        )

        state1 = detector.check()
        state2 = detector.get_stuck_state()

        # Should be equivalent
        assert state1.is_stuck == state2.is_stuck
        assert state1.reason == state2.reason
        assert state1.confidence == state2.confidence
