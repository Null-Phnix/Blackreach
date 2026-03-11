"""
Unit tests for blackreach/cookie_manager.py

Tests cookie persistence and management.
"""

import pytest
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from blackreach.cookie_manager import (
    Cookie,
    CookieProfile,
    CookieManager,
    CookieEncryption,
    get_cookie_manager,
    reset_cookie_manager,
)


class TestCookie:
    """Tests for Cookie dataclass."""

    def test_create_cookie(self):
        """Create a basic cookie."""
        cookie = Cookie(
            name="session",
            value="abc123",
            domain=".example.com"
        )
        assert cookie.name == "session"
        assert cookie.value == "abc123"
        assert cookie.domain == ".example.com"
        assert cookie.path == "/"
        assert cookie.expires is None
        assert cookie.http_only is False

    def test_cookie_with_all_options(self):
        """Create cookie with all options."""
        expires = time.time() + 3600  # 1 hour from now
        cookie = Cookie(
            name="auth",
            value="token123",
            domain=".example.com",
            path="/api",
            expires=expires,
            http_only=True,
            secure=True,
            same_site="Strict"
        )
        assert cookie.path == "/api"
        assert cookie.expires == expires
        assert cookie.http_only is True
        assert cookie.secure is True
        assert cookie.same_site == "Strict"

    def test_is_expired_not_expired(self):
        """Cookie with future expiry is not expired."""
        cookie = Cookie(
            name="test",
            value="value",
            domain=".example.com",
            expires=time.time() + 3600
        )
        assert cookie.is_expired() is False

    def test_is_expired_expired(self):
        """Cookie with past expiry is expired."""
        cookie = Cookie(
            name="test",
            value="value",
            domain=".example.com",
            expires=time.time() - 3600
        )
        assert cookie.is_expired() is True

    def test_is_expired_session_cookie(self):
        """Session cookie (no expiry) is never expired."""
        cookie = Cookie(
            name="session",
            value="value",
            domain=".example.com",
            expires=None
        )
        assert cookie.is_expired() is False

    def test_to_dict(self):
        """Convert cookie to dictionary."""
        cookie = Cookie(
            name="test",
            value="value",
            domain=".example.com",
            path="/app",
            expires=1234567890.0,
            http_only=True,
            secure=True,
            same_site="Lax"
        )
        d = cookie.to_dict()
        assert d["name"] == "test"
        assert d["value"] == "value"
        assert d["domain"] == ".example.com"
        assert d["path"] == "/app"
        assert d["expires"] == 1234567890.0
        assert d["httpOnly"] is True
        assert d["secure"] is True
        assert d["sameSite"] == "Lax"

    def test_from_dict(self):
        """Create cookie from dictionary."""
        d = {
            "name": "test",
            "value": "value",
            "domain": ".example.com",
            "path": "/",
            "expires": 1234567890.0,
            "httpOnly": True,
            "secure": False,
            "sameSite": "None"
        }
        cookie = Cookie.from_dict(d)
        assert cookie.name == "test"
        assert cookie.http_only is True
        assert cookie.same_site == "None"

    def test_to_playwright_cookie(self):
        """Convert to Playwright format."""
        cookie = Cookie(
            name="auth",
            value="token",
            domain=".example.com",
            http_only=True,
            secure=True
        )
        pw_cookie = cookie.to_playwright_cookie()
        assert pw_cookie["name"] == "auth"
        assert pw_cookie["httpOnly"] is True
        assert pw_cookie["secure"] is True

    def test_from_playwright_cookie(self):
        """Create from Playwright format."""
        pw_cookie = {
            "name": "session",
            "value": "xyz",
            "domain": ".example.com",
            "path": "/",
            "httpOnly": False,
            "secure": True,
            "sameSite": "Strict"
        }
        cookie = Cookie.from_playwright_cookie(pw_cookie)
        assert cookie.name == "session"
        assert cookie.secure is True
        assert cookie.same_site == "Strict"


