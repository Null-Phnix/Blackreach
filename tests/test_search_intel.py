"""
Unit tests for blackreach/search_intel.py

Tests search query formulation, result analysis, and learning.
"""

import pytest
from blackreach.search_intel import (
    SearchEngine,
    SearchQuery,
    SearchResult,
    SearchSession,
    QueryFormulator,
    ResultAnalyzer,
    SearchIntelligence,
    get_search_intel,
)


class TestSearchEngine:
    """Tests for SearchEngine enum."""

    def test_all_engines_exist(self):
        """All expected search engines should exist."""
        assert SearchEngine.GOOGLE.value == "google"
        assert SearchEngine.DUCKDUCKGO.value == "duckduckgo"
        assert SearchEngine.BING.value == "bing"
        assert SearchEngine.SITE_SPECIFIC.value == "site_specific"


class TestSearchQuery:
    """Tests for SearchQuery dataclass."""

    def test_creation(self):
        """SearchQuery stores all fields."""
        query = SearchQuery(
            original="Download Python PDF",
            query="Python PDF download",
            engine=SearchEngine.GOOGLE,
            modifiers=["filetype:pdf"],
            alternatives=["Python ebook"]
        )
        assert query.original == "Download Python PDF"
        assert query.query == "Python PDF download"
        assert query.engine == SearchEngine.GOOGLE
        assert "filetype:pdf" in query.modifiers
        assert "Python ebook" in query.alternatives

    def test_default_lists(self):
        """SearchQuery has empty defaults for lists."""
        query = SearchQuery(
            original="test",
            query="test",
            engine=SearchEngine.GOOGLE
        )
        assert query.modifiers == []
        assert query.alternatives == []


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_creation(self):
        """SearchResult stores all fields."""
        result = SearchResult(
            title="Python Tutorial",
            url="https://example.com/python",
            snippet="Learn Python programming",
            position=1,
            relevance_score=0.8
        )
        assert result.title == "Python Tutorial"
        assert result.url == "https://example.com/python"
        assert result.position == 1
        assert result.relevance_score == 0.8
        assert result.clicked is False
        assert result.led_to_download is False

    def test_mark_clicked(self):
        """Can mark result as clicked."""
        result = SearchResult(
            title="Test",
            url="http://test.com",
            snippet="",
            position=1,
            relevance_score=0.5
        )
        result.clicked = True
        assert result.clicked is True


class TestSearchSession:
    """Tests for SearchSession dataclass."""

    def test_creation(self):
        """SearchSession stores query and defaults."""
        query = SearchQuery(original="test", query="test", engine=SearchEngine.GOOGLE)
        session = SearchSession(query=query)

        assert session.query == query
        assert session.results == []
        assert session.clicks == []
        assert session.successful is False


class TestQueryFormulator:
    """Tests for QueryFormulator class."""

    def test_init(self):
        """QueryFormulator initializes correctly."""
        formulator = QueryFormulator()
        assert formulator is not None

    def test_stop_words(self):
        """Stop words should be defined."""
        formulator = QueryFormulator()
        assert "the" in formulator.STOP_WORDS
        assert "download" in formulator.STOP_WORDS
        assert "please" in formulator.STOP_WORDS

    def test_formulate_basic_goal(self):
        """Should formulate query from basic goal."""
        formulator = QueryFormulator()
        query = formulator.formulate("download python tutorial")

        assert query is not None
        assert query.original == "download python tutorial"
        assert "python" in query.query.lower()
        assert "tutorial" in query.query.lower()

    def test_formulate_extracts_quoted_title(self):
        """Should extract quoted book titles."""
        formulator = QueryFormulator()
        query = formulator.formulate('Download "The Python Handbook" PDF')

        assert "The Python Handbook" in query.query

    def test_formulate_extracts_author(self):
        """Should extract author names."""
        formulator = QueryFormulator()
        extracted = formulator._extract_components("Book by John Smith 2023")

        assert "author" in extracted
        assert "John Smith" in extracted["author"]

    def test_formulate_extracts_year(self):
        """Should extract publication year."""
        formulator = QueryFormulator()
        extracted = formulator._extract_components("Book published in 2023")

        assert "year" in extracted
        assert extracted["year"] == "2023"

    def test_formulate_extracts_isbn(self):
        """Should extract ISBN numbers."""
        formulator = QueryFormulator()
        extracted = formulator._extract_components("ISBN: 9781234567890")

        assert "isbn" in extracted
        assert "9781234567890" in extracted["isbn"]

    def test_formulate_extracts_file_type(self):
        """Should extract file type."""
        formulator = QueryFormulator()
        extracted = formulator._extract_components("Download PDF book")

        assert "file_type" in extracted
        assert extracted["file_type"] == "pdf"

    def test_formulate_adds_modifiers(self):
        """Should add content type modifiers."""
        formulator = QueryFormulator()
        query = formulator.formulate("Python programming", content_type="ebook")

        # Should have some modifiers
        assert query.modifiers is not None

    def test_formulate_generates_alternatives(self):
        """Should generate alternative queries."""
        formulator = QueryFormulator()
        query = formulator.formulate("Python programming book")

        assert len(query.alternatives) > 0

    def test_record_and_get_proven_query(self):
        """Should record and retrieve successful queries."""
        formulator = QueryFormulator()
        formulator.record_success("python pdf download", "python book")

        proven = formulator.get_proven_query("python book")
        assert proven == "python pdf download"

    def test_record_failure(self):
        """Should record failed queries."""
        formulator = QueryFormulator()
        formulator.record_failure("bad query", "subject")

        assert "subject" in formulator.failed_queries
        assert "bad query" in formulator.failed_queries["subject"]


