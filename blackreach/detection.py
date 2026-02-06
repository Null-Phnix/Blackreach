"""
Site condition detection for Blackreach.

Detects:
- CAPTCHAs (reCAPTCHA, hCaptcha, etc.)
- Login walls
- Paywalls
- Rate limiting
- Access denied pages
- Site type (static vs SPA) for adaptive timeouts
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple
from urllib.parse import urlparse
from enum import Enum

from blackreach.exceptions import (
    CaptchaError,
    LoginRequiredError,
    PaywallError,
    AccessDeniedError,
    RateLimitError,
)


class SiteType(Enum):
    """Site type classification for adaptive timeout behavior."""
    STATIC = "static"           # Traditional server-rendered pages (Wikipedia, GitHub)
    SPA = "spa"                 # Single Page Applications (React, Vue, Angular)
    HYBRID = "hybrid"           # Server-rendered with client hydration (Next.js)
    SEARCH_ENGINE = "search"    # Search engines (Google, DuckDuckGo)
    UNKNOWN = "unknown"


@dataclass
class SiteCharacteristics:
    """Characteristics of a site for timeout tuning."""
    site_type: SiteType
    # Timeout recommendations in milliseconds
    network_idle_timeout: int = 10000  # Default 10s
    content_wait_timeout: int = 5000   # Default 5s
    # Whether to skip certain wait phases
    skip_framework_detection: bool = False
    skip_dynamic_content_wait: bool = False
    # Early exit thresholds
    min_links_for_ready: int = 3
    min_text_length_for_ready: int = 200
    # Description for logging
    description: str = ""


# Known static sites that load quickly - map domain patterns to characteristics
STATIC_SITE_PATTERNS = {
    # Wikipedia and Wikimedia
    "wikipedia.org": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        min_links_for_ready=10,
        min_text_length_for_ready=500,
        description="Wikipedia - static server-rendered"
    ),
    "wikimedia.org": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="Wikimedia - static server-rendered"
    ),
    # GitHub
    "github.com": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        min_text_length_for_ready=200,
        description="GitHub - hybrid with pjax navigation"
    ),
    "raw.githubusercontent.com": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=3000,
        content_wait_timeout=2000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="GitHub raw content - static"
    ),
    # Search engines
    "google.com": SiteCharacteristics(
        site_type=SiteType.SEARCH_ENGINE,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Google - search engine"
    ),
    "duckduckgo.com": SiteCharacteristics(
        site_type=SiteType.SEARCH_ENGINE,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="DuckDuckGo - search engine"
    ),
    "bing.com": SiteCharacteristics(
        site_type=SiteType.SEARCH_ENGINE,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Bing - search engine"
    ),
    # Documentation sites
    "docs.python.org": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="Python docs - static"
    ),
    "developer.mozilla.org": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        description="MDN - static documentation"
    ),
    # News/content sites
    "arxiv.org": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="arXiv - static academic papers"
    ),
    "stackoverflow.com": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=6000,
        content_wait_timeout=4000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Stack Overflow - mostly static"
    ),
    # Reddit (old reddit is static, new reddit is SPA - we detect by subdomain)
    "old.reddit.com": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=6000,
        content_wait_timeout=4000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Old Reddit - static"
    ),
    # Book/document download sites
    "libgen": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="LibGen - static book database"
    ),
    "annas-archive": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=6000,
        content_wait_timeout=4000,
        skip_framework_detection=True,
        min_links_for_ready=3,
        description="Anna's Archive - static book search"
    ),
    # News sites
    "bbc.com": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="BBC News - hybrid"
    ),
    "reuters.com": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Reuters - hybrid"
    ),
    # Tech documentation
    "docs.microsoft.com": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=6000,
        content_wait_timeout=4000,
        skip_framework_detection=True,
        description="Microsoft Docs - static"
    ),
    "learn.microsoft.com": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=6000,
        content_wait_timeout=4000,
        skip_framework_detection=True,
        description="Microsoft Learn - static"
    ),
    "readthedocs.io": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="ReadTheDocs - static documentation"
    ),
    "readthedocs.org": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="ReadTheDocs - static documentation"
    ),
    # Image sites
    "unsplash.com": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=6000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Unsplash - hybrid image site"
    ),
    "pexels.com": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=6000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Pexels - hybrid image site"
    ),
    "wallhaven.cc": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=6000,
        content_wait_timeout=4000,
        skip_framework_detection=True,
        min_links_for_ready=3,
        description="Wallhaven - static wallpaper site"
    ),
    # Code repositories
    "gitlab.com": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="GitLab - hybrid"
    ),
    "bitbucket.org": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Bitbucket - hybrid"
    ),
    # AI/ML sites
    "huggingface.co": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Hugging Face - hybrid"
    ),
    "kaggle.com": SiteCharacteristics(
        site_type=SiteType.HYBRID,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Kaggle - hybrid"
    ),
    # Academic
    "sciencedirect.com": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=6000,
        content_wait_timeout=4000,
        skip_framework_detection=True,
        min_links_for_ready=3,
        description="ScienceDirect - mostly static"
    ),
    "pubmed.ncbi.nlm.nih.gov": SiteCharacteristics(
        site_type=SiteType.STATIC,
        network_idle_timeout=5000,
        content_wait_timeout=3000,
        skip_framework_detection=True,
        skip_dynamic_content_wait=True,
        description="PubMed - static"
    ),
    "scholar.google.com": SiteCharacteristics(
        site_type=SiteType.SEARCH_ENGINE,
        network_idle_timeout=8000,
        content_wait_timeout=5000,
        skip_framework_detection=True,
        min_links_for_ready=5,
        description="Google Scholar - search engine"
    ),
}


def get_site_characteristics(url: str) -> SiteCharacteristics:
    """
    Get site characteristics for adaptive timeout tuning.

    Args:
        url: The URL to analyze

    Returns:
        SiteCharacteristics with recommended timeout values
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check against known patterns
        for pattern, characteristics in STATIC_SITE_PATTERNS.items():
            if pattern in domain:
                return characteristics

        # Default characteristics for unknown sites
        return SiteCharacteristics(
            site_type=SiteType.UNKNOWN,
            network_idle_timeout=10000,
            content_wait_timeout=8000,
            description="Unknown site - using default timeouts"
        )
    except Exception:
        return SiteCharacteristics(
            site_type=SiteType.UNKNOWN,
            description="Could not parse URL"
        )

