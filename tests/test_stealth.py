"""
Unit tests for blackreach/stealth.py

Tests browser stealth and anti-detection features.
"""

import pytest
from blackreach.stealth import (
    Stealth,
    StealthConfig,
    USER_AGENTS,
    VIEWPORTS,
    BLOCKED_DOMAINS,
)


class TestStealthConfig:
    """Tests for StealthConfig."""

    def test_default_values(self):
        """StealthConfig has sensible defaults."""
        config = StealthConfig()
        assert config.min_delay > 0
        assert config.max_delay > config.min_delay
        assert isinstance(config.human_mouse, bool)
        assert isinstance(config.block_tracking, bool)

    def test_typing_speed_is_tuple(self):
        """Typing speed is a tuple of (min, max)."""
        config = StealthConfig()
        assert isinstance(config.typing_speed, tuple)
        assert len(config.typing_speed) == 2
        assert config.typing_speed[0] < config.typing_speed[1]

    def test_custom_proxy(self):
        """StealthConfig accepts proxy configuration."""
        config = StealthConfig(proxy="http://localhost:8080")
        assert config.proxy == "http://localhost:8080"


class TestUserAgents:
    """Tests for user agent rotation."""

    def test_user_agents_exist(self):
        """USER_AGENTS list is not empty."""
        assert len(USER_AGENTS) > 0

    def test_user_agents_are_strings(self):
        """All user agents are strings."""
        for ua in USER_AGENTS:
            assert isinstance(ua, str)
            assert len(ua) > 10

    def test_user_agents_contain_browser_info(self):
        """User agents contain browser identification."""
        for ua in USER_AGENTS:
            # Should contain browser or platform info
            assert any(x in ua for x in ['Mozilla', 'Chrome', 'Firefox', 'Safari', 'Edge'])


class TestViewports:
    """Tests for viewport sizes."""

    def test_viewports_exist(self):
        """VIEWPORTS list is not empty."""
        assert len(VIEWPORTS) > 0

    def test_viewports_have_dimensions(self):
        """All viewports have width and height."""
        for vp in VIEWPORTS:
            assert "width" in vp
            assert "height" in vp
            assert vp["width"] > 0
            assert vp["height"] > 0

    def test_common_resolutions_included(self):
        """Common screen resolutions are included."""
        widths = [vp["width"] for vp in VIEWPORTS]
        # Should include 1920x1080 (most common)
        assert 1920 in widths


class TestBlockedDomains:
    """Tests for tracking domain blocking."""

    def test_blocked_domains_exist(self):
        """BLOCKED_DOMAINS list is not empty."""
        assert len(BLOCKED_DOMAINS) > 0

    def test_common_trackers_blocked(self):
        """Common tracking domains are blocked."""
        blocked_str = " ".join(BLOCKED_DOMAINS).lower()
        assert "google-analytics" in blocked_str
        assert "facebook" in blocked_str or "doubleclick" in blocked_str


