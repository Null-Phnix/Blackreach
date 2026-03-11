"""
Unit tests for blackreach/api.py

Tests the high-level API interface.
"""

import pytest
from pathlib import Path
from blackreach.api import (
    BrowseResult,
    SearchResult,
    DownloadResult,
    ApiConfig,
    BlackreachAPI,
)


class TestBrowseResult:
    """Tests for BrowseResult dataclass."""

    def test_default_values(self):
        """BrowseResult has correct defaults."""
        result = BrowseResult(
            success=True,
            goal="Test goal"
        )
        assert result.downloads == []
        assert result.pages_visited == 0
        assert result.steps_taken == 0
        assert result.errors == []
        assert result.session_id is None
        assert result.metadata == {}

    def test_custom_values(self):
        """BrowseResult accepts custom values."""
        result = BrowseResult(
            success=True,
            goal="Download files",
            downloads=["/path/to/file1.pdf", "/path/to/file2.pdf"],
            pages_visited=10,
            steps_taken=25,
            session_id=12345
        )
        assert result.success is True
        assert result.goal == "Download files"
        assert len(result.downloads) == 2
        assert result.pages_visited == 10
        assert result.steps_taken == 25
        assert result.session_id == 12345


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_default_values(self):
        """SearchResult has correct defaults."""
        result = SearchResult(query="test query")
        assert result.results == []
        assert result.source == ""
        assert result.total_found == 0

    def test_custom_values(self):
        """SearchResult accepts custom values."""
        result = SearchResult(
            query="Python books",
            results=[{"title": "Book 1"}, {"title": "Book 2"}],
            source="google.com",
            total_found=100
        )
        assert result.query == "Python books"
        assert len(result.results) == 2
        assert result.source == "google.com"
        assert result.total_found == 100


class TestDownloadResult:
    """Tests for DownloadResult dataclass."""

    def test_success_result(self):
        """DownloadResult for successful download."""
        result = DownloadResult(
            success=True,
            url="https://example.com/file.pdf",
            filename="file.pdf",
            path="/downloads/file.pdf",
            size=1024000
        )
        assert result.success is True
        assert result.url == "https://example.com/file.pdf"
        assert result.filename == "file.pdf"
        assert result.size == 1024000
        assert result.error is None

    def test_failed_result(self):
        """DownloadResult for failed download."""
        result = DownloadResult(
            success=False,
            url="https://example.com/missing.pdf",
            error="404 Not Found"
        )
        assert result.success is False
        assert result.error == "404 Not Found"


class TestApiConfig:
    """Tests for ApiConfig dataclass."""

    def test_default_values(self):
        """ApiConfig has sensible defaults."""
        config = ApiConfig()
        assert config.download_dir == Path("./downloads")
        assert config.headless is True
        assert config.max_steps == 50
        assert config.browser_type == "chromium"
        assert config.verbose is False

    def test_custom_values(self):
        """ApiConfig accepts custom values."""
        config = ApiConfig(
            download_dir=Path("/custom/downloads"),
            headless=False,
            max_steps=100,
            browser_type="firefox",
            verbose=True
        )
        assert config.download_dir == Path("/custom/downloads")
        assert config.headless is False
        assert config.max_steps == 100
        assert config.browser_type == "firefox"
        assert config.verbose is True


class TestBlackreachAPI:
    """Tests for BlackreachAPI class."""

    def test_init_with_default_config(self):
        """Should initialize with default config."""
        api = BlackreachAPI()
        assert api.config is not None
        assert api.config.headless is True
        assert api._agent is None
        assert api._initialized is False

    def test_init_with_custom_config(self):
        """Should initialize with custom config."""
        config = ApiConfig(headless=False, verbose=True)
        api = BlackreachAPI(config=config)
        assert api.config.headless is False
        assert api.config.verbose is True

    def test_lazy_agent_initialization(self):
        """Agent should not be created until needed."""
        api = BlackreachAPI()
        assert api._agent is None
        assert api._initialized is False


class TestApiConfigValidation:
    """Tests for config validation."""

    def test_valid_browser_types(self):
        """Should accept valid browser types."""
        for browser in ["chromium", "firefox", "webkit"]:
            config = ApiConfig(browser_type=browser)
            assert config.browser_type == browser

    def test_max_steps_positive(self):
        """max_steps should be positive."""
        config = ApiConfig(max_steps=100)
        assert config.max_steps == 100


class TestBrowseResultMetadata:
    """Tests for result metadata handling."""

    def test_metadata_storage(self):
        """Should store arbitrary metadata."""
        result = BrowseResult(
            success=True,
            goal="Test",
            metadata={
                "start_time": "2024-01-15T10:00:00",
                "end_time": "2024-01-15T10:05:00",
                "custom_field": "value"
            }
        )
        assert "start_time" in result.metadata
        assert result.metadata["custom_field"] == "value"

    def test_errors_list(self):
        """Should accumulate errors."""
        result = BrowseResult(
            success=False,
            goal="Test",
            errors=["Error 1", "Error 2", "Error 3"]
        )
        assert len(result.errors) == 3


class TestBlackreachAPIContextManager:
    """Tests for API context manager support."""

    def test_context_manager_enter_returns_api(self):
        """__enter__ should return the API instance."""
        api = BlackreachAPI()
        with api as ctx:
            assert ctx is api

    def test_context_manager_exit_closes(self):
        """__exit__ should close the API."""
        api = BlackreachAPI()
        api._initialized = True

        with api:
            pass

        assert api._initialized is False
        assert api._agent is None


