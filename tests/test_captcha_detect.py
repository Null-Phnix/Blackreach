"""
Unit tests for blackreach/captcha_detect.py

Tests CAPTCHA detection for various providers.
"""

import pytest
from blackreach.captcha_detect import (
    CaptchaDetector,
    CaptchaDetectionResult,
    CaptchaProvider,
    detect_captcha,
    is_captcha_present,
    get_captcha_detector,
)


class TestCaptchaDetectionResult:
    """Tests for CaptchaDetectionResult dataclass."""

    def test_default_values(self):
        """Result has sensible defaults."""
        result = CaptchaDetectionResult(detected=False)
        assert result.detected is False
        assert result.provider is None
        assert result.confidence == 0.0
        assert result.sitekey is None
        assert result.selectors == []

    def test_detected_result(self):
        """Detected result has proper values."""
        result = CaptchaDetectionResult(
            detected=True,
            provider=CaptchaProvider.RECAPTCHA_V2,
            confidence=0.95,
            sitekey="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"
        )
        assert result.detected is True
        assert result.provider == CaptchaProvider.RECAPTCHA_V2
        assert result.confidence == 0.95


class TestCaptchaProvider:
    """Tests for CaptchaProvider enum."""

    def test_all_providers_defined(self):
        """All major CAPTCHA providers are defined."""
        providers = [p.value for p in CaptchaProvider]
        assert "recaptcha_v2" in providers
        assert "recaptcha_v3" in providers
        assert "hcaptcha" in providers
        assert "cloudflare_turnstile" in providers
        assert "funcaptcha" in providers
        assert "geetest" in providers