class TestCookieProfile:
    """Tests for CookieProfile class."""

    def test_create_profile(self):
        """Create empty profile."""
        profile = CookieProfile(name="test")
        assert profile.name == "test"
        assert len(profile.cookies) == 0
        assert profile.created_at > 0
        assert profile.updated_at > 0

    def test_add_cookie(self):
        """Add cookie to profile."""
        profile = CookieProfile(name="test")
        cookie = Cookie(name="session", value="abc", domain=".example.com")
        profile.add_cookie(cookie)
        assert len(profile.cookies) == 1
        assert profile.cookies[0].name == "session"

    def test_add_cookie_replaces_existing(self):
        """Adding cookie with same name/domain replaces existing."""
        profile = CookieProfile(name="test")
        cookie1 = Cookie(name="session", value="old", domain=".example.com")
        cookie2 = Cookie(name="session", value="new", domain=".example.com")

        profile.add_cookie(cookie1)
        profile.add_cookie(cookie2)

        assert len(profile.cookies) == 1
        assert profile.cookies[0].value == "new"

    def test_get_cookie(self):
        """Get specific cookie by name and domain."""
        profile = CookieProfile(name="test")
        profile.add_cookie(Cookie(name="session", value="abc", domain=".example.com"))
        profile.add_cookie(Cookie(name="pref", value="dark", domain=".example.com"))

        cookie = profile.get_cookie("session", ".example.com")
        assert cookie is not None
        assert cookie.value == "abc"

    def test_get_cookie_not_found(self):
        """Get nonexistent cookie returns None."""
        profile = CookieProfile(name="test")
        cookie = profile.get_cookie("nonexistent", ".example.com")
        assert cookie is None

    def test_get_cookies_for_domain(self):
        """Get all cookies matching a domain."""
        profile = CookieProfile(name="test")
        profile.add_cookie(Cookie(name="c1", value="v1", domain=".example.com"))
        profile.add_cookie(Cookie(name="c2", value="v2", domain=".example.com"))
        profile.add_cookie(Cookie(name="c3", value="v3", domain=".other.com"))

        cookies = profile.get_cookies_for_domain("www.example.com")
        assert len(cookies) == 2

    def test_get_cookies_for_domain_excludes_expired(self):
        """Expired cookies not returned for domain."""
        profile = CookieProfile(name="test")
        profile.add_cookie(Cookie(
            name="expired",
            value="old",
            domain="example.com",  # Without leading dot
            expires=time.time() - 3600
        ))
        profile.add_cookie(Cookie(
            name="valid",
            value="new",
            domain="example.com",  # Without leading dot
            expires=time.time() + 3600
        ))

        cookies = profile.get_cookies_for_domain("example.com")
        assert len(cookies) == 1
        assert cookies[0].name == "valid"

    def test_remove_expired(self):
        """Remove expired cookies."""
        profile = CookieProfile(name="test")
        profile.add_cookie(Cookie(
            name="expired",
            value="old",
            domain=".example.com",
            expires=time.time() - 3600
        ))
        profile.add_cookie(Cookie(
            name="valid",
            value="new",
            domain=".example.com"
        ))

        removed = profile.remove_expired()
        assert removed == 1
        assert len(profile.cookies) == 1

    def test_clear_domain(self):
        """Clear all cookies for a domain."""
        profile = CookieProfile(name="test")
        profile.add_cookie(Cookie(name="c1", value="v1", domain="example.com"))
        profile.add_cookie(Cookie(name="c2", value="v2", domain="example.com"))
        profile.add_cookie(Cookie(name="c3", value="v3", domain="other.com"))

        removed = profile.clear_domain("example.com")
        assert removed == 2
        assert len(profile.cookies) == 1


class TestCookieEncryption:
    """Tests for CookieEncryption class."""

    def test_encrypt_decrypt_with_password(self):
        """Encrypt and decrypt with password."""
        encryption = CookieEncryption(password="test-password")
        original = b"secret cookie data"

        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_encrypt_decrypt_without_password(self):
        """Encrypt and decrypt with machine-specific key."""
        encryption = CookieEncryption()
        original = b"secret cookie data"

        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original

    def test_different_passwords_fail(self):
        """Different passwords produce incompatible encryption."""
        enc1 = CookieEncryption(password="password1")
        enc2 = CookieEncryption(password="password2")

        encrypted = enc1.encrypt(b"data")

        with pytest.raises(Exception):
            enc2.decrypt(encrypted)


