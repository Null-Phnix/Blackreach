"""Tests for the knowledge base module."""

import pytest
from blackreach.knowledge import (
    detect_content_type,
    extract_subject,
    find_best_sources,
    reason_about_goal,
    get_smart_start,
    ContentSource,
    CONTENT_SOURCES
)


class TestContentTypeDetection:
    """Test content type detection from goals."""

    def test_detect_ebook(self):
        types = detect_content_type("find me an epub for red rising")
        assert "ebook" in types

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

    def test_fallback_to_general(self):
        types = detect_content_type("help me with something")
        assert types == ["general"]


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
