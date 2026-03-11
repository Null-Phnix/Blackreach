"""
Unit tests for blackreach/site_handlers.py

Tests site-specific handlers for various websites.
"""

import pytest
from blackreach.site_handlers import (
    SiteHandler,
    SiteAction,
    HandlerResult,
    AnnasArchiveHandler,
    LibGenHandler,
    ZLibraryHandler,
    GoogleHandler,
    ArxivHandler,
    WallhavenHandler,
    UnsplashHandler,
    GitHubHandler,
    WikipediaHandler,
    DuckDuckGoHandler,
    RedditHandler,
    YouTubeHandler,
    StackOverflowHandler,
    PexelsHandler,
    PixabayHandler,
    AmazonHandler,
    HuggingFaceHandler,
    get_handler_for_url,
    get_site_hints,
    get_download_sequence,
    get_search_sequence,
    SITE_HANDLERS,
)


class TestSiteHandlerRegistry:
    """Tests for the site handler registry."""

    def test_registry_not_empty(self):
        """Registry should have handlers."""
        assert len(SITE_HANDLERS) > 0

    def test_all_handlers_registered(self):
        """All handler classes should be in registry."""
        expected = [
            AnnasArchiveHandler,
            LibGenHandler,
            ZLibraryHandler,
            GoogleHandler,
            ArxivHandler,
            WallhavenHandler,
            UnsplashHandler,
            GitHubHandler,
            WikipediaHandler,
            DuckDuckGoHandler,
            RedditHandler,
            YouTubeHandler,
            StackOverflowHandler,
            PexelsHandler,
            PixabayHandler,
            AmazonHandler,
            HuggingFaceHandler,
        ]
        for handler_class in expected:
            assert handler_class in SITE_HANDLERS


class TestGetHandlerForUrl:
    """Tests for get_handler_for_url function."""

    def test_annas_archive(self):
        """Should return AnnasArchiveHandler for Anna's Archive URLs."""
        handler = get_handler_for_url("https://annas-archive.org/search")
        assert handler is not None
        assert isinstance(handler, AnnasArchiveHandler)

    def test_libgen(self):
        """Should return LibGenHandler for LibGen URLs."""
        handler = get_handler_for_url("https://libgen.is/search.php")
        assert handler is not None
        assert isinstance(handler, LibGenHandler)

    def test_google(self):
        """Should return GoogleHandler for Google URLs."""
        handler = get_handler_for_url("https://www.google.com/search?q=test")
        assert handler is not None
        assert isinstance(handler, GoogleHandler)

    def test_github(self):
        """Should return GitHubHandler for GitHub URLs."""
        handler = get_handler_for_url("https://github.com/anthropics/claude")
        assert handler is not None
        assert isinstance(handler, GitHubHandler)

    def test_wikipedia(self):
        """Should return WikipediaHandler for Wikipedia URLs."""
        handler = get_handler_for_url("https://en.wikipedia.org/wiki/Python")
        assert handler is not None
        assert isinstance(handler, WikipediaHandler)

    def test_duckduckgo(self):
        """Should return DuckDuckGoHandler for DuckDuckGo URLs."""
        handler = get_handler_for_url("https://duckduckgo.com/?q=test")
        assert handler is not None
        assert isinstance(handler, DuckDuckGoHandler)

    def test_reddit(self):
        """Should return RedditHandler for Reddit URLs."""
        handler = get_handler_for_url("https://www.reddit.com/r/python")
        assert handler is not None
        assert isinstance(handler, RedditHandler)

    def test_youtube(self):
        """Should return YouTubeHandler for YouTube URLs."""
        handler = get_handler_for_url("https://www.youtube.com/watch?v=test")
        assert handler is not None
        assert isinstance(handler, YouTubeHandler)

    def test_stackoverflow(self):
        """Should return StackOverflowHandler for Stack Overflow URLs."""
        handler = get_handler_for_url("https://stackoverflow.com/questions/123")
        assert handler is not None
        assert isinstance(handler, StackOverflowHandler)

    def test_arxiv(self):
        """Should return ArxivHandler for arXiv URLs."""
        handler = get_handler_for_url("https://arxiv.org/abs/2301.00001")
        assert handler is not None
        assert isinstance(handler, ArxivHandler)

    def test_wallhaven(self):
        """Should return WallhavenHandler for Wallhaven URLs."""
        handler = get_handler_for_url("https://wallhaven.cc/search?q=nature")
        assert handler is not None
        assert isinstance(handler, WallhavenHandler)

    def test_unsplash(self):
        """Should return UnsplashHandler for Unsplash URLs."""
        handler = get_handler_for_url("https://unsplash.com/photos/abc")
        assert handler is not None
        assert isinstance(handler, UnsplashHandler)

    def test_pexels(self):
        """Should return PexelsHandler for Pexels URLs."""
        handler = get_handler_for_url("https://www.pexels.com/search/nature")
        assert handler is not None
        assert isinstance(handler, PexelsHandler)

    def test_pixabay(self):
        """Should return PixabayHandler for Pixabay URLs."""
        handler = get_handler_for_url("https://pixabay.com/images/search/nature")
        assert handler is not None
        assert isinstance(handler, PixabayHandler)

    def test_amazon(self):
        """Should return AmazonHandler for Amazon URLs."""
        handler = get_handler_for_url("https://www.amazon.com/s?k=python")
        assert handler is not None
        assert isinstance(handler, AmazonHandler)

    def test_huggingface(self):
        """Should return HuggingFaceHandler for Hugging Face URLs."""
        handler = get_handler_for_url("https://huggingface.co/models")
        assert handler is not None
        assert isinstance(handler, HuggingFaceHandler)

    def test_unknown_url(self):
        """Should return None for unknown URLs."""
        handler = get_handler_for_url("https://example.com/unknown")
        assert handler is None


