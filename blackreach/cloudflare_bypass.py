"""
Cloudflare Challenge Bypass Module

Advanced techniques for bypassing Cloudflare, DataDome, and other anti-bot systems.
Uses undetected-playwright for maximum stealth.
"""

import time
import random
from typing import Optional
from playwright.sync_api import Page, Browser, BrowserContext
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Try to import undetected-playwright
try:
    from undetected_playwright import Malenia
    UNDETECTED_AVAILABLE = True
except ImportError:
    UNDETECTED_AVAILABLE = False
    logger.warning("undetected-playwright not available - Cloudflare bypass may be limited")


@dataclass
class CloudflareBypassConfig:
    """Configuration for Cloudflare bypass behavior."""
    max_wait_time: int = 45  # Max seconds to wait for challenge to resolve
    check_interval: float = 0.5  # How often to check if challenge resolved
    mouse_movements: bool = True  # Perform mouse movements during wait
    enable_undetected: bool = True  # Use undetected-playwright if available


class CloudflareBypasser:
    """Handles Cloudflare challenge detection and bypass."""

    def __init__(self, config: Optional[CloudflareBypassConfig] = None):
        self.config = config or CloudflareBypassConfig()
        self._challenge_count = 0
        self._success_count = 0

    def is_challenge_page(self, page: Page) -> bool:
        """
        Detect if current page is a Cloudflare challenge.

        Checks for:
        - Cloudflare "Just a moment" text
        - cf-challenge-running class
        - Turnstile widget
        - Ray ID (Cloudflare error pages)
        """
        try:
            # Get page content for analysis
            html = page.content().lower()
            title = page.title().lower()

            # Cloudflare indicators
            cloudflare_indicators = [
                "just a moment",
                "checking your browser",
                "cf-challenge-running",
                "cf-browser-verification",
                "__cf_chl_jschl_tk__",
                "cloudflare",
                "ray id:",
                "attention required",
                "captcha-bypass",
            ]

            # Check title
            if any(indicator in title for indicator in cloudflare_indicators):
                return True

            # Check HTML content
            if any(indicator in html for indicator in cloudflare_indicators):
                return True

            # Check for challenge elements using Playwright
            selectors = [
                "#cf-challenge-running",
                ".cf-browser-verification",
                "[name='cf-turnstile-response']",
                "iframe[src*='challenges.cloudflare.com']",
            ]

            for selector in selectors:
                try:
                    if page.locator(selector).count() > 0:
                        return True
                except Exception:
                    pass

            return False

        except Exception as e:
            logger.debug(f"Error checking for challenge page: {e}")
            return False

    def wait_for_challenge_resolution(self, page: Page) -> bool:
        """
        Wait for Cloudflare challenge to auto-resolve.

        Performs human-like actions to help bypass:
        - Random mouse movements
        - Small scroll actions
        - Waiting patiently

        Returns:
            True if challenge resolved, False if timed out
        """
        if not self.is_challenge_page(page):
            return True

        logger.info("Cloudflare challenge detected, waiting for auto-resolution...")
        self._challenge_count += 1

        start_time = time.time()
        elapsed = 0
        attempt = 0

        while elapsed < self.config.max_wait_time:
            attempt += 1

            # Check if challenge resolved
            if not self.is_challenge_page(page):
                logger.info(f"Challenge resolved after {elapsed:.1f}s")
                self._success_count += 1
                return True

            # Perform human-like actions to help pass challenge
            if self.config.mouse_movements:
                try:
                    # Random mouse movement every few attempts
                    if attempt % 3 == 0:
                        viewport = page.viewport_size
                        if viewport:
                            x = random.randint(100, viewport['width'] - 100)
                            y = random.randint(100, viewport['height'] - 100)
                            page.mouse.move(x, y)

                    # Tiny scroll every 10 attempts
                    if attempt % 10 == 0:
                        page.mouse.wheel(0, random.randint(-50, 50))

                    # Click in safe area occasionally (helps some challenges)
                    if attempt % 15 == 0:
                        # Click near center but avoid actual challenge widget
                        viewport = page.viewport_size
                        if viewport:
                            center_x = viewport['width'] // 2
                            center_y = viewport['height'] // 2
                            # Click slightly off-center
                            page.mouse.click(
                                center_x + random.randint(-100, 100),
                                center_y + random.randint(-100, 100)
                            )

                except Exception as e:
                    logger.debug(f"Error during challenge interaction: {e}")

            # Wait before next check
            time.sleep(self.config.check_interval)
            elapsed = time.time() - start_time

        logger.warning(f"Challenge did not resolve after {self.config.max_wait_time}s")
        return False

    def get_stats(self) -> dict:
        """Get bypass statistics."""
        success_rate = (self._success_count / self._challenge_count * 100) if self._challenge_count > 0 else 0
        return {
            "challenges_encountered": self._challenge_count,
            "challenges_resolved": self._success_count,
            "success_rate": f"{success_rate:.1f}%"
        }


def create_undetected_browser(headless: bool = False, **kwargs) -> Optional[Browser]:
    """
    Create an undetected browser using Malenia (undetected-playwright).

    This uses a patched Chromium binary that bypasses most bot detection.

    Args:
        headless: Run in headless mode (note: headless is more detectable)
        **kwargs: Additional arguments passed to browser launch

    Returns:
        Browser instance or None if undetected-playwright unavailable
    """
    if not UNDETECTED_AVAILABLE:
        logger.warning("undetected-playwright not available, falling back to standard Playwright")
        return None

    try:
        # Malenia creates a fully stealthy browser
        malenia = Malenia(
            headless=headless,
            **kwargs
        )
        browser = malenia.playwright.chromium.launch()
        logger.info("Undetected browser created successfully")
        return browser

    except Exception as e:
        logger.error(f"Failed to create undetected browser: {e}")
        return None
