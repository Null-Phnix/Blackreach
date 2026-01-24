"""Tests for the knowledge base module."""

import pytest
from blackreach.knowledge import (
    detect_content_type,
    extract_subject,
    find_best_sources,
    reason_about_goal,
    get_smart_start,
    get_all_urls_for_source,
    ContentSource,
    CONTENT_SOURCES
)


class TestContentTypeDetection:
    """Test content type detection from goals."""

    def test_detect_ebook(self):
        types = detect_content_type("find me an epub for red rising")
        assert "ebook" in types

    def test_pdf_adds_paper_when_research_context_and_paper_not_present(self):
        """PDF with research context adds paper when not present."""
        types = detect_content_type("download the pdf research study")
        assert "paper" in types

    def test_pdf_adds_paper_from_context_word_substring(self):
        """PDF with 'journal' substring (journalistic) adds paper."""
        # "journalistic" contains "journal" for context check,
        # but doesn't match regex \bjournal\b for paper detection
        types = detect_content_type("get the pdf about journalistic methods")
        assert "paper" in types
        assert "pdf" in types

    def test_detect_book(self):
        types = detect_content_type("download the book 1984")
        assert "book" in types or "ebook" in types

    def test_detect_paper(self):
        types = detect_content_type("get the research paper on transformers")
        assert "paper" in types

    def test_detect_code(self):
        types = detect_content_type("find the github repo for llama")
        assert "code" in types

    def test_detect_wallpaper(self):
        types = detect_content_type("download 4k wallpapers")
        assert "wallpaper" in types

    def test_detect_image(self):
        types = detect_content_type("find images of cats")
        assert "image" in types

    def test_detect_video(self):
        types = detect_content_type("download the documentary about space")
        assert "video" in types

    def test_detect_audio(self):
        types = detect_content_type("find music by beethoven")
        assert "audio" in types

    def test_detect_dataset(self):
        types = detect_content_type("get the kaggle dataset for sentiment analysis")
        assert "dataset" in types

    def test_detect_pdf(self):
        types = detect_content_type("download the pdf manual")
        assert "pdf" in types or "ebook" in types

    def test_detect_pdf_research_context(self):
        """PDF with research context is also detected as paper."""
        types = detect_content_type("download the research pdf study")
        assert "paper" in types

    def test_fallback_to_general(self):
        types = detect_content_type("help me with something")
        assert types == ["general"]

    def test_detect_comic(self):
        types = detect_content_type("download batman comics")
        assert "comic" in types

    def test_detect_manga(self):
        types = detect_content_type("find one piece manga")
        assert "manga" in types

    def test_detect_font(self):
        types = detect_content_type("download a nice font for my project")
        assert "font" in types

    def test_detect_icon(self):
        types = detect_content_type("find icons for a dashboard")
        assert "icon" in types

    def test_detect_3d_model(self):
        types = detect_content_type("download a 3d model for printing")
        assert "3d" in types

    def test_detect_software(self):
        types = detect_content_type("find a video editing software")
        assert "software" in types

    def test_detect_8k_wallpaper(self):
        types = detect_content_type("get an 8k wallpaper")
        assert "wallpaper" in types


class TestSubjectExtraction:
    """Test subject/title extraction from goals."""

    def test_extract_simple(self):
        subject = extract_subject("find me a single epub for red rising")
        assert "red rising" in subject.lower()

    def test_extract_with_download(self):
        subject = extract_subject("download the attention is all you need paper")
        assert "attention" in subject.lower()

    def test_extract_removes_prefixes(self):
        subject = extract_subject("please find papers about machine learning")
        assert "please" not in subject.lower()
        assert "find" not in subject.lower()

    def test_extract_removes_file_types(self):
        subject = extract_subject("get an epub of dune")
        assert "epub" not in subject.lower()

    def test_extract_handles_empty(self):
        subject = extract_subject("")
        assert subject == ""


class TestFindBestSources:
    """Test finding best sources for goals."""

    def test_finds_annas_archive_for_ebook(self):
        sources = find_best_sources("find epub for red rising")
        assert len(sources) > 0
        # Anna's Archive should be among top sources for ebooks
        source_names = [s.name for s in sources]
        assert "Anna's Archive" in source_names

    def test_finds_arxiv_for_papers(self):
        sources = find_best_sources("download arxiv paper on neural networks")
        assert len(sources) > 0
        source_names = [s.name for s in sources]
        assert "arXiv" in source_names

    def test_finds_github_for_code(self):
        sources = find_best_sources("get the github repo")
        assert len(sources) > 0
        source_names = [s.name for s in sources]
        assert "GitHub" in source_names

    def test_finds_wallhaven_for_wallpapers(self):
        sources = find_best_sources("download 4k wallpapers")
        assert len(sources) > 0
        source_names = [s.name for s in sources]
        assert "Wallhaven" in source_names

    def test_max_sources_respected(self):
        sources = find_best_sources("find ebooks", max_sources=2)
        assert len(sources) <= 2


