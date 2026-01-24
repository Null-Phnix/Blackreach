"""
CAPTCHA Detection Module (v1.0.0)

Detects common CAPTCHA providers in page HTML:
- reCAPTCHA (v2, v3, Enterprise)
- hCaptcha
- Cloudflare Turnstile
- FunCaptcha (Arkose Labs)
- GeeTest
- AWS WAF CAPTCHA
- PerimeterX / HUMAN
- DataDome
- Generic CAPTCHA patterns

Provides detection results with provider info and confidence levels.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from enum import Enum


class CaptchaProvider(Enum):
    """Known CAPTCHA providers."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    RECAPTCHA_ENTERPRISE = "recaptcha_enterprise"
    HCAPTCHA = "hcaptcha"
    CLOUDFLARE_TURNSTILE = "cloudflare_turnstile"
    FUNCAPTCHA = "funcaptcha"
    GEETEST = "geetest"
    AWS_WAF = "aws_waf"
    PERIMETERX = "perimeterx"
    DATADOME = "datadome"
    KEYCAPTCHA = "keycaptcha"
    TEXTCAPTCHA = "textcaptcha"
    GENERIC = "generic"
    UNKNOWN = "unknown"


@dataclass
class CaptchaDetectionResult:
    """Result of CAPTCHA detection."""
    detected: bool
    provider: Optional[CaptchaProvider] = None
    confidence: float = 0.0  # 0.0 to 1.0
    sitekey: Optional[str] = None  # Site key if extractable
    details: Optional[str] = None
    selectors: List[str] = None  # CSS selectors for CAPTCHA elements

    def __post_init__(self):
        if self.selectors is None:
            self.selectors = []


# Detection patterns for each provider
CAPTCHA_PATTERNS: Dict[CaptchaProvider, List[Tuple[str, float]]] = {
    CaptchaProvider.RECAPTCHA_V2: [
        (r'class=["\']g-recaptcha["\']', 0.95),
        (r'data-sitekey=["\'][0-9A-Za-z_-]{40}["\']', 0.95),
        (r'google\.com/recaptcha/api\.js', 0.9),
        (r'google\.com/recaptcha/api2', 0.9),
        (r'grecaptcha\.render', 0.85),
        (r'grecaptcha\.execute', 0.85),
        (r'recaptcha/api2/anchor', 0.9),
        (r'recaptcha-checkbox', 0.8),
    ],
    CaptchaProvider.RECAPTCHA_V3: [
        (r'recaptcha/api\.js\?render=', 0.95),
        (r'grecaptcha\.execute\([^)]+,\s*\{action:', 0.95),
        (r'data-action=["\'][^"\']+["\'].*g-recaptcha', 0.85),
        (r'recaptcha-v3', 0.9),
    ],
    CaptchaProvider.RECAPTCHA_ENTERPRISE: [
        (r'recaptcha/enterprise\.js', 0.95),
        (r'grecaptcha\.enterprise', 0.95),
        (r'recaptchaenterprise\.googleapis\.com', 0.95),
    ],
    CaptchaProvider.HCAPTCHA: [
        (r'class=["\']h-captcha["\']', 0.95),
        (r'data-sitekey=["\'][0-9a-f-]{36}["\']', 0.8),  # UUID format
        (r'hcaptcha\.com/1/api\.js', 0.95),
        (r'js\.hcaptcha\.com', 0.95),
        (r'hcaptcha-box', 0.85),
        (r'hcaptcha\.render', 0.9),
        (r'hcaptcha\.execute', 0.9),
    ],
    CaptchaProvider.CLOUDFLARE_TURNSTILE: [
        (r'class=["\']cf-turnstile["\']', 0.95),
        (r'challenges\.cloudflare\.com/turnstile', 0.95),
        (r'turnstile\.render', 0.9),
        (r'data-sitekey=["\']0x[A-Za-z0-9]+["\']', 0.8),  # Turnstile format
        (r'cfTurnstileToken', 0.85),
    ],
    CaptchaProvider.FUNCAPTCHA: [
        (r'arkoselabs\.com', 0.95),
        (r'funcaptcha\.com', 0.95),
        (r'ArkoseEnforcement', 0.9),
        (r'arkose-token', 0.85),
        (r'fc-token', 0.85),
        (r'FunCaptcha', 0.9),
    ],
    CaptchaProvider.GEETEST: [
        (r'geetest\.com', 0.95),
        (r'gt\.js', 0.7),
        (r'initGeetest', 0.9),
        (r'geetest_challenge', 0.9),
        (r'geetest_validate', 0.9),
        (r'geetest_seccode', 0.9),
        (r'class=["\']geetest', 0.85),
    ],
    CaptchaProvider.AWS_WAF: [
        (r'awswaf-captcha', 0.95),
        (r'aws-waf-captcha', 0.95),
        (r'captcha\.awswaf\.com', 0.95),
        (r'WAFCaptchaToken', 0.9),
    ],
    CaptchaProvider.PERIMETERX: [
        (r'px\.js', 0.7),
        (r'perimeterx\.net', 0.95),
        (r'_px[23]', 0.8),
        (r'pxCaptcha', 0.95),
        (r'human\.com.*captcha', 0.9),
        (r'px-captcha', 0.95),
    ],
    CaptchaProvider.DATADOME: [
        (r'datadome\.co', 0.95),
        (r'dd\.js', 0.6),
        (r'DataDome', 0.9),
        (r'datadome-captcha', 0.95),
        (r'geo\.captcha-delivery\.com', 0.95),
    ],
    CaptchaProvider.KEYCAPTCHA: [
        (r'keycaptcha\.com', 0.95),
        (r'KeyCAPTCHA', 0.9),
        (r's_s_c_user_id', 0.85),
    ],
    CaptchaProvider.TEXTCAPTCHA: [
        (r'textcaptcha\.com', 0.95),
    ],
}