# P0-PERF: Pre-compiled regex patterns for detection
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.IGNORECASE)
_RE_RETRY_AFTER = re.compile(r'try\s*again\s*in\s*(\d+)\s*(second|minute|hour)?', re.IGNORECASE)
_RE_HTML_TAGS = re.compile(r'<[^>]+>')
_RE_COUNTDOWN = re.compile(r'seconds?|wait\s*\d+')


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
        # DDoS-Guard
        r'ddos-guard',
        r'ddos_guard',
        r'DDoS-Guard',
        r'checking\s*your\s*browser',
        r'please\s*wait.*redirect',
        # Generic
        r'captcha',
        r'robot\s*check',
        r'are\s*you\s*a\s*human',
        r'prove\s*you.re\s*human',
        r'security\s*check',
        r'bot\s*detection',
        r'verify\s*you.re\s*not\s*a\s*robot',
        r'just\s*a\s*moment',
        r'browser\s*verification',
    ]

    CAPTCHA_SCRIPTS = [
        'recaptcha/api.js',
        'recaptcha/api2/',
        'hcaptcha.com/1/',
        'challenges.cloudflare.com',
        'turnstile/v0/api.js',
        'ddos-guard.net',
    ]

    # Challenge/interstitial page indicators (auto-solving, need to wait)
    CHALLENGE_PATTERNS = [
        r'ddos-guard',
        r'DDoS-Guard',
        r'checking\s*your\s*browser',
        r'please\s*wait',
        r'just\s*a\s*moment',
        r'verifying.*connection',
        r'cf-browser-verification',
        r'ray\s*id',  # Cloudflare Ray ID
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
        self._challenge_re = re.compile('|'.join(self.CHALLENGE_PATTERNS), re.IGNORECASE)

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

        # Check title (uses pre-compiled pattern)
        if '<title>' in html_lower:
            title_match = _RE_TITLE.search(html)
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

        # Try to extract retry-after hint (uses pre-compiled pattern)
        retry_after = None
        retry_match = _RE_RETRY_AFTER.search(html)
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

    def detect_challenge(self, html: str, url: str = "") -> DetectionResult:
        """
        Detect if page is a challenge/interstitial page that may auto-resolve.

        These are pages like DDoS-Guard, Cloudflare "checking your browser",
        etc. that often resolve automatically if you wait a few seconds.
        """
        indicators = []
        confidence = 0.0
        html_lower = html.lower()

        # Check for challenge patterns
        matches = self._challenge_re.findall(html)
        for match in matches[:3]:
            indicators.append(f"Pattern: {match}")
            confidence += 0.3

        # Check for DDoS-Guard specific indicators
        if 'ddos-guard' in html_lower or 'ddos_guard' in html_lower:
            indicators.append("DDoS-Guard")
            confidence += 0.5

        # Check for Cloudflare challenge
        if 'cf-browser-verification' in html_lower or 'cf_clearance' in html_lower:
            indicators.append("Cloudflare challenge")
            confidence += 0.4

        # Check for minimal page content (interstitial pages are usually minimal)
        # Count actual content elements (uses pre-compiled pattern)
        text_content = _RE_HTML_TAGS.sub('', html)
        word_count = len(text_content.split())
        if word_count < 50:
            indicators.append(f"Minimal content ({word_count} words)")
            confidence += 0.2

        # Check for JavaScript redirect indicators
        if 'location.href' in html or 'window.location' in html:
            if 'setTimeout' in html or 'setInterval' in html:
                indicators.append("JS redirect timer")
                confidence += 0.3

        # Check for meta refresh
        if 'http-equiv="refresh"' in html_lower or "http-equiv='refresh'" in html_lower:
            indicators.append("Meta refresh")
            confidence += 0.3

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.4 or 'ddos-guard' in html_lower

        challenge_type = None
        if 'ddos-guard' in html_lower:
            challenge_type = "DDoS-Guard"
        elif 'cloudflare' in html_lower or 'cf-' in html_lower:
            challenge_type = "Cloudflare"
        elif detected:
            challenge_type = "Unknown"

        return DetectionResult(
            detected=detected,
            condition="challenge" if detected else None,
            confidence=confidence,
            details=challenge_type,
            indicators=indicators
        )

    def detect_download_landing(self, html: str, url: str = "") -> DetectionResult:
        """
        Detect if page is a download landing page (not the file itself).

        These pages show file info but require another click to actually download.
        Common on sites like: vdoc.pub, mediafire, mega.nz, 4shared, etc.
        """
        indicators = []
        confidence = 0.0
        html_lower = html.lower()
        url_lower = url.lower()

        # Known download landing page domains
        landing_page_domains = [
            'vdoc.pub', 'mediafire.com', '4shared.com', 'depositfiles.com',
            'zippyshare.com', 'mega.nz', 'drive.google.com', 'dropbox.com',
            'sendspace.com', 'uploaded.net', 'rapidgator.net', 'nitroflare.com',
            'annas-archive.org', 'annas-archive.li', 'annas-archive.se',
            'libgen.is', 'libgen.rs', 'library.lol', 'z-lib.org', 'z-lib.is',
        ]
        for domain in landing_page_domains:
            if domain in url_lower:
                indicators.append(f"Known landing domain: {domain}")
                confidence += 0.4

        # URL patterns indicating download pages
        download_url_patterns = ['/download/', '/get/', '/file/', '/d/', '/files/']
        for pattern in download_url_patterns:
            if pattern in url_lower:
                indicators.append(f"URL pattern: {pattern}")
                confidence += 0.2

        # Common download button text (these indicate need to click again)
        download_button_patterns = [
            r'click\s*(here\s*)?to\s*download',
            r'download\s*(now|file|pdf|epub)',
            r'start\s*download',
            r'get\s*(your\s*)?(file|download)',
            r'direct\s*download',
            r'slow\s*download',
            r'fast\s*download',
            r'free\s*download',
            # Anna's Archive specific patterns
            r'slow\s*partner\s*server',
            r'fast\s*partner\s*server',
            r'libgen\.li',
            r'libgen\.rs',
            r'z-library',
            r'ipfs\.io',
            # LibGen patterns
            r'get\s*this\s*book',
            r'download\s*from',
            r'mirror\s*\d+',
        ]
        for pattern in download_button_patterns:
            if re.search(pattern, html_lower):
                indicators.append(f"Button text: {pattern}")
                confidence += 0.2

        # Check for file info display (size, format, pages)
        file_info_patterns = [
            r'file\s*size[:\s]*[\d.]+\s*(mb|kb|gb)',
            r'format[:\s]*(pdf|epub|mobi|doc)',
            r'pages?[:\s]*\d+',
            r'author[:\s]',
            r'isbn[:\s]',
        ]
        for pattern in file_info_patterns:
            if re.search(pattern, html_lower):
                indicators.append(f"File info: {pattern}")
                confidence += 0.1

        # Check for countdown timers (common on file hosting sites)
        if 'countdown' in html_lower or 'timer' in html_lower or 'wait' in html_lower:
            if _RE_COUNTDOWN.search(html_lower):
                indicators.append("Countdown timer detected")
                confidence += 0.3

        confidence = min(confidence, 1.0)
        detected = confidence >= 0.4

        return DetectionResult(
            detected=detected,
            condition="download_landing" if detected else None,
            confidence=confidence,
            details="Click download button to get actual file",
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
