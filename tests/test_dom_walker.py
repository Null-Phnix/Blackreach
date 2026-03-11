"""
Unit tests for blackreach/dom_walker.py

Tests the DOM walker module that extracts interactive elements from the
live browser DOM. All browser interactions are mocked - no real browser needed.
"""

import pytest
from unittest.mock import Mock, MagicMock, PropertyMock, patch
from blackreach.dom_walker import (
    walk_dom,
    format_elements,
    format_text_summary,
    _format_single_element,
    _empty_result,
    CONTEXT_PRESETS,
    DOM_WALK_JS,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_page():
    """Create a mock Playwright page object."""
    page = MagicMock()
    page.url = "https://example.com/test"
    return page


@pytest.fixture
def sample_dom_result():
    """Sample DOM walk result with typical elements."""
    return {
        "elements": [
            {"id": 1, "tag": "input", "text": "", "type": "search",
             "placeholder": "Search Wikipedia", "name": "q", "visible": True},
            {"id": 2, "tag": "button", "text": "Search", "visible": True},
            {"id": 3, "tag": "a", "text": "Main page",
             "href": "/wiki/Main_Page", "visible": True},
            {"id": 4, "tag": "a", "text": "Random article",
             "href": "/wiki/Special:Random", "visible": True},
            {"id": 5, "tag": "input", "text": "", "type": "checkbox",
             "checked": True, "name": "remember", "visible": True},
        ],
        "text_summary": "Wikipedia is a free online encyclopedia.",
        "url": "https://en.wikipedia.org/wiki/Main_Page",
        "title": "Wikipedia, the free encyclopedia",
        "total_elements": 5,
        "visible_elements": 5,
        "viewport": {"width": 1920, "height": 1080},
    }


@pytest.fixture
def large_dom_result():
    """DOM result with many elements for cap testing."""
    elements = []
    for i in range(1, 251):
        elements.append({
            "id": i,
            "tag": "a",
            "text": f"Link {i}",
            "href": f"/page/{i}",
            "visible": True,
        })
    return {
        "elements": elements,
        "text_summary": "A page with many links.",
        "url": "https://example.com/many-links",
        "title": "Many Links Page",
        "total_elements": 250,
        "visible_elements": 100,
    }


@pytest.fixture
def empty_dom_result():
    """DOM result with no elements."""
    return {
        "elements": [],
        "text_summary": "",
        "url": "https://example.com/empty",
        "title": "Empty Page",
        "total_elements": 0,
        "visible_elements": 0,
    }


@pytest.fixture
def dom_result_with_select():
    """DOM result with a select element."""
    return {
        "elements": [
            {"id": 1, "tag": "select", "text": "United States",
             "name": "country", "options": ["Select...", "United States", "Canada", "UK"],
             "visible": True},
        ],
        "text_summary": "Select your country.",
        "url": "https://example.com/form",
        "title": "Form Page",
        "total_elements": 1,
        "visible_elements": 1,
    }


# =============================================================================
# TESTS: CONTEXT_PRESETS
# =============================================================================

class TestContextPresets:
    """Tests for CONTEXT_PRESETS configuration."""

    def test_small_preset_exists(self):
        """Small preset is defined."""
        assert "small" in CONTEXT_PRESETS

    def test_medium_preset_exists(self):
        """Medium preset is defined."""
        assert "medium" in CONTEXT_PRESETS

    def test_large_preset_exists(self):
        """Large preset is defined."""
        assert "large" in CONTEXT_PRESETS

    def test_small_max_elements(self):
        """Small preset has maxElements of 100."""
        assert CONTEXT_PRESETS["small"]["maxElements"] == 100

    def test_medium_max_elements(self):
        """Medium preset has maxElements of 150."""
        assert CONTEXT_PRESETS["medium"]["maxElements"] == 150

    def test_large_max_elements(self):
        """Large preset has maxElements of 200."""
        assert CONTEXT_PRESETS["large"]["maxElements"] == 200

    def test_small_text_summary_len(self):
        """Small preset has textSummaryLen of 500."""
        assert CONTEXT_PRESETS["small"]["textSummaryLen"] == 500

    def test_medium_text_summary_len(self):
        """Medium preset has textSummaryLen of 1000."""
        assert CONTEXT_PRESETS["medium"]["textSummaryLen"] == 1000

    def test_large_text_summary_len(self):
        """Large preset has textSummaryLen of 3000."""
        assert CONTEXT_PRESETS["large"]["textSummaryLen"] == 3000

    def test_presets_has_exactly_three_keys(self):
        """CONTEXT_PRESETS contains exactly three size presets."""
        assert len(CONTEXT_PRESETS) == 3

    def test_each_preset_has_max_elements_key(self):
        """Every preset has a maxElements key."""
        for name, preset in CONTEXT_PRESETS.items():
            assert "maxElements" in preset, f"Preset '{name}' missing maxElements"

    def test_each_preset_has_text_summary_len_key(self):
        """Every preset has a textSummaryLen key."""
        for name, preset in CONTEXT_PRESETS.items():
            assert "textSummaryLen" in preset, f"Preset '{name}' missing textSummaryLen"

    def test_presets_ordered_by_size(self):
        """Presets maxElements increase: small < medium < large."""
        assert CONTEXT_PRESETS["small"]["maxElements"] < CONTEXT_PRESETS["medium"]["maxElements"]
        assert CONTEXT_PRESETS["medium"]["maxElements"] < CONTEXT_PRESETS["large"]["maxElements"]

    def test_presets_text_len_ordered_by_size(self):
        """Presets textSummaryLen increase: small < medium < large."""
        assert CONTEXT_PRESETS["small"]["textSummaryLen"] < CONTEXT_PRESETS["medium"]["textSummaryLen"]
        assert CONTEXT_PRESETS["medium"]["textSummaryLen"] < CONTEXT_PRESETS["large"]["textSummaryLen"]


# =============================================================================
# TESTS: DOM_WALK_JS
# =============================================================================

class TestDomWalkJS:
    """Tests for the DOM walk JavaScript constant."""

    def test_js_is_a_string(self):
        """DOM_WALK_JS is a non-empty string."""
        assert isinstance(DOM_WALK_JS, str)
        assert len(DOM_WALK_JS) > 0

    def test_js_is_an_arrow_function(self):
        """DOM_WALK_JS starts with an arrow function signature."""
        assert "(config) =>" in DOM_WALK_JS

    def test_js_returns_elements_key(self):
        """DOM_WALK_JS returns object with elements key."""
        assert "elements:" in DOM_WALK_JS

    def test_js_returns_text_summary_key(self):
        """DOM_WALK_JS returns object with text_summary key."""
        assert "text_summary:" in DOM_WALK_JS

    def test_js_returns_url_key(self):
        """DOM_WALK_JS returns object with url key."""
        assert "url:" in DOM_WALK_JS

    def test_js_sets_data_br_id(self):
        """DOM_WALK_JS sets data-br-id attributes."""
        assert "data-br-id" in DOM_WALK_JS

    def test_js_references_max_elements_config(self):
        """DOM_WALK_JS reads maxElements from config."""
        assert "config.maxElements" in DOM_WALK_JS

    def test_js_references_max_text_len_config(self):
        """DOM_WALK_JS reads maxTextLen from config."""
        assert "config.maxTextLen" in DOM_WALK_JS

    def test_js_references_max_href_len_config(self):
        """DOM_WALK_JS reads maxHrefLen from config."""
        assert "config.maxHrefLen" in DOM_WALK_JS

    def test_js_references_text_summary_len_config(self):
        """DOM_WALK_JS reads textSummaryLen from config."""
        assert "config.textSummaryLen" in DOM_WALK_JS

    def test_js_returns_title_key(self):
        """DOM_WALK_JS returns object with title key."""
        assert "title:" in DOM_WALK_JS

    def test_js_returns_total_elements_key(self):
        """DOM_WALK_JS returns object with total_elements key."""
        assert "total_elements:" in DOM_WALK_JS

    def test_js_returns_visible_elements_key(self):
        """DOM_WALK_JS returns object with visible_elements key."""
        assert "visible_elements:" in DOM_WALK_JS

    def test_js_returns_viewport_key(self):
        """DOM_WALK_JS returns object with viewport key."""
        assert "viewport:" in DOM_WALK_JS

    def test_js_contains_visibility_check(self):
        """DOM_WALK_JS contains isVisible function."""
        assert "isVisible" in DOM_WALK_JS

    def test_js_contains_viewport_check(self):
        """DOM_WALK_JS contains isInViewport function."""
        assert "isInViewport" in DOM_WALK_JS

    def test_js_cleans_previous_br_ids(self):
        """DOM_WALK_JS removes previous data-br-id attributes."""
        assert "removeAttribute" in DOM_WALK_JS


# =============================================================================
# TESTS: walk_dom()
# =============================================================================

class TestWalkDom:
    """Tests for walk_dom() function."""

    def test_normal_page_returns_result(self, mock_page, sample_dom_result):
        """walk_dom returns structured result for normal page."""
        mock_page.evaluate.return_value = sample_dom_result

        result = walk_dom(mock_page)

        assert result is sample_dom_result
        assert "elements" in result
        assert "text_summary" in result
        assert "url" in result
        assert "title" in result

    def test_calls_page_evaluate_with_js(self, mock_page, sample_dom_result):
        """walk_dom calls page.evaluate with DOM_WALK_JS and config."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page)

        mock_page.evaluate.assert_called_once()
        call_args = mock_page.evaluate.call_args
        assert call_args[0][0] == DOM_WALK_JS

    def test_passes_config_to_evaluate(self, mock_page, sample_dom_result):
        """walk_dom passes correct config dict to page.evaluate."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="large")

        call_args = mock_page.evaluate.call_args
        config = call_args[0][1]
        assert config["maxElements"] == 200
        assert config["maxTextLen"] == 60
        assert config["maxHrefLen"] == 120
        assert config["textSummaryLen"] == 3000

    def test_small_context_config(self, mock_page, sample_dom_result):
        """walk_dom passes small context config correctly."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="small")

        call_args = mock_page.evaluate.call_args
        config = call_args[0][1]
        assert config["maxElements"] == 100
        assert config["textSummaryLen"] == 500

    def test_medium_context_config(self, mock_page, sample_dom_result):
        """walk_dom passes medium context config correctly."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="medium")

        call_args = mock_page.evaluate.call_args
        config = call_args[0][1]
        assert config["maxElements"] == 150
        assert config["textSummaryLen"] == 1000

    def test_large_context_config(self, mock_page, sample_dom_result):
        """walk_dom passes large context config correctly."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="large")

        call_args = mock_page.evaluate.call_args
        config = call_args[0][1]
        assert config["maxElements"] == 200
        assert config["textSummaryLen"] == 3000

    def test_unknown_context_size_defaults_to_large(self, mock_page, sample_dom_result):
        """walk_dom falls back to large preset for unknown context_size."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="unknown_size")

        call_args = mock_page.evaluate.call_args
        config = call_args[0][1]
        assert config["maxElements"] == 200
        assert config["textSummaryLen"] == 3000

    def test_max_elements_override(self, mock_page, sample_dom_result):
        """walk_dom max_elements parameter overrides context_size preset."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="small", max_elements=50)

        call_args = mock_page.evaluate.call_args
        config = call_args[0][1]
        assert config["maxElements"] == 50
        # textSummaryLen still follows the context_size preset
        assert config["textSummaryLen"] == 500

    def test_max_elements_none_uses_preset(self, mock_page, sample_dom_result):
        """walk_dom with max_elements=None uses preset value."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="medium", max_elements=None)

        call_args = mock_page.evaluate.call_args
        config = call_args[0][1]
        assert config["maxElements"] == 150

    def test_empty_page_returns_empty_elements(self, mock_page, empty_dom_result):
        """walk_dom handles page with no interactive elements."""
        mock_page.evaluate.return_value = empty_dom_result

        result = walk_dom(mock_page)

        assert result["elements"] == []
        assert result["total_elements"] == 0
        assert result["visible_elements"] == 0

    def test_evaluate_exception_returns_empty_result(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate raises."""
        mock_page.evaluate.side_effect = Exception("Page crashed")

        result = walk_dom(mock_page)

        assert result["elements"] == []
        assert result["error"] == "Page crashed"
        assert result["url"] == "https://example.com/test"

    def test_evaluate_timeout_returns_empty_result(self, mock_page):
        """walk_dom handles timeout errors from page.evaluate."""
        mock_page.evaluate.side_effect = TimeoutError("Execution context was destroyed")

        result = walk_dom(mock_page)

        assert result["elements"] == []
        assert "error" in result

    def test_non_dict_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate returns non-dict."""
        mock_page.evaluate.return_value = "not a dict"

        result = walk_dom(mock_page)

        assert result["elements"] == []
        assert result["url"] == "https://example.com/test"

    def test_none_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate returns None."""
        mock_page.evaluate.return_value = None

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_dict_without_elements_key_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when result dict lacks 'elements' key."""
        mock_page.evaluate.return_value = {"url": "https://example.com", "title": "Test"}

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_list_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate returns a list."""
        mock_page.evaluate.return_value = [1, 2, 3]

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_integer_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate returns an integer."""
        mock_page.evaluate.return_value = 42

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_result_preserves_all_keys(self, mock_page, sample_dom_result):
        """walk_dom preserves all keys from the JavaScript result."""
        mock_page.evaluate.return_value = sample_dom_result

        result = walk_dom(mock_page)

        assert result["url"] == "https://en.wikipedia.org/wiki/Main_Page"
        assert result["title"] == "Wikipedia, the free encyclopedia"
        assert result["total_elements"] == 5
        assert result["visible_elements"] == 5
        assert len(result["elements"]) == 5

    def test_boolean_true_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate returns True."""
        mock_page.evaluate.return_value = True

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_boolean_false_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate returns False."""
        mock_page.evaluate.return_value = False

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_float_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result when page.evaluate returns a float."""
        mock_page.evaluate.return_value = 3.14

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_empty_dict_result_returns_empty(self, mock_page):
        """walk_dom returns _empty_result for empty dict (no 'elements' key)."""
        mock_page.evaluate.return_value = {}

        result = walk_dom(mock_page)

        assert result["elements"] == []

    def test_max_elements_large_value_override(self, mock_page, sample_dom_result):
        """walk_dom with very large max_elements passes it through."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, max_elements=9999)

        config = mock_page.evaluate.call_args[0][1]
        assert config["maxElements"] == 9999

    def test_max_elements_one(self, mock_page, sample_dom_result):
        """walk_dom with max_elements=1 passes it through."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, max_elements=1)

        config = mock_page.evaluate.call_args[0][1]
        assert config["maxElements"] == 1

    def test_config_always_has_four_keys(self, mock_page, sample_dom_result):
        """walk_dom always passes config with exactly 4 keys."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page)

        config = mock_page.evaluate.call_args[0][1]
        assert set(config.keys()) == {"maxElements", "maxTextLen", "maxHrefLen", "textSummaryLen"}

    def test_config_max_text_len_always_60(self, mock_page, sample_dom_result):
        """walk_dom always sets maxTextLen to 60 regardless of context_size."""
        for size in ["small", "medium", "large"]:
            mock_page.evaluate.return_value = sample_dom_result
            walk_dom(mock_page, context_size=size)
            config = mock_page.evaluate.call_args[0][1]
            assert config["maxTextLen"] == 60

    def test_config_max_href_len_always_120(self, mock_page, sample_dom_result):
        """walk_dom always sets maxHrefLen to 120 regardless of context_size."""
        for size in ["small", "medium", "large"]:
            mock_page.evaluate.return_value = sample_dom_result
            walk_dom(mock_page, context_size=size)
            config = mock_page.evaluate.call_args[0][1]
            assert config["maxHrefLen"] == 120

    def test_evaluate_called_exactly_once(self, mock_page, sample_dom_result):
        """walk_dom calls page.evaluate exactly once."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page)

        assert mock_page.evaluate.call_count == 1

    def test_runtime_error_returns_empty_result(self, mock_page):
        """walk_dom handles RuntimeError from page.evaluate."""
        mock_page.evaluate.side_effect = RuntimeError("Frame detached")

        result = walk_dom(mock_page)

        assert result["elements"] == []
        assert "Frame detached" in result["error"]

    def test_keyboard_interrupt_propagates(self, mock_page):
        """walk_dom does not catch KeyboardInterrupt (it is BaseException, not Exception)."""
        mock_page.evaluate.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            walk_dom(mock_page)

    def test_error_logging_on_exception(self, mock_page):
        """walk_dom logs an error when page.evaluate raises."""
        mock_page.evaluate.side_effect = Exception("Eval failed")

        with patch("blackreach.dom_walker.logger") as mock_logger:
            walk_dom(mock_page)
            mock_logger.error.assert_called_once()

    def test_no_error_key_on_success(self, mock_page, sample_dom_result):
        """walk_dom result has no 'error' key on success."""
        mock_page.evaluate.return_value = sample_dom_result

        result = walk_dom(mock_page)

        assert "error" not in result

    def test_result_with_extra_keys_preserved(self, mock_page):
        """walk_dom preserves extra keys returned by JavaScript."""
        custom_result = {
            "elements": [{"id": 1, "tag": "a", "text": "Link"}],
            "text_summary": "test",
            "url": "https://test.com",
            "title": "Test",
            "total_elements": 1,
            "visible_elements": 1,
            "custom_key": "custom_value",
        }
        mock_page.evaluate.return_value = custom_result

        result = walk_dom(mock_page)

        assert result["custom_key"] == "custom_value"


# =============================================================================
# TESTS: _empty_result()
# =============================================================================

class TestEmptyResult:
    """Tests for _empty_result() helper function."""

    def test_returns_dict(self):
        """_empty_result returns a dictionary."""
        result = _empty_result()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """_empty_result has all required keys."""
        result = _empty_result()
        assert "elements" in result
        assert "text_summary" in result
        assert "url" in result
        assert "title" in result
        assert "total_elements" in result
        assert "visible_elements" in result

    def test_elements_is_empty_list(self):
        """_empty_result elements is empty list."""
        result = _empty_result()
        assert result["elements"] == []

    def test_text_summary_is_empty(self):
        """_empty_result text_summary is empty string."""
        result = _empty_result()
        assert result["text_summary"] == ""

    def test_title_is_empty(self):
        """_empty_result title is empty string."""
        result = _empty_result()
        assert result["title"] == ""

    def test_totals_are_zero(self):
        """_empty_result totals are zero."""
        result = _empty_result()
        assert result["total_elements"] == 0
        assert result["visible_elements"] == 0

    def test_with_page_url(self, mock_page):
        """_empty_result extracts URL from page object."""
        result = _empty_result(page=mock_page)
        assert result["url"] == "https://example.com/test"

    def test_with_none_page(self):
        """_empty_result handles None page."""
        result = _empty_result(page=None)
        assert result["url"] == ""

    def test_without_page(self):
        """_empty_result handles no page argument."""
        result = _empty_result()
        assert result["url"] == ""

    def test_with_error_message(self):
        """_empty_result includes error when provided."""
        result = _empty_result(error="Something went wrong")
        assert result["error"] == "Something went wrong"

    def test_without_error_message(self):
        """_empty_result has no error key when no error provided."""
        result = _empty_result()
        assert "error" not in result

    def test_with_empty_error_string(self):
        """_empty_result omits error key for empty error string."""
        result = _empty_result(error="")
        assert "error" not in result

    def test_page_url_access_exception(self):
        """_empty_result handles exception when accessing page.url."""
        page = Mock()
        type(page).url = PropertyMock(side_effect=Exception("Detached"))

        result = _empty_result(page=page)

        assert result["url"] == ""

    def test_with_page_and_error(self, mock_page):
        """_empty_result includes both URL and error."""
        result = _empty_result(page=mock_page, error="DOM walk failed")

        assert result["url"] == "https://example.com/test"
        assert result["error"] == "DOM walk failed"

    def test_returns_new_dict_each_call(self):
        """_empty_result returns a new dict on each call (not shared)."""
        result1 = _empty_result()
        result2 = _empty_result()
        assert result1 is not result2

    def test_elements_list_is_independent(self):
        """_empty_result elements lists are independent between calls."""
        result1 = _empty_result()
        result2 = _empty_result()
        result1["elements"].append("should not appear in result2")
        assert result2["elements"] == []

    def test_page_with_empty_url(self):
        """_empty_result handles page with empty string URL."""
        page = Mock()
        page.url = ""
        result = _empty_result(page=page)
        assert result["url"] == ""

    def test_error_with_special_characters(self):
        """_empty_result stores error messages with special characters."""
        result = _empty_result(error='Error: "timeout" at line 42')
        assert result["error"] == 'Error: "timeout" at line 42'

    def test_has_exactly_six_keys_without_error(self):
        """_empty_result without error has exactly 6 keys."""
        result = _empty_result()
        assert len(result) == 6

    def test_has_exactly_seven_keys_with_error(self):
        """_empty_result with error has exactly 7 keys."""
        result = _empty_result(error="fail")
        assert len(result) == 7

    def test_page_url_attribute_error(self):
        """_empty_result handles page without url attribute."""
        page = Mock(spec=[])  # No attributes at all
        result = _empty_result(page=page)
        assert result["url"] == ""


# =============================================================================
# TESTS: _format_single_element()
# =============================================================================

class TestFormatSingleElement:
    """Tests for _format_single_element() function."""

    def test_basic_link(self):
        """Format a basic link element."""
        el = {"id": 1, "tag": "a", "text": "Home", "href": "/home"}
        result = _format_single_element(el)
        assert result == '[1] <a href="/home"> "Home"'

    def test_link_with_long_href_truncated(self):
        """Format a link with href longer than 80 chars gets truncated."""
        long_href = "https://example.com/" + "a" * 100
        el = {"id": 1, "tag": "a", "text": "Long Link", "href": long_href}
        result = _format_single_element(el)

        assert '...' in result
        # The href in the output should be 77 chars + "..."
        assert len(long_href) > 80
        assert f'href="{long_href[:77]}..."' in result

    def test_link_with_short_href_not_truncated(self):
        """Format a link with href under 80 chars is not truncated."""
        short_href = "https://example.com/page"
        el = {"id": 1, "tag": "a", "text": "Short", "href": short_href}
        result = _format_single_element(el)
        assert f'href="{short_href}"' in result
        assert "..." not in result

    def test_link_with_exactly_80_char_href(self):
        """Format a link with exactly 80 char href is not truncated."""
        href_80 = "https://example.com/" + "x" * 60  # exactly 80 chars
        assert len(href_80) == 80
        el = {"id": 1, "tag": "a", "text": "Exact", "href": href_80}
        result = _format_single_element(el)
        assert f'href="{href_80}"' in result
        assert "..." not in result

    def test_search_input(self):
        """Format a search input element."""
        el = {"id": 2, "tag": "input", "text": "", "type": "search",
              "placeholder": "Search...", "name": "q"}
        result = _format_single_element(el)
        assert '[2] <input' in result
        assert 'type="search"' in result
        assert 'placeholder="Search..."' in result
        assert 'name="q"' in result

    def test_text_input(self):
        """Format a text input element."""
        el = {"id": 3, "tag": "input", "text": "", "type": "text",
              "placeholder": "Enter name", "name": "username"}
        result = _format_single_element(el)
        assert 'type="text"' in result
        assert 'placeholder="Enter name"' in result
        assert 'name="username"' in result

    def test_button_with_text(self):
        """Format a button element with text."""
        el = {"id": 4, "tag": "button", "text": "Submit"}
        result = _format_single_element(el)
        assert result == '[4] <button> "Submit"'

    def test_button_with_aria_label_no_text(self):
        """Format a button with aria-label but no text shows aria-label."""
        el = {"id": 5, "tag": "button", "text": "", "aria-label": "Close dialog"}
        result = _format_single_element(el)
        assert 'aria-label="Close dialog"' in result

    def test_button_with_text_and_aria_label(self):
        """Format a button with both text and aria-label shows text, not aria-label."""
        el = {"id": 6, "tag": "button", "text": "Close", "aria-label": "Close dialog"}
        result = _format_single_element(el)
        assert '"Close"' in result
        # aria-label should NOT be shown when text is present
        assert "aria-label" not in result

    def test_checkbox_checked(self):
        """Format a checked checkbox."""
        el = {"id": 7, "tag": "input", "text": "", "type": "checkbox",
              "checked": True, "name": "agree"}
        result = _format_single_element(el)
        assert 'type="checkbox"' in result
        assert "checked" in result
        assert 'name="agree"' in result

    def test_checkbox_unchecked(self):
        """Format an unchecked checkbox does not show 'checked'."""
        el = {"id": 8, "tag": "input", "text": "", "type": "checkbox",
              "checked": False, "name": "agree"}
        result = _format_single_element(el)
        assert 'type="checkbox"' in result
        # "checked" should not appear as a standalone attribute
        # It appears inside type="checkbox" but not as a separate attr
        parts = result.split()
        standalone_checked = [p for p in parts if p == "checked"]
        assert len(standalone_checked) == 0

    def test_select_with_options(self, dom_result_with_select):
        """Format a select element (options are not shown in _format_single_element)."""
        el = dom_result_with_select["elements"][0]
        result = _format_single_element(el)
        assert '[1] <select' in result
        assert 'name="country"' in result
        assert '"United States"' in result

    def test_textarea(self):
        """Format a textarea element."""
        el = {"id": 9, "tag": "textarea", "text": "",
              "placeholder": "Enter message", "name": "message"}
        result = _format_single_element(el)
        assert '[9] <textarea' in result
        assert 'placeholder="Enter message"' in result
        assert 'name="message"' in result

    def test_element_with_no_id(self):
        """Format element without id uses '?'."""
        el = {"tag": "a", "text": "Link", "href": "/page"}
        result = _format_single_element(el)
        assert "[?]" in result

    def test_element_with_no_tag(self):
        """Format element without tag uses '?'."""
        el = {"id": 1, "text": "Something"}
        result = _format_single_element(el)
        assert "<?" in result

    def test_element_with_no_text(self):
        """Format element without text shows no quoted text."""
        el = {"id": 1, "tag": "input", "type": "hidden"}
        result = _format_single_element(el)
        # Should not have quoted text
        assert '" "' not in result
        assert result.endswith('"hidden">')

    def test_name_attribute_only_for_form_elements(self):
        """Name attribute is only shown for input/textarea/select."""
        # For a link (non-form element), name should NOT be shown
        el = {"id": 1, "tag": "a", "text": "Link", "name": "nav-link"}
        result = _format_single_element(el)
        assert 'name=' not in result

    def test_name_attribute_for_input(self):
        """Name attribute is shown for input elements."""
        el = {"id": 1, "tag": "input", "text": "", "type": "text", "name": "email"}
        result = _format_single_element(el)
        assert 'name="email"' in result

    def test_name_attribute_for_textarea(self):
        """Name attribute is shown for textarea elements."""
        el = {"id": 1, "tag": "textarea", "text": "", "name": "comment"}
        result = _format_single_element(el)
        assert 'name="comment"' in result

    def test_name_attribute_for_select(self):
        """Name attribute is shown for select elements."""
        el = {"id": 1, "tag": "select", "text": "Option 1", "name": "choice"}
        result = _format_single_element(el)
        assert 'name="choice"' in result

    def test_empty_dict(self):
        """Format empty element dict returns a minimal line."""
        result = _format_single_element({})
        assert result == "[?] <?>"

    def test_all_attributes_combined(self):
        """Format element with multiple attributes."""
        el = {"id": 10, "tag": "input", "text": "", "type": "email",
              "placeholder": "user@example.com", "name": "email"}
        result = _format_single_element(el)
        assert '[10] <input' in result
        assert 'type="email"' in result
        assert 'placeholder="user@example.com"' in result
        assert 'name="email"' in result

    def test_radio_button(self):
        """Format a radio button input."""
        el = {"id": 11, "tag": "input", "text": "", "type": "radio",
              "checked": True, "name": "gender"}
        result = _format_single_element(el)
        assert 'type="radio"' in result
        assert "checked" in result
        assert 'name="gender"' in result

    def test_radio_button_unchecked(self):
        """Format an unchecked radio button does not show 'checked'."""
        el = {"id": 12, "tag": "input", "text": "", "type": "radio",
              "checked": False, "name": "gender"}
        result = _format_single_element(el)
        assert 'type="radio"' in result
        parts = result.split()
        standalone_checked = [p for p in parts if p == "checked"]
        assert len(standalone_checked) == 0

    def test_link_without_href(self):
        """Format a link element without href attribute."""
        el = {"id": 1, "tag": "a", "text": "Click here"}
        result = _format_single_element(el)
        assert "href" not in result
        assert '"Click here"' in result

    def test_element_with_empty_text_string(self):
        """Format element with explicitly empty text string."""
        el = {"id": 1, "tag": "button", "text": ""}
        result = _format_single_element(el)
        assert result == "[1] <button>"

    def test_element_with_none_text(self):
        """Format element where text key is None (treated as falsy)."""
        el = {"id": 1, "tag": "div", "text": None}
        result = _format_single_element(el)
        # None is falsy, so no text_str appended
        assert result == "[1] <div>"

    def test_input_with_no_type(self):
        """Format an input element with no type attribute."""
        el = {"id": 1, "tag": "input", "text": "", "name": "field"}
        result = _format_single_element(el)
        assert 'name="field"' in result
        assert 'type=' not in result

    def test_name_not_shown_for_button(self):
        """Name attribute is not shown for button elements."""
        el = {"id": 1, "tag": "button", "text": "Submit", "name": "btn-submit"}
        result = _format_single_element(el)
        assert 'name=' not in result

    def test_name_not_shown_for_div(self):
        """Name attribute is not shown for div elements."""
        el = {"id": 1, "tag": "div", "text": "Section", "name": "section-1"}
        result = _format_single_element(el)
        assert 'name=' not in result

    def test_checked_none_is_not_shown(self):
        """Element with checked=None does not show checked attribute."""
        el = {"id": 1, "tag": "input", "type": "checkbox", "text": "", "checked": None}
        result = _format_single_element(el)
        parts = result.split()
        standalone_checked = [p for p in parts if p == "checked"]
        assert len(standalone_checked) == 0

    def test_href_empty_string_not_shown(self):
        """Element with empty href does not show href attribute."""
        el = {"id": 1, "tag": "a", "text": "Link", "href": ""}
        result = _format_single_element(el)
        assert "href" not in result

    def test_placeholder_empty_string_not_shown(self):
        """Element with empty placeholder does not show placeholder."""
        el = {"id": 1, "tag": "input", "text": "", "type": "text", "placeholder": ""}
        result = _format_single_element(el)
        assert "placeholder" not in result

    def test_type_empty_string_not_shown(self):
        """Element with empty type string does not show type."""
        el = {"id": 1, "tag": "input", "text": "", "type": ""}
        result = _format_single_element(el)
        assert "type=" not in result

    def test_integer_id(self):
        """Format element with integer id."""
        el = {"id": 42, "tag": "a", "text": "Link"}
        result = _format_single_element(el)
        assert "[42]" in result

    def test_large_id_number(self):
        """Format element with large id number."""
        el = {"id": 999, "tag": "button", "text": "Far"}
        result = _format_single_element(el)
        assert "[999]" in result

    def test_aria_label_with_text_present(self):
        """aria-label is suppressed when text is present (any element)."""
        el = {"id": 1, "tag": "div", "text": "Visible", "aria-label": "Hidden label"}
        result = _format_single_element(el)
        assert "aria-label" not in result
        assert '"Visible"' in result

    def test_aria_label_without_text_shown(self):
        """aria-label is shown when text is absent."""
        el = {"id": 1, "tag": "div", "text": "", "aria-label": "Icon button"}
        result = _format_single_element(el)
        assert 'aria-label="Icon button"' in result

    def test_attribute_ordering_type_before_href(self):
        """Type attribute appears before href in the formatted string."""
        el = {"id": 1, "tag": "a", "text": "Link", "type": "submit", "href": "/go"}
        result = _format_single_element(el)
        type_pos = result.index('type=')
        href_pos = result.index('href=')
        assert type_pos < href_pos

    def test_attribute_ordering_href_before_placeholder(self):
        """Href attribute appears before placeholder in the formatted string."""
        el = {"id": 1, "tag": "input", "text": "", "href": "/go", "placeholder": "Enter"}
        result = _format_single_element(el)
        href_pos = result.index('href=')
        placeholder_pos = result.index('placeholder=')
        assert href_pos < placeholder_pos

    def test_summary_element(self):
        """Format a summary element."""
        el = {"id": 1, "tag": "summary", "text": "Click to expand"}
        result = _format_single_element(el)
        assert '[1] <summary>' in result
        assert '"Click to expand"' in result

    def test_label_element(self):
        """Format a label element."""
        el = {"id": 1, "tag": "label", "text": "Username"}
        result = _format_single_element(el)
        assert '[1] <label>' in result
        assert '"Username"' in result

    def test_contenteditable_div(self):
        """Format a contenteditable div (role-based interactive element)."""
        el = {"id": 1, "tag": "div", "text": "Edit me"}
        result = _format_single_element(el)
        assert '[1] <div>' in result
        assert '"Edit me"' in result


# =============================================================================
# TESTS: format_elements()
# =============================================================================

class TestFormatElements:
    """Tests for format_elements() function."""

    def test_format_normal_result(self, sample_dom_result):
        """format_elements produces formatted string for normal result."""
        result = format_elements(sample_dom_result)

        assert '[1] <input' in result
        assert '[2] <button> "Search"' in result
        assert '[3] <a' in result
        assert "Main page" in result

    def test_format_empty_elements(self, empty_dom_result):
        """format_elements returns message for empty elements."""
        result = format_elements(empty_dom_result)
        assert result == "No interactive elements found on this page."

    def test_format_missing_elements_key(self):
        """format_elements handles missing 'elements' key."""
        result = format_elements({})
        assert result == "No interactive elements found on this page."

    def test_format_non_list_elements(self):
        """format_elements handles non-list 'elements' value."""
        result = format_elements({"elements": "not a list"})
        assert result == "No interactive elements found on this page."

    def test_format_none_elements(self):
        """format_elements handles None 'elements' value."""
        result = format_elements({"elements": None})
        assert result == "No interactive elements found on this page."

    def test_format_integer_elements(self):
        """format_elements handles integer 'elements' value."""
        result = format_elements({"elements": 42})
        assert result == "No interactive elements found on this page."

    def test_footer_count_when_all_shown(self, sample_dom_result):
        """format_elements shows total count when all elements shown."""
        result = format_elements(sample_dom_result)
        assert "(5 interactive elements)" in result

    def test_footer_count_when_capped(self, large_dom_result):
        """format_elements shows X of Y when elements are capped."""
        result = format_elements(large_dom_result, context_size="large")
        assert "200 of 250 interactive elements shown" in result

    def test_large_context_caps_at_200(self, large_dom_result):
        """format_elements caps at 200 elements for large context."""
        result = format_elements(large_dom_result, context_size="large")
        # Count lines that start with "[" (element lines)
        element_lines = [line for line in result.split("\n") if line.strip().startswith("[")]
        assert len(element_lines) == 200

    def test_medium_context_caps_at_150(self, large_dom_result):
        """format_elements caps at 150 elements for medium context."""
        result = format_elements(large_dom_result, context_size="medium")
        element_lines = [line for line in result.split("\n") if line.strip().startswith("[")]
        assert len(element_lines) == 150

    def test_small_context_caps_at_100(self, large_dom_result):
        """format_elements caps at 100 elements for small context."""
        result = format_elements(large_dom_result, context_size="small")
        element_lines = [line for line in result.split("\n") if line.strip().startswith("[")]
        assert len(element_lines) == 100

    def test_footer_shows_correct_cap_count_medium(self, large_dom_result):
        """format_elements footer shows correct counts for medium cap."""
        result = format_elements(large_dom_result, context_size="medium")
        assert "150 of 250 interactive elements shown" in result

    def test_footer_shows_correct_cap_count_small(self, large_dom_result):
        """format_elements footer shows correct counts for small cap."""
        result = format_elements(large_dom_result, context_size="small")
        assert "100 of 250 interactive elements shown" in result

    def test_unknown_context_defaults_to_large(self, large_dom_result):
        """format_elements with unknown context_size defaults to large."""
        result = format_elements(large_dom_result, context_size="banana")
        element_lines = [line for line in result.split("\n") if line.strip().startswith("[")]
        assert len(element_lines) == 200

    def test_format_with_links(self):
        """format_elements displays links with href and text."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "a", "text": "Example", "href": "https://example.com"},
            ],
            "text_summary": "",
            "url": "https://test.com",
            "title": "Test",
            "total_elements": 1,
            "visible_elements": 1,
        }
        result = format_elements(dom_result)
        assert '[1] <a href="https://example.com"> "Example"' in result

    def test_format_with_inputs(self):
        """format_elements displays inputs with type, placeholder, name."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "input", "text": "", "type": "text",
                 "placeholder": "Search...", "name": "q"},
            ],
            "text_summary": "",
            "url": "https://test.com",
            "title": "Test",
            "total_elements": 1,
            "visible_elements": 1,
        }
        result = format_elements(dom_result)
        assert 'type="text"' in result
        assert 'placeholder="Search..."' in result
        assert 'name="q"' in result

    def test_format_with_buttons(self):
        """format_elements displays buttons with text."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "button", "text": "Submit"},
            ],
            "text_summary": "",
            "url": "https://test.com",
            "title": "Test",
            "total_elements": 1,
            "visible_elements": 1,
        }
        result = format_elements(dom_result)
        assert '[1] <button> "Submit"' in result

    def test_format_with_checkboxes(self):
        """format_elements displays checkboxes with checked state."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "input", "text": "", "type": "checkbox",
                 "checked": True, "name": "agree"},
            ],
            "text_summary": "",
            "url": "https://test.com",
            "title": "Test",
            "total_elements": 1,
            "visible_elements": 1,
        }
        result = format_elements(dom_result)
        assert "checked" in result

    def test_format_with_selects(self, dom_result_with_select):
        """format_elements displays select elements."""
        result = format_elements(dom_result_with_select)
        assert '[1] <select' in result
        assert 'name="country"' in result

    def test_total_elements_non_numeric_fallback(self):
        """format_elements handles non-numeric total_elements gracefully."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "button", "text": "Click"},
            ],
            "total_elements": "not a number",
            "visible_elements": 1,
        }
        result = format_elements(dom_result)
        # Should fall back to len(elements) = 1
        assert "(1 interactive elements)" in result

    def test_total_elements_none_fallback(self):
        """format_elements handles None total_elements gracefully."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "button", "text": "Click"},
            ],
            "total_elements": None,
        }
        result = format_elements(dom_result)
        assert "(1 interactive elements)" in result

    def test_total_elements_missing_key_fallback(self):
        """format_elements handles missing total_elements key."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "button", "text": "Click"},
                {"id": 2, "tag": "button", "text": "Cancel"},
            ],
        }
        result = format_elements(dom_result)
        assert "(2 interactive elements)" in result

    def test_one_element_footer(self):
        """format_elements footer for a single element."""
        dom_result = {
            "elements": [{"id": 1, "tag": "a", "text": "Link", "href": "/p"}],
            "total_elements": 1,
        }
        result = format_elements(dom_result)
        assert "(1 interactive elements)" in result

    def test_format_dict_elements_value(self):
        """format_elements handles dict 'elements' value."""
        result = format_elements({"elements": {"key": "value"}})
        assert result == "No interactive elements found on this page."

    def test_format_boolean_elements_value(self):
        """format_elements handles boolean 'elements' value."""
        result = format_elements({"elements": True})
        assert result == "No interactive elements found on this page."

    def test_format_float_elements_value(self):
        """format_elements handles float 'elements' value."""
        result = format_elements({"elements": 3.14})
        assert result == "No interactive elements found on this page."

    def test_total_elements_float_fallback(self):
        """format_elements handles float total_elements by converting to int."""
        dom_result = {
            "elements": [{"id": 1, "tag": "a", "text": "Link"}],
            "total_elements": 5.7,
        }
        result = format_elements(dom_result)
        # float is convertible to int, so int(5.7) = 5
        assert "1 of 5 interactive elements shown" in result

    def test_total_elements_list_fallback(self):
        """format_elements handles list total_elements gracefully."""
        dom_result = {
            "elements": [{"id": 1, "tag": "a", "text": "Link"}],
            "total_elements": [1, 2],
        }
        result = format_elements(dom_result)
        # list cannot be converted to int, so falls back to len(elements)
        assert "(1 interactive elements)" in result

    def test_format_returns_string(self, sample_dom_result):
        """format_elements always returns a string."""
        result = format_elements(sample_dom_result)
        assert isinstance(result, str)

    def test_format_empty_result_returns_string(self):
        """format_elements returns a string even for empty input."""
        result = format_elements({})
        assert isinstance(result, str)

    def test_elements_under_cap_show_all(self):
        """format_elements shows all elements when count is under cap."""
        elements = [{"id": i, "tag": "a", "text": f"Link {i}"} for i in range(1, 11)]
        dom_result = {"elements": elements, "total_elements": 10}
        result = format_elements(dom_result, context_size="small")
        element_lines = [line for line in result.split("\n") if line.strip().startswith("[")]
        assert len(element_lines) == 10

    def test_footer_newline_prefix(self, sample_dom_result):
        """format_elements footer line starts with a newline for visual separation."""
        result = format_elements(sample_dom_result)
        lines = result.split("\n")
        footer = lines[-1]
        # The footer line should start with "(" after the newline join
        assert footer.startswith("(")

    def test_format_mixed_element_types(self):
        """format_elements handles mixed element types correctly."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "a", "text": "Link", "href": "/page"},
                {"id": 2, "tag": "input", "text": "", "type": "text", "name": "q"},
                {"id": 3, "tag": "button", "text": "Go"},
                {"id": 4, "tag": "select", "text": "Option A", "name": "sel"},
                {"id": 5, "tag": "textarea", "text": "", "name": "msg", "placeholder": "Type"},
            ],
            "total_elements": 5,
        }
        result = format_elements(dom_result)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result
        assert "[4]" in result
        assert "[5]" in result
        assert "(5 interactive elements)" in result


# =============================================================================
# TESTS: format_text_summary()
# =============================================================================

class TestFormatTextSummary:
    """Tests for format_text_summary() function."""

    def test_normal_text(self, sample_dom_result):
        """format_text_summary returns text for normal result."""
        result = format_text_summary(sample_dom_result)
        assert result == "Wikipedia is a free online encyclopedia."

    def test_empty_text(self, empty_dom_result):
        """format_text_summary returns placeholder for empty text."""
        result = format_text_summary(empty_dom_result)
        assert result == "(No readable text content on this page)"

    def test_missing_text_summary_key(self):
        """format_text_summary handles missing 'text_summary' key."""
        result = format_text_summary({})
        assert result == "(No readable text content on this page)"

    def test_non_string_text(self):
        """format_text_summary handles non-string text_summary."""
        result = format_text_summary({"text_summary": 12345})
        assert result == "(No readable text content on this page)"

    def test_none_text(self):
        """format_text_summary handles None text_summary."""
        result = format_text_summary({"text_summary": None})
        assert result == "(No readable text content on this page)"

    def test_list_text(self):
        """format_text_summary handles list text_summary."""
        result = format_text_summary({"text_summary": ["a", "b"]})
        assert result == "(No readable text content on this page)"

    def test_truncation_large_context(self):
        """format_text_summary truncates at 3000 chars for large context."""
        long_text = "x" * 4000
        dom_result = {"text_summary": long_text}
        result = format_text_summary(dom_result, context_size="large")
        # Should be 3000 chars + "..."
        assert len(result) == 3003
        assert result.endswith("...")

    def test_truncation_medium_context(self):
        """format_text_summary truncates at 1000 chars for medium context."""
        long_text = "y" * 2000
        dom_result = {"text_summary": long_text}
        result = format_text_summary(dom_result, context_size="medium")
        assert len(result) == 1003
        assert result.endswith("...")

    def test_truncation_small_context(self):
        """format_text_summary truncates at 500 chars for small context."""
        long_text = "z" * 2000
        dom_result = {"text_summary": long_text}
        result = format_text_summary(dom_result, context_size="small")
        assert len(result) == 503
        assert result.endswith("...")

    def test_no_truncation_when_short(self):
        """format_text_summary does not truncate short text."""
        dom_result = {"text_summary": "Short text here."}
        result = format_text_summary(dom_result, context_size="large")
        assert result == "Short text here."
        assert "..." not in result

    def test_exact_length_not_truncated(self):
        """format_text_summary does not truncate text at exact limit length."""
        text_3000 = "a" * 3000
        dom_result = {"text_summary": text_3000}
        result = format_text_summary(dom_result, context_size="large")
        assert result == text_3000
        assert "..." not in result

    def test_one_char_over_truncated(self):
        """format_text_summary truncates text one char over the limit."""
        text_3001 = "a" * 3001
        dom_result = {"text_summary": text_3001}
        result = format_text_summary(dom_result, context_size="large")
        assert result == "a" * 3000 + "..."

    def test_unknown_context_defaults_to_large(self):
        """format_text_summary with unknown context_size defaults to large."""
        long_text = "b" * 4000
        dom_result = {"text_summary": long_text}
        result = format_text_summary(dom_result, context_size="unknown")
        assert len(result) == 3003  # 3000 + "..."

    def test_preserves_content_before_truncation(self):
        """format_text_summary preserves text content up to the limit."""
        text = "Hello world! " * 400  # Long text with known content
        dom_result = {"text_summary": text}
        result = format_text_summary(dom_result, context_size="large")
        # First 3000 chars should match
        assert result[:3000] == text[:3000]

    def test_boolean_text_summary(self):
        """format_text_summary handles boolean text_summary."""
        result = format_text_summary({"text_summary": True})
        assert result == "(No readable text content on this page)"

    def test_dict_text_summary(self):
        """format_text_summary handles dict text_summary."""
        result = format_text_summary({"text_summary": {"key": "value"}})
        assert result == "(No readable text content on this page)"

    def test_float_text_summary(self):
        """format_text_summary handles float text_summary."""
        result = format_text_summary({"text_summary": 3.14})
        assert result == "(No readable text content on this page)"

    def test_returns_string(self, sample_dom_result):
        """format_text_summary always returns a string."""
        result = format_text_summary(sample_dom_result)
        assert isinstance(result, str)

    def test_single_char_text(self):
        """format_text_summary handles single character text."""
        result = format_text_summary({"text_summary": "A"})
        assert result == "A"

    def test_whitespace_only_text(self):
        """format_text_summary handles whitespace-only text as valid string."""
        result = format_text_summary({"text_summary": "   "})
        # Whitespace is a non-empty string, so it passes the check
        assert result == "   "

    def test_exact_small_limit(self):
        """format_text_summary does not truncate at exactly 500 for small."""
        text_500 = "c" * 500
        dom_result = {"text_summary": text_500}
        result = format_text_summary(dom_result, context_size="small")
        assert result == text_500
        assert "..." not in result

    def test_exact_medium_limit(self):
        """format_text_summary does not truncate at exactly 1000 for medium."""
        text_1000 = "d" * 1000
        dom_result = {"text_summary": text_1000}
        result = format_text_summary(dom_result, context_size="medium")
        assert result == text_1000
        assert "..." not in result

    def test_one_over_small_limit(self):
        """format_text_summary truncates at 501 for small context."""
        text_501 = "e" * 501
        dom_result = {"text_summary": text_501}
        result = format_text_summary(dom_result, context_size="small")
        assert result == "e" * 500 + "..."
        assert len(result) == 503

    def test_one_over_medium_limit(self):
        """format_text_summary truncates at 1001 for medium context."""
        text_1001 = "f" * 1001
        dom_result = {"text_summary": text_1001}
        result = format_text_summary(dom_result, context_size="medium")
        assert result == "f" * 1000 + "..."
        assert len(result) == 1003


# =============================================================================
# TESTS: Integration-style tests combining multiple functions
# =============================================================================

class TestDomWalkerIntegration:
    """Integration tests combining walk_dom with formatting functions."""

    def test_walk_then_format_elements(self, mock_page, sample_dom_result):
        """Walk DOM then format elements produces expected output."""
        mock_page.evaluate.return_value = sample_dom_result

        dom_result = walk_dom(mock_page)
        formatted = format_elements(dom_result)

        assert "[1]" in formatted
        assert "Search" in formatted
        assert "Main page" in formatted

    def test_walk_then_format_text(self, mock_page, sample_dom_result):
        """Walk DOM then format text summary produces expected output."""
        mock_page.evaluate.return_value = sample_dom_result

        dom_result = walk_dom(mock_page)
        text = format_text_summary(dom_result)

        assert "Wikipedia" in text

    def test_walk_error_then_format(self, mock_page):
        """Walk DOM error then format produces graceful output."""
        mock_page.evaluate.side_effect = Exception("Page crashed")

        dom_result = walk_dom(mock_page)
        formatted = format_elements(dom_result)
        text = format_text_summary(dom_result)

        assert "No interactive elements" in formatted
        assert "No readable text" in text

    def test_walk_empty_then_format(self, mock_page, empty_dom_result):
        """Walk DOM empty page then format produces graceful output."""
        mock_page.evaluate.return_value = empty_dom_result

        dom_result = walk_dom(mock_page)
        formatted = format_elements(dom_result)
        text = format_text_summary(dom_result)

        assert "No interactive elements" in formatted
        assert "No readable text" in text

    def test_full_pipeline_with_context_sizes(self, mock_page, large_dom_result):
        """Full pipeline with different context sizes produces correct caps."""
        mock_page.evaluate.return_value = large_dom_result

        for size, expected_cap in [("small", 100), ("medium", 150), ("large", 200)]:
            dom_result = walk_dom(mock_page, context_size=size)
            formatted = format_elements(dom_result, context_size=size)
            element_lines = [line for line in formatted.split("\n")
                             if line.strip().startswith("[")]
            assert len(element_lines) == expected_cap, \
                f"Expected {expected_cap} elements for {size}, got {len(element_lines)}"

    def test_walk_non_dict_then_format_both(self, mock_page):
        """Walk DOM with non-dict result then format both produces graceful output."""
        mock_page.evaluate.return_value = [1, 2, 3]

        dom_result = walk_dom(mock_page)
        formatted = format_elements(dom_result)
        text = format_text_summary(dom_result)

        assert "No interactive elements" in formatted
        assert "No readable text" in text

    def test_walk_with_override_then_format(self, mock_page, large_dom_result):
        """Walk with max_elements override then format respects both caps."""
        mock_page.evaluate.return_value = large_dom_result

        dom_result = walk_dom(mock_page, context_size="large", max_elements=50)
        # format_elements uses context_size preset, not max_elements
        formatted = format_elements(dom_result, context_size="large")
        element_lines = [line for line in formatted.split("\n")
                         if line.strip().startswith("[")]
        # The JavaScript would have limited to 50, but we passed 250 elements
        # via mock, so format_elements caps at 200 (large preset)
        assert len(element_lines) == 200


# =============================================================================
# TESTS: Edge cases and defensive coding
# =============================================================================

class TestEdgeCases:
    """Edge case and defensive coding tests."""

    def test_format_elements_with_empty_element_dicts(self):
        """format_elements handles elements that are empty dicts."""
        dom_result = {
            "elements": [{}, {}, {}],
            "total_elements": 3,
        }
        result = format_elements(dom_result)
        # Should not crash, each element formatted minimally
        assert "[?] <?>" in result

    def test_format_elements_skips_none_format_results(self):
        """format_elements handles elements that format to empty strings."""
        # _format_single_element always returns a string, so this tests the line filter
        dom_result = {
            "elements": [
                {"id": 1, "tag": "a", "text": "Valid", "href": "/page"},
            ],
            "total_elements": 1,
        }
        result = format_elements(dom_result)
        assert "[1]" in result

    def test_walk_dom_with_page_url_exception_on_error(self):
        """walk_dom handles page.url exception during error path."""
        page = Mock()
        page.evaluate.side_effect = Exception("Crash")
        type(page).url = PropertyMock(side_effect=Exception("Detached"))

        result = walk_dom(page)

        assert result["elements"] == []
        assert result["url"] == ""
        assert "Crash" in result["error"]

    def test_format_elements_handles_very_large_element_count(self):
        """format_elements handles result claiming huge total_elements."""
        dom_result = {
            "elements": [{"id": 1, "tag": "a", "text": "Link"}],
            "total_elements": 999999,
        }
        result = format_elements(dom_result)
        assert "1 of 999999 interactive elements shown" in result

    def test_format_elements_total_less_than_shown(self):
        """format_elements when total_elements is less than shown count."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "a", "text": "A"},
                {"id": 2, "tag": "a", "text": "B"},
                {"id": 3, "tag": "a", "text": "C"},
            ],
            "total_elements": 3,
        }
        result = format_elements(dom_result)
        # total (3) == shown (3), so footer should say "(3 interactive elements)"
        assert "(3 interactive elements)" in result

    def test_href_exactly_81_chars_is_truncated(self):
        """Href with exactly 81 chars gets truncated."""
        href_81 = "https://example.com/" + "x" * 61  # 81 chars total
        assert len(href_81) == 81
        el = {"id": 1, "tag": "a", "text": "Link", "href": href_81}
        result = _format_single_element(el)
        assert "..." in result

    def test_walk_dom_max_elements_zero_uses_preset(self, mock_page, sample_dom_result):
        """walk_dom with max_elements=0 uses preset (0 is falsy)."""
        mock_page.evaluate.return_value = sample_dom_result

        walk_dom(mock_page, context_size="small", max_elements=0)

        config = mock_page.evaluate.call_args[0][1]
        # 0 is falsy, so `max_elements or preset["maxElements"]` uses preset
        assert config["maxElements"] == 100

    def test_total_elements_lower_than_shown_uses_equal_footer(self):
        """format_elements uses equal footer when total < shown (data inconsistency)."""
        dom_result = {
            "elements": [
                {"id": 1, "tag": "a", "text": "A"},
                {"id": 2, "tag": "a", "text": "B"},
                {"id": 3, "tag": "a", "text": "C"},
            ],
            "total_elements": 1,  # Less than actual shown count
        }
        result = format_elements(dom_result)
        # total (1) < shown (3), so "total > shown" is False
        # Footer says "(3 interactive elements)"
        assert "(3 interactive elements)" in result

    def test_walk_dom_preserves_viewport_info(self, mock_page, sample_dom_result):
        """walk_dom preserves viewport info from JavaScript result."""
        mock_page.evaluate.return_value = sample_dom_result

        result = walk_dom(mock_page)

        assert result["viewport"]["width"] == 1920
        assert result["viewport"]["height"] == 1080

    def test_format_single_element_returns_string(self):
        """_format_single_element always returns a string."""
        el = {"id": 1, "tag": "a", "text": "Link"}
        result = _format_single_element(el)
        assert isinstance(result, str)

    def test_format_single_element_never_returns_none(self):
        """_format_single_element never returns None, even for bad input."""
        result = _format_single_element({})
        assert result is not None

    def test_format_elements_with_single_empty_dict(self):
        """format_elements with a single empty dict element."""
        dom_result = {
            "elements": [{}],
            "total_elements": 1,
        }
        result = format_elements(dom_result)
        assert "[?] <?>" in result
        assert "(1 interactive elements)" in result

    def test_walk_dom_with_magicmock_page(self, sample_dom_result):
        """walk_dom works with MagicMock page objects."""
        page = MagicMock()
        page.url = "https://mock.test"
        page.evaluate.return_value = sample_dom_result

        result = walk_dom(page)

        assert result is sample_dom_result

    def test_format_elements_total_zero_with_elements(self):
        """format_elements with total_elements=0 but actual elements present."""
        dom_result = {
            "elements": [{"id": 1, "tag": "a", "text": "Link"}],
            "total_elements": 0,
        }
        result = format_elements(dom_result)
        # total (0) < shown (1), so total > shown is False
        assert "(1 interactive elements)" in result

    def test_empty_result_compatible_with_format_elements(self):
        """_empty_result output is directly usable by format_elements."""
        empty = _empty_result()
        result = format_elements(empty)
        assert result == "No interactive elements found on this page."

    def test_empty_result_compatible_with_format_text_summary(self):
        """_empty_result output is directly usable by format_text_summary."""
        empty = _empty_result()
        result = format_text_summary(empty)
        assert result == "(No readable text content on this page)"

    def test_walk_dom_ose_error_returns_empty(self, mock_page):
        """walk_dom handles OSError from page.evaluate."""
        mock_page.evaluate.side_effect = OSError("Connection refused")

        result = walk_dom(mock_page)

        assert result["elements"] == []
        assert "Connection refused" in result["error"]

    def test_format_elements_output_ends_with_footer(self, sample_dom_result):
        """format_elements output ends with the footer count line."""
        result = format_elements(sample_dom_result)
        assert result.rstrip().endswith(")")

    def test_format_elements_element_lines_before_footer(self, sample_dom_result):
        """format_elements has element lines followed by footer."""
        result = format_elements(sample_dom_result)
        lines = result.split("\n")
        # Last non-empty line should be the footer
        non_empty = [line for line in lines if line.strip()]
        assert non_empty[-1].startswith("(")
        # All other non-empty lines should start with "["
        for line in non_empty[:-1]:
            assert line.startswith("["), f"Expected '[' prefix, got: {line}"