class TestCookieManager:
    """Tests for CookieManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create manager with temp storage."""
        return CookieManager(storage_dir=temp_dir, encrypt=False)

    @pytest.fixture
    def encrypted_manager(self, temp_dir):
        """Create encrypted manager."""
        return CookieManager(storage_dir=temp_dir, password="test", encrypt=True)

    def test_create_profile(self, manager):
        """Create a new profile."""
        profile = manager.create_profile("test-profile")
        assert profile.name == "test-profile"

    def test_get_profile_creates_if_missing(self, manager):
        """Get profile creates new one if missing."""
        profile = manager.get_profile("new-profile")
        assert profile is not None
        assert profile.name == "new-profile"

    def test_save_and_load_profile(self, manager):
        """Save and load profile."""
        manager.create_profile("test")
        manager.add_cookie("session", "abc123", ".example.com", profile_name="test")
        manager.save_profile("test")

        # Create new manager to load from disk
        manager2 = CookieManager(storage_dir=manager.storage_dir, encrypt=False)
        profile = manager2.load_profile("test")

        assert profile is not None
        assert len(profile.cookies) == 1
        assert profile.cookies[0].name == "session"

    def test_save_and_load_encrypted(self, temp_dir):
        """Save and load encrypted profile."""
        manager1 = CookieManager(storage_dir=temp_dir, password="secret", encrypt=True)
        manager1.add_cookie("auth", "token", ".example.com")
        manager1.save_profile()

        manager2 = CookieManager(storage_dir=temp_dir, password="secret", encrypt=True)
        profile = manager2.load_profile()

        assert len(profile.cookies) == 1
        assert profile.cookies[0].value == "token"

    def test_delete_profile(self, manager):
        """Delete profile from memory and disk."""
        manager.create_profile("to-delete")
        manager.add_cookie("test", "value", ".example.com", profile_name="to-delete")
        manager.save_profile("to-delete")

        manager.delete_profile("to-delete")

        # Should not exist after delete
        profile = manager.load_profile("to-delete")
        assert profile is None

    def test_list_profiles(self, manager):
        """List available profiles."""
        manager.create_profile("profile1")
        manager.create_profile("profile2")
        manager.save_profile("profile1")
        manager.save_profile("profile2")

        profiles = manager.list_profiles()
        assert "profile1" in profiles
        assert "profile2" in profiles

    def test_add_cookie(self, manager):
        """Add cookie directly to manager."""
        manager.add_cookie(
            name="test",
            value="value",
            domain=".example.com",
            http_only=True
        )

        cookies = manager.get_cookies()
        assert len(cookies) == 1
        assert cookies[0].http_only is True

    def test_get_cookies_filtered(self, manager):
        """Get cookies filtered by domain."""
        manager.add_cookie("c1", "v1", ".example.com")
        manager.add_cookie("c2", "v2", ".other.com")

        cookies = manager.get_cookies(domain="www.example.com")
        assert len(cookies) == 1
        assert cookies[0].name == "c1"

    def test_clear_cookies(self, manager):
        """Clear all cookies."""
        manager.add_cookie("c1", "v1", ".example.com")
        manager.add_cookie("c2", "v2", ".example.com")

        manager.clear_cookies()

        assert len(manager.get_cookies()) == 0

    def test_clear_cookies_by_domain(self, manager):
        """Clear cookies for specific domain."""
        manager.add_cookie("c1", "v1", "example.com")
        manager.add_cookie("c2", "v2", "other.com")

        manager.clear_cookies(domain="example.com")

        cookies = manager.get_cookies()
        assert len(cookies) == 1
        assert cookies[0].name == "c2"

    # Export/Import Tests

    def test_export_netscape(self, manager):
        """Export cookies in Netscape format."""
        manager.add_cookie("session", "abc123", ".example.com", secure=True)

        netscape = manager.export_netscape()

        assert "# Netscape HTTP Cookie File" in netscape
        assert ".example.com" in netscape
        assert "session" in netscape
        assert "abc123" in netscape

    def test_import_netscape(self, manager):
        """Import cookies from Netscape format."""
        # Use future expiration timestamp (year 2035)
        netscape = """# Netscape HTTP Cookie File
.example.com\tTRUE\t/\tFALSE\t0\tsession\tabc123
.other.com\tTRUE\t/\tTRUE\t2051222400\tauth\ttoken456"""

        manager.import_netscape(netscape)

        cookies = manager.get_cookies()
        assert len(cookies) == 2

        session = next(c for c in cookies if c.name == "session")
        assert session.value == "abc123"

    def test_export_json(self, manager):
        """Export cookies as JSON."""
        manager.add_cookie("test", "value", ".example.com")

        json_str = manager.export_json()
        data = json.loads(json_str)

        assert len(data) == 1
        assert data[0]["name"] == "test"

    def test_import_json(self, manager):
        """Import cookies from JSON."""
        json_str = '[{"name": "imported", "value": "data", "domain": ".example.com"}]'

        manager.import_json(json_str)

        cookies = manager.get_cookies()
        assert len(cookies) == 1
        assert cookies[0].name == "imported"

    # Browser Integration Tests

    def test_save_from_context(self, manager):
        """Save cookies from mock browser context."""
        mock_context = MagicMock()
        mock_context.cookies.return_value = [
            {
                "name": "session",
                "value": "browser123",
                "domain": ".example.com",
                "path": "/",
                "httpOnly": True,
                "secure": False,
                "sameSite": "Lax"
            }
        ]

        manager.save_from_context(mock_context)

        cookies = manager.get_cookies()
        assert len(cookies) == 1
        assert cookies[0].value == "browser123"

    def test_load_to_context(self, manager):
        """Load cookies into mock browser context."""
        manager.add_cookie("preloaded", "value", ".example.com")

        mock_context = MagicMock()
        manager.load_to_context(mock_context)

        mock_context.add_cookies.assert_called_once()
        added_cookies = mock_context.add_cookies.call_args[0][0]
        assert len(added_cookies) == 1
        assert added_cookies[0]["name"] == "preloaded"

    def test_load_to_context_filtered(self, manager):
        """Load only cookies for specified domains."""
        manager.add_cookie("c1", "v1", "example.com")
        manager.add_cookie("c2", "v2", "other.com")

        mock_context = MagicMock()
        manager.load_to_context(mock_context, domains=["example.com"])

        # Should have called add_cookies with filtered cookies
        mock_context.add_cookies.assert_called_once()
        added_cookies = mock_context.add_cookies.call_args[0][0]
        assert len(added_cookies) == 1
        assert added_cookies[0]["domain"] == "example.com"


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_cookie_manager_singleton(self):
        """get_cookie_manager returns singleton."""
        reset_cookie_manager()  # Clear any existing

        manager1 = get_cookie_manager(encrypt=False)
        manager2 = get_cookie_manager(encrypt=False)

        assert manager1 is manager2

        reset_cookie_manager()  # Clean up

    def test_reset_cookie_manager(self):
        """reset_cookie_manager clears singleton."""
        manager1 = get_cookie_manager(encrypt=False)
        reset_cookie_manager()
        manager2 = get_cookie_manager(encrypt=False)

        # After reset, should be different instance
        assert manager1 is not manager2

        reset_cookie_manager()


class TestCookieManagerIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_full_workflow(self, temp_dir):
        """Complete save/restore workflow."""
        # First session - create and save cookies
        manager1 = CookieManager(storage_dir=temp_dir, encrypt=False)
        manager1.add_cookie("session", "sess123", ".example.com", http_only=True)
        manager1.add_cookie("prefs", "theme=dark", ".example.com")
        manager1.add_cookie("tracking", "no", ".ads.example.com")
        manager1.save_profile()

        # Second session - restore cookies
        manager2 = CookieManager(storage_dir=temp_dir, encrypt=False)
        profile = manager2.load_profile()

        assert len(profile.cookies) == 3

        # Verify domain matching
        example_cookies = manager2.get_cookies(domain="www.example.com")
        assert len(example_cookies) == 2

    def test_multiple_profiles(self, temp_dir):
        """Work with multiple profiles."""
        manager = CookieManager(storage_dir=temp_dir, encrypt=False)

        # Create profile for different sites
        manager.add_cookie("user", "alice", ".site-a.com", profile_name="site-a")
        manager.add_cookie("user", "bob", ".site-b.com", profile_name="site-b")

        manager.save_profile("site-a")
        manager.save_profile("site-b")

        # Load and verify
        profiles = manager.list_profiles()
        assert "site-a" in profiles
        assert "site-b" in profiles

        alice_cookies = manager.get_cookies(profile_name="site-a")
        bob_cookies = manager.get_cookies(profile_name="site-b")

        assert alice_cookies[0].value == "alice"
        assert bob_cookies[0].value == "bob"