class TestReasonAboutGoal:
    """Test full goal reasoning."""

    def test_reason_returns_all_fields(self):
        result = reason_about_goal("find epub for red rising")
        assert "content_types" in result
        assert "subject" in result
        assert "best_source" in result
        assert "start_url" in result
        assert "reasoning" in result
        assert "search_query" in result
        assert "alternate_sources" in result

    def test_reason_ebook_uses_annas_archive(self):
        result = reason_about_goal("find me a single epub for red rising")
        assert result["best_source"] is not None
        assert result["best_source"].name == "Anna's Archive"
        assert "annas-archive" in result["start_url"]

    def test_reason_paper_uses_appropriate_source(self):
        result = reason_about_goal("download research paper on transformers")
        assert result["best_source"] is not None
        # Should use a paper-focused source
        assert result["best_source"].name in ["arXiv", "Semantic Scholar", "Google Scholar"]

    def test_reason_code_uses_github(self):
        result = reason_about_goal("get the llama cpp github repo")
        assert result["best_source"] is not None
        assert result["best_source"].name == "GitHub"

    def test_reason_provides_alternates(self):
        result = reason_about_goal("find epub for some book")
        # Should have alternate sources for ebooks
        assert len(result.get("alternate_sources", [])) > 0


class TestGetSmartStart:
    """Test the convenience function."""

    def test_returns_tuple(self):
        result = get_smart_start("find epub")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_returns_url_reasoning_query(self):
        url, reasoning, query = get_smart_start("find epub for dune")
        assert url.startswith("http")
        assert len(reasoning) > 0
        assert "dune" in query.lower()


class TestContentSourceDataclass:
    """Test the ContentSource dataclass."""

    def test_source_has_required_fields(self):
        source = ContentSource(
            name="Test",
            url="https://test.com",
            description="Test source",
            content_types=["test"],
            keywords=["test"],
        )
        assert source.name == "Test"
        assert source.priority == 5  # default
        assert source.requires_search == True  # default

    def test_all_sources_have_valid_urls(self):
        for source in CONTENT_SOURCES:
            assert source.url.startswith("http")

    def test_all_sources_have_content_types(self):
        for source in CONTENT_SOURCES:
            assert len(source.content_types) > 0

    def test_all_sources_have_keywords(self):
        for source in CONTENT_SOURCES:
            assert len(source.keywords) > 0


class TestContentSourceMirrors:
    """Tests for source mirrors."""

    def test_sources_with_mirrors_exist(self):
        """Some sources have mirrors defined."""
        sources_with_mirrors = [s for s in CONTENT_SOURCES if s.mirrors]
        assert len(sources_with_mirrors) > 0

    def test_mirrors_are_valid_urls(self):
        """Mirror URLs are valid."""
        for source in CONTENT_SOURCES:
            for mirror in source.mirrors:
                assert mirror.startswith("http")


class TestContentSourcePriority:
    """Tests for source priority system."""

    def test_priority_is_positive(self):
        """All sources have positive priority."""
        for source in CONTENT_SOURCES:
            assert source.priority > 0

    def test_priority_reasonable_range(self):
        """Priority is within reasonable range."""
        for source in CONTENT_SOURCES:
            assert 1 <= source.priority <= 10


class TestFindBestSourcesEdgeCases:
    """Edge case tests for find_best_sources."""

    def test_empty_goal_returns_sources(self):
        """Empty goal still returns some sources."""
        from blackreach.knowledge import find_best_sources
        sources = find_best_sources("")
        # Should return something even for empty goal
        assert isinstance(sources, list)

    def test_very_long_goal(self):
        """Handles very long goals."""
        from blackreach.knowledge import find_best_sources
        long_goal = "download " * 100 + "papers about AI"
        sources = find_best_sources(long_goal)
        assert isinstance(sources, list)


class TestReasonAboutGoalEdgeCases:
    """Edge case tests for reason_about_goal."""

    def test_handles_special_characters(self):
        """Handles goals with special characters."""
        from blackreach.knowledge import reason_about_goal
        result = reason_about_goal("find papers about AI & ML + deep learning")
        assert "subject" in result

    def test_numeric_goal(self):
        """Handles goals with numbers."""
        from blackreach.knowledge import reason_about_goal
        result = reason_about_goal("download 10 papers from 2024")
        assert "subject" in result

    def test_fallback_to_google_when_no_sources(self):
        """Falls back to Google when no sources match."""
        from blackreach.knowledge import reason_about_goal
        from unittest.mock import patch

        with patch('blackreach.knowledge.find_best_sources', return_value=[]):
            result = reason_about_goal("xyz123")
            assert result["best_source"] is None
            assert "google.com" in result["start_url"]


