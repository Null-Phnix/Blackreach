"""Tests for the adaptive browser router and bulk fetcher."""

import json
import os
import urllib.request
from urllib.parse import urlparse
import pytest

from blackreach.adaptive_browser import (
    BrowserRouter, BrowserMode, RoutePlan, get_router, scan_url,
    _KNOWN_HARD_SITES, _KNOWN_LIGHT_SITES, _require_web_url,
)
from blackreach.exceptions import NavigationError


class TestBrowserRouterInit:
    def test_router_creates_cache_dir(self, tmp_path):
        cache = tmp_path / "route_cache.json"
        router = BrowserRouter(cache_path=cache)
        assert cache.parent.exists()

    def test_singleton_router(self):
        r1 = get_router()
        r2 = get_router()
        assert r1 is r2


class TestStaticReputations:
    def test_known_light_domain(self):
        plan = scan_url("https://en.wikipedia.org/wiki/Artificial_intelligence")
        assert plan.mode == BrowserMode.LIGHTWEIGHT
        assert any("light-domain" in r for r in plan.reasons)

    def test_known_hard_domain(self):
        plan = scan_url("https://www.amazon.com")
        assert plan.mode == BrowserMode.FULL_STEALTH
        assert plan.confidence >= 0.5

    def test_api_endpoint_is_light(self):
        plan = scan_url("https://api.github.com/users/octocat")
        assert plan.mode == BrowserMode.LIGHTWEIGHT

    def test_auth_path_is_suspicious(self):
        plan = scan_url("https://example.com/login")
        # Auth path adds +0.3, but example.com has no probe response
        # so it lands at edge of lightweight/headless boundary
        assert plan.mode in (BrowserMode.LIGHTWEIGHT, BrowserMode.HEADLESS)
        assert any("auth-path" in r for r in plan.reasons)


class TestCaching:
    def test_cache_hit(self, tmp_path):
        cache = tmp_path / "route_cache.json"
        router = BrowserRouter(cache_path=cache, ttl_seconds=3600)
        plan1 = router.plan_for("https://example.com/foo")
        plan2 = router.plan_for("https://example.com/foo")
        assert plan1.mode == plan2.mode
        # Should have written cache
        assert cache.exists()

    def test_force_refresh_bypasses_cache(self, tmp_path):
        cache = tmp_path / "route_cache.json"
        router = BrowserRouter(cache_path=cache, ttl_seconds=3600)
        router.plan_for("https://example.com/bar")
        # Force refresh should still work (no assert needed, just no crash)
        router.plan_for("https://example.com/bar", force_refresh=True)


class TestScoreBoundaries:
    def test_score_ranges(self):
        router = BrowserRouter()
        # Very lightweight should be near 0 confidence
        assert router._mode_from_score(-0.5) == BrowserMode.LIGHTWEIGHT
        # Medium should be headless
        assert router._mode_from_score(0.5) == BrowserMode.HEADLESS
        # High should be full stealth
        assert router._mode_from_score(0.9) == BrowserMode.FULL_STEALTH

    def test_confidence_is_between_0_and_1(self):
        plan = scan_url("https://github.com")
        assert 0.0 <= plan.confidence <= 1.0

    def test_cost_estimates(self):
        router = BrowserRouter()
        assert router._estimate_cost(BrowserMode.LIGHTWEIGHT) < router._estimate_cost(BrowserMode.HEADLESS)
        assert router._estimate_cost(BrowserMode.HEADLESS) < router._estimate_cost(BrowserMode.FULL_STEALTH)


class TestNonWebUrls:
    def test_file_and_javascript_urls_are_rejected(self):
        with pytest.raises(NavigationError, match="Only http and https"):
            _require_web_url("file:///etc/passwd")
        with pytest.raises(NavigationError, match="Only http and https"):
            _require_web_url("javascript:alert(1)")
        _require_web_url("https://example.com/paper.pdf")

    def test_header_probe_does_not_read_local_files(self, tmp_path, monkeypatch):
        """file:// used to be opened by urllib during the route probe."""
        def refuse_open(*args, **kwargs):
            raise AssertionError(f"probe opened {args!r}")

        monkeypatch.setattr(urllib.request, "urlopen", refuse_open)
        router = BrowserRouter(cache_path=tmp_path / "route_cache.json")
        score, reasons = router._probe_headers("file:///etc/passwd")
        assert score == 0.5
        assert reasons == ["unsupported-scheme"]


class TestBulkFetcherImport:
    def test_fetch_result_exists(self):
        from blackreach.bulk_fetcher import FetchResult
        r = FetchResult(url="https://example.com", status=200, html="<html></html>")
        assert r.ok

    def test_fetch_result_text_content(self):
        from blackreach.bulk_fetcher import FetchResult
        r = FetchResult(url="https://example.com", status=200, html="<html><body>Hello</body></html>")
        text = r.text_content()
        assert "Hello" in text

    def test_fetch_result_extract_title(self):
        from blackreach.bulk_fetcher import FetchResult
        r = FetchResult(url="https://example.com", status=200, html="<html><head><title>Foo</title></head></html>")
        assert r.extract_title() == "Foo"