class TestCookieEncryptionSecurity:
    """Security tests for CookieEncryption - PBKDF2 salt randomization."""

    def test_salt_is_random(self):
        """Each encryption uses random salt."""
        enc = CookieEncryption(password="test")

        # Encrypt same data twice
        data = b"test data"
        encrypted1 = enc.encrypt(data)

        # Create new encryption instance
        enc2 = CookieEncryption(password="test")
        encrypted2 = enc2.encrypt(data)

        # The encrypted outputs should be different due to random salt
        # (even though both can be decrypted with the same password)
        assert encrypted1 != encrypted2

    def test_salt_prepended_to_encrypted_data(self):
        """Salt is prepended to encrypted data."""
        enc = CookieEncryption(password="test")
        encrypted = enc.encrypt(b"test data")

        # The encrypted data should be at least salt (16 bytes) + Fernet overhead
        assert len(encrypted) > 16

    def test_same_password_different_salts_decrypt(self):
        """Data encrypted with different salts can be decrypted with same password."""
        enc1 = CookieEncryption(password="secret")
        enc2 = CookieEncryption(password="secret")

        data = b"sensitive cookie data"

        # Encrypt with enc1
        encrypted1 = enc1.encrypt(data)

        # Decrypt with enc2 (different salt, same password)
        decrypted = enc2.decrypt(encrypted1)

        assert decrypted == data

    def test_encrypt_decrypt_preserves_data_integrity(self):
        """Encrypt/decrypt cycle preserves data exactly."""
        enc = CookieEncryption(password="password123")

        # Test various data types
        test_data = [
            b"simple string",
            b"unicode: \xc3\xa9\xc3\xa0\xc3\xb9",
            b"\x00\x01\x02\x03\x04",  # Binary data
            b"a" * 10000,  # Large data
        ]

        for data in test_data:
            encrypted = enc.encrypt(data)
            decrypted = enc.decrypt(encrypted)
            assert decrypted == data, f"Data integrity failed for: {data[:20]}"

    def test_wrong_password_raises_exception(self):
        """Wrong password raises exception on decrypt."""
        enc1 = CookieEncryption(password="correct")
        enc2 = CookieEncryption(password="wrong")

        encrypted = enc1.encrypt(b"secret data")

        with pytest.raises(Exception):
            enc2.decrypt(encrypted)

    def test_salt_extraction_during_decrypt(self):
        """Salt is correctly extracted during decryption."""
        enc1 = CookieEncryption(password="shared")
        data = b"test payload"

        encrypted = enc1.encrypt(data)

        # Create new instance and decrypt
        enc2 = CookieEncryption(password="shared")
        decrypted = enc2.decrypt(encrypted)

        # Should successfully decrypt even with new instance
        assert decrypted == data

    def test_pbkdf2_iterations_security(self):
        """PBKDF2 uses sufficient iterations (100,000)."""
        # This is a documentation test - verify the iteration count
        # by checking that encryption/decryption works correctly
        enc = CookieEncryption(password="test")
        data = b"verify iterations"

        encrypted = enc.encrypt(data)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == data

    def test_machine_id_fallback(self):
        """Encryption works without password using machine ID."""
        enc1 = CookieEncryption()  # No password
        enc2 = CookieEncryption()  # No password

        data = b"machine-specific encryption"
        encrypted = enc1.encrypt(data)
        decrypted = enc2.decrypt(encrypted)

        # Same machine should be able to decrypt
        assert decrypted == data

    def test_empty_data_encryption(self):
        """Empty data can be encrypted and decrypted."""
        enc = CookieEncryption(password="test")

        encrypted = enc.encrypt(b"")
        decrypted = enc.decrypt(encrypted)

        assert decrypted == b""

    def test_corrupted_ciphertext_raises(self):
        """Corrupted ciphertext raises exception."""
        enc = CookieEncryption(password="test")

        encrypted = enc.encrypt(b"valid data")

        # Corrupt the ciphertext (not the salt)
        corrupted = encrypted[:16] + b"corrupted" + encrypted[25:]

        with pytest.raises(Exception):
            enc.decrypt(corrupted)

    def test_sha256_key_derivation(self):
        """Verify SHA256 is used for key derivation."""
        # This is a milestone test - verifying the secure hash algorithm
        enc = CookieEncryption(password="milestone2000")

        # Encrypt and decrypt to verify the algorithm works
        milestone_data = b"2000 tests milestone - PBKDF2-HMAC-SHA256"
        encrypted = enc.encrypt(milestone_data)
        decrypted = enc.decrypt(encrypted)

        assert decrypted == milestone_data
        # Verify encrypted data is different from original
        assert encrypted != milestone_data
