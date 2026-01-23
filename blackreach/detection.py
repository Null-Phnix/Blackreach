"""
Site condition detection for Blackreach.

Detects:
- CAPTCHAs (reCAPTCHA, hCaptcha, etc.)
- Login walls
- Paywalls
- Rate limiting
- Access denied pages
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple
from urllib.parse import urlparse

from blackreach.exceptions import (
    CaptchaError,
    LoginRequiredError,
    PaywallError,
    AccessDeniedError,
    RateLimitError,
)


@dataclass
class DetectionResult:
    """Result of page condition detection."""
    detected: bool
    condition: Optional[str] = None  # 'captcha', 'login', 'paywall', 'rate_limit', 'access_denied'
    confidence: float = 0.0  # 0.0 to 1.0
    details: Optional[str] = None
    indicators: List[str] = None

    def __post_init__(self):
        if self.indicators is None:
            self.indicators = []


class SiteDetector:
    """
    Detects various site conditions that may block agent progress.
    """

    # CAPTCHA indicators
    CAPTCHA_PATTERNS = [
        # reCAPTCHA
        r'recaptcha',
        r'g-recaptcha',
        r'grecaptcha',
        r'rc-anchor',
        r'rc-imageselect',
        # hCaptcha
        r'hcaptcha',
        r'h-captcha',
        # Cloudflare
        r'cf-challenge',
        r'challenge-form',
        r'cf-turnstile',
        # Generic
        r'captcha',
        r'robot\s*check',
        r'are\s*you\s*a\s*human',
        r'prove\s*you.re\s*human',
        r'security\s*check',
        r'bot\s*detection',
        r'verify\s*you.re\s*not\s*a\s*robot',
    ]

    CAPTCHA_SCRIPTS = [
        'recaptcha/api.js',
        'recaptcha/api2/',
        'hcaptcha.com/1/',
        'challenges.cloudflare.com',
        'turnstile/v0/api.js',
    ]

    # Login wall indicators
    LOGIN_PATTERNS = [
        r'sign\s*in\s*to\s*continue',
        r'log\s*in\s*to\s*continue',
        r'login\s*required',
        r'sign\s*in\s*required',
        r'create\s*an?\s*account',
        r'must\s*be\s*logged\s*in',
        r'please\s*sign\s*in',
        r'please\s*log\s*in',
        r'members?\s*only',
        r'subscribers?\s*only',
        r'authentication\s*required',
    ]

    LOGIN_FORM_INDICATORS = [
        'type="password"',
        'name="password"',
        'id="password"',
        'autocomplete="current-password"',
    ]

    # Paywall indicators
    PAYWALL_PATTERNS = [
        r'subscribe\s*to\s*read',
        r'subscribe\s*to\s*continue',
        r'premium\s*content',
        r'premium\s*access',
        r'upgrade\s*to\s*premium',
        r'this\s*article\s*is\s*for\s*subscribers',
        r'subscribe\s*now',
        r'unlock\s*this\s*article',
        r'free\s*trial',
        r'start\s*your\s*free',
        r'subscription\s*required',
        r'paid\s*content',
    ]

    PAYWALL_CLASSES = [
        'paywall',
        'premium-wall',
        'subscribe-wall',
        'paid-content',
        'meter-',
    ]

    # Rate limit indicators
    RATE_LIMIT_PATTERNS = [
        r'rate\s*limit',
        r'too\s*many\s*requests',
        r'slow\s*down',
        r'try\s*again\s*later',
        r'temporarily\s*blocked',
        r'access\s*temporarily\s*denied',
        r'quota\s*exceeded',
        r'request\s*limit',
    ]

    # Access denied indicators
    ACCESS_DENIED_PATTERNS = [
        r'access\s*denied',
        r'forbidden',
        r'403\s*error',
        r'you\s*don.t\s*have\s*permission',
        r'not\s*authorized',
        r'unauthorized',
        r'blocked',
    ]

    def __init__(self):
        # Compile patterns for efficiency
        self._captcha_re = re.compile('|'.join(self.CAPTCHA_PATTERNS), re.IGNORECASE)
        self._login_re = re.compile('|'.join(self.LOGIN_PATTERNS), re.IGNORECASE)
        self._paywall_re = re.compile('|'.join(self.PAYWALL_PATTERNS), re.IGNORECASE)
        self._rate_limit_re = re.compile('|'.join(self.RATE_LIMIT_PATTERNS), re.IGNORECASE)
        self._access_denied_re = re.compile('|'.join(self.ACCESS_DENIED_PATTERNS), re.IGNORECASE)

    def detect_captcha(self, html: str, url: str = "") -> DetectionResult:
        """Detect if page contains a CAPTCHA challenge."""
        indicators = []
        confidence = 0.0
        html_lower = html.lower()

        # Check for CAPTCHA scripts
        for script in self.CAPTCHA_SCRIPTS:
            if script.lower() in html_lower:
                indicators.append(f"Script: {script}")
                confidence += 0.4

        # Check for CAPTCHA patterns
        matches = self._captcha_re.findall(html)
        for match in matches[:3]:  # Limit to first 3
            indicators.append(f"Pattern: {match}")
            confidence += 0.2

        # Check for specific elements
        if 'data-sitekey' in html_lower:
            indicators.append("CAPTCHA sitekey")
            confidence += 0.3

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        detected = confidence >= 0.5 or len(indicators) >= 2

        captcha_type = None
        if 'recaptcha' in html_lower:
            captcha_type = "reCAPTCHA"
        elif 'hcaptcha' in html_lower:
            captcha_type = "hCaptcha"
        elif 'turnstile' in html_lower or 'cf-challenge' in html_lower:
            captcha_type = "Cloudflare"

        return DetectionResult(
            detected=detected,
            condition="captcha" if detected else None,
            confidence=confidence,
            details=captcha_type,
            indicators=indicators
        )

    def detect_login(self, html: str, url: str = "") -> DetectionResult:
        """Detect if page requires login."""
        indicators = []
        confidence = 0.0
        html_lower = html.lower()

        # Check URL patterns (login pages)
        url_lower = url.lower()
        if any(p in url_lower for p in ['/login', '/signin', '/sign-in', '/auth']):
            indicators.append(f"URL pattern: {url}")
            confidence += 0.3

        # Check for login patterns in text
        matches = self._login_re.findall(html)
        for match in matches[:3]:
            indicators.append(f"Pattern: {match}")
            confidence += 0.25

        # Check for password fields
        for indicator in self.LOGIN_FORM_INDICATORS:
            if indicator.lower() in html_lower:
                indicators.append(f"Form: {indicator}")
                confidence += 0.2

        # Check title
        if '<title>' in html_lower:
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).lower()
                if any(word in title for word in ['login', 'sign in', 'log in', 'authenticate']):
                    indicators.append(f"Title: {title_match.group(1)}")
                    confidence += 0.3

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.5

        return DetectionResult(
            detected=detected,
            condition="login" if detected else None,
            confidence=confidence,
            indicators=indicators
        )

    def detect_paywall(self, html: str, url: str = "") -> DetectionResult:
        """Detect if page has a paywall."""
        indicators = []
        confidence = 0.0
        html_lower = html.lower()

        # Check for paywall patterns
        matches = self._paywall_re.findall(html)
        for match in matches[:3]:
            indicators.append(f"Pattern: {match}")
            confidence += 0.25

        # Check for paywall classes/ids
        for cls in self.PAYWALL_CLASSES:
            if cls in html_lower:
                indicators.append(f"Class/ID: {cls}")
                confidence += 0.3

        # Check for overlay/modal patterns that block content
        if 'blurred' in html_lower or 'blur(' in html_lower:
            indicators.append("Blurred content")
            confidence += 0.2

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.5

        return DetectionResult(
            detected=detected,
            condition="paywall" if detected else None,
            confidence=confidence,
            indicators=indicators
        )

    def detect_rate_limit(self, html: str, url: str = "", status_code: int = None) -> DetectionResult:
        """Detect if we've been rate limited."""
        indicators = []
        confidence = 0.0

        # Check status code
        if status_code == 429:
            indicators.append("HTTP 429")
            confidence += 0.8

        # Check for rate limit patterns
        matches = self._rate_limit_re.findall(html)
        for match in matches[:3]:
            indicators.append(f"Pattern: {match}")
            confidence += 0.3

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.5

        # Try to extract retry-after hint
        retry_after = None
        retry_match = re.search(r'try\s*again\s*in\s*(\d+)\s*(second|minute|hour)?', html, re.IGNORECASE)
        if retry_match:
            value = int(retry_match.group(1))
            unit = (retry_match.group(2) or 'second').lower()
            if 'minute' in unit:
                value *= 60
            elif 'hour' in unit:
                value *= 3600
            retry_after = value

        return DetectionResult(
            detected=detected,
            condition="rate_limit" if detected else None,
            confidence=confidence,
            details=f"Retry after {retry_after}s" if retry_after else None,
            indicators=indicators
        )

    def detect_access_denied(self, html: str, url: str = "", status_code: int = None) -> DetectionResult:
        """Detect if access is denied."""
        indicators = []
        confidence = 0.0

        # Check status codes
        if status_code in [401, 403]:
            indicators.append(f"HTTP {status_code}")
            confidence += 0.7

        # Check for access denied patterns
        matches = self._access_denied_re.findall(html)
        for match in matches[:3]:
            indicators.append(f"Pattern: {match}")
            confidence += 0.3

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.5

        return DetectionResult(
            detected=detected,
            condition="access_denied" if detected else None,
            confidence=confidence,
            indicators=indicators
        )

    def detect_all(self, html: str, url: str = "", status_code: int = None) -> List[DetectionResult]:
        """Run all detections and return any positive results."""
        results = []

        captcha = self.detect_captcha(html, url)
        if captcha.detected:
            results.append(captcha)

        login = self.detect_login(html, url)
        if login.detected:
            results.append(login)

        paywall = self.detect_paywall(html, url)
        if paywall.detected:
            results.append(paywall)

        rate_limit = self.detect_rate_limit(html, url, status_code)
        if rate_limit.detected:
            results.append(rate_limit)

        access_denied = self.detect_access_denied(html, url, status_code)
        if access_denied.detected:
            results.append(access_denied)

        # Sort by confidence (highest first)
        results.sort(key=lambda r: r.confidence, reverse=True)

        return results

    def detect_and_raise(self, html: str, url: str = "", status_code: int = None) -> None:
        """
        Detect site conditions and raise appropriate exception if found.

        Args:
            html: Page HTML content
            url: Current page URL
            status_code: HTTP status code if available

        Raises:
            CaptchaError: If CAPTCHA detected
            LoginRequiredError: If login wall detected
            PaywallError: If paywall detected
            RateLimitError: If rate limited
            AccessDeniedError: If access denied
        """
        results = self.detect_all(html, url, status_code)

        if not results:
            return

        # Raise exception for the highest confidence detection
        top = results[0]

        if top.condition == "captcha":
            raise CaptchaError(url, captcha_type=top.details)
        elif top.condition == "login":
            raise LoginRequiredError(url)
        elif top.condition == "paywall":
            raise PaywallError(url)
        elif top.condition == "rate_limit":
            # Extract retry_after from details if present
            retry_after = None
            if top.details and "Retry after" in top.details:
                try:
                    retry_after = float(top.details.split()[-1].rstrip('s'))
                except (ValueError, IndexError):
                    pass
            raise RateLimitError("site", retry_after=retry_after)
        elif top.condition == "access_denied":
            raise AccessDeniedError(url, status_code=status_code)
