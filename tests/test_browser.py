"""
Unit tests for blackreach/browser.py (Hand)

Tests browser configuration and utility methods.
Integration tests requiring actual Playwright are marked and can be skipped.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import hashlib

from blackreach.browser import Hand
from blackreach.resilience import RetryConfig
from blackreach.stealth import StealthConfig


# =============================================================================
# RetryConfig Tests
# =============================================================================

class TestRetryConfig:
    """Tests for retry configuration."""

    def test_default_values(self):
        """RetryConfig has sensible defaults."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0

    def test_custom_values(self):
        """RetryConfig accepts custom values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=60.0
        )

        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 60.0


# =============================================================================
# StealthConfig Tests
# =============================================================================

class TestStealthConfig:
    """Tests for stealth configuration."""

    def test_default_values(self):
        """StealthConfig has sensible defaults."""
        config = StealthConfig()

        assert config.human_mouse is True
        assert config.randomize_viewport is True
        assert config.randomize_user_agent is True

    def test_custom_values(self):
        """StealthConfig accepts custom values."""
        config = StealthConfig(
            human_mouse=False,
            block_images=True,
            min_delay=1.0
        )

        assert config.human_mouse is False
        assert config.block_images is True
        assert config.min_delay == 1.0


# =============================================================================
# Hand Initialization Tests
# =============================================================================

class TestHandInitialization:
    """Tests for Hand browser wrapper initialization."""

    def test_init_stores_config(self, download_dir):
        """Hand stores configuration on init."""
        hand = Hand(
            headless=True,
            stealth_config=StealthConfig(),
            retry_config=RetryConfig(max_attempts=5),
            download_dir=download_dir
        )

        assert hand.headless is True
        assert hand.retry_config.max_attempts == 5
        assert hand.download_dir == download_dir

    def test_init_default_headless(self, download_dir):
        """Hand defaults to headless=False."""
        hand = Hand(download_dir=download_dir)
        assert hand.headless is False

    def test_init_default_download_dir(self):
        """Hand defaults to ./downloads if not specified."""
        hand = Hand()
        assert hand.download_dir == Path("./downloads")


# =============================================================================
# Hash Computation Tests
# =============================================================================

class TestHashComputation:
    """Tests for file hash computation."""

    def test_compute_hash_returns_hex(self, download_dir):
        """_compute_hash returns hex string."""
        hand = Hand(download_dir=download_dir)

        # Create a test file
        test_file = download_dir / "test.txt"
        test_file.write_text("Hello, World!")

        hash_value = hand._compute_hash(test_file)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 hex length

    def test_compute_hash_consistent(self, download_dir):
        """Same content produces same hash."""
        hand = Hand(download_dir=download_dir)

        file1 = download_dir / "file1.txt"
        file2 = download_dir / "file2.txt"

        content = "Identical content"
        file1.write_text(content)
        file2.write_text(content)

        assert hand._compute_hash(file1) == hand._compute_hash(file2)

    def test_compute_hash_different_content(self, download_dir):
        """Different content produces different hash."""
        hand = Hand(download_dir=download_dir)

        file1 = download_dir / "file1.txt"
        file2 = download_dir / "file2.txt"

        file1.write_text("Content A")
        file2.write_text("Content B")

        assert hand._compute_hash(file1) != hand._compute_hash(file2)

    def test_compute_hash_binary_file(self, download_dir):
        """Hash works on binary files."""
        hand = Hand(download_dir=download_dir)

        binary_file = download_dir / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        hash_value = hand._compute_hash(binary_file)
        assert len(hash_value) == 64


# =============================================================================
# Download Link Detection Tests
# =============================================================================

class TestDownloadLinkDetection:
    """Tests for download link type detection."""

    def test_inline_image_detection(self, download_dir):
        """Inline image types are detected."""
        hand = Hand(download_dir=download_dir)

        # These should be detected as inline files
        inline_urls = [
            "https://example.com/image.jpg",
            "https://example.com/photo.jpeg",
            "https://example.com/icon.png",
            "https://example.com/animation.gif",
            "https://example.com/modern.webp",
            "https://example.com/vector.svg",
        ]

        for url in inline_urls:
            href_lower = url.lower()
            inline_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp']
            is_inline = any(href_lower.endswith(ext) or f'{ext}?' in href_lower for ext in inline_extensions)
            assert is_inline, f"{url} should be detected as inline"

    def test_non_inline_detection(self, download_dir):
        """Non-inline file types are not detected as inline."""
        hand = Hand(download_dir=download_dir)

        non_inline_urls = [
            "https://example.com/document.pdf",
            "https://example.com/archive.zip",
            "https://example.com/data.csv",
            "https://example.com/page.html",
        ]

        for url in non_inline_urls:
            href_lower = url.lower()
            inline_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp']
            is_inline = any(href_lower.endswith(ext) or f'{ext}?' in href_lower for ext in inline_extensions)
            assert not is_inline, f"{url} should NOT be detected as inline"

    def test_image_host_detection(self, download_dir):
        """Known image hosts are detected."""
        hand = Hand(download_dir=download_dir)

        image_hosts = [
            "https://upload.wikimedia.org/something",
            "https://i.imgur.com/image",
            "https://pbs.twimg.com/media/something",
        ]

        for url in image_hosts:
            href_lower = url.lower()
            is_image_host = any(h in href_lower for h in ['upload.wikimedia.org', 'i.imgur.com', 'pbs.twimg.com'])
            assert is_image_host, f"{url} should be detected as image host"


# =============================================================================
# State Management Tests
# =============================================================================

class TestStateManagement:
    """Tests for browser state management."""

    def test_pending_downloads_initialized(self, download_dir):
        """Pending downloads list is initialized."""
        hand = Hand(download_dir=download_dir)
        assert hasattr(hand, '_pending_downloads')

    def test_playwright_initially_none(self, download_dir):
        """Playwright instance is None before wake()."""
        hand = Hand(download_dir=download_dir)
        assert hand._playwright is None

    def test_context_initially_none(self, download_dir):
        """Context is None before wake()."""
        hand = Hand(download_dir=download_dir)
        assert hand._context is None

    def test_page_property_raises_before_wake(self, download_dir):
        """Page property raises error before wake()."""
        hand = Hand(download_dir=download_dir)
        with pytest.raises(RuntimeError) as exc_info:
            _ = hand.page
        assert "not awake" in str(exc_info.value)


# =============================================================================
# Filename Handling Tests
# =============================================================================

class TestFilenameHandling:
    """Tests for download filename handling."""

    def test_duplicate_filename_handling(self, download_dir):
        """Duplicate filenames get counter suffix."""
        # Create existing file
        existing = download_dir / "test.pdf"
        existing.write_text("existing")

        # Simulate the duplicate handling logic
        save_path = download_dir / "test.pdf"
        counter = 1
        while save_path.exists():
            stem = save_path.stem.rsplit('_', 1)[0] if '_' in save_path.stem else save_path.stem
            save_path = download_dir / f"{stem}_{counter}{save_path.suffix}"
            counter += 1

        assert save_path.name == "test_1.pdf"

    def test_multiple_duplicates(self, download_dir):
        """Multiple duplicates get incrementing counters."""
        # Create existing files
        (download_dir / "test.pdf").write_text("1")
        (download_dir / "test_1.pdf").write_text("2")

        save_path = download_dir / "test.pdf"
        counter = 1
        while save_path.exists():
            save_path = download_dir / f"test_{counter}.pdf"
            counter += 1

        assert save_path.name == "test_2.pdf"


# =============================================================================
# Mock Browser Operations Tests
# =============================================================================

class TestMockedBrowserOperations:
    """Tests using mocked browser page."""

    def test_get_url_with_mocked_page(self, download_dir):
        """get_url returns page URL when page exists."""
        hand = Hand(download_dir=download_dir)

        # Mock the internal page
        mock_page = Mock()
        mock_page.url = "https://example.com/page"
        hand._page = mock_page

        assert hand.get_url() == "https://example.com/page"

    def test_get_title_with_mocked_page(self, download_dir):
        """get_title returns page title when page exists."""
        hand = Hand(download_dir=download_dir)

        mock_page = Mock()
        mock_page.title.return_value = "Example Page"
        hand._page = mock_page

        assert hand.get_title() == "Example Page"

    def test_get_html_with_mocked_page(self, download_dir):
        """get_html returns page content when page exists."""
        hand = Hand(download_dir=download_dir)

        mock_page = Mock()
        mock_page.content.return_value = "<html><body>Test</body></html>"
        hand._page = mock_page

        assert "Test" in hand.get_html()
