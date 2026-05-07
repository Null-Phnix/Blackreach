"""Deprecated: observer.py functionality has been merged into dom_walker.py.

This shim re-exports the old Eyes class for backwards compatibility.
All new code should use blackreach.dom_walker directly.
"""

from blackreach.dom_walker import debug_html


class EyesConfig:
    """Deprecated configuration class — kept for import compatibility."""

    max_text_length: int = 8000
    max_links: int = 50
    max_inputs: int = 20
    max_buttons: int = 20
    prioritize_main_content: bool = True
    extract_headings: bool = True
    extract_lists: bool = True
    extract_tables: bool = False
    use_cache: bool = True
    cache_size: int = 100


class Eyes:
    """Deprecated: use blackreach.dom_walker functions directly.

    Only debug_html() is still referenced by agent.py; all other
    methods (see, see_simple, see_for_llm) are stubbed.
    """

    def __init__(self, config=None):
        self.config = config or EyesConfig()

    def debug_html(self, html: str) -> dict:
        """Forward to dom_walker.debug_html."""
        return debug_html(html)

    def see(self, html: str, use_cache: bool = None) -> dict:
        """Deprecated — returns minimal placeholder."""
        return {"text": "", "headings": [], "links": [], "inputs": [], "buttons": [], "forms": []}

    def see_simple(self, html: str) -> str:
        """Deprecated — returns empty string."""
        return ""

    def see_for_llm(self, html: str, max_tokens: int = 4000) -> str:
        """Deprecated — returns empty string."""
        return ""