class TestSiteAction:
    """Tests for SiteAction dataclass."""

    def test_default_values(self):
        """SiteAction has correct defaults."""
        action = SiteAction(
            action_type="click",
            target="button",
            description="Click button"
        )
        assert action.wait_after == 0.5
        assert action.optional is False

    def test_custom_values(self):
        """SiteAction accepts custom values."""
        action = SiteAction(
            action_type="type",
            target="input",
            description="Type text",
            wait_after=1.0,
            optional=True
        )
        assert action.action_type == "type"
        assert action.target == "input"
        assert action.wait_after == 1.0
        assert action.optional is True


class TestAnnasArchiveHandler:
    """Tests for AnnasArchiveHandler."""

    def test_matches_annas_archive(self):
        """Should match Anna's Archive URLs."""
        assert AnnasArchiveHandler.matches("https://annas-archive.org/md5/123")
        assert AnnasArchiveHandler.matches("https://annas-archive.se/search")

    def test_get_download_actions_md5_page(self):
        """Should return download actions for md5 page."""
        handler = AnnasArchiveHandler()
        actions = handler.get_download_actions("", "https://annas-archive.org/md5/123")
        assert len(actions) > 0
        assert any("download" in a.description.lower() for a in actions)

    def test_get_search_actions(self):
        """Should return search actions."""
        handler = AnnasArchiveHandler()
        actions = handler.get_search_actions("python book")
        assert len(actions) > 0
        assert any("type" in a.action_type for a in actions)


class TestGitHubHandler:
    """Tests for GitHubHandler."""

    def test_matches_github(self):
        """Should match GitHub URLs."""
        assert GitHubHandler.matches("https://github.com/user/repo")
        assert GitHubHandler.matches("https://github.com/user/repo/releases")

    def test_get_download_actions_releases(self):
        """Should return download actions for releases page."""
        handler = GitHubHandler()
        actions = handler.get_download_actions("", "https://github.com/user/repo/releases")
        assert len(actions) > 0

    def test_navigation_hints_releases(self):
        """Should provide hints for releases page."""
        handler = GitHubHandler()
        hints = handler.get_navigation_hints("", "https://github.com/user/repo/releases", "")
        assert "GITHUB RELEASES" in hints