# Generic CAPTCHA patterns (provider-agnostic)
GENERIC_CAPTCHA_PATTERNS = [
    (r'<img[^>]*captcha[^>]*>', 0.7),
    (r'captcha-image', 0.75),
    (r'captcha-input', 0.75),
    (r'id=["\']captcha["\']', 0.7),
    (r'name=["\']captcha["\']', 0.7),
    (r'class=["\'][^"\']*captcha[^"\']*["\']', 0.6),
    (r'enter.*(the\s+)?(characters|text|code).*image', 0.6),
    (r'verify.*human', 0.5),
    (r'not\s+a\s+robot', 0.5),
    (r'prove.*human', 0.5),
    (r'type.*characters.*see', 0.6),
    (r'security.*check', 0.4),
    (r'challenge-form', 0.5),
]

# Challenge page patterns (not necessarily CAPTCHA but blocking access)
CHALLENGE_PAGE_PATTERNS = [
    (r'checking your browser', 0.8),
    (r'just a moment', 0.7),
    (r'please wait.*redirect', 0.6),
    (r'access denied', 0.5),
    (r'blocked', 0.4),
    (r'verify.*identity', 0.5),
]


class CaptchaDetector:
    """Detects CAPTCHA presence and type in HTML content."""

    def __init__(self):
        self._compiled_patterns: Dict[CaptchaProvider, List[Tuple[re.Pattern, float]]] = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        for provider, patterns in CAPTCHA_PATTERNS.items():
            self._compiled_patterns[provider] = [
                (re.compile(pattern, re.IGNORECASE), confidence)
                for pattern, confidence in patterns
            ]

        self._generic_patterns = [
            (re.compile(pattern, re.IGNORECASE), confidence)
            for pattern, confidence in GENERIC_CAPTCHA_PATTERNS
        ]

        self._challenge_patterns = [
            (re.compile(pattern, re.IGNORECASE), confidence)
            for pattern, confidence in CHALLENGE_PAGE_PATTERNS
        ]

    def detect(self, html: str) -> CaptchaDetectionResult:
        """
        Detect if HTML contains a CAPTCHA.

        Args:
            html: Page HTML content

        Returns:
            CaptchaDetectionResult with detection details
        """
        if not html:
            return CaptchaDetectionResult(detected=False)

        # Check each known provider
        best_match: Optional[Tuple[CaptchaProvider, float, str]] = None

        for provider, patterns in self._compiled_patterns.items():
            for pattern, base_confidence in patterns:
                match = pattern.search(html)
                if match:
                    # Boost confidence if multiple patterns match
                    confidence = base_confidence
                    if best_match and best_match[0] == provider:
                        confidence = min(1.0, best_match[1] + 0.1)

                    if not best_match or confidence > best_match[1]:
                        best_match = (provider, confidence, match.group(0))

        if best_match:
            provider, confidence, matched_text = best_match
            sitekey = self._extract_sitekey(html, provider)
            selectors = self._get_selectors(provider)

            return CaptchaDetectionResult(
                detected=True,
                provider=provider,
                confidence=confidence,
                sitekey=sitekey,
                details=f"Matched: {matched_text[:100]}",
                selectors=selectors
            )

        # Check generic CAPTCHA patterns
        for pattern, confidence in self._generic_patterns:
            match = pattern.search(html)
            if match:
                return CaptchaDetectionResult(
                    detected=True,
                    provider=CaptchaProvider.GENERIC,
                    confidence=confidence,
                    details=f"Generic CAPTCHA pattern: {match.group(0)[:100]}"
                )

        return CaptchaDetectionResult(detected=False)

    def detect_challenge_page(self, html: str) -> Tuple[bool, float, str]:
        """
        Detect if the page is a challenge/verification page.

        Returns:
            Tuple of (is_challenge, confidence, details)
        """
        if not html:
            return (False, 0.0, "")

        for pattern, confidence in self._challenge_patterns:
            match = pattern.search(html)
            if match:
                return (True, confidence, match.group(0))

        return (False, 0.0, "")

    def _extract_sitekey(self, html: str, provider: CaptchaProvider) -> Optional[str]:
        """Extract the site key for known providers."""
        sitekey_patterns = {
            CaptchaProvider.RECAPTCHA_V2: r'data-sitekey=["\']([0-9A-Za-z_-]{40})["\']',
            CaptchaProvider.RECAPTCHA_V3: r'grecaptcha\.execute\(["\']([0-9A-Za-z_-]{40})["\']',
            CaptchaProvider.RECAPTCHA_ENTERPRISE: r'data-sitekey=["\']([0-9A-Za-z_-]{40})["\']',
            CaptchaProvider.HCAPTCHA: r'data-sitekey=["\']([0-9a-f-]{36})["\']',
            CaptchaProvider.CLOUDFLARE_TURNSTILE: r'data-sitekey=["\']([0-9A-Za-z_]+)["\']',
        }

        pattern = sitekey_patterns.get(provider)
        if pattern:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _get_selectors(self, provider: CaptchaProvider) -> List[str]:
        """Get CSS selectors for common CAPTCHA elements by provider."""
        selectors = {
            CaptchaProvider.RECAPTCHA_V2: [
                '.g-recaptcha',
                '[data-sitekey]',
                '.recaptcha-checkbox',
                '#g-recaptcha',
            ],
            CaptchaProvider.RECAPTCHA_V3: [
                '.g-recaptcha',
                '[data-sitekey]',
            ],
            CaptchaProvider.RECAPTCHA_ENTERPRISE: [
                '.g-recaptcha',
                '[data-sitekey]',
            ],
            CaptchaProvider.HCAPTCHA: [
                '.h-captcha',
                '[data-sitekey]',
                '.hcaptcha-box',
            ],
            CaptchaProvider.CLOUDFLARE_TURNSTILE: [
                '.cf-turnstile',
                '[data-sitekey]',
            ],
            CaptchaProvider.FUNCAPTCHA: [
                '#FunCaptcha',
                '.funcaptcha',
                '[data-pkey]',
            ],
            CaptchaProvider.GEETEST: [
                '.geetest_holder',
                '#geetest',
                '.geetest_radar_btn',
            ],
        }
        return selectors.get(provider, ['.captcha', '#captcha', '[class*="captcha"]'])

    def get_all_captcha_elements(self, html: str) -> List[Dict]:
        """
        Find all potential CAPTCHA-related elements in HTML.

        Returns list of dicts with element info.
        """
        elements = []

        # Common CAPTCHA container patterns
        patterns = [
            (r'<div[^>]*class=["\'][^"\']*captcha[^"\']*["\'][^>]*>', 'div.captcha'),
            (r'<div[^>]*id=["\'][^"\']*captcha[^"\']*["\'][^>]*>', 'div#captcha'),
            (r'<iframe[^>]*src=["\'][^"\']*recaptcha[^"\']*["\'][^>]*>', 'iframe.recaptcha'),
            (r'<iframe[^>]*src=["\'][^"\']*hcaptcha[^"\']*["\'][^>]*>', 'iframe.hcaptcha'),
            (r'<img[^>]*captcha[^>]*>', 'img.captcha'),
            (r'<input[^>]*captcha[^>]*>', 'input.captcha'),
        ]

        for pattern, element_type in patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE):
                elements.append({
                    'type': element_type,
                    'html': match.group(0)[:200],
                    'position': match.start()
                })

        return elements

    def get_bypass_suggestions(self, result: CaptchaDetectionResult) -> List[str]:
        """
        Get suggestions for handling the detected CAPTCHA.

        Note: These are legitimate approaches like waiting, using
        authenticated sessions, or finding alternative content sources.
        """
        if not result.detected:
            return []

        suggestions = [
            "Consider if the content is available from an alternative source",
            "Check if an API is available for this service",
            "Verify if authentication would grant access without CAPTCHA",
        ]

        if result.provider == CaptchaProvider.CLOUDFLARE_TURNSTILE:
            suggestions.append("Cloudflare challenges often resolve automatically - wait and retry")

        if result.provider in (CaptchaProvider.RECAPTCHA_V3,):
            suggestions.append("reCAPTCHA v3 runs in background - ensure human-like browsing patterns")

        if result.confidence < 0.7:
            suggestions.append("Low confidence detection - this might be a false positive")

        return suggestions


# Singleton instance
_detector: Optional[CaptchaDetector] = None


def get_captcha_detector() -> CaptchaDetector:
    """Get the global CaptchaDetector instance."""
    global _detector
    if _detector is None:
        _detector = CaptchaDetector()
    return _detector


def detect_captcha(html: str) -> CaptchaDetectionResult:
    """Convenience function to detect CAPTCHA in HTML."""
    return get_captcha_detector().detect(html)


def is_captcha_present(html: str) -> bool:
    """Quick check if any CAPTCHA is present."""
    return get_captcha_detector().detect(html).detected