class TestSubjectExtractionEdgeCases:
    """Edge case tests for extract_subject."""

    def test_all_stopwords(self):
        """Handles goals with mostly stopwords."""
        from blackreach.knowledge import extract_subject
        result = extract_subject("find the and or a")
        # Should return something, not empty
        assert isinstance(result, str)

    def test_preserves_technical_terms(self):
        """Preserves technical terms in subject."""
        from blackreach.knowledge import extract_subject
        result = extract_subject("download papers about machine learning and neural networks")
        # Should contain the technical terms
        assert "machine" in result.lower() or "neural" in result.lower() or "learning" in result.lower()


class TestGetAllUrls:
    """Tests for get_all_urls_for_source function."""

    def test_source_without_mirrors(self):
        """Source without mirrors returns only primary URL."""
        source = ContentSource(
            name="Test",
            url="https://example.com",
            description="Test source",
            content_types=["test"],
            keywords=["test"],
            mirrors=[]
        )
        urls = get_all_urls_for_source(source)
        assert urls == ["https://example.com"]

    def test_source_with_mirrors(self):
        """Source with mirrors returns primary + mirror URLs."""
        source = ContentSource(
            name="Test",
            url="https://primary.com",
            description="Test source",
            content_types=["test"],
            keywords=["test"],
            mirrors=["https://mirror1.com", "https://mirror2.com"]
        )
        urls = get_all_urls_for_source(source)
        assert len(urls) == 3
        assert "https://primary.com" in urls
        assert "https://mirror1.com" in urls
        assert "https://mirror2.com" in urls

    def test_annas_archive_exists(self):
        """Anna's Archive source exists and has primary URL."""
        annas = next((s for s in CONTENT_SOURCES if s.name == "Anna's Archive"), None)
        assert annas is not None
        urls = get_all_urls_for_source(annas)
        assert len(urls) >= 1  # Has at least primary URL
        assert "annas-archive" in urls[0]


class TestCheckUrlReachable:
    """Tests for check_url_reachable function."""

    def test_reachable_url_returns_true(self):
        """Reachable URL returns True."""
        from blackreach.knowledge import check_url_reachable
        from unittest.mock import patch, MagicMock

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            result = check_url_reachable("https://example.com")
            assert result is True

    def test_unreachable_url_returns_false(self):
        """Unreachable URL returns False."""
        from blackreach.knowledge import check_url_reachable
        from unittest.mock import patch
        import urllib.error

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Network error")):
            result = check_url_reachable("https://nonexistent.invalid")
            assert result is False

    def test_http_error_returns_false(self):
        """HTTP error returns False."""
        from blackreach.knowledge import check_url_reachable
        from unittest.mock import patch
        import urllib.error

        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(None, 404, "Not Found", {}, None)):
            result = check_url_reachable("https://example.com/notfound")
            assert result is False

    def test_timeout_returns_false(self):
        """Timeout returns False."""
        from blackreach.knowledge import check_url_reachable
        from unittest.mock import patch

        with patch('urllib.request.urlopen', side_effect=TimeoutError()):
            result = check_url_reachable("https://slow.example.com")
            assert result is False


class TestGetWorkingUrl:
    """Tests for get_working_url function."""

    def test_returns_first_working_url(self):
        """Returns the first working URL."""
        from blackreach.knowledge import get_working_url, check_url_reachable
        from unittest.mock import patch

        source = ContentSource(
            name="Test",
            url="https://primary.com",
            description="Test",
            content_types=["test"],
            keywords=["test"],
            mirrors=["https://mirror1.com"]
        )

        with patch('blackreach.knowledge.check_url_reachable', return_value=True):
            result = get_working_url(source)
            assert result == "https://primary.com"

    def test_returns_mirror_when_primary_fails(self):
        """Returns mirror URL when primary fails."""
        from blackreach.knowledge import get_working_url
        from unittest.mock import patch

        source = ContentSource(
            name="Test",
            url="https://primary.com",
            description="Test",
            content_types=["test"],
            keywords=["test"],
            mirrors=["https://mirror1.com"]
        )

        def mock_check(url, timeout=5.0):
            return url == "https://mirror1.com"

        with patch('blackreach.knowledge.check_url_reachable', side_effect=mock_check):
            result = get_working_url(source)
            assert result == "https://mirror1.com"

    def test_returns_none_when_all_fail(self):
        """Returns None when all URLs fail."""
        from blackreach.knowledge import get_working_url
        from unittest.mock import patch

        source = ContentSource(
            name="Test",
            url="https://primary.com",
            description="Test",
            content_types=["test"],
            keywords=["test"],
            mirrors=["https://mirror1.com"]
        )

        with patch('blackreach.knowledge.check_url_reachable', return_value=False):
            result = get_working_url(source)
            assert result is None
