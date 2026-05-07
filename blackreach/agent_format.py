"""Agent Formatting Mixin - DOM formatting extracted from agent.py.

Contains _format_elements for building LLM prompts.
Imported by agent.py via multiple inheritance (mixin pattern).
"""

import logging
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

RE_URL = re.compile(r'https?://\S+')
RE_ARXIV_ID = re.compile(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)')


class AgentFormatMixin:
    """Mixin providing DOM formatting for LLM prompts."""

    def _format_elements(self, parsed: Dict, exclude_urls: list = None) -> str:
        """Format parsed elements for prompt - general purpose for any content type.

        Args:
            parsed: Parsed page elements from Eyes
            exclude_urls: URLs to exclude from output (already visited/downloaded)
        """
        lines = []
        exclude_urls = exclude_urls or []

        # Helper to extract content ID from URL (papers, items, etc.)
        def extract_content_id(url: str) -> str:
            """Extract content ID from various URL patterns."""
            url_lower = url.lower()
            # ArXiv pattern (precompiled)
            arxiv_match = RE_ARXIV_ID.search(url_lower)
            if arxiv_match:
                return f"arxiv:{arxiv_match.group(1)}"
            # Generic ID patterns
            for pattern in [r'/(\d{5,})', r'/([a-f0-9]{8,})', r'id=(\w+)']:
                match = re.search(pattern, url_lower)
                if match:
                    return match.group(1)
            return ""

        # Helper to check if URL should be excluded
        def is_excluded(url: str) -> bool:
            if not url or not exclude_urls:
                return False
            url_lower = url.lower()
            url_id = extract_content_id(url_lower)

            for excluded in exclude_urls:
                excluded_lower = excluded.lower()
                if url_lower == excluded_lower or excluded_lower in url_lower or url_lower in excluded_lower:
                    return True
                if url_id and url_id == extract_content_id(excluded_lower):
                    return True
            return False

        # Images with downloadable content
        images = parsed.get("images", [])[:15]
        image_lines = []
        for img in images:
            src = img.get("src", "")
            full_src = img.get("full_src", "")
            link = img.get("link", "")

            if is_excluded(link) or is_excluded(src) or is_excluded(full_src):
                continue

            # Detect thumbnails vs full images
            src_lower = src.lower()
            is_thumbnail = any(t in src_lower for t in ['/small/', '/thumb/', 'thumbnail', 'preview', '_s.', '_t.'])
            is_full = any(t in src_lower for t in ['/full/', '/large/', '/original/', '_o.', '_l.'])

            if full_src:
                image_lines.append(f"  - DOWNLOAD: {full_src}")
            elif is_full:
                image_lines.append(f"  - DOWNLOAD: {src}")
            elif link:
                image_lines.append(f"  - NAVIGATE TO: {link}")
            elif not is_thumbnail:
                image_lines.append(f"  - Img: {src[:60]}")

        if image_lines:
            lines.append("Images:")
            lines.extend(image_lines[:10])

        # Links - use pre-scored links from observer
        all_links = parsed.get("links", [])

        download_links = []
        detail_links = []
        other_links = []

        for link in all_links:
            href = link.get("href", "")
            text = link.get("text", "")[:40]
            link_type = link.get("type", "other")

            if is_excluded(href):
                continue

            if link_type == "download":
                download_links.append(f"  - DOWNLOAD: \"{text}\" -> {href}")
            elif link_type == "detail":
                detail_links.append(f"  - DETAIL PAGE: \"{text}\" -> {href}")
            else:
                other_links.append(f"  - \"{text}\" -> {href[:70]}")

        # Combine with priority
        prioritized = download_links[:10] + detail_links[:10] + other_links[:5]
        if prioritized:
            lines.append("Links:")
            lines.extend(prioritized)

        # Pagination info (if available)
        pagination = parsed.get("pagination", {})
        if pagination.get("has_pagination"):
            lines.append("Pagination:")
            if pagination.get("current_page"):
                lines.append(f"  - Current page: {pagination['current_page']}")
            if pagination.get("total_pages"):
                lines.append(f"  - Total pages: {pagination['total_pages']}")
            if pagination.get("next_page"):
                lines.append(f"  - NEXT PAGE: {pagination['next_page']}")

        # Inputs
        inputs = parsed.get("inputs", [])[:5]
        if inputs:
            lines.append("Inputs:")
            for inp in inputs:
                name = inp.get("name", inp.get("id", "input"))
                placeholder = inp.get("placeholder", "")
                lines.append(f"  - {name}: {placeholder}")

        # Buttons
        buttons = parsed.get("buttons", [])[:5]
        if buttons:
            lines.append("Buttons:")
            for btn in buttons:
                text = btn.get("text", "button")[:30]
                lines.append(f"  - {text}")

        return "\n".join(lines) if lines else "No interactive elements found"

