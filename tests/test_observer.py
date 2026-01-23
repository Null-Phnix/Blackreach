"""
Unit tests for blackreach/observer.py (Eyes)

Tests HTML parsing, element extraction, and LLM-optimized output.
"""

import pytest
from blackreach.observer import Eyes, EyesConfig


# =============================================================================
# Basic Parsing Tests
# =============================================================================

class TestEyesBasic:
    """Basic parsing functionality tests."""

    def test_init_default_config(self):
        """Eyes initializes with default config."""
        eyes = Eyes()
        assert eyes.config.max_text_length == 8000
        assert eyes.config.max_links == 50

    def test_init_custom_config(self):
        """Eyes accepts custom config."""
        config = EyesConfig(max_links=10, max_text_length=1000)
        eyes = Eyes(config)
        assert eyes.config.max_links == 10
        assert eyes.config.max_text_length == 1000

    def test_see_returns_dict(self, simple_html):
        """see() returns a dictionary with expected keys."""
        eyes = Eyes()
        result = eyes.see(simple_html)

        assert isinstance(result, dict)
        assert "text" in result
        assert "links" in result
        assert "inputs" in result
        assert "buttons" in result
        assert "headings" in result
        assert "forms" in result
        assert "images" in result

    def test_see_removes_script_tags(self):
        """Script tags are removed from output."""
        html = """
        <html>
        <body>
            <p>Visible text</p>
            <script>alert('hidden');</script>
        </body>
        </html>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert "Visible text" in result["text"]
        assert "alert" not in result["text"]
        assert "hidden" not in result["text"]

    def test_see_removes_style_tags(self):
        """Style tags are removed from output."""
        html = """
        <html>
        <body>
            <p>Visible text</p>
            <style>.hidden { display: none; }</style>
        </body>
        </html>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert "Visible text" in result["text"]
        assert "display" not in result["text"]


# =============================================================================
# Link Extraction Tests
# =============================================================================

class TestLinkExtraction:
    """Tests for link extraction functionality."""

    def test_extract_basic_links(self, simple_html):
        """Basic links are extracted."""
        eyes = Eyes()
        result = eyes.see(simple_html)

        links = result["links"]
        assert len(links) == 2

        hrefs = [l["href"] for l in links]
        assert "/page1" in hrefs
        assert "/page2" in hrefs

    def test_link_text_extracted(self, simple_html):
        """Link text is captured."""
        eyes = Eyes()
        result = eyes.see(simple_html)

        texts = [l["text"] for l in result["links"]]
        assert "Link 1" in texts
        assert "Link 2" in texts

    def test_skip_empty_links(self):
        """Links with no text are skipped."""
        html = """
        <a href="/page1">Valid Link</a>
        <a href="/page2"></a>
        <a href="/page3">   </a>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["links"]) == 1
        assert result["links"][0]["text"] == "Valid Link"

    def test_skip_anchor_only_links(self):
        """Links that are just # are skipped."""
        html = """
        <a href="/page1">Valid Link</a>
        <a href="#">Skip Me</a>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["links"]) == 1

    def test_deduplicate_links(self):
        """Duplicate href links are removed."""
        html = """
        <a href="/page1">First</a>
        <a href="/page1">Second</a>
        <a href="/page2">Third</a>
        """
        eyes = Eyes()
        result = eyes.see(html)

        hrefs = [l["href"] for l in result["links"]]
        assert hrefs.count("/page1") == 1

    def test_link_selector_generated(self):
        """Links have CSS selectors."""
        html = '<a href="/page" id="my-link">Click me</a>'
        eyes = Eyes()
        result = eyes.see(html)

        assert result["links"][0]["selector"] == "#my-link"

    def test_links_respect_limit(self):
        """Number of links respects config limit."""
        html = "".join([f'<a href="/page{i}">Link {i}</a>' for i in range(100)])
        config = EyesConfig(max_links=10)
        eyes = Eyes(config)
        result = eyes.see(html)

        assert len(result["links"]) == 10

    def test_arxiv_links_extracted(self, arxiv_search_html):
        """ArXiv-style links are properly extracted."""
        eyes = Eyes()
        result = eyes.see(arxiv_search_html)

        hrefs = [l["href"] for l in result["links"]]
        assert "/abs/2401.12345" in hrefs
        assert "/pdf/2401.12345.pdf" in hrefs


# =============================================================================
# Input Extraction Tests
# =============================================================================

class TestInputExtraction:
    """Tests for form input extraction."""

    def test_extract_text_input(self, simple_html):
        """Text inputs are extracted."""
        eyes = Eyes()
        result = eyes.see(simple_html)

        inputs = result["inputs"]
        assert len(inputs) >= 1

        search_input = next((i for i in inputs if i.get("id") == "search"), None)
        assert search_input is not None
        assert search_input["placeholder"] == "Search..."

    def test_extract_textarea(self):
        """Textareas are extracted."""
        html = '<textarea id="comment" placeholder="Enter comment"></textarea>'
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["inputs"]) == 1
        assert result["inputs"][0]["id"] == "comment"

    def test_skip_hidden_inputs(self):
        """Hidden inputs are skipped."""
        html = """
        <input type="text" id="visible">
        <input type="hidden" id="hidden">
        """
        eyes = Eyes()
        result = eyes.see(html)

        ids = [i.get("id") for i in result["inputs"]]
        assert "visible" in ids
        assert "hidden" not in ids

    def test_input_label_from_for(self):
        """Input label is extracted from associated label element."""
        html = """
        <label for="email">Email Address</label>
        <input type="email" id="email">
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert result["inputs"][0]["label"] == "Email Address"

    def test_input_aria_label(self):
        """Input aria-label is extracted."""
        html = '<input type="text" aria-label="Search query">'
        eyes = Eyes()
        result = eyes.see(html)

        assert result["inputs"][0]["label"] == "Search query"

    def test_input_required_flag(self):
        """Required attribute is captured."""
        html = """
        <input type="text" id="required-field" required>
        <input type="text" id="optional-field">
        """
        eyes = Eyes()
        result = eyes.see(html)

        required = next(i for i in result["inputs"] if i["id"] == "required-field")
        optional = next(i for i in result["inputs"] if i["id"] == "optional-field")

        assert required["required"] is True
        assert optional["required"] is False