class TestResultAnalyzer:
    """Tests for ResultAnalyzer class."""

    def test_init(self):
        """ResultAnalyzer initializes correctly."""
        analyzer = ResultAnalyzer()
        assert analyzer is not None

    def test_quality_indicators_exist(self):
        """Quality indicators should be defined."""
        analyzer = ResultAnalyzer()
        assert "download" in analyzer.QUALITY_INDICATORS
        assert "pdf" in analyzer.QUALITY_INDICATORS

    def test_spam_indicators_exist(self):
        """Spam indicators should be defined."""
        analyzer = ResultAnalyzer()
        assert "signup" in analyzer.SPAM_INDICATORS
        assert "premium" in analyzer.SPAM_INDICATORS

    def test_analyze_result_neutral_baseline(self):
        """Analysis should start at neutral score."""
        analyzer = ResultAnalyzer()
        query = SearchQuery(original="test", query="test", engine=SearchEngine.GOOGLE)
        result = SearchResult(
            title="Generic Result",
            url="http://example.com",
            snippet="Generic content",
            position=10,
            relevance_score=0
        )

        score = analyzer.analyze_result(result, query)
        # Should be around 0.5 for neutral content
        assert 0.3 <= score <= 0.7

    def test_analyze_result_boosts_quality_indicators(self):
        """Should boost score for quality indicators."""
        analyzer = ResultAnalyzer()
        query = SearchQuery(original="test", query="python", engine=SearchEngine.GOOGLE)
        result = SearchResult(
            title="Free PDF Download",
            url="http://example.com/download",
            snippet="Official download page",
            position=1,
            relevance_score=0
        )

        score = analyzer.analyze_result(result, query)
        # Should be boosted for quality keywords
        assert score > 0.5

    def test_analyze_result_penalizes_spam(self):
        """Should penalize spam indicators."""
        analyzer = ResultAnalyzer()
        query = SearchQuery(original="test", query="test", engine=SearchEngine.GOOGLE)
        result = SearchResult(
            title="Premium Signup Required",
            url="http://spam.com/survey",
            snippet="Complete survey to download",
            position=1,
            relevance_score=0
        )

        score = analyzer.analyze_result(result, query)
        # Should be penalized for spam keywords
        assert score < 0.5

    def test_analyze_result_boosts_trusted_domains(self):
        """Should boost trusted domains."""
        analyzer = ResultAnalyzer()
        query = SearchQuery(original="test", query="test", engine=SearchEngine.GOOGLE)
        result = SearchResult(
            title="Python Book",
            url="http://archive.org/details/python-book",
            snippet="Download the book",
            position=5,
            relevance_score=0
        )

        score = analyzer.analyze_result(result, query, content_type="ebook")
        # archive.org is trusted for ebooks
        assert score > 0.5

    def test_rank_results(self):
        """Should rank results by relevance."""
        analyzer = ResultAnalyzer()
        query = SearchQuery(original="python", query="python", engine=SearchEngine.GOOGLE)

        results = [
            SearchResult(title="Spam Site", url="http://spam.com/survey",
                        snippet="Complete survey", position=1, relevance_score=0),
            SearchResult(title="Python PDF Download", url="http://good.com/download",
                        snippet="Free PDF download", position=2, relevance_score=0),
        ]

        ranked = analyzer.rank_results(results, query)

        # Good result should be first after ranking
        assert "download" in ranked[0].title.lower() or "download" in ranked[0].url.lower()

    def test_should_try_alternative_empty_results(self):
        """Should try alternative with empty results."""
        analyzer = ResultAnalyzer()
        assert analyzer.should_try_alternative([]) is True

    def test_should_try_alternative_poor_results(self):
        """Should try alternative with poor results."""
        analyzer = ResultAnalyzer()

        poor_results = [
            SearchResult(title="Bad", url="http://spam.com", snippet="",
                        position=1, relevance_score=0.2),
            SearchResult(title="Also Bad", url="http://spam2.com", snippet="",
                        position=2, relevance_score=0.3),
        ]

        assert analyzer.should_try_alternative(poor_results) is True


