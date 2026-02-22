"""
DOM Walker - Extracts interactive elements from the live browser DOM.

Replaces the old BeautifulSoup-based observer for page representation.
Runs JavaScript directly in the browser via page.evaluate() to get
ALL interactive elements with their properties, then assigns numeric
IDs (data-br-id) for reliable re-targeting.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# JavaScript that walks the DOM and extracts interactive elements.
# Injected into the browser via page.evaluate().
DOM_WALK_JS = """
(config) => {
    const MAX_ELEMENTS = config.maxElements || 200;
    const MAX_TEXT_LEN = config.maxTextLen || 60;
    const MAX_HREF_LEN = config.maxHrefLen || 120;
    const TEXT_SUMMARY_LEN = config.textSummaryLen || 1500;

    // Clean up any previous data-br-id attributes
    document.querySelectorAll('[data-br-id]').forEach(el => {
        el.removeAttribute('data-br-id');
    });

    // Interactive element selectors
    const SELECTORS = [
        'a[href]',
        'button',
        'input:not([type="hidden"])',
        'textarea',
        'select',
        '[role="button"]',
        '[role="link"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[role="option"]',
        '[role="switch"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[contenteditable="true"]',
        'summary',
        'details > summary',
        'label[for]',
    ];

    // Visibility check
    function isVisible(el) {
        if (!el || !el.getBoundingClientRect) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
        }
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) return false;
        return true;
    }

    // Check if element is in viewport
    function isInViewport(el) {
        const rect = el.getBoundingClientRect();
        return (
            rect.top < window.innerHeight &&
            rect.bottom > 0 &&
            rect.left < window.innerWidth &&
            rect.right > 0
        );
    }

    // Get clean text content (direct text, not deep children for containers)
    function getText(el) {
        // For links and buttons, get all nested text
        if (el.tagName === 'A' || el.tagName === 'BUTTON' || el.tagName === 'SUMMARY') {
            let text = el.textContent || '';
            text = text.replace(/\\s+/g, ' ').trim();
            return text.substring(0, MAX_TEXT_LEN);
        }
        // For inputs, get value or placeholder
        if (el.tagName === 'INPUT') {
            return el.value || el.placeholder || '';
        }
        if (el.tagName === 'TEXTAREA') {
            return el.value || el.placeholder || '';
        }
        if (el.tagName === 'SELECT') {
            const selected = el.options[el.selectedIndex];
            return selected ? selected.text : '';
        }
        // For other elements, get direct text
        let text = el.textContent || '';
        text = text.replace(/\\s+/g, ' ').trim();
        return text.substring(0, MAX_TEXT_LEN);
    }

    // Get key attributes for an element
    function getAttrs(el) {
        const attrs = {};
        const tag = el.tagName.toLowerCase();

        // Common attributes
        if (el.getAttribute('aria-label')) attrs['aria-label'] = el.getAttribute('aria-label').substring(0, 60);
        if (el.getAttribute('role') && !SELECTORS.some(s => s.includes('role'))) attrs.role = el.getAttribute('role');
        if (el.getAttribute('title')) attrs.title = el.getAttribute('title').substring(0, 60);
        if (el.getAttribute('name')) attrs.name = el.getAttribute('name');

        // Tag-specific attributes
        if (tag === 'a') {
            const href = el.getAttribute('href') || '';
            if (href && href !== '#' && !href.startsWith('javascript:')) {
                attrs.href = href.substring(0, MAX_HREF_LEN);
            }
        }
        if (tag === 'input' || tag === 'textarea') {
            if (el.type) attrs.type = el.type;
            if (el.placeholder) attrs.placeholder = el.placeholder.substring(0, 40);
            if (el.type === 'checkbox' || el.type === 'radio') {
                attrs.checked = el.checked;
            }
        }
        if (tag === 'select') {
            attrs.options = Array.from(el.options).slice(0, 5).map(o => o.text.substring(0, 30));
        }
        if (tag === 'img') {
            if (el.alt) attrs.alt = el.alt.substring(0, 60);
            if (el.src) attrs.src = el.src.substring(0, MAX_HREF_LEN);
        }

        return attrs;
    }

    // Collect all interactive elements
    const allElements = [];
    const seen = new Set();

    for (const selector of SELECTORS) {
        try {
            const elements = document.querySelectorAll(selector);
            for (const el of elements) {
                if (seen.has(el)) continue;
                seen.add(el);

                if (!isVisible(el)) continue;

                const tag = el.tagName.toLowerCase();
                const text = getText(el);
                const attrs = getAttrs(el);

                // Skip empty links (no text, no aria-label, no meaningful href)
                if (tag === 'a' && !text && !attrs['aria-label'] && !attrs.href) continue;
                // Skip empty buttons with no text
                if (tag === 'button' && !text && !attrs['aria-label']) continue;

                allElements.push({
                    el: el,
                    tag: tag,
                    text: text,
                    attrs: attrs,
                    inViewport: isInViewport(el),
                    rect: el.getBoundingClientRect()
                });
            }
        } catch (e) {
            // Skip invalid selectors
        }
    }

    // Determine content priority for each element.
    // Elements inside main content areas get boosted; elements inside
    // nav, dropdowns, dialogs, popups get deprioritized so they don't
    // eat up the element cap on complex pages.
    const mainContent = document.querySelector('main') ||
                        document.querySelector('article') ||
                        document.querySelector('[role="main"]') ||
                        document.querySelector('#content') ||
                        document.querySelector('.content');

    function getContentPriority(item) {
        const el = item.el;
        // Priority 0 (highest): inputs, textareas, search boxes - always important
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
            return 0;
        }

        // Check if inside a deprioritized container
        const deprioritized = el.closest(
            'nav, [role="navigation"], [role="dialog"], [role="menu"], ' +
            '[role="listbox"], dialog, .dropdown-menu, .popup, .modal, ' +
            '.popover, .SelectMenu, .select-menu, [aria-haspopup] ul, ' +
            'footer'
        );

        // Also deprioritize menu/option role elements themselves
        // (dropdown options that balloon element count)
        const isMenuOption = el.matches(
            '[role="option"], [role="menuitemradio"], [role="menuitemcheckbox"]'
        );

        // Check if inside main content
        const inMain = mainContent && mainContent.contains(el);

        if (isMenuOption || (deprioritized && !inMain)) {
            // Inside nav/dropdown/dialog or a menu option element
            return 3;
        }
        if (inMain) {
            // Inside main content area
            return 1;
        }
        // Neutral - header links, footer links, etc.
        return 2;
    }

    // Score each element
    for (const item of allElements) {
        item.priority = getContentPriority(item);
    }

    // Sort by: priority first, then viewport, then vertical position
    allElements.sort((a, b) => {
        // Primary: content priority (lower = better)
        if (a.priority !== b.priority) return a.priority - b.priority;
        // Secondary: in-viewport first
        if (a.inViewport !== b.inViewport) return a.inViewport ? -1 : 1;
        // Tertiary: vertical position (top to bottom)
        return a.rect.top - b.rect.top;
    });

    const sorted = allElements;
    const viewportEls = allElements.filter(e => e.inViewport);

    // Assign IDs and inject data-br-id
    const elements = [];
    let id = 1;
    for (const item of sorted) {
        if (id > MAX_ELEMENTS) break;

        item.el.setAttribute('data-br-id', String(id));

        const entry = {
            id: id,
            tag: item.tag,
            text: item.text,
            visible: item.inViewport
        };

        // Merge attributes
        Object.assign(entry, item.attrs);

        elements.push(entry);
        id++;
    }

    // Extract page text summary.
    // Try multiple content selectors and pick the one with the
    // cleanest, most relevant text (not dropdown/menu junk).
    let textSummary = '';

    function extractCleanText(root) {
        if (!root) return '';
        const clone = root.cloneNode(true);
        clone.querySelectorAll(
            'script, style, noscript, nav, header, footer, ' +
            '[role="menu"], [role="listbox"], [role="dialog"], ' +
            '.dropdown-menu, .SelectMenu, .select-menu, ' +
            'details > :not(summary), dialog, [aria-hidden="true"]'
        ).forEach(el => el.remove());
        return clone.textContent.replace(/\\s+/g, ' ').trim();
    }

    // Priority order for text extraction
    const textCandidates = [
        document.querySelector('[role="main"]'),
        document.querySelector('main'),
        document.querySelector('article'),
        document.querySelector('.content'),
        document.querySelector('#content'),
        document.body,
    ];

    for (const candidate of textCandidates) {
        if (!candidate) continue;
        const text = extractCleanText(candidate);
        if (text.length > 50) {
            textSummary = text.substring(0, TEXT_SUMMARY_LEN);
            break;
        }
    }

    return {
        elements: elements,
        text_summary: textSummary,
        url: window.location.href,
        title: document.title,
        total_elements: allElements.length,
        visible_elements: viewportEls.length,
        viewport: {
            width: window.innerWidth,
            height: window.innerHeight
        }
    };
}
"""


# Context window size presets
CONTEXT_PRESETS = {
    "small": {"maxElements": 100, "textSummaryLen": 500},    # Ollama local models
    "medium": {"maxElements": 150, "textSummaryLen": 1000},  # GPT-4o-mini, Haiku
    "large": {"maxElements": 200, "textSummaryLen": 1500},   # GPT-4o, Sonnet, Opus
}


def walk_dom(page, context_size: str = "large", max_elements: Optional[int] = None) -> Dict:
    """Extract all interactive elements from the live browser DOM.

    Runs JavaScript in the page to walk the DOM tree, find all interactive
    elements, assign numeric IDs via data-br-id attributes, and return
    structured data for the LLM.

    Args:
        page: Playwright page object
        context_size: One of "small", "medium", "large" for element/text caps
        max_elements: Override max elements (takes precedence over context_size)

    Returns:
        Dict with:
            - elements: List of element dicts with id, tag, text, attrs
            - text_summary: Page text content summary
            - url: Current page URL
            - title: Page title
            - total_elements: Total interactive elements found
            - visible_elements: Elements currently in viewport
    """
    preset = CONTEXT_PRESETS.get(context_size, CONTEXT_PRESETS["large"])
    config = {
        "maxElements": max_elements or preset["maxElements"],
        "maxTextLen": 60,
        "maxHrefLen": 120,
        "textSummaryLen": preset["textSummaryLen"],
    }

    try:
        result = page.evaluate(DOM_WALK_JS, config)
        # Validate result is a proper dict (not a Mock or other unexpected type)
        if not isinstance(result, dict) or "elements" not in result:
            return _empty_result(page)
        return result
    except Exception as e:
        logger.error("DOM walk failed: %s", e)
        return _empty_result(page, error=str(e))


def _empty_result(page=None, error: str = "") -> Dict:
    """Return an empty DOM walk result."""
    url = ""
    try:
        url = page.url if page else ""
    except Exception:
        pass
    result = {
        "elements": [],
        "text_summary": "",
        "url": url,
        "title": "",
        "total_elements": 0,
        "visible_elements": 0,
    }
    if error:
        result["error"] = error
    return result


def format_elements(dom_result: Dict, context_size: str = "large") -> str:
    """Format DOM walker results into a string for the LLM prompt.

    Produces output like:
        [1] <input type="search" placeholder="Search Wikipedia">
        [2] <button> "Search"
        [3] <a href="/wiki/Main_Page"> "Main page"

    Args:
        dom_result: Output from walk_dom()
        context_size: Controls element cap

    Returns:
        Formatted string of interactive elements
    """
    elements = dom_result.get("elements", [])
    if not isinstance(elements, list):
        return "No interactive elements found on this page."

    total_raw = dom_result.get("total_elements", len(elements))
    try:
        total = int(total_raw)
    except (ValueError, TypeError):
        total = len(elements)

    if not elements:
        return "No interactive elements found on this page."

    preset = CONTEXT_PRESETS.get(context_size, CONTEXT_PRESETS["large"])
    max_show = preset["maxElements"]
    elements = elements[:max_show]

    lines = []
    for el in elements:
        line = _format_single_element(el)
        if line:
            lines.append(line)

    # Footer with count
    shown = len(lines)
    if total > shown:
        lines.append(f"\n({shown} of {total} interactive elements shown)")
    else:
        lines.append(f"\n({shown} interactive elements)")

    return "\n".join(lines)


def _format_single_element(el: Dict) -> str:
    """Format a single element dict into a display string."""
    eid = el.get("id", "?")
    tag = el.get("tag", "?")
    text = el.get("text", "")

    # Build attribute string
    attr_parts = []

    # Type for inputs
    if el.get("type"):
        attr_parts.append(f'type="{el["type"]}"')

    # Href for links
    if el.get("href"):
        href = el["href"]
        if len(href) > 80:
            href = href[:77] + "..."
        attr_parts.append(f'href="{href}"')

    # Placeholder for inputs
    if el.get("placeholder"):
        attr_parts.append(f'placeholder="{el["placeholder"]}"')

    # Aria-label if no text
    if not text and el.get("aria-label"):
        attr_parts.append(f'aria-label="{el["aria-label"]}"')

    # Name for inputs
    if el.get("name") and tag in ("input", "textarea", "select"):
        attr_parts.append(f'name="{el["name"]}"')

    # Checked state
    if el.get("checked") is True:
        attr_parts.append("checked")

    # Build the line
    attrs_str = " " + " ".join(attr_parts) if attr_parts else ""
    text_str = f' "{text}"' if text else ""

    return f"[{eid}] <{tag}{attrs_str}>{text_str}"


def format_text_summary(dom_result: Dict, context_size: str = "large") -> str:
    """Format the page text summary for the LLM prompt.

    Args:
        dom_result: Output from walk_dom()
        context_size: Controls text length cap

    Returns:
        Formatted text summary string
    """
    text = dom_result.get("text_summary", "")
    if not text or not isinstance(text, str):
        return "(No readable text content on this page)"

    preset = CONTEXT_PRESETS.get(context_size, CONTEXT_PRESETS["large"])
    max_len = preset["textSummaryLen"]

    text = text[:max_len]
    if len(dom_result.get("text_summary", "")) > max_len:
        text += "..."

    return text