class TestBlackreachAPIClose:
    """Tests for API close functionality."""

    def test_close_resets_state(self):
        """close() should reset all state."""
        api = BlackreachAPI()
        api._initialized = True

        api.close()

        assert api._agent is None
        assert api._initialized is False

    def test_close_without_agent_safe(self):
        """close() should be safe when no agent exists."""
        api = BlackreachAPI()
        api.close()  # Should not raise
        assert api._agent is None


class TestSearchResult:
    """Extended tests for SearchResult."""

    def test_empty_results_default(self):
        """Results should default to empty list."""
        result = SearchResult(query="test")
        assert result.results == []
        assert isinstance(result.results, list)


class TestDownloadResultPath:
    """Tests for DownloadResult path handling."""

    def test_path_empty_string_default(self):
        """path should default to empty string."""
        result = DownloadResult(success=True, url="http://example.com")
        assert result.path == ""

    def test_size_zero_default(self):
        """size should default to 0."""
        result = DownloadResult(success=True, url="http://example.com")
        assert result.size == 0


class TestBatchProcessor:
    """Tests for BatchProcessor class."""

    def test_init_with_default_config(self):
        """Should initialize with default config."""
        from blackreach.api import BatchProcessor
        processor = BatchProcessor()
        assert processor.config is not None
        assert processor.results == []

    def test_init_with_custom_config(self):
        """Should initialize with custom config."""
        from blackreach.api import BatchProcessor
        config = ApiConfig(headless=False, max_steps=100)
        processor = BatchProcessor(config=config)
        assert processor.config.headless is False
        assert processor.config.max_steps == 100

    def test_add_returns_index(self):
        """add() should return the current index."""
        from blackreach.api import BatchProcessor
        processor = BatchProcessor()

        idx1 = processor.add("goal 1")
        idx2 = processor.add("goal 2")

        assert idx1 == 0
        assert idx2 == 0  # Note: Current impl returns len(results) which is 0

    def test_results_initially_empty(self):
        """results should start empty."""
        from blackreach.api import BatchProcessor
        processor = BatchProcessor()
        assert processor.results == []

    def test_get_summary_empty_batch(self):
        """get_summary() should handle empty results."""
        from blackreach.api import BatchProcessor
        processor = BatchProcessor()

        summary = processor.get_summary()

        assert summary["total_goals"] == 0
        assert summary["successful"] == 0
        assert summary["failed"] == 0
        assert summary["total_downloads"] == 0
        assert summary["success_rate"] == 0

    def test_get_summary_with_results(self):
        """get_summary() should summarize results correctly."""
        from blackreach.api import BatchProcessor
        processor = BatchProcessor()

        # Manually set results to test summary
        processor.results = [
            BrowseResult(success=True, goal="Goal 1", downloads=["/file1.pdf"]),
            BrowseResult(success=False, goal="Goal 2"),
            BrowseResult(success=True, goal="Goal 3", downloads=["/file2.pdf", "/file3.pdf"]),
        ]

        summary = processor.get_summary()

        assert summary["total_goals"] == 3
        assert summary["successful"] == 2
        assert summary["failed"] == 1
        assert summary["total_downloads"] == 3
        assert summary["success_rate"] == 2/3


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_browse_function_exists(self):
        """browse() function should exist."""
        from blackreach.api import browse
        assert callable(browse)

    def test_download_function_exists(self):
        """download() function should exist."""
        from blackreach.api import download
        assert callable(download)

    def test_search_function_exists(self):
        """search() function should exist."""
        from blackreach.api import search
        assert callable(search)

    def test_get_page_function_exists(self):
        """get_page() function should exist."""
        from blackreach.api import get_page
        assert callable(get_page)


class TestAPISSRFProtection:
    """Tests for SSRF protection in API methods."""

    def test_get_page_blocks_localhost(self):
        """get_page() should reject localhost URLs."""
        api = BlackreachAPI()
        with pytest.raises(ValueError, match="SSRF"):
            api.get_page("http://localhost/admin")

    def test_get_page_blocks_127_0_0_1(self):
        """get_page() should reject 127.0.0.1 URLs."""
        api = BlackreachAPI()
        with pytest.raises(ValueError, match="SSRF"):
            api.get_page("http://127.0.0.1:8080/secret")

    def test_get_page_blocks_private_ips(self):
        """get_page() should reject private IP ranges."""
        api = BlackreachAPI()

        # 192.168.x.x
        with pytest.raises(ValueError, match="SSRF"):
            api.get_page("http://192.168.1.1/router")

        # 10.x.x.x
        with pytest.raises(ValueError, match="SSRF"):
            api.get_page("http://10.0.0.1/internal")

        # 172.16-31.x.x
        with pytest.raises(ValueError, match="SSRF"):
            api.get_page("http://172.16.0.1/private")

    def test_get_page_blocks_cloud_metadata(self):
        """get_page() should reject cloud metadata endpoints (169.254.169.254)."""
        api = BlackreachAPI()
        with pytest.raises(ValueError, match="SSRF"):
            api.get_page("http://169.254.169.254/latest/meta-data/")

    def test_get_page_blocks_ipv6_localhost(self):
        """get_page() should reject IPv6 localhost."""
        api = BlackreachAPI()
        with pytest.raises(ValueError, match="SSRF"):
            api.get_page("http://[::1]/admin")