class TestCaptchaDetector:
    """Tests for CaptchaDetector class."""

    @pytest.fixture
    def detector(self):
        """Create detector instance."""
        return CaptchaDetector()

    def test_no_captcha_empty_html(self, detector):
        """No CAPTCHA detected in empty HTML."""
        result = detector.detect("")
        assert result.detected is False

    def test_no_captcha_normal_page(self, detector):
        """No CAPTCHA detected in normal page."""
        html = """
        <html>
        <head><title>Normal Page</title></head>
        <body>
            <h1>Welcome</h1>
            <p>This is a normal page with no CAPTCHA.</p>
            <form action="/submit">
                <input type="text" name="name">
                <button type="submit">Submit</button>
            </form>
        </body>
        </html>
        """
        result = detector.detect(html)
        assert result.detected is False

    # reCAPTCHA v2 Tests

    def test_recaptcha_v2_class(self, detector):
        """Detect reCAPTCHA v2 by class."""
        html = '<div class="g-recaptcha" data-sitekey="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"></div>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.RECAPTCHA_V2
        assert result.confidence >= 0.9

    def test_recaptcha_v2_script(self, detector):
        """Detect reCAPTCHA v2 by script URL."""
        html = '<script src="https://www.google.com/recaptcha/api.js"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.RECAPTCHA_V2

    def test_recaptcha_v2_sitekey_extraction(self, detector):
        """Extract sitekey from reCAPTCHA v2."""
        html = '<div class="g-recaptcha" data-sitekey="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"></div>'
        result = detector.detect(html)
        assert result.sitekey == "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"

    # reCAPTCHA v3 Tests

    def test_recaptcha_v3_script(self, detector):
        """Detect reCAPTCHA v3 by script URL."""
        html = '<script src="https://www.google.com/recaptcha/api.js?render=6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.RECAPTCHA_V3

    def test_recaptcha_v3_execute(self, detector):
        """Detect reCAPTCHA v3 by execute call."""
        html = "grecaptcha.execute('6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-', {action: 'submit'})"
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.RECAPTCHA_V3

    # reCAPTCHA Enterprise Tests

    def test_recaptcha_enterprise(self, detector):
        """Detect reCAPTCHA Enterprise."""
        html = '<script src="https://www.google.com/recaptcha/enterprise.js"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.RECAPTCHA_ENTERPRISE

    # hCaptcha Tests

    def test_hcaptcha_class(self, detector):
        """Detect hCaptcha by class."""
        html = '<div class="h-captcha" data-sitekey="10000000-ffff-ffff-ffff-000000000001"></div>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.HCAPTCHA

    def test_hcaptcha_script(self, detector):
        """Detect hCaptcha by script URL."""
        html = '<script src="https://hcaptcha.com/1/api.js" async defer></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.HCAPTCHA

    def test_hcaptcha_sitekey_extraction(self, detector):
        """Extract sitekey from hCaptcha."""
        html = '<div class="h-captcha" data-sitekey="10000000-ffff-ffff-ffff-000000000001"></div>'
        result = detector.detect(html)
        assert result.sitekey == "10000000-ffff-ffff-ffff-000000000001"

    # Cloudflare Turnstile Tests

    def test_cloudflare_turnstile_class(self, detector):
        """Detect Cloudflare Turnstile by class."""
        html = '<div class="cf-turnstile" data-sitekey="0x4AAAAAAADnPIDROrmt1Wwj"></div>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.CLOUDFLARE_TURNSTILE

    def test_cloudflare_turnstile_script(self, detector):
        """Detect Cloudflare Turnstile by script URL."""
        html = '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.CLOUDFLARE_TURNSTILE

    # FunCaptcha Tests

    def test_funcaptcha_arkoselabs(self, detector):
        """Detect FunCaptcha/Arkose Labs."""
        html = '<script src="https://client-api.arkoselabs.com/v2/api.js"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.FUNCAPTCHA

    # GeeTest Tests

    def test_geetest(self, detector):
        """Detect GeeTest CAPTCHA."""
        html = '<script src="https://static.geetest.com/gt.js"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.GEETEST

    def test_geetest_init(self, detector):
        """Detect GeeTest by init call."""
        html = "initGeetest({gt: 'xxx', challenge: 'yyy'})"
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.GEETEST

    # AWS WAF Tests

    def test_aws_waf_captcha(self, detector):
        """Detect AWS WAF CAPTCHA."""
        html = '<script src="https://captcha.awswaf.com/api.js"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.AWS_WAF

    # PerimeterX Tests

    def test_perimeterx(self, detector):
        """Detect PerimeterX/HUMAN CAPTCHA."""
        html = '<script src="https://client.perimeterx.net/px.js"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.PERIMETERX

    # DataDome Tests

    def test_datadome(self, detector):
        """Detect DataDome CAPTCHA."""
        html = '<script src="https://js.datadome.co/tags.js"></script>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.DATADOME

    # Generic CAPTCHA Tests

    def test_generic_captcha_image(self, detector):
        """Detect generic CAPTCHA image."""
        html = '<img src="/captcha/generate" id="captcha-image" alt="captcha">'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.GENERIC

    def test_generic_captcha_class(self, detector):
        """Detect generic CAPTCHA by class."""
        html = '<div class="captcha-container"><input name="captcha" placeholder="Enter captcha"></div>'
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.GENERIC

    # Challenge Page Tests

    def test_challenge_page_detection(self, detector):
        """Detect challenge page patterns."""
        html = "<html><body><h1>Checking your browser before accessing...</h1></body></html>"
        is_challenge, confidence, details = detector.detect_challenge_page(html)
        assert is_challenge is True
        assert confidence > 0.5

    def test_challenge_page_just_a_moment(self, detector):
        """Detect 'Just a moment' challenge page."""
        html = "<html><body><p>Just a moment...</p><p>Please wait while we verify your browser.</p></body></html>"
        is_challenge, confidence, _ = detector.detect_challenge_page(html)
        assert is_challenge is True

    # Selectors Tests

    def test_get_selectors_recaptcha(self, detector):
        """Get selectors for reCAPTCHA."""
        selectors = detector._get_selectors(CaptchaProvider.RECAPTCHA_V2)
        assert ".g-recaptcha" in selectors
        assert "[data-sitekey]" in selectors

    def test_get_selectors_hcaptcha(self, detector):
        """Get selectors for hCaptcha."""
        selectors = detector._get_selectors(CaptchaProvider.HCAPTCHA)
        assert ".h-captcha" in selectors

    # All Elements Tests

    def test_get_all_captcha_elements(self, detector):
        """Find all CAPTCHA elements in HTML."""
        html = '''
        <div id="captcha-container">
            <div class="g-recaptcha" data-sitekey="xxx"></div>
            <img src="/captcha.png" class="captcha-image">
        </div>
        '''
        elements = detector.get_all_captcha_elements(html)
        assert len(elements) >= 1

    # Bypass Suggestions Tests

    def test_bypass_suggestions(self, detector):
        """Get bypass suggestions for detected CAPTCHA."""
        result = CaptchaDetectionResult(
            detected=True,
            provider=CaptchaProvider.CLOUDFLARE_TURNSTILE,
            confidence=0.95
        )
        suggestions = detector.get_bypass_suggestions(result)
        assert len(suggestions) > 0
        assert any("cloudflare" in s.lower() for s in suggestions)

    def test_bypass_suggestions_low_confidence(self, detector):
        """Get suggestions mention low confidence."""
        result = CaptchaDetectionResult(
            detected=True,
            provider=CaptchaProvider.GENERIC,
            confidence=0.5
        )
        suggestions = detector.get_bypass_suggestions(result)
        assert any("confidence" in s.lower() for s in suggestions)


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_detect_captcha_function(self):
        """detect_captcha convenience function works."""
        html = '<div class="g-recaptcha" data-sitekey="xxx"></div>'
        result = detect_captcha(html)
        assert result.detected is True

    def test_is_captcha_present_function(self):
        """is_captcha_present convenience function works."""
        html_with_captcha = '<div class="g-recaptcha"></div>'
        html_without = '<div>Normal content</div>'

        assert is_captcha_present(html_with_captcha) is True
        assert is_captcha_present(html_without) is False

    def test_get_captcha_detector_singleton(self):
        """get_captcha_detector returns singleton."""
        detector1 = get_captcha_detector()
        detector2 = get_captcha_detector()
        assert detector1 is detector2