# =============================================================================
# Button Extraction Tests
# =============================================================================

class TestButtonExtraction:
    """Tests for button extraction."""

    def test_extract_button_element(self, simple_html):
        """Button elements are extracted."""
        eyes = Eyes()
        result = eyes.see(simple_html)

        buttons = result["buttons"]
        texts = [b["text"] for b in buttons]
        assert "Submit" in texts

    def test_extract_submit_input(self):
        """Submit inputs are treated as buttons."""
        html = '<input type="submit" value="Send">'
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["buttons"]) == 1
        assert result["buttons"][0]["text"] == "Send"

    def test_extract_button_input(self):
        """Button-type inputs are extracted."""
        html = '<input type="button" value="Click Me">'
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["buttons"]) == 1
        assert result["buttons"][0]["text"] == "Click Me"

    def test_extract_role_button(self):
        """Elements with role="button" are extracted."""
        html = '<div role="button">Custom Button</div>'
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["buttons"]) == 1
        assert result["buttons"][0]["text"] == "Custom Button"
        assert result["buttons"][0]["type"] == "role-button"

    def test_deduplicate_buttons(self):
        """Duplicate button text is deduplicated."""
        html = """
        <button>Submit</button>
        <button>Submit</button>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["buttons"]) == 1


# =============================================================================
# Heading Extraction Tests
# =============================================================================

class TestHeadingExtraction:
    """Tests for heading extraction."""

    def test_extract_headings(self, simple_html):
        """Headings are extracted."""
        eyes = Eyes()
        result = eyes.see(simple_html)

        headings = result["headings"]
        assert len(headings) >= 1
        assert headings[0]["text"] == "Welcome"
        assert headings[0]["level"] == 1

    def test_heading_levels(self):
        """All heading levels are captured."""
        html = """
        <h1>Level 1</h1>
        <h2>Level 2</h2>
        <h3>Level 3</h3>
        """
        eyes = Eyes()
        result = eyes.see(html)

        levels = [h["level"] for h in result["headings"]]
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    def test_skip_empty_headings(self):
        """Empty headings are skipped."""
        html = """
        <h1>Valid</h1>
        <h2></h2>
        <h3>   </h3>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["headings"]) == 1


# =============================================================================
# Image Extraction Tests
# =============================================================================

