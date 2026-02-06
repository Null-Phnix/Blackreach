"""
Unit tests for blackreach/timeout_manager.py

Tests adaptive timeout management with historical learning.
"""

import pytest
import time
from datetime import datetime, timedelta
from blackreach.timeout_manager import (
    TimeoutConfig,
    ActionTiming,
    TimeoutStats,
    TimeoutManager,
    get_timeout_manager,
    reset_timeout_manager,
)


class TestTimeoutConfig:
    """Tests for TimeoutConfig dataclass."""

    def test_default_values(self):
        """TimeoutConfig has sensible defaults."""
        config = TimeoutConfig()
        assert config.default_timeout == 30.0
        assert config.min_timeout == 5.0
        assert config.max_timeout == 120.0
        assert config.adaptive is True
        assert config.buffer_factor == 1.5
        assert config.sample_size == 10

    def test_custom_values(self):
        """TimeoutConfig accepts custom values."""
        config = TimeoutConfig(
            default_timeout=60.0,
            min_timeout=10.0,
            max_timeout=300.0,
            adaptive=False,
            buffer_factor=2.0,
            sample_size=20
        )
        assert config.default_timeout == 60.0
        assert config.min_timeout == 10.0
        assert config.max_timeout == 300.0
        assert config.adaptive is False
        assert config.buffer_factor == 2.0
        assert config.sample_size == 20


class TestActionTiming:
    """Tests for ActionTiming dataclass."""

    def test_creation(self):
        """ActionTiming stores all fields."""
        timing = ActionTiming(
            duration=5.5,
            success=True
        )
        assert timing.duration == 5.5
        assert timing.success is True
        assert timing.timestamp is not None

    def test_failed_timing(self):
        """ActionTiming can represent failures."""
        timing = ActionTiming(
            duration=30.0,
            success=False
        )
        assert timing.success is False


class TestTimeoutStats:
    """Tests for TimeoutStats dataclass."""

    def test_default_values(self):
        """TimeoutStats has correct defaults."""
        stats = TimeoutStats()
        assert stats.total_attempts == 0
        assert stats.timeouts == 0
        assert stats.avg_duration == 0.0
        assert stats.max_duration == 0.0
        assert stats.predicted_timeout == 30.0


class TestTimeoutManager:
    """Tests for TimeoutManager class."""

    def test_init(self):
        """TimeoutManager initializes correctly."""
        manager = TimeoutManager()
        assert manager is not None
        assert manager.config is not None

    def test_init_with_config(self):
        """TimeoutManager accepts custom config."""
        config = TimeoutConfig(default_timeout=60.0)
        manager = TimeoutManager(config=config)
        assert manager.config.default_timeout == 60.0

    def test_action_defaults(self):
        """TimeoutManager has action-specific defaults."""
        manager = TimeoutManager()
        assert manager.action_defaults["navigate"] == 30.0
        assert manager.action_defaults["click"] == 10.0
        assert manager.action_defaults["type"] == 5.0
        assert manager.action_defaults["scroll"] == 3.0
        assert manager.action_defaults["download"] == 120.0
        assert manager.action_defaults["wait"] == 60.0


class TestTimeoutManagerGetTimeout:
    """Tests for get_timeout method."""

    def test_get_default_timeout(self):
        """Should return default when no history."""
        manager = TimeoutManager()
        timeout = manager.get_timeout("navigate")
        assert timeout == 30.0

    def test_get_action_default(self):
        """Should return action-specific default."""
        manager = TimeoutManager()
        timeout = manager.get_timeout("click")
        assert timeout == 10.0

    def test_get_fallback_for_unknown_action(self):
        """Should return config default for unknown actions."""
        manager = TimeoutManager()
        timeout = manager.get_timeout("unknown_action")
        assert timeout == manager.config.default_timeout

    def test_non_adaptive_returns_default(self):
        """Should return default when adaptive is disabled."""
        config = TimeoutConfig(adaptive=False)
        manager = TimeoutManager(config=config)

        # Add some timing history
        for i in range(5):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=2.0, success=True)
            )

        # Should still return default, not learned value
        timeout = manager.get_timeout("navigate", "example.com")
        assert timeout == 30.0

    def test_adaptive_timeout_with_history(self):
        """Should adapt timeout based on history."""
        manager = TimeoutManager()

        # Add timing history (3+ entries required)
        for i in range(5):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=5.0, success=True)
            )

        timeout = manager.get_timeout("navigate", "example.com")
        # Should be based on historical data, not default
        assert timeout != 30.0
        assert timeout > 5.0  # With buffer factor


