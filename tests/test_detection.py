"""
Unit tests for blackreach/detection.py

Tests CAPTCHA, login, paywall, and rate limit detection.
"""

import pytest
from blackreach.detection import SiteDetector, DetectionResult
from blackreach.exceptions import (
    CaptchaError,
    LoginRequiredError,
    PaywallError,
    RateLimitError,
    AccessDeniedError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def detector():
    """Create detector instance."""
    return SiteDetector()


@pytest.fixture
def recaptcha_html():
    """HTML with reCAPTCHA."""
    return """
    <html>
    <head>
        <script src="https://www.google.com/recaptcha/api.js"></script>
    </head>
    <body>
        <div class="g-recaptcha" data-sitekey="6LcXXXXXXXXX"></div>
        <p>Please verify you're not a robot</p>
    </body>
    </html>
    """


@pytest.fixture
def hcaptcha_html():
    """HTML with hCaptcha."""
    return """
    <html>
    <head>
        <script src="https://hcaptcha.com/1/api.js"></script>
    </head>
    <body>
        <div class="h-captcha" data-sitekey="xxx"></div>
    </body>
    </html>
    """


@pytest.fixture
def cloudflare_html():
    """HTML with Cloudflare challenge."""
    return """
    <html>
    <head>
        <title>Just a moment...</title>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>
    </head>
    <body>
        <div id="cf-challenge-running">
            <div class="cf-turnstile"></div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def login_html():
    """HTML with login form."""
    return """
    <html>
    <head><title>Sign In</title></head>
    <body>
        <h1>Sign in to continue</h1>
        <form action="/login">
            <input type="email" name="email" placeholder="Email">
            <input type="password" name="password" placeholder="Password">
            <button type="submit">Log In</button>
        </form>
    </body>
    </html>
    """


@pytest.fixture
def paywall_html():
    """HTML with paywall."""
    return """
    <html>
    <body>
        <article class="premium-content">
            <h1>Premium Article</h1>
            <div class="paywall-overlay" style="filter: blur(5px)">
                <p>This content is blurred...</p>
            </div>
            <div class="subscribe-wall">
                <h2>Subscribe to read this article</h2>
                <p>Unlock this article with a subscription</p>
            </div>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def rate_limit_html():
    """HTML for rate limited response."""
    return """
    <html>
    <body>
        <h1>Too Many Requests</h1>
        <p>You have been rate limited. Please try again in 60 seconds.</p>
    </body>
    </html>
    """


@pytest.fixture
def access_denied_html():
    """HTML for access denied."""
    return """
    <html>
    <body>
        <h1>403 Forbidden</h1>
        <p>Access denied. You don't have permission to view this page.</p>
    </body>
    </html>
    """


@pytest.fixture
def normal_html():
    """Normal page without any blockers."""
    return """
    <html>
    <head><title>Normal Page</title></head>
    <body>
        <h1>Welcome</h1>
        <p>This is a normal page with no special conditions.</p>
        <a href="/other">Link</a>
    </body>
    </html>
    """


# =============================================================================
# CAPTCHA Detection Tests
# =============================================================================

class TestCaptchaDetection:
    """Tests for CAPTCHA detection."""

    def test_detect_recaptcha(self, detector, recaptcha_html):
        """Detects reCAPTCHA."""
        result = detector.detect_captcha(recaptcha_html)

        assert result.detected is True
        assert result.condition == "captcha"
        assert result.confidence >= 0.5
        assert result.details == "reCAPTCHA"

    def test_detect_hcaptcha(self, detector, hcaptcha_html):
        """Detects hCaptcha."""
        result = detector.detect_captcha(hcaptcha_html)

        assert result.detected is True
        assert result.condition == "captcha"
        assert result.details == "hCaptcha"

    def test_detect_cloudflare(self, detector, cloudflare_html):
        """Detects Cloudflare challenge."""
        result = detector.detect_captcha(cloudflare_html)

        assert result.detected is True
        assert result.condition == "captcha"
        assert result.details == "Cloudflare"

    def test_no_captcha_on_normal_page(self, detector, normal_html):
        """No false positive on normal page."""
        result = detector.detect_captcha(normal_html)

        assert result.detected is False
        assert result.condition is None

    def test_captcha_script_detection(self, detector):
        """Detects CAPTCHA by script URL."""
        html = '<script src="https://www.google.com/recaptcha/api2/anchor"></script>'
        result = detector.detect_captcha(html)

        assert result.detected is True
        assert any("Script" in i for i in result.indicators)

    def test_captcha_sitekey_detection(self, detector):
        """Detects CAPTCHA by sitekey attribute."""
        html = '<div data-sitekey="abc123"></div>'
        result = detector.detect_captcha(html)

        assert result.confidence > 0
        assert "CAPTCHA sitekey" in result.indicators


# =============================================================================
# Login Detection Tests
# =============================================================================

class TestLoginDetection:
    """Tests for login wall detection."""

    def test_detect_login_form(self, detector, login_html):
        """Detects login form."""
        result = detector.detect_login(login_html)

        assert result.detected is True
        assert result.condition == "login"
        assert result.confidence >= 0.5

    def test_detect_login_url(self, detector, normal_html):
        """Detects login by URL pattern."""
        result = detector.detect_login(normal_html, url="https://example.com/login")

        assert result.confidence > 0
        assert any("URL" in i for i in result.indicators)

    def test_detect_login_text(self, detector):
        """Detects login by text patterns."""
        # Multiple login indicators to reach confidence threshold
        html = '''
        <h1>Please sign in</h1>
        <p>You must be logged in to view this content</p>
        <form><input type="password"></form>
        '''
        result = detector.detect_login(html)

        assert result.detected is True
        assert any("Pattern" in i for i in result.indicators)

    def test_detect_password_field(self, detector):
        """Detects login by password field."""
        html = '<input type="password" name="password">'
        result = detector.detect_login(html)

        assert result.confidence > 0

    def test_no_login_on_normal_page(self, detector, normal_html):
        """No false positive on normal page."""
        result = detector.detect_login(normal_html)

        assert result.detected is False

    def test_login_title_detection(self, detector):
        """Detects login by page title."""
        html = '<html><head><title>Log In - Example</title></head></html>'
        result = detector.detect_login(html)

        assert result.confidence > 0


# =============================================================================
# Paywall Detection Tests
# =============================================================================

class TestPaywallDetection:
    """Tests for paywall detection."""

    def test_detect_paywall(self, detector, paywall_html):
        """Detects paywall."""
        result = detector.detect_paywall(paywall_html)

        assert result.detected is True
        assert result.condition == "paywall"
        assert result.confidence >= 0.5

    def test_detect_subscribe_text(self, detector):
        """Detects paywall by subscription text."""
        # Multiple paywall indicators to reach confidence threshold
        html = '''
        <div class="paywall">
            <p>Subscribe to continue reading this article</p>
            <p>Premium content - subscribers only</p>
        </div>
        '''
        result = detector.detect_paywall(html)

        assert result.detected is True

    def test_detect_premium_content(self, detector):
        """Detects paywall by premium content indicators."""
        html = '<div class="premium-wall">Premium content locked</div>'
        result = detector.detect_paywall(html)

        assert result.detected is True

    def test_detect_blurred_content(self, detector):
        """Detects paywall by blurred content."""
        html = '<div style="filter: blur(5px)">Content here</div>'
        result = detector.detect_paywall(html)

        assert result.confidence > 0

    def test_no_paywall_on_normal_page(self, detector, normal_html):
        """No false positive on normal page."""
        result = detector.detect_paywall(normal_html)

        assert result.detected is False


# =============================================================================
# Rate Limit Detection Tests
# =============================================================================

class TestRateLimitDetection:
    """Tests for rate limit detection."""

    def test_detect_rate_limit(self, detector, rate_limit_html):
        """Detects rate limiting."""
        result = detector.detect_rate_limit(rate_limit_html)

        assert result.detected is True
        assert result.condition == "rate_limit"

    def test_detect_429_status(self, detector, normal_html):
        """Detects rate limit by HTTP 429."""
        result = detector.detect_rate_limit(normal_html, status_code=429)

        assert result.detected is True
        assert "HTTP 429" in result.indicators

    def test_detect_rate_limit_text(self, detector):
        """Detects rate limit by text patterns."""
        html = '<p>Too many requests. Slow down!</p>'
        result = detector.detect_rate_limit(html)

        assert result.detected is True

    def test_no_rate_limit_on_normal_page(self, detector, normal_html):
        """No false positive on normal page."""
        result = detector.detect_rate_limit(normal_html)

        assert result.detected is False


# =============================================================================
# Access Denied Detection Tests
# =============================================================================

class TestAccessDeniedDetection:
    """Tests for access denied detection."""

    def test_detect_access_denied(self, detector, access_denied_html):
        """Detects access denied."""
        result = detector.detect_access_denied(access_denied_html)

        assert result.detected is True
        assert result.condition == "access_denied"

    def test_detect_403_status(self, detector, normal_html):
        """Detects access denied by HTTP 403."""
        result = detector.detect_access_denied(normal_html, status_code=403)

        assert result.detected is True
        assert "HTTP 403" in result.indicators

    def test_detect_401_status(self, detector, normal_html):
        """Detects access denied by HTTP 401."""
        result = detector.detect_access_denied(normal_html, status_code=401)

        assert result.detected is True

    def test_detect_forbidden_text(self, detector):
        """Detects access denied by text."""
        html = '<h1>Forbidden</h1><p>You are not authorized to access this resource.</p>'
        result = detector.detect_access_denied(html)

        assert result.detected is True

    def test_no_access_denied_on_normal_page(self, detector, normal_html):
        """No false positive on normal page."""
        result = detector.detect_access_denied(normal_html)

        assert result.detected is False


# =============================================================================
# Combined Detection Tests
# =============================================================================

class TestCombinedDetection:
    """Tests for detect_all method."""

    def test_detect_all_returns_list(self, detector, normal_html):
        """detect_all returns list."""
        results = detector.detect_all(normal_html)
        assert isinstance(results, list)

    def test_detect_all_empty_on_normal(self, detector, normal_html):
        """No detections on normal page."""
        results = detector.detect_all(normal_html)
        assert len(results) == 0

    def test_detect_all_finds_captcha(self, detector, recaptcha_html):
        """detect_all finds CAPTCHA."""
        results = detector.detect_all(recaptcha_html)

        assert len(results) >= 1
        assert results[0].condition == "captcha"

    def test_detect_all_sorted_by_confidence(self, detector):
        """Results sorted by confidence (highest first)."""
        # Page with weak signals for multiple conditions
        html = """
        <p>sign in</p>
        <p>subscribe</p>
        <p>captcha</p>
        """
        results = detector.detect_all(html)

        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].confidence >= results[i + 1].confidence


