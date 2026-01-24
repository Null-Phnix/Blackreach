"""
Pytest configuration and fixtures for Blackreach tests.

Includes:
- Temporary directory fixtures
- Mock HTML page fixtures
- Mock LLM response fixtures
- Browser testing fixtures
- Mock web server fixture for reliable integration testing
- Debug tools fixtures
"""

import pytest
import tempfile
import shutil
import threading
import socket
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
import json

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


@pytest.fixture
def debug_output_dir(temp_dir):
    """Create a temporary debug output directory."""
    path = temp_dir / "debug_output"
    path.mkdir()
    return path


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


@pytest.fixture
def form_page_html():
    """HTML page with various form elements for interaction testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Form Test Page</title></head>
    <body>
        <h1>Form Test</h1>
        <form id="test-form" action="/submit" method="post">
            <label for="username">Username:</label>
            <input type="text" id="username" name="username" placeholder="Enter username">

            <label for="password">Password:</label>
            <input type="password" id="password" name="password">

            <label for="email">Email:</label>
            <input type="email" id="email" name="email" placeholder="user@example.com">

            <label for="search">Search:</label>
            <input type="search" id="search" name="q" placeholder="Search...">

            <label for="message">Message:</label>
            <textarea id="message" name="message" rows="4"></textarea>

            <label for="country">Country:</label>
            <select id="country" name="country">
                <option value="">Select...</option>
                <option value="us">United States</option>
                <option value="uk">United Kingdom</option>
                <option value="ca">Canada</option>
            </select>

            <label>
                <input type="checkbox" id="agree" name="agree">
                I agree to terms
            </label>

            <button type="submit" id="submit-btn">Submit</button>
            <button type="reset" id="reset-btn">Reset</button>
        </form>

        <div id="result" style="display:none;">
            <p>Form submitted successfully!</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def dynamic_content_html():
    """HTML page that simulates dynamic content loading."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Dynamic Content Page</title></head>
    <body>
        <h1>Dynamic Content Test</h1>
        <div id="loading" class="loading">Loading...</div>
        <div id="content" style="display:none;">
            <h2>Content Loaded!</h2>
            <ul id="items">
                <li><a href="/item/1">Item 1</a></li>
                <li><a href="/item/2">Item 2</a></li>
                <li><a href="/item/3">Item 3</a></li>
            </ul>
            <button id="load-more">Load More</button>
        </div>
        <script>
            // Simulate delayed content loading
            setTimeout(function() {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('content').style.display = 'block';
            }, 500);
        </script>
    </body>
    </html>
    """


@pytest.fixture
def error_page_html():
    """HTML page simulating various error states."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Error Page</title></head>
    <body>
        <h1>Something went wrong</h1>
        <div id="error-message">
            <p class="error">An error occurred while processing your request.</p>
            <p class="error-code">Error code: 500</p>
        </div>
        <a href="/" id="home-link">Return to Home</a>
        <button id="retry-btn" onclick="location.reload()">Retry</button>
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
    browser.is_awake = True
    browser.is_healthy.return_value = True
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


# =============================================================================
# FIXTURES: Mock Web Server
# =============================================================================

class MockWebServerHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for mock web server with configurable responses."""

    # Class-level storage for routes and test files
    routes = {}
    test_files_dir = None

    def log_message(self, format, *args):
        """Suppress server logging during tests."""
        pass

    def do_GET(self):
        """Handle GET requests with custom routing."""
        path = self.path.split('?')[0]  # Remove query string

        # Check if we have a custom route
        if path in self.routes:
            response = self.routes[path]
            self._send_response(response)
            return

        # Check for downloadable test files
        if path.startswith('/download/') and self.test_files_dir:
            filename = path.replace('/download/', '')
            filepath = self.test_files_dir / filename
            if filepath.exists():
                self._send_file(filepath)
                return

        # Default 404 response
        self.send_error(404, f"Path not found: {path}")

    def do_POST(self):
        """Handle POST requests."""
        path = self.path.split('?')[0]

        if path in self.routes:
            response = self.routes[path]
            self._send_response(response)
            return

        # Default: echo back the request
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b''

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = json.dumps({
            "received": body.decode('utf-8', errors='replace'),
            "path": path,
        })
        self.wfile.write(response.encode())

    def _send_response(self, response):
        """Send a custom response."""
        if isinstance(response, dict):
            status = response.get('status', 200)
            content_type = response.get('content_type', 'text/html')
            body = response.get('body', '')
            headers = response.get('headers', {})
        else:
            # Assume it's just the body content
            status = 200
            content_type = 'text/html'
            body = response
            headers = {}

        self.send_response(status)
        self.send_header('Content-Type', content_type)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()

        if isinstance(body, str):
            body = body.encode('utf-8')
        self.wfile.write(body)

    def _send_file(self, filepath: Path):
        """Send a file as download."""
        content_type = self._guess_type(filepath)

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Disposition', f'attachment; filename="{filepath.name}"')
        self.send_header('Content-Length', str(filepath.stat().st_size))
        self.end_headers()

        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    def _guess_type(self, filepath: Path) -> str:
        """Guess content type from file extension."""
        ext = filepath.suffix.lower()
        types = {
            '.html': 'text/html',
            '.htm': 'text/html',
            '.txt': 'text/plain',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.zip': 'application/zip',
        }
        return types.get(ext, 'application/octet-stream')


class MockWebServer:
    """
    Mock web server for testing browser automation.

    Provides a local HTTP server with configurable routes for
    reliable, offline testing of browser interactions.
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 0):
        """
        Initialize mock server.

        Args:
            host: Host to bind to (default localhost)
            port: Port to use (0 for auto-assign)
        """
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self.test_files_dir = None
        self._routes = {}

    def add_route(self, path: str, response):
        """
        Add a route to the server.

        Args:
            path: URL path (e.g., '/test' or '/api/data')
            response: Either a string (HTML body) or dict with:
                      - status: HTTP status code
                      - content_type: MIME type
                      - body: Response body
                      - headers: Additional headers dict
        """
        self._routes[path] = response
        MockWebServerHandler.routes[path] = response

    def set_test_files_dir(self, path: Path):
        """Set directory for downloadable test files."""
        self.test_files_dir = path
        MockWebServerHandler.test_files_dir = path

    def start(self):
        """Start the server in a background thread."""
        handler = MockWebServerHandler
        self.server = HTTPServer((self.host, self.port), handler)

        # Get the actual assigned port if we used 0
        self.port = self.server.server_address[1]

        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        # Wait a moment for server to start
        time.sleep(0.1)

    def stop(self):
        """Stop the server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1.0)
        # Clear routes
        MockWebServerHandler.routes.clear()

    @property
    def url(self) -> str:
        """Get the base URL of the server."""
        return f"http://{self.host}:{self.port}"

    def url_for(self, path: str) -> str:
        """Get full URL for a path."""
        if not path.startswith('/'):
            path = '/' + path
        return f"{self.url}{path}"


@pytest.fixture
def mock_server(temp_dir):
    """
    Create a mock web server fixture.

    The server runs in a background thread and is automatically
    stopped after the test completes.

    Usage:
        def test_navigation(mock_server, browser):
            mock_server.add_route('/', '<html><body>Home</body></html>')
            browser.goto(mock_server.url)
    """
    server = MockWebServer()
    server.set_test_files_dir(temp_dir)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def mock_server_with_pages(mock_server, simple_html, form_page_html, dynamic_content_html, error_page_html):
    """
    Mock server pre-configured with common test pages.
    """
    mock_server.add_route('/', simple_html)
    mock_server.add_route('/index.html', simple_html)
    mock_server.add_route('/form', form_page_html)
    mock_server.add_route('/dynamic', dynamic_content_html)
    mock_server.add_route('/error', error_page_html)
    mock_server.add_route('/page1', '<html><body><h1>Page 1</h1><a href="/">Back</a></body></html>')
    mock_server.add_route('/page2', '<html><body><h1>Page 2</h1><a href="/">Back</a></body></html>')
    mock_server.add_route('/submit', {
        'status': 200,
        'content_type': 'application/json',
        'body': '{"success": true, "message": "Form submitted"}'
    })
    return mock_server


# =============================================================================
# FIXTURES: Browser Testing
# =============================================================================

@pytest.fixture
def browser_config():
    """Default browser configuration for testing."""
    from blackreach.stealth import StealthConfig
    from blackreach.resilience import RetryConfig

    return {
        'headless': True,
        'stealth_config': StealthConfig(
            min_delay=0.05,
            max_delay=0.1,
            randomize_viewport=False,
            randomize_user_agent=False,
            human_mouse=False,
        ),
        'retry_config': RetryConfig(
            max_attempts=2,
            base_delay=0.1,
        ),
    }


@pytest.fixture
def browser(browser_config, download_dir):
    """
    Create a real browser instance for integration testing.

    The browser runs in headless mode with minimal delays for fast testing.
    Automatically starts and stops the browser.
    """
    from blackreach.browser import Hand

    hand = Hand(
        headless=browser_config['headless'],
        stealth_config=browser_config['stealth_config'],
        retry_config=browser_config['retry_config'],
        download_dir=download_dir,
    )
    hand.wake()
    yield hand
    hand.sleep()


@pytest.fixture
def browser_with_debug(browser, debug_output_dir):
    """
    Browser wrapped with debug tools for automatic error capture.
    """
    from blackreach.debug_tools import DebugTools, DebugConfig, ErrorCapturingWrapper

    config = DebugConfig(
        output_dir=debug_output_dir,
        capture_on_error=True,
    )
    debug_tools = DebugTools(config)

    return ErrorCapturingWrapper(browser, debug_tools)


# =============================================================================
# FIXTURES: Debug Tools
# =============================================================================

@pytest.fixture
def debug_tools(debug_output_dir):
    """Create debug tools instance for testing."""
    from blackreach.debug_tools import DebugTools, DebugConfig

    config = DebugConfig(
        output_dir=debug_output_dir,
        capture_screenshots=True,
        capture_html=True,
        capture_on_error=True,
    )
    return DebugTools(config)


@pytest.fixture
def test_result_tracker(debug_tools):
    """Create test result tracker for testing."""
    from blackreach.debug_tools import TestResultTracker

    tracker = TestResultTracker(debug_tools)
    tracker.start_session()
    return tracker


# =============================================================================
# HELPERS: Test utilities
# =============================================================================

def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def create_test_file(directory: Path, filename: str, content: bytes = None, size: int = 1024) -> Path:
    """
    Create a test file for download testing.

    Args:
        directory: Directory to create file in
        filename: Name of the file
        content: File content (or generate random if None)
        size: Size if generating content

    Returns:
        Path to created file
    """
    filepath = directory / filename
    if content is None:
        content = b'X' * size
    filepath.write_bytes(content)
    return filepath


@pytest.fixture
def test_download_file(temp_dir):
    """Create a test file for download testing."""
    return create_test_file(temp_dir, 'test_file.txt', b'Test file content for download testing.')


@pytest.fixture
def test_pdf_file(temp_dir):
    """Create a minimal PDF file for testing."""
    # Minimal valid PDF content
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Root 1 0 R /Size 4 >>
startxref
196
%%EOF"""
    return create_test_file(temp_dir, 'test.pdf', pdf_content)


@pytest.fixture
def test_image_file(temp_dir):
    """Create a minimal PNG file for testing."""
    # Minimal 1x1 red PNG
    png_content = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D,  # IHDR length
        0x49, 0x48, 0x44, 0x52,  # IHDR
        0x00, 0x00, 0x00, 0x01,  # width
        0x00, 0x00, 0x00, 0x01,  # height
        0x08, 0x02,  # bit depth, color type
        0x00, 0x00, 0x00,  # compression, filter, interlace
        0x90, 0x77, 0x53, 0xDE,  # CRC
        0x00, 0x00, 0x00, 0x0C,  # IDAT length
        0x49, 0x44, 0x41, 0x54,  # IDAT
        0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00,
        0x01, 0x01, 0x01, 0x00,  # compressed data + CRC
        0x1B, 0xB6, 0xEE, 0x56,
        0x00, 0x00, 0x00, 0x00,  # IEND length
        0x49, 0x45, 0x4E, 0x44,  # IEND
        0xAE, 0x42, 0x60, 0x82,  # CRC
    ])
    return create_test_file(temp_dir, 'test.png', png_content)