class TestImageExtraction:
    """Tests for image extraction."""

    def test_extract_images(self, image_gallery_html):
        """Images are extracted from gallery."""
        eyes = Eyes()
        result = eyes.see(image_gallery_html)

        assert len(result["images"]) >= 2

    def test_image_src_captured(self, image_gallery_html):
        """Image src is captured."""
        eyes = Eyes()
        result = eyes.see(image_gallery_html)

        srcs = [i["src"] for i in result["images"]]
        assert any("/thumb/" in s for s in srcs)

    def test_image_link_captured(self, image_gallery_html):
        """Parent link href is captured for images."""
        eyes = Eyes()
        result = eyes.see(image_gallery_html)

        # Images inside links should have link field populated
        linked_images = [i for i in result["images"] if i["link"]]
        assert len(linked_images) >= 1

    def test_skip_icon_images(self):
        """Icon images are skipped."""
        html = """
        <img src="/images/photo.jpg" alt="Photo">
        <img src="/icons/menu-icon.png" alt="Menu">
        <img src="/logo.png" alt="Logo">
        """
        eyes = Eyes()
        result = eyes.see(html)

        srcs = [i["src"] for i in result["images"]]
        assert "/images/photo.jpg" in srcs
        assert not any("icon" in s for s in srcs)
        assert not any("logo" in s for s in srcs)

    def test_data_src_fallback(self):
        """data-src is used when src is missing."""
        html = '<img data-src="/lazy-image.jpg" alt="Lazy">'
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["images"]) == 1
        assert result["images"][0]["src"] == "/lazy-image.jpg"


# =============================================================================
# Form Extraction Tests
# =============================================================================