class TestStealth:
    """Tests for Stealth class."""

    def test_init_with_default_config(self):
        """Stealth initializes with default config."""
        stealth = Stealth()
        assert stealth.config is not None
        assert isinstance(stealth.config, StealthConfig)

    def test_init_with_custom_config(self):
        """Stealth accepts custom config."""
        config = StealthConfig(min_delay=2.0, max_delay=5.0)
        stealth = Stealth(config)
        assert stealth.config.min_delay == 2.0
        assert stealth.config.max_delay == 5.0

    def test_get_random_user_agent(self):
        """get_random_user_agent returns valid user agent."""
        stealth = Stealth()
        ua = stealth.get_random_user_agent()
        assert isinstance(ua, str)
        assert ua in USER_AGENTS

    def test_get_random_viewport(self):
        """get_random_viewport returns valid viewport."""
        stealth = Stealth()
        vp = stealth.get_random_viewport()
        assert "width" in vp
        assert "height" in vp

    def test_random_delay_within_bounds(self):
        """random_delay returns value within configured bounds."""
        config = StealthConfig(min_delay=1.0, max_delay=2.0)
        stealth = Stealth(config)
        for _ in range(10):
            delay = stealth.random_delay()
            assert 1.0 <= delay <= 2.0

    def test_typing_delay_reasonable(self):
        """typing_delay returns reasonable values."""
        stealth = Stealth()
        for _ in range(10):
            delay = stealth.typing_delay()
            assert 0 < delay < 1.0  # Should be less than 1 second per character

    def test_should_block_url_tracking(self):
        """should_block_url blocks tracking domains."""
        stealth = Stealth(StealthConfig(block_tracking=True))
        assert stealth.should_block_url("https://google-analytics.com/collect")
        assert stealth.should_block_url("https://www.facebook.net/pixel.js")

    def test_should_block_url_normal(self):
        """should_block_url allows normal domains."""
        stealth = Stealth(StealthConfig(block_tracking=True))
        assert not stealth.should_block_url("https://www.google.com")
        assert not stealth.should_block_url("https://example.com")

    def test_should_block_url_disabled(self):
        """should_block_url respects disabled setting."""
        stealth = Stealth(StealthConfig(block_tracking=False))
        assert not stealth.should_block_url("https://google-analytics.com/collect")

    def test_get_resource_types_to_block(self):
        """get_resource_types_to_block returns correct types."""
        config = StealthConfig(block_images=True, block_media=True, block_fonts=False)
        stealth = Stealth(config)
        blocked = stealth.get_resource_types_to_block()
        assert "image" in blocked
        assert "media" in blocked
        assert "font" not in blocked

    def test_get_resource_types_with_fonts_blocked(self):
        """get_resource_types_to_block includes fonts when configured."""
        config = StealthConfig(block_images=False, block_media=False, block_fonts=True)
        stealth = Stealth(config)
        blocked = stealth.get_resource_types_to_block()
        assert "font" in blocked
        assert "image" not in blocked

    def test_get_next_proxy_no_rotation(self):
        """get_next_proxy returns single proxy when no rotation."""
        config = StealthConfig(proxy="http://proxy.example.com:8080")
        stealth = Stealth(config)
        proxy = stealth.get_next_proxy()
        assert proxy == "http://proxy.example.com:8080"

    def test_get_next_proxy_with_rotation(self):
        """get_next_proxy cycles through proxy rotation list."""
        config = StealthConfig(proxy_rotation=[
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
            "http://proxy3.example.com:8080",
        ])
        stealth = Stealth(config)
        # First cycle through all proxies
        proxy1 = stealth.get_next_proxy()
        proxy2 = stealth.get_next_proxy()
        proxy3 = stealth.get_next_proxy()
        # Should cycle back
        proxy4 = stealth.get_next_proxy()

        assert proxy1 == "http://proxy1.example.com:8080"
        assert proxy2 == "http://proxy2.example.com:8080"
        assert proxy3 == "http://proxy3.example.com:8080"
        assert proxy4 == proxy1  # Cycles back


class TestBezierPath:
    """Tests for mouse path generation."""

    def test_bezier_path_endpoints(self):
        """Bezier path starts and ends at correct points."""
        stealth = Stealth()
        start = (0, 0)
        end = (100, 100)
        path = stealth.generate_bezier_path(start, end, num_points=10)

        # Should start near start point and end near end point
        assert len(path) == 11  # num_points + 1
        assert abs(path[0][0] - start[0]) < 1
        assert abs(path[0][1] - start[1]) < 1
        assert abs(path[-1][0] - end[0]) < 1
        assert abs(path[-1][1] - end[1]) < 1

    def test_bezier_path_not_straight(self):
        """Bezier path is not a straight line."""
        stealth = Stealth()
        path = stealth.generate_bezier_path((0, 0), (100, 100), num_points=20)

        # At least some middle points should deviate from straight line
        # A straight line would have all points on y=x
        deviations = [abs(p[0] - p[1]) for p in path[5:-5]]
        max_deviation = max(deviations)
        assert max_deviation > 0  # Some curve exists


class TestScrollPattern:
    """Tests for scroll pattern generation."""

    def test_scroll_pattern_sums_to_distance(self):
        """Scroll pattern sums to requested distance."""
        stealth = Stealth()
        total_distance = 1000
        scrolls = stealth.generate_scroll_pattern(total_distance)
        assert sum(scrolls) == total_distance

    def test_scroll_pattern_negative(self):
        """Scroll pattern handles negative distances."""
        stealth = Stealth()
        total_distance = -500
        scrolls = stealth.generate_scroll_pattern(total_distance)
        assert sum(scrolls) == total_distance
        assert all(s < 0 for s in scrolls)


class TestStealthScripts:
    """Tests for stealth JavaScript scripts."""

    def test_get_stealth_scripts_not_empty(self):
        """get_stealth_scripts returns scripts."""
        stealth = Stealth()
        scripts = stealth.get_stealth_scripts()
        assert len(scripts) > 0

    def test_scripts_contain_javascript(self):
        """Scripts contain valid JavaScript patterns."""
        stealth = Stealth()
        scripts = stealth.get_stealth_scripts()
        for script in scripts:
            # Should contain JS patterns
            assert any(x in script for x in ['Object.defineProperty', 'window.', 'navigator.'])

    def test_get_all_stealth_scripts(self):
        """get_all_stealth_scripts includes all script types."""
        stealth = Stealth()
        all_scripts = stealth.get_all_stealth_scripts()
        # Should have basic + canvas + webgl + audio + font + timezone
        assert len(all_scripts) > 5