# =============================================================================
# Exception Raising Tests
# =============================================================================

class TestDetectAndRaise:
    """Tests for detect_and_raise method."""

    def test_raises_captcha_error(self, detector, recaptcha_html):
        """Raises CaptchaError for CAPTCHA."""
        with pytest.raises(CaptchaError) as exc_info:
            detector.detect_and_raise(recaptcha_html, "https://example.com")

        assert "example.com" in str(exc_info.value)

    def test_raises_login_error(self, detector, login_html):
        """Raises LoginRequiredError for login wall."""
        with pytest.raises(LoginRequiredError):
            detector.detect_and_raise(login_html, "https://example.com/login")

    def test_raises_paywall_error(self, detector, paywall_html):
        """Raises PaywallError for paywall."""
        with pytest.raises(PaywallError):
            detector.detect_and_raise(paywall_html, "https://example.com")

    def test_raises_rate_limit_error(self, detector):
        """Raises RateLimitError for rate limit."""
        with pytest.raises(RateLimitError):
            detector.detect_and_raise("<p>too many requests</p>", status_code=429)

    def test_raises_access_denied_error(self, detector, access_denied_html):
        """Raises AccessDeniedError for access denied."""
        with pytest.raises(AccessDeniedError):
            detector.detect_and_raise(access_denied_html, status_code=403)

    def test_no_raise_on_normal(self, detector, normal_html):
        """No exception on normal page."""
        # Should not raise
        detector.detect_and_raise(normal_html, "https://example.com")


# =============================================================================
# Detection Result Tests
# =============================================================================

class TestDetectionResult:
    """Tests for DetectionResult dataclass."""

    def test_default_values(self):
        """DetectionResult has sensible defaults."""
        result = DetectionResult(detected=False)

        assert result.detected is False
        assert result.condition is None
        assert result.confidence == 0.0
        assert result.details is None
        assert result.indicators == []

    def test_with_all_fields(self):
        """DetectionResult accepts all fields."""
        result = DetectionResult(
            detected=True,
            condition="captcha",
            confidence=0.9,
            details="reCAPTCHA",
            indicators=["script found", "sitekey found"]
        )

        assert result.detected is True
        assert result.condition == "captcha"
        assert result.confidence == 0.9
        assert result.details == "reCAPTCHA"
        assert len(result.indicators) == 2