class TestWikipediaHandler:
    """Tests for WikipediaHandler."""

    def test_matches_wikipedia(self):
        """Should match Wikipedia URLs."""
        assert WikipediaHandler.matches("https://en.wikipedia.org/wiki/Python")
        assert WikipediaHandler.matches("https://en.m.wikipedia.org/wiki/Python")

    def test_navigation_hints_article(self):
        """Should provide hints for article pages."""
        handler = WikipediaHandler()
        hints = handler.get_navigation_hints("", "https://en.wikipedia.org/wiki/Python", "")
        assert "WIKIPEDIA ARTICLE" in hints


class TestGoogleHandler:
    """Tests for GoogleHandler."""

    def test_matches_google(self):
        """Should match Google URLs."""
        assert GoogleHandler.matches("https://www.google.com/search?q=test")
        assert GoogleHandler.matches("https://google.com")

    def test_navigation_hints_search(self):
        """Should provide hints for search results."""
        handler = GoogleHandler()
        hints = handler.get_navigation_hints("", "https://www.google.com/search?q=test", "")
        assert "GOOGLE RESULTS" in hints


class TestGetSiteHints:
    """Tests for get_site_hints function."""

    def test_returns_hints_for_known_site(self):
        """Should return hints for known sites."""
        hints = get_site_hints("https://github.com/user/repo/releases", "", "")
        assert hints != ""

    def test_returns_empty_for_unknown_site(self):
        """Should return empty string for unknown sites."""
        hints = get_site_hints("https://example.com/page", "", "")
        assert hints == ""


class TestGetDownloadSequence:
    """Tests for get_download_sequence function."""

    def test_returns_actions_for_known_site(self):
        """Should return actions for sites with downloads."""
        actions = get_download_sequence("https://annas-archive.org/md5/123", "")
        assert len(actions) > 0

    def test_returns_empty_for_no_download_site(self):
        """Should return empty for sites without downloads."""
        actions = get_download_sequence("https://www.youtube.com/watch?v=test", "")
        assert len(actions) == 0


class TestGetSearchSequence:
    """Tests for get_search_sequence function."""

    def test_returns_actions_for_search_site(self):
        """Should return search actions for search engines."""
        actions = get_search_sequence("https://www.google.com", "test query")
        assert len(actions) > 0

    def test_search_actions_include_type(self):
        """Search actions should include typing."""
        actions = get_search_sequence("https://duckduckgo.com", "test query")
        assert any(a.action_type == "type" for a in actions)


class TestHandlerResult:
    """Tests for HandlerResult dataclass."""

    def test_default_values(self):
        """HandlerResult has correct defaults."""
        result = HandlerResult(success=True, message="OK")
        assert result.actions_taken == []
        assert result.download_url is None
        assert result.next_step is None
        assert result.data == {}

    def test_custom_values(self):
        """HandlerResult accepts custom values."""
        action = SiteAction("click", "button", "Click")
        result = HandlerResult(
            success=True,
            message="Done",
            actions_taken=[action],
            download_url="https://example.com/file.pdf",
            next_step="verify download"
        )
        assert len(result.actions_taken) == 1
        assert result.download_url == "https://example.com/file.pdf"


class TestAllHandlersHaveRequiredMethods:
    """Test that all handlers implement required methods."""

    @pytest.mark.parametrize("handler_class", SITE_HANDLERS)
    def test_handler_has_get_download_actions(self, handler_class):
        """Handler should have get_download_actions method."""
        handler = handler_class()
        assert hasattr(handler, "get_download_actions")
        assert callable(handler.get_download_actions)

    @pytest.mark.parametrize("handler_class", SITE_HANDLERS)
    def test_handler_has_get_search_actions(self, handler_class):
        """Handler should have get_search_actions method."""
        handler = handler_class()
        assert hasattr(handler, "get_search_actions")
        assert callable(handler.get_search_actions)

    @pytest.mark.parametrize("handler_class", SITE_HANDLERS)
    def test_handler_has_domains(self, handler_class):
        """Handler should have domains list."""
        assert hasattr(handler_class, "domains")
        assert isinstance(handler_class.domains, list)
        assert len(handler_class.domains) > 0
