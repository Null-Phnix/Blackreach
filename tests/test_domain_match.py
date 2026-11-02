"""Tests for label-aware hostname matching and the call sites that use it.

Each call-site test below failed before the fix: the old code used plain
substring checks (``"google.com" in url``) which matched lookalike hosts and
domains buried in query strings.
"""

import pytest

from blackreach.detection import SiteDetector, SiteType, get_site_characteristics
from blackreach.domain_match import best_host_match, host_matches, hostname_of
from blackreach.rate_limiter import RateLimiter
from blackreach.search_intel import ResultAnalyzer, SearchEngine, SearchQuery, SearchResult
from blackreach.site_handlers import (
    GitHubHandler,
    GoogleHandler,
    LibGenHandler,
    WikipediaHandler,
    get_handler_for_url,
)


class TestHostnameOf:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("https://Api.GitHub.com/repos", "api.github.com"),
            ("github.com:443", "github.com"),
            ("github.com", "github.com"),
            ("https://github.com./x", "github.com"),
            ("https://user:pw@github.com/", "github.com"),
            ("", ""),
        ],
    )
    def test_extracts_host(self, value, expected):
        assert hostname_of(value) == expected


class TestHostMatches:
    @pytest.mark.parametrize(
        "url,pattern",
        [
            ("https://github.com/x", "github.com"),
            ("https://api.github.com/x", "github.com"),
            ("github.com", "github.com"),
            ("https://libgen.is/search", "libgen"),
            ("https://annas-archive.org/", "annas-archive"),
        ],
    )
    def test_matches(self, url, pattern):
        assert host_matches(url, pattern)

    @pytest.mark.parametrize(
        "url,pattern",
        [
            ("https://notgithub.com/", "github.com"),
            ("https://github.com.evil.io/", "github.com"),
            ("https://evil.io/?next=github.com", "github.com"),
            ("https://evil.io/github.com/page", "github.com"),
            ("https://mylibgen.is/", "libgen"),
            ("", "github.com"),
        ],
    )
    def test_rejects(self, url, pattern):
        assert not host_matches(url, pattern)

    def test_best_match_prefers_most_specific(self):
        assert best_host_match("api.github.com", ["github.com", "api.github.com"]) == "api.github.com"
        assert best_host_match("github.com", ["github.com", "api.github.com"]) == "github.com"
        assert best_host_match("gitlab.com", ["github.com"]) is None


class TestRateLimiterKnownLimits:
    def test_subdomain_gets_its_own_limit(self):
        # github.com (60) is listed before api.github.com (30); the old loop
        # returned the first substring hit, so the API got the web limit.
        limiter = RateLimiter()
        assert limiter._get_rate_limit("api.github.com") == 30.0
        assert limiter._get_rate_limit("github.com") == 60.0

    def test_lookalike_domain_gets_default(self):
        limiter = RateLimiter()
        default = limiter._get_rate_limit("example.org")
        assert limiter._get_rate_limit("notgoogle.com") == default


class TestSiteCharacteristics:
    def test_lookalike_is_unknown(self):
        assert get_site_characteristics("https://notgithub.com/").site_type == SiteType.UNKNOWN

    def test_real_and_subdomain_match(self):
        assert get_site_characteristics("https://github.com/").site_type != SiteType.UNKNOWN
        assert get_site_characteristics("https://en.wikipedia.org/wiki/X").site_type != SiteType.UNKNOWN

    def test_most_specific_pattern_wins(self):
        # scholar.google.com has its own entry and must not get google.com's.
        from blackreach.detection import STATIC_SITE_PATTERNS

        assert (
            get_site_characteristics("https://scholar.google.com/x")
            is STATIC_SITE_PATTERNS["scholar.google.com"]
        )


class TestDetectorHostChecks:
    def test_search_block_ignores_engine_in_query_string(self):
        detector = SiteDetector()
        result = detector.detect_search_block(
            "<html><body>hi</body></html>",
            url="https://example.com/landing?ref=google.com",
        )
        assert not result.detected

    def test_search_block_still_checks_real_engine(self):
        detector = SiteDetector()
        result = detector.detect_search_block(
            "<html><body>hi</body></html>",
            url="https://duckduckgo.com/html/?q=x",
            status_code=418,
        )
        assert result.detected

    def test_landing_domain_requires_host_match(self):
        detector = SiteDetector()
        page = "<html><body>nothing here</body></html>"
        real = detector.detect_download_landing(page, url="https://www.mediafire.com/file/abc")
        fake = detector.detect_download_landing(page, url="https://example.com/?from=mediafire.com")
        assert any("Known landing domain" in i for i in real.indicators)
        assert not any("Known landing domain" in i for i in fake.indicators)


class TestSiteHandlerMatching:
    def test_handlers_match_real_hosts(self):
        assert GitHubHandler.matches("https://github.com/a/b")
        assert GoogleHandler.matches("https://www.google.com/search?q=x")
        assert GoogleHandler.matches("https://www.google.co.uk/search?q=x")
        assert WikipediaHandler.matches("https://en.m.wikipedia.org/wiki/X")
        assert LibGenHandler.matches("https://libgen.rs/search.php?req=x")

    def test_handlers_reject_lookalikes(self):
        assert not GitHubHandler.matches("https://notgithub.com/a/b")
        assert not GitHubHandler.matches("https://evil.io/?u=github.com")
        assert not GoogleHandler.matches("https://notgoogle.com/")

    def test_query_string_does_not_pick_handler(self):
        handler = get_handler_for_url("https://example.com/?ref=github.com")
        assert not isinstance(handler, GitHubHandler)


class TestTrustedDomainBoost:
    def _score(self, url):
        intel = ResultAnalyzer()
        query = SearchQuery(original="x", query="x", engine=SearchEngine.DUCKDUCKGO)
        result = SearchResult(title="t", url=url, snippet="s", position=1, relevance_score=0.0)
        return intel.analyze_result(result, query, content_type="paper")

    def test_boost_needs_host_match(self):
        assert self._score("https://arxiv.org/abs/1") > self._score("https://example.com/?arxiv.org")

    def test_scholar_still_trusted(self):
        assert self._score("https://scholar.google.com/x") > self._score("https://example.com/x")
