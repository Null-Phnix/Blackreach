"""
Unit tests for enhanced rate_limiter.py

Tests adaptive throttling and response-based rate limiting.
"""

import pytest
import time
from datetime import datetime, timedelta

from blackreach.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    DomainState,
    ServerResponseType,
    ResponseMetrics,
    get_rate_limiter,
    reset_rate_limiter,
)


class TestServerResponseType:
    """Tests for ServerResponseType enum."""

    def test_all_types_defined(self):
        """All response types are defined."""
        types = [t.value for t in ServerResponseType]
        assert "success" in types
        assert "slow" in types
        assert "rate_limited" in types
        assert "error" in types
        assert "blocked" in types


class TestResponseMetrics:
    """Tests for ResponseMetrics dataclass."""

    def test_create_metrics(self):
        """Create response metrics."""
        now = datetime.now()
        metrics = ResponseMetrics(
            timestamp=now,
            response_time=1.5,
            status_code=200,
            response_type=ServerResponseType.SUCCESS
        )
        assert metrics.response_time == 1.5
        assert metrics.status_code == 200
        assert metrics.response_type == ServerResponseType.SUCCESS


class TestRateLimitConfigEnhanced:
    """Tests for enhanced RateLimitConfig."""

    def test_default_adaptive_settings(self):
        """Default adaptive throttling settings."""
        config = RateLimitConfig()
        assert config.adaptive_throttling is True
        assert config.slow_response_threshold > 0
        assert config.target_response_time > 0
        assert config.throttle_increase_factor > 1.0
        assert config.throttle_decrease_factor < 1.0

    def test_custom_adaptive_settings(self):
        """Custom adaptive throttling settings."""
        config = RateLimitConfig(
            adaptive_throttling=False,
            slow_response_threshold=5.0,
            target_response_time=2.0
        )
        assert config.adaptive_throttling is False
        assert config.slow_response_threshold == 5.0


class TestDomainStateEnhanced:
    """Tests for enhanced DomainState."""

    def test_default_adaptive_state(self):
        """Default adaptive state fields."""
        state = DomainState()
        assert state.response_metrics == []
        assert state.adaptive_interval is None
        assert state.consecutive_successes == 0
        assert state.consecutive_slow == 0


class TestRateLimiterAdaptive:
    """Tests for adaptive throttling in RateLimiter."""

    @pytest.fixture
    def limiter(self):
        """Create limiter with adaptive throttling."""
        config = RateLimitConfig(
            adaptive_throttling=True,
            slow_response_threshold=2.0,
            target_response_time=0.5,
            min_interval_adaptive=0.1,
            max_interval_adaptive=5.0
        )
        return RateLimiter(config)

    @pytest.fixture
    def limiter_no_adaptive(self):
        """Create limiter without adaptive throttling."""
        config = RateLimitConfig(adaptive_throttling=False)
        return RateLimiter(config)

    def test_record_success_with_response_time(self, limiter):
        """Record success includes response time."""
        limiter.record_success("example.com", response_time=0.5, status_code=200)
        state = limiter.domains["example.com"]
        assert len(state.response_metrics) == 1
        assert state.response_metrics[0].response_time == 0.5

    def test_classify_success(self, limiter):
        """Classify fast response as success."""
        response_type = limiter._classify_response(0.5, 200)
        assert response_type == ServerResponseType.SUCCESS

    def test_classify_slow(self, limiter):
        """Classify slow response."""
        response_type = limiter._classify_response(5.0, 200)
        assert response_type == ServerResponseType.SLOW

    def test_classify_rate_limited(self, limiter):
        """Classify 429 as rate limited."""
        response_type = limiter._classify_response(0.5, 429)
        assert response_type == ServerResponseType.RATE_LIMITED

    def test_classify_blocked(self, limiter):
        """Classify 403/503 as blocked."""
        assert limiter._classify_response(0.5, 403) == ServerResponseType.BLOCKED
        assert limiter._classify_response(0.5, 503) == ServerResponseType.BLOCKED

    def test_classify_error(self, limiter):
        """Classify server errors."""
        assert limiter._classify_response(0.5, 500) == ServerResponseType.ERROR
        assert limiter._classify_response(0.5, 502) == ServerResponseType.ERROR

    def test_adaptive_interval_increases_on_slow(self, limiter):
        """Adaptive interval increases on slow responses."""
        domain = "slow.example.com"

        # Initial interval
        initial_interval = limiter.get_adaptive_interval(domain)

        # Record slow response
        limiter.record_success(domain, response_time=5.0, status_code=200)

        new_interval = limiter.get_adaptive_interval(domain)
        assert new_interval > initial_interval

    def test_adaptive_interval_decreases_on_fast(self, limiter):
        """Adaptive interval decreases on fast responses."""
        domain = "fast.example.com"

        # Set a higher initial interval
        limiter.domains[domain].adaptive_interval = 2.0

        # Record several fast successful responses
        for _ in range(5):
            limiter.record_success(domain, response_time=0.1, status_code=200)

        new_interval = limiter.get_adaptive_interval(domain)
        assert new_interval < 2.0

    def test_adaptive_interval_spikes_on_rate_limit(self, limiter):
        """Adaptive interval increases significantly on rate limit."""
        domain = "limited.example.com"
        limiter.domains[domain].adaptive_interval = 1.0

        # Record rate limited response
        limiter.record_success(domain, response_time=0.5, status_code=429)

        new_interval = limiter.get_adaptive_interval(domain)
        # Should increase by square of factor
        assert new_interval > 1.0 * (limiter.config.throttle_increase_factor ** 2) * 0.9

    def test_consecutive_success_tracking(self, limiter):
        """Track consecutive successful responses."""
        domain = "success.example.com"

        for _ in range(3):
            limiter.record_success(domain, response_time=0.3, status_code=200)

        state = limiter.domains[domain]
        assert state.consecutive_successes == 3
        assert state.consecutive_slow == 0

    def test_consecutive_slow_tracking(self, limiter):
        """Track consecutive slow responses."""
        domain = "slow.example.com"

        for _ in range(3):
            limiter.record_success(domain, response_time=5.0, status_code=200)

        state = limiter.domains[domain]
        assert state.consecutive_slow == 3
        assert state.consecutive_successes == 0

    def test_adaptive_disabled(self, limiter_no_adaptive):
        """Adaptive throttling disabled respects setting."""
        domain = "test.com"
        limiter_no_adaptive.record_success(domain, response_time=5.0)

        # Should return min_request_interval when adaptive disabled
        interval = limiter_no_adaptive.get_adaptive_interval(domain)
        assert interval == limiter_no_adaptive.config.min_request_interval