class TestTimeoutManagerTiming:
    """Tests for start/end timing methods."""

    def test_start_timing(self):
        """Should start timing and return key."""
        manager = TimeoutManager()
        key = manager.start_timing("navigate", "example.com")

        assert key is not None
        assert "example.com" in key
        assert "navigate" in key
        assert key in manager._active

    def test_end_timing_returns_duration(self):
        """Should return duration when ending timing."""
        manager = TimeoutManager()
        key = manager.start_timing("navigate", "example.com")
        time.sleep(0.1)  # Small delay

        duration = manager.end_timing(key, success=True, action="navigate", domain="example.com")

        assert duration >= 0.1
        assert key not in manager._active

    def test_end_timing_records_data(self):
        """Should record timing data."""
        manager = TimeoutManager()
        key = manager.start_timing("navigate", "example.com")

        manager.end_timing(key, success=True, action="navigate", domain="example.com")

        timings = manager.timings["example.com"]["navigate"]
        assert len(timings) == 1
        assert timings[0].success is True

    def test_end_timing_invalid_key(self):
        """Should handle invalid timing key."""
        manager = TimeoutManager()
        duration = manager.end_timing("invalid_key", success=True, action="navigate")
        assert duration == 0.0

    def test_timing_data_trimmed(self):
        """Should trim old timing data."""
        config = TimeoutConfig(sample_size=5)
        manager = TimeoutManager(config=config)

        # Add more than max samples
        for i in range(15):
            key = manager.start_timing("navigate", "example.com")
            manager.end_timing(key, success=True, action="navigate", domain="example.com")

        # Should be trimmed to 2x sample_size
        assert len(manager.timings["example.com"]["navigate"]) <= 10


class TestTimeoutManagerRecordTimeout:
    """Tests for record_timeout method."""

    def test_record_timeout(self):
        """Should record timeout as failed timing."""
        manager = TimeoutManager()
        manager.record_timeout("navigate", "example.com")

        timings = manager.timings["example.com"]["navigate"]
        assert len(timings) == 1
        assert timings[0].success is False
        assert timings[0].duration == manager.config.max_timeout


class TestTimeoutManagerStats:
    """Tests for get_stats method."""

    def test_get_stats_empty(self):
        """Should return empty stats when no data."""
        manager = TimeoutManager()
        stats = manager.get_stats()

        assert stats.total_attempts == 0
        assert stats.timeouts == 0

    def test_get_stats_with_data(self):
        """Should calculate stats from timing data."""
        manager = TimeoutManager()

        # Add some timings
        manager.timings["example.com"]["navigate"].append(
            ActionTiming(duration=5.0, success=True)
        )
        manager.timings["example.com"]["navigate"].append(
            ActionTiming(duration=10.0, success=True)
        )
        manager.timings["example.com"]["navigate"].append(
            ActionTiming(duration=30.0, success=False)
        )

        stats = manager.get_stats("example.com", "navigate")

        assert stats.total_attempts == 3
        assert stats.timeouts == 1
        assert stats.max_duration == 30.0
        assert 10 <= stats.avg_duration <= 20  # (5+10+30)/3 = 15

    def test_get_stats_by_domain(self):
        """Should aggregate stats by domain."""
        manager = TimeoutManager()

        manager.timings["example.com"]["navigate"].append(
            ActionTiming(duration=5.0, success=True)
        )
        manager.timings["example.com"]["click"].append(
            ActionTiming(duration=2.0, success=True)
        )

        stats = manager.get_stats(domain="example.com")

        assert stats.total_attempts == 2

    def test_get_stats_by_action(self):
        """Should aggregate stats by action across domains."""
        manager = TimeoutManager()

        manager.timings["example.com"]["navigate"].append(
            ActionTiming(duration=5.0, success=True)
        )
        manager.timings["other.com"]["navigate"].append(
            ActionTiming(duration=8.0, success=True)
        )

        stats = manager.get_stats(action="navigate")

        assert stats.total_attempts == 2