class TestFormExtraction:
    """Tests for form structure extraction."""

    def test_extract_form(self):
        """Forms are extracted with structure."""
        html = """
        <form action="/search" method="GET" id="search-form">
            <input type="text" name="q" placeholder="Search">
            <button type="submit">Go</button>
        </form>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert len(result["forms"]) == 1
        form = result["forms"][0]
        assert form["action"] == "/search"
        assert form["method"] == "GET"
        assert form["id"] == "search-form"
        assert len(form["fields"]) == 1  # Hidden fields excluded

    def test_form_fields_extracted(self):
        """Form fields are extracted."""
        html = """
        <form>
            <input type="text" name="username">
            <input type="password" name="password">
            <input type="hidden" name="csrf">
        </form>
        """
        eyes = Eyes()
        result = eyes.see(html)

        fields = result["forms"][0]["fields"]
        names = [f["name"] for f in fields]

        assert "username" in names
        assert "password" in names
        assert "csrf" not in names  # Hidden excluded


# =============================================================================
# Selector Generation Tests
# =============================================================================

class TestSelectorGeneration:
    """Tests for CSS selector generation."""

    def test_selector_uses_id(self):
        """ID is preferred for selectors."""
        html = '<button id="submit-btn" class="btn primary">Submit</button>'
        eyes = Eyes()
        result = eyes.see(html)

        assert result["buttons"][0]["selector"] == "#submit-btn"

    def test_selector_uses_name(self):
        """Name attribute is used when no ID."""
        html = '<input name="email" type="email">'
        eyes = Eyes()
        result = eyes.see(html)

        assert result["inputs"][0]["selector"] == "[name='email']"

    def test_selector_uses_data_testid(self):
        """data-testid is used when available."""
        html = '<button data-testid="login-btn">Login</button>'
        eyes = Eyes()
        result = eyes.see(html)

        assert "data-testid" in result["buttons"][0]["selector"]

    def test_selector_uses_class(self):
        """Class is used as fallback."""
        html = '<button class="btn primary">Click</button>'
        eyes = Eyes()
        result = eyes.see(html)

        assert "btn" in result["buttons"][0]["selector"]


# =============================================================================
# Output Format Tests
# =============================================================================

class TestOutputFormats:
    """Tests for different output formats."""

    def test_see_simple_format(self, simple_html):
        """see_simple() returns formatted string."""
        eyes = Eyes()
        output = eyes.see_simple(simple_html)

        assert isinstance(output, str)
        assert "PAGE CONTENT" in output
        assert "INPUT FIELDS" in output
        assert "BUTTONS" in output
        assert "LINKS" in output

    def test_see_for_llm_format(self, simple_html):
        """see_for_llm() returns LLM-optimized string."""
        eyes = Eyes()
        output = eyes.see_for_llm(simple_html)

        assert isinstance(output, str)
        assert "##" in output  # Markdown headers

    def test_see_for_llm_respects_token_limit(self, simple_html):
        """see_for_llm() respects max_tokens parameter."""
        eyes = Eyes()
        short = eyes.see_for_llm(simple_html, max_tokens=100)
        long = eyes.see_for_llm(simple_html, max_tokens=10000)

        assert len(short) < len(long)


# =============================================================================
# Caching Tests
# =============================================================================

class TestCaching:
    """Tests for parsing cache."""

    def test_cache_enabled_by_default(self, simple_html):
        """Caching is enabled by default."""
        eyes = Eyes()
        eyes.see(simple_html)

        assert len(eyes._cache) == 1

    def test_cache_can_be_disabled(self, simple_html):
        """Caching can be disabled."""
        config = EyesConfig(use_cache=False)
        eyes = Eyes(config)
        eyes.see(simple_html)

        assert len(eyes._cache) == 0

    def test_cache_returns_same_result(self, simple_html):
        """Cached results are returned on second call."""
        eyes = Eyes()
        result1 = eyes.see(simple_html)
        result2 = eyes.see(simple_html)

        assert result1 is result2  # Same object from cache

    def test_clear_cache(self, simple_html):
        """clear_cache() empties the cache."""
        eyes = Eyes()
        eyes.see(simple_html)
        assert len(eyes._cache) == 1

        eyes.clear_cache()
        assert len(eyes._cache) == 0

    def test_cache_size_limit(self):
        """Cache respects size limit."""
        config = EyesConfig(cache_size=2)
        eyes = Eyes(config)

        eyes.see("<html>1</html>")
        eyes.see("<html>2</html>")
        eyes.see("<html>3</html>")  # Should not be cached (limit reached)

        assert len(eyes._cache) == 2


# =============================================================================
# Content Prioritization Tests
# =============================================================================

class TestContentPrioritization:
    """Tests for main content prioritization."""

    def test_main_content_prioritized(self):
        """Content in <main> is prioritized."""
        html = """
        <html>
        <body>
            <nav>Navigation stuff</nav>
            <main>Important content here</main>
            <footer>Footer stuff</footer>
        </body>
        </html>
        """
        eyes = Eyes()
        result = eyes.see(html)

        # Main content should appear first
        text = result["text"]
        main_pos = text.find("Important")
        nav_pos = text.find("Navigation") if "Navigation" in text else 9999
        footer_pos = text.find("Footer") if "Footer" in text else 9999

        assert main_pos < nav_pos or nav_pos == 9999
        assert main_pos < footer_pos or footer_pos == 9999

    def test_article_content_prioritized(self):
        """Content in <article> is prioritized."""
        html = """
        <html>
        <body>
            <aside>Sidebar</aside>
            <article>Article content</article>
        </body>
        </html>
        """
        eyes = Eyes()
        result = eyes.see(html)

        assert "Article content" in result["text"]

    def test_prioritization_can_be_disabled(self):
        """Content prioritization can be disabled."""
        config = EyesConfig(prioritize_main_content=False)
        eyes = Eyes(config)

        html = "<main>Main</main><nav>Nav</nav>"
        result = eyes.see(html)

        # Both should be in output without prioritization
        assert "Main" in result["text"]
        assert "Nav" in result["text"]


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_html(self):
        """Empty HTML doesn't crash."""
        eyes = Eyes()
        result = eyes.see("")

        assert result["text"] == ""
        assert result["links"] == []

    def test_malformed_html(self):
        """Malformed HTML is handled gracefully."""
        html = "<div><p>Unclosed tags<span>More text"
        eyes = Eyes()
        result = eyes.see(html)

        assert "Unclosed" in result["text"]

    def test_unicode_content(self):
        """Unicode content is handled."""
        html = "<p>日本語テスト</p><a href='/'>リンク</a>"
        eyes = Eyes()
        result = eyes.see(html)

        assert "日本語" in result["text"]
        assert result["links"][0]["text"] == "リンク"

    def test_very_long_text_truncated(self):
        """Very long text is truncated."""
        config = EyesConfig(max_text_length=100)
        eyes = Eyes(config)

        html = f"<p>{'a' * 1000}</p>"
        result = eyes.see(html)

        assert len(result["text"]) <= 100

    def test_deeply_nested_elements(self):
        """Deeply nested elements are handled."""
        # Create 50 levels of nesting
        html = "<div>" * 50 + "<p>Deep content</p>" + "</div>" * 50
        eyes = Eyes()
        result = eyes.see(html)

        assert "Deep content" in result["text"]