class TestSearchIntelligence:
    """Tests for SearchIntelligence class."""

    def test_init(self):
        """SearchIntelligence initializes correctly."""
        intel = SearchIntelligence()
        assert intel is not None
        assert intel.formulator is not None
        assert intel.analyzer is not None

    def test_create_search(self):
        """Should create search query from goal."""
        intel = SearchIntelligence()
        query = intel.create_search("download python book")

        assert query is not None
        assert query.original == "download python book"

    def test_get_search_url_google(self):
        """Should generate Google search URL."""
        intel = SearchIntelligence()
        query = SearchQuery(
            original="test",
            query="python book",
            engine=SearchEngine.GOOGLE
        )

        url = intel.get_search_url(query)
        assert "google.com" in url
        assert "python" in url

    def test_get_search_url_duckduckgo(self):
        """Should generate DuckDuckGo search URL."""
        intel = SearchIntelligence()
        query = SearchQuery(
            original="test",
            query="python book",
            engine=SearchEngine.DUCKDUCKGO
        )

        url = intel.get_search_url(query)
        assert "duckduckgo.com" in url

    def test_get_search_url_bing(self):
        """Should generate Bing search URL."""
        intel = SearchIntelligence()
        query = SearchQuery(
            original="test",
            query="python book",
            engine=SearchEngine.BING
        )

        url = intel.get_search_url(query)
        assert "bing.com" in url

    def test_start_session(self):
        """Should start a search session."""
        intel = SearchIntelligence()
        query = intel.create_search("test search")
        session = intel.start_session(query)

        assert session is not None
        assert session.query == query
        assert session in intel.sessions

    def test_analyze_results(self):
        """Should analyze and rank results."""
        intel = SearchIntelligence()
        query = intel.create_search("python book")
        session = intel.start_session(query)

        raw_results = [
            {"title": "Python Book PDF", "url": "http://good.com/pdf", "snippet": "Download"},
            {"title": "Spam Site", "url": "http://spam.com", "snippet": "Survey required"},
        ]

        ranked = intel.analyze_results(session, raw_results, "ebook")

        assert len(ranked) == 2
        assert all(r.relevance_score > 0 for r in ranked)

    def test_record_click(self):
        """Should record result clicks."""
        intel = SearchIntelligence()
        query = intel.create_search("test")
        session = intel.start_session(query)

        raw_results = [
            {"title": "Test", "url": "http://test.com", "snippet": "Test"}
        ]
        intel.analyze_results(session, raw_results)

        intel.record_click(session, 1)

        assert 1 in session.clicks
        assert session.results[0].clicked is True

    def test_record_success(self):
        """Should record successful download."""
        intel = SearchIntelligence()
        query = intel.create_search("test")
        session = intel.start_session(query)

        raw_results = [
            {"title": "Test", "url": "http://test.com", "snippet": "Test"}
        ]
        intel.analyze_results(session, raw_results)

        intel.record_success(session, 1)

        assert session.successful is True
        assert session.results[0].led_to_download is True

    def test_should_reformulate_empty(self):
        """Should reformulate with no results."""
        intel = SearchIntelligence()
        query = intel.create_search("test")
        session = intel.start_session(query)

        assert intel.should_reformulate(session) is True

    def test_should_reformulate_many_clicks(self):
        """Should reformulate after many unsuccessful clicks."""
        intel = SearchIntelligence()
        query = intel.create_search("test")
        session = intel.start_session(query)

        raw_results = [
            {"title": "Test", "url": "http://test.com", "snippet": "Test"}
        ]
        intel.analyze_results(session, raw_results)

        # Simulate 3 clicks without success
        session.clicks = [1, 2, 3]
        session.successful = False

        assert intel.should_reformulate(session) is True

    def test_get_next_query(self):
        """Should get next alternative query."""
        intel = SearchIntelligence()
        query = intel.create_search("python programming book")
        session = intel.start_session(query)

        if query.alternatives:
            next_query = intel.get_next_query(session)
            assert next_query is not None

    def test_get_best_result_url(self):
        """Should get best unclicked result URL."""
        intel = SearchIntelligence()
        query = intel.create_search("test")
        session = intel.start_session(query)

        raw_results = [
            {"title": "Best Result", "url": "http://best.com", "snippet": "Best"},
            {"title": "Second", "url": "http://second.com", "snippet": "Second"},
        ]
        intel.analyze_results(session, raw_results)

        url = intel.get_best_result_url(session)
        assert url is not None

    def test_export_import_learnings(self):
        """Should export and import learned patterns."""
        intel1 = SearchIntelligence()
        intel1.formulator.record_success("python pdf", "python book")
        intel1.formulator.record_failure("bad query", "python book")

        data = intel1.export_learnings()

        intel2 = SearchIntelligence()
        intel2.import_learnings(data)

        assert intel2.formulator.get_proven_query("python book") == "python pdf"


class TestGlobalSearchIntel:
    """Tests for global search intelligence."""

    def test_get_search_intel(self):
        """Should return global instance."""
        intel1 = get_search_intel()
        intel2 = get_search_intel()

        assert intel1 is intel2