class TestTimeoutManagerSuggestions:
    """Tests for timeout adjustment suggestions."""

    def test_suggest_not_enough_data(self):
        """Should indicate not enough data."""
        manager = TimeoutManager()

        suggestion, reason = manager.suggest_timeout_adjustment("example.com", "navigate")

        assert "Not enough data" in reason

    def test_suggest_increase_high_timeout_rate(self):
        """Should suggest increase when timeout rate is high."""
        manager = TimeoutManager()

        # Add mostly failed timings
        for _ in range(3):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=30.0, success=False)
            )

        suggestion, reason = manager.suggest_timeout_adjustment("example.com", "navigate")

        assert "increasing" in reason.lower()

    def test_suggest_appropriate(self):
        """Should indicate timeout is appropriate."""
        manager = TimeoutManager()

        # Add mostly successful timings with a few timeouts
        for _ in range(8):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=5.0, success=True)
            )
        manager.timings["example.com"]["navigate"].append(
            ActionTiming(duration=30.0, success=False)
        )

        _, reason = manager.suggest_timeout_adjustment("example.com", "navigate")

        # Should be appropriate (timeout rate ~11%)
        assert "appropriate" in reason.lower() or "reduce" in reason.lower()


class TestTimeoutPrediction:
    """Tests for timeout prediction algorithm."""

    def test_predict_from_successful(self):
        """Should predict based on successful timings."""
        manager = TimeoutManager()

        # Add consistent successful timings
        for _ in range(5):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=10.0, success=True)
            )

        timeout = manager.get_timeout("navigate", "example.com")

        # Should be around 10 * 1.5 (buffer factor) = 15
        assert 10 <= timeout <= 20

    def test_predict_increases_with_all_failures(self):
        """Should increase timeout when all recent attempts failed."""
        manager = TimeoutManager()

        # Add only failed timings
        for _ in range(5):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=30.0, success=False)
            )

        timeout = manager.get_timeout("navigate", "example.com")

        # Should be default * 2 (increased for failures)
        assert timeout == min(manager.config.max_timeout, manager.config.default_timeout * 2)

    def test_predict_respects_min_timeout(self):
        """Predicted timeout should not go below minimum."""
        config = TimeoutConfig(min_timeout=10.0)
        manager = TimeoutManager(config=config)

        # Add very fast timings
        for _ in range(5):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=1.0, success=True)
            )

        timeout = manager.get_timeout("navigate", "example.com")

        assert timeout >= 10.0

    def test_predict_respects_max_timeout(self):
        """Predicted timeout should not exceed maximum."""
        config = TimeoutConfig(max_timeout=60.0)
        manager = TimeoutManager(config=config)

        # Add very slow timings
        for _ in range(5):
            manager.timings["example.com"]["navigate"].append(
                ActionTiming(duration=50.0, success=True)
            )

        timeout = manager.get_timeout("navigate", "example.com")

        assert timeout <= 60.0


class TestTimeoutManagerExportImport:
    """Tests for data export/import."""

    def test_export_data(self):
        """Should export timing data."""
        manager = TimeoutManager()

        manager.timings["example.com"]["navigate"].append(
            ActionTiming(duration=5.0, success=True)
        )

        data = manager.export_data()

        assert "example.com" in data
        assert "navigate" in data["example.com"]
        assert len(data["example.com"]["navigate"]) == 1
        assert data["example.com"]["navigate"][0]["duration"] == 5.0

    def test_import_data(self):
        """Should import timing data."""
        manager = TimeoutManager()

        data = {
            "example.com": {
                "navigate": [
                    {
                        "duration": 5.0,
                        "success": True,
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            }
        }

        manager.import_data(data)

        assert len(manager.timings["example.com"]["navigate"]) == 1
        assert manager.timings["example.com"]["navigate"][0].duration == 5.0

    def test_export_import_roundtrip(self):
        """Exported data should import correctly."""
        manager1 = TimeoutManager()

        # Add some data
        manager1.timings["example.com"]["navigate"].append(
            ActionTiming(duration=5.0, success=True)
        )
        manager1.timings["other.com"]["click"].append(
            ActionTiming(duration=2.0, success=False)
        )

        # Export and import to new manager
        data = manager1.export_data()
        manager2 = TimeoutManager()
        manager2.import_data(data)

        # Verify data
        assert len(manager2.timings["example.com"]["navigate"]) == 1
        assert len(manager2.timings["other.com"]["click"]) == 1


class TestGlobalTimeoutManager:
    """Tests for global timeout manager."""

    def test_get_timeout_manager(self):
        """Should return global timeout manager."""
        reset_timeout_manager()  # Start fresh

        manager1 = get_timeout_manager()
        manager2 = get_timeout_manager()

        assert manager1 is manager2

    def test_reset_timeout_manager(self):
        """Should reset global timeout manager."""
        manager1 = get_timeout_manager()
        reset_timeout_manager()
        manager2 = get_timeout_manager()

        assert manager1 is not manager2
