"""Agent Actions Mixin - Browser action execution extracted from agent.py.

Contains _execute_action and all per-action handler methods.
Imported by agent.py via multiple inheritance (mixin pattern).
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urljoin

from blackreach.exceptions import (
    BrowserError, NavigationError, DownloadError,
    InvalidActionArgsError, UnknownActionError, LLMError, NetworkError,
)
from blackreach.search_intel import get_search_fallback_url, SearchEngine, DEFAULT_SEARCH_ENGINE

STEP_PAUSE_SECONDS = 0.5
MIN_FULL_IMAGE_SIZE = 200000
MIN_EBOOK_SIZE = 50000

logger = logging.getLogger(__name__)

RE_URL = re.compile(r'https?://\S+')
RE_QUOTED_TEXT = re.compile(r"['\"]([^'\"]+)['\"]")

# Minimal image-size thresholds
MIN_FULL_IMAGE_SIZE = 200000
MIN_EBOOK_SIZE = 50000


class AgentActionsMixin:
    """Mixin providing _execute_action and per-action handlers."""

    def _execute_action(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a browser action."""
        action = action.lower()

        # Normalize action aliases (LLMs sometimes use different names)
        action_aliases = {
            "search": "type",     # search is just type with submit:true
            "go": "navigate",
            "goto": "navigate",
            "visit": "navigate",
            "enter": "type",
            "input": "type",
            "link": "click",
            "press_key": "press",
            "finish": "done",
            "complete": "done",
        }
        action = action_aliases.get(action, action)

        if action == "click":
            element_id = args.get("_element_id")
            selector = args.get("selector", "")
            text = args.get("text", "")
            thought = args.get("_thought", "")
            domain = self._get_domain()
            skill_hint = text or (",".join(RE_QUOTED_TEXT.findall(thought))[:30] if thought else "click")

            # Skill-0: Try learned domain skill *before* generic discovery
            if domain and self._skill_manager:
                skill_result = self._try_skill_click(domain, skill_hint)
                if skill_result:
                    self._record_skill(domain, "click", element_id, selector,
                                      success=True)
                    return skill_result

            # Priority 1: Click by element ID (new DOM walker system)
            if element_id is not None:
                br_selector = f'[data-br-id="{element_id}"]'
                loc = self.hand.page.locator(br_selector)
                if loc.count() > 0:
                    loc.first.click(timeout=10000)
                    self._record_skill(domain, "click", element_id, br_selector,
                                      success=True)
                    return {"action": "click", "element": element_id}

            # Priority 2: Click by explicit text
            if text:
                text = text.strip('[]"\'')
                try:
                    self.hand.page.get_by_text(text, exact=False).first.click()
                    self._record_skill(domain, "click", element_id, selector,
                                      success=True)
                    return {"action": "click", "text": text}
                except (BrowserError, OSError) as e:
                    self._record_skill(domain, "click", element_id, None,
                                      success=False, error=str(e))
                    logger.debug("Click by text '%s' failed, trying fallback: %s", text, e)

            # Priority 3: Extract text from thought (backward compat)
            if not text and thought:
                quoted = RE_QUOTED_TEXT.findall(thought)
                if quoted:
                    text = quoted[0].strip('[]"\'')
                    try:
                        self.hand.page.get_by_text(text, exact=False).first.click()
                        self._record_skill(domain, "click", element_id, None,
                                          success=True)
                        return {"action": "click", "text": text}
                    except (BrowserError, OSError) as e:
                        self._record_skill(domain, "click", element_id, None,
                                          success=False, error=str(e))
                        logger.debug("Click by quoted text '%s' failed: %s", text, e)

            # Priority 4: Click by CSS selector (backward compat)
            if selector:
                try:
                    self.hand.click(selector)
                    self._record_skill(domain, "click", element_id, selector,
                                      success=True)
                    return {"action": "click", "selector": selector}
                except Exception as e:
                    self._record_skill(domain, "click", element_id, selector,
                                      success=False, error=str(e))
                    raise

            self._record_skill(domain, "click", element_id, None,
                              success=False, error="no valid target")
            raise InvalidActionArgsError("click", "Must provide element ID, text, or selector")

        elif action == "type":
            element_id = args.get("_element_id")
            text = args.get("text", "")
            submit = args.get("submit", True)

            # Priority 1: Type into element by ID (new DOM walker system)
            if element_id is not None:
                br_selector = f'[data-br-id="{element_id}"]'
                loc = self.hand.page.locator(br_selector)
                if loc.count() > 0:
                    loc.first.click(timeout=10000)
                    loc.first.fill(text, timeout=10000)
                    if submit:
                        self.hand.page.keyboard.press("Enter")
                        time.sleep(STEP_PAUSE_SECONDS)
                    return {"action": "type", "element": element_id, "text": text, "submit": submit}

            # Priority 2: Type by CSS selector (backward compat)
            selector = args.get("selector", "input")
            self.hand.type(selector, text)
            if submit:
                self.hand.page.keyboard.press("Enter")
                time.sleep(STEP_PAUSE_SECONDS)
            return {"action": "type", "selector": selector, "text": text, "submit": submit}

        elif action == "press":
            key = args.get("key", "Enter")
            self.hand.page.keyboard.press(key)
            return {"action": "press", "key": key}

        elif action == "scroll":
            direction = args.get("direction", "down")
            amount = args.get("amount", 500)
            self.hand.scroll(direction, amount)
            return {"action": "scroll", "direction": direction}

        elif action == "navigate":
            url = args.get("url", "")
            current_url = self.hand.get_url()

            # Resolve relative URLs to absolute
            if url and not url.startswith(('http://', 'https://')):
                url = urljoin(current_url, url)

            # Redirect blocked search engines before wasting time on timeouts.
            # Also handles bare search engine homepages (no query param) — these
            # time out on Google in headless mode.
            target_engine = self._identify_search_engine(url)
            if target_engine and target_engine != DEFAULT_SEARCH_ENGINE:
                query = self._extract_search_query(url)
                if query:
                    fallback_url, fallback_engine = get_search_fallback_url(
                        query, exclude=[target_engine]
                    )
                    self._blocked_engines.add(target_engine)
                    logger.debug("Redirecting %s search to %s", target_engine.value, fallback_engine.value)
                    url = fallback_url
                else:
                    # Bare homepage (e.g. google.com with no query) — redirect to default search homepage
                    self._blocked_engines.add(target_engine)
                    url = "https://lite.duckduckgo.com/lite/"

            # Skip only if navigating to the exact same URL (normalized)
            # Compare without trailing slash and fragment
            def normalize_url(u):
                u = u.rstrip('/').split('#')[0]
                return u

            if normalize_url(url) == normalize_url(current_url):
                logger.debug("Navigate skipped: already on %s", url[:50])
                return {"action": "navigate", "skipped": True, "url": url}

            logger.debug("Navigating to %s", url[:70])
            self._navigate_with_scan(url)
            self._record_visit(url)
            return {"action": "navigate", "url": url}

        elif action == "back":
            self.hand.back()
            return {"action": "back"}

        elif action == "wait":
            seconds = args.get("seconds", 1)
            time.sleep(seconds)
            return {"action": "wait", "seconds": seconds}

        elif action == "download":
            url = args.get("url", "")
            selector = args.get("selector", "")

            # Resolve relative URLs to absolute
            if url and not url.startswith(('http://', 'https://')):
                base_url = self.hand.get_url()
                url = urljoin(base_url, url)
                logger.debug("Resolved download URL: %s", url[:70])

            # Check if we've already downloaded this URL
            if url and self.persistent_memory.has_downloaded(url=url):
                logger.info("SKIP: Already downloaded %s", url[:50])
                self.session_memory.add_failure(f"Already downloaded {url[:50]}... Try a different item!")
                return {"action": "download", "skipped": True, "reason": "already downloaded"}

            # Check if this URL previously failed
            if url and url in self._failed_download_urls:
                logger.info("SKIP: URL previously failed %s", url[:50])
                self.session_memory.add_failure(f"Download URL failed before - use a different link")
                return {"action": "download", "skipped": True, "reason": "previously failed"}

            try:
                logger.info("Starting download...")
                download_start = time.time()

                if url:
                    result = self.hand.download_link(url)
                elif selector:
                    result = self.hand.click_and_download(selector)
                else:
                    raise InvalidActionArgsError("download", "Must provide either url or selector")

                download_time = time.time() - download_start
                logger.info("Download completed in %.1fs", download_time)

                # Check if we already have this file (by hash)
                if self.persistent_memory.has_downloaded(file_hash=result["hash"]):
                    # Delete the duplicate
                    Path(result["path"]).unlink()
                    logger.info("SKIP: Duplicate content (same hash)")
                    return {"action": "download", "skipped": True, "reason": "duplicate content"}

                # Use centralized content verification
                file_path = Path(result["path"])
                if file_path.exists():
                    verification = self.content_verifier.verify_file(file_path)

                    if verification.status != VerificationStatus.VALID:
                        # Delete invalid file
                        file_path.unlink()
                        logger.warning("INVALID download: %s", verification.message)
                        self.session_memory.add_failure(verification.message)
                        return {
                            "action": "download",
                            "skipped": True,
                            "reason": verification.status.value,
                            "verification": verification.message
                        }

                self._record_download(
                    filename=result["filename"],
                    url=result.get("url", url)
                )

                self.persistent_memory.add_download(
                    filename=result["filename"],
                    url=result.get("url", url),
                    source_site=self._get_domain(),
                    file_hash=result["hash"],
                    file_size=result["size"]
                )

                # Reset selector click counts on successful download (we made progress!)
                self._selector_click_counts = {}
                self._clicked_selectors = set()

                # Mark current page as excellent in navigation context (we got a download!)
                current_url = self.hand.get_url()
                self.nav_context.mark_page_value(current_url, PageValue.EXCELLENT)

                # Also record the selector that led to the download as valuable
                domain = self._get_domain()
                if selector:
                    self.nav_context.record_valuable_selector(domain, selector)

                logger.info("Downloaded: %s (%d bytes)", result['filename'], result['size'])

                return {
                    "action": "download",
                    "filename": result["filename"],
                    "path": result["path"],
                    "size": result["size"]
                }
            except (DownloadError, BrowserError, NetworkError, OSError) as e:
                error_str = str(e)
                current_url = self.hand.get_url()
                self._record_failure(current_url, "download", error_str)

                # Mark page as low value (download failed)
                self.nav_context.mark_page_value(current_url, PageValue.LOW)

                # Track failed download URL to avoid retrying
                if url:
                    self._failed_download_urls.add(url)

                # Provide helpful hints for common download failures
                if "Timeout" in error_str:
                    logger.warning("Download timeout - file may be very large or server is slow")
                    self.session_memory.add_failure("Download timed out - try a different mirror or source")
                elif "Download is starting" in error_str:
                    # This usually means the page didn't trigger a download
                    logger.warning("No download triggered - may need to click a different button")
                    self.session_memory.add_failure("No download triggered - look for actual file download links")
                elif "net::ERR" in error_str or "NetworkError" in error_str:
                    logger.warning("Network error on download - try a different mirror")
                    self.session_memory.add_failure("Network error - try alternative download source")
                else:
                    logger.warning("Download failed: %s", error_str[:100])

                # Add hint about failed URLs for LLM
                if len(self._failed_download_urls) > 0:
                    self.session_memory.add_failure(
                        f"Already tried {len(self._failed_download_urls)} download URLs that failed - use a different link"
                    )

                raise

        elif action == "done":
            return {"done": True, "reason": args.get("reason", "Goal complete")}

        else:
            raise UnknownActionError(action)


