"""
Pytest configuration and fixtures for Blackreach tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# FIXTURES: Temporary directories
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def download_dir(temp_dir):
    """Create a temporary download directory."""
    path = temp_dir / "downloads"
    path.mkdir()
    return path


@pytest.fixture
def memory_db(temp_dir):
    """Create a temporary memory database path."""
    return temp_dir / "test_memory.db"


# =============================================================================
# FIXTURES: Mock HTML pages
# =============================================================================

@pytest.fixture
def simple_html():
    """Simple HTML page with basic elements."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Welcome</h1>
        <p>This is a test page.</p>
        <a href="/page1">Link 1</a>
        <a href="/page2">Link 2</a>
        <input type="text" id="search" placeholder="Search...">
        <button id="submit">Submit</button>
    </body>
    </html>
    """


@pytest.fixture
def arxiv_search_html():
    """Mock ArXiv search results page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Search Results - arXiv</title></head>
    <body>
        <div id="search-results">
            <div class="arxiv-result">
                <p class="title">
                    <a href="/abs/2401.12345">Paper Title One</a>
                </p>
                <p class="authors">Author A, Author B</p>
                <a href="/pdf/2401.12345.pdf">PDF</a>
            </div>
            <div class="arxiv-result">
                <p class="title">
                    <a href="/abs/2401.67890">Paper Title Two</a>
                </p>
                <p class="authors">Author C</p>
                <a href="/pdf/2401.67890.pdf">PDF</a>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def github_repo_html():
    """Mock GitHub repository page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>repo - GitHub</title></head>
    <body>
        <div class="file-list">
            <a href="/user/repo/blob/main/README.md">README.md</a>
            <a href="/user/repo/blob/main/src/main.py">main.py</a>
            <a href="/user/repo/raw/main/data.csv">data.csv</a>
        </div>
        <a href="/user/repo/archive/refs/heads/main.zip">Download ZIP</a>
    </body>
    </html>
    """


@pytest.fixture
def image_gallery_html():
    """Mock image gallery page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Image Gallery</title></head>
    <body>
        <div class="gallery">
            <a href="/images/full/img1.jpg">
                <img src="/images/thumb/img1.jpg" alt="Image 1">
            </a>
            <a href="/images/full/img2.png">
                <img src="/images/thumb/img2.png" alt="Image 2">
            </a>
            <a href="/w/12345">
                <img src="/images/thumb/img3.jpg" alt="Detail page">
            </a>
        </div>
    </body>
    </html>
    """


# =============================================================================
# FIXTURES: Mock LLM responses
# =============================================================================

@pytest.fixture
def mock_llm_navigate():
    """Mock LLM response for navigate action."""
    return """
    {
        "thought": "I need to go to the search page to find papers.",
        "action": "navigate",
        "args": {"url": "https://arxiv.org/search"}
    }
    """


@pytest.fixture
def mock_llm_click():
    """Mock LLM response for click action."""
    return """
    {
        "thought": "I see the paper link, I should click it.",
        "action": "click",
        "args": {"text": "Paper Title One"}
    }
    """


@pytest.fixture
def mock_llm_download():
    """Mock LLM response for download action."""
    return """
    {
        "thought": "Found the PDF link, downloading it now.",
        "action": "download",
        "args": {"url": "https://arxiv.org/pdf/2401.12345.pdf"}
    }
    """


@pytest.fixture
def mock_llm_done():
    """Mock LLM response for done action."""
    return """
    {
        "thought": "I have downloaded all requested files.",
        "action": "done",
        "args": {"reason": "Downloaded 2 papers successfully"}
    }
    """


@pytest.fixture
def mock_llm_type():
    """Mock LLM response for type action."""
    return """
    {
        "thought": "I need to search for machine learning papers.",
        "action": "type",
        "args": {"selector": "#search", "text": "machine learning"}
    }
    """


# =============================================================================
# FIXTURES: Mock objects
# =============================================================================

@pytest.fixture
def mock_browser():
    """Mock browser (Hand) object."""
    browser = Mock()
    browser.get_url.return_value = "https://example.com"
    browser.get_title.return_value = "Example Page"
    browser.get_html.return_value = "<html><body>Test</body></html>"
    browser.goto.return_value = None
    browser.click.return_value = {"action": "click", "success": True}
    browser.type_text.return_value = {"action": "type", "success": True}
    return browser


@pytest.fixture
def mock_llm():
    """Mock LLM object."""
    llm = Mock()
    llm.generate.return_value = '{"thought": "test", "action": "done", "args": {}}'
    return llm


# =============================================================================
# FIXTURES: Sample data
# =============================================================================

@pytest.fixture
def sample_visited_urls():
    """Sample list of visited URLs."""
    return [
        "https://arxiv.org/search?query=ml",
        "https://arxiv.org/abs/2401.12345",
        "https://arxiv.org/pdf/2401.12345.pdf",
        "https://github.com/user/repo",
    ]


@pytest.fixture
def sample_downloaded_files():
    """Sample list of downloaded files."""
    return [
        "2401.12345v1.pdf",
        "README.md",
        "data.csv",
    ]