class TestRealWorldExamples:
    """Tests with realistic HTML snippets from common sites."""

    @pytest.fixture
    def detector(self):
        return CaptchaDetector()

    def test_google_login_recaptcha(self, detector):
        """Detect reCAPTCHA on Google-style login page."""
        html = '''
        <!DOCTYPE html>
        <html>
        <head><title>Sign in</title></head>
        <body>
            <form action="/login" method="POST">
                <input type="email" name="email">
                <input type="password" name="password">
                <div class="g-recaptcha"
                     data-sitekey="6LcW6AUUAAAAAE_P_bIwMPTaGqvqYLk9TFHRKvCK"
                     data-callback="onCaptchaSuccess">
                </div>
                <button type="submit">Sign in</button>
            </form>
            <script src="https://www.google.com/recaptcha/api.js" async defer></script>
        </body>
        </html>
        '''
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.RECAPTCHA_V2
        assert result.sitekey == "6LcW6AUUAAAAAE_P_bIwMPTaGqvqYLk9TFHRKvCK"

    def test_cloudflare_challenge_page(self, detector):
        """Detect Cloudflare challenge page."""
        html = '''
        <!DOCTYPE html>
        <html>
        <head><title>Just a moment...</title></head>
        <body>
            <div id="cf-wrapper">
                <div id="cf-content">
                    <h2>Checking your browser before accessing example.com</h2>
                    <div class="cf-turnstile"
                         data-sitekey="0x4AAAAAAADnPIDROrmt1Wwj"
                         data-callback="onTurnstileSuccess">
                    </div>
                </div>
            </div>
            <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
        </body>
        </html>
        '''
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.CLOUDFLARE_TURNSTILE

        # Also check challenge page detection
        is_challenge, _, _ = detector.detect_challenge_page(html)
        assert is_challenge is True

    def test_hcaptcha_contact_form(self, detector):
        """Detect hCaptcha on contact form."""
        html = '''
        <form id="contact-form">
            <input type="text" name="name" placeholder="Your name">
            <input type="email" name="email" placeholder="Your email">
            <textarea name="message"></textarea>
            <div class="h-captcha"
                 data-sitekey="10000000-ffff-ffff-ffff-000000000001"
                 data-theme="light">
            </div>
            <button type="submit">Send Message</button>
        </form>
        <script src="https://js.hcaptcha.com/1/api.js" async defer></script>
        '''
        result = detector.detect(html)
        assert result.detected is True
        assert result.provider == CaptchaProvider.HCAPTCHA
        assert result.sitekey == "10000000-ffff-ffff-ffff-000000000001"