class TestResponseStats:
    """Tests for response statistics."""

    @pytest.fixture
    def limiter(self):
        config = RateLimitConfig(adaptive_throttling=True)
        return RateLimiter(config)

    def test_get_response_stats_empty(self, limiter):
        """Get stats for domain with no requests."""
        stats = limiter.get_response_stats("new.domain.com")
        assert stats["total_responses"] == 0
        assert stats["avg_response_time"] == 0

    def test_get_response_stats_with_data(self, limiter):
        """Get stats after some requests."""
        domain = "test.com"

        # Record various responses - note: slow threshold is 3.0 in the config
        limiter.record_success(domain, response_time=0.5, status_code=200)
        limiter.record_success(domain, response_time=1.0, status_code=200)
        limiter.record_success(domain, response_time=5.0, status_code=200)  # Slow (above 3.0 threshold)
        limiter.record_success(domain, response_time=0.3, status_code=429)  # Rate limited

        stats = limiter.get_response_stats(domain)
        assert stats["total_responses"] == 4
        assert stats["avg_response_time"] > 0
        assert stats["slow_responses"] == 1
        assert stats["rate_limited"] == 1


class TestShouldThrottle:
    """Tests for should_throttle method."""

    @pytest.fixture
    def limiter(self):
        config = RateLimitConfig(
            adaptive_throttling=True,
            response_window=5
        )
        return RateLimiter(config)

    def test_no_throttle_no_data(self, limiter):
        """No throttling with no data."""
        should_throttle, wait_time = limiter.should_throttle("new.domain.com")
        assert should_throttle is False
        assert wait_time == 0

    def test_throttle_on_errors(self, limiter):
        """Recommend throttling after errors."""
        domain = "error.com"

        # Record some errors
        for _ in range(3):
            limiter.record_success(domain, response_time=0.5, status_code=429)

        should_throttle, wait_time = limiter.should_throttle(domain)
        assert should_throttle is True
        assert wait_time > 0

    def test_throttle_on_many_slow(self, limiter):
        """Recommend throttling after many slow responses."""
        domain = "slow.com"

        # Record mostly slow responses (>30%)
        for _ in range(4):
            limiter.record_success(domain, response_time=5.0, status_code=200)

        should_throttle, wait_time = limiter.should_throttle(domain)
        assert should_throttle is True

    def test_no_throttle_good_responses(self, limiter):
        """No throttling with good responses."""
        domain = "good.com"

        for _ in range(5):
            limiter.record_success(domain, response_time=0.3, status_code=200)

        should_throttle, _ = limiter.should_throttle(domain)
        assert should_throttle is False


class TestMetricsCleanup:
    """Tests for metrics cleanup."""

    def test_old_metrics_removed(self):
        """Old metrics are cleaned up."""
        config = RateLimitConfig(adaptive_throttling=True)
        limiter = RateLimiter(config)
        domain = "test.com"

        # Add old metric (simulate old data)
        old_time = datetime.now() - timedelta(minutes=10)
        state = limiter.domains[domain]
        state.response_metrics.append(ResponseMetrics(
            timestamp=old_time,
            response_time=1.0,
            response_type=ServerResponseType.SUCCESS
        ))

        # Add new metric (should trigger cleanup)
        limiter.record_success(domain, response_time=0.5)

        # Old metric should be removed
        for metric in state.response_metrics:
            age = datetime.now() - metric.timestamp
            assert age.total_seconds() < 300  # 5 minutes


class TestGlobalRateLimiterEnhanced:
    """Tests for global rate limiter with enhanced features."""

    def test_singleton_preserves_metrics(self):
        """Singleton preserves response metrics."""
        reset_rate_limiter()

        limiter1 = get_rate_limiter()
        limiter1.record_success("test.com", response_time=0.5, status_code=200)

        limiter2 = get_rate_limiter()
        stats = limiter2.get_response_stats("test.com")
        assert stats["total_responses"] == 1

        reset_rate_limiter()
