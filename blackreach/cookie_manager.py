"""
Cookie Persistence Manager (v1.0.0)

Manages browser cookies across sessions:
- Save and load cookies to/from disk
- Cookie encryption for security
- Domain-based cookie filtering
- Cookie expiration handling
- Support for multiple profiles
- Import/export in various formats (Netscape, JSON)
"""

import json
import logging
import os
import time
import base64
import hashlib
import secrets
from pathlib import Path

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Union, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass
class Cookie:
    """Represents a browser cookie."""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: Optional[float] = None  # Unix timestamp
    http_only: bool = False
    secure: bool = False
    same_site: str = "Lax"  # Strict, Lax, or None

    def is_expired(self) -> bool:
        """Check if cookie has expired."""
        if self.expires is None:
            return False  # Session cookie
        return time.time() > self.expires

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "path": self.path,
            "expires": self.expires,
            "httpOnly": self.http_only,
            "secure": self.secure,
            "sameSite": self.same_site,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Cookie":
        """Create Cookie from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            domain=data["domain"],
            path=data.get("path", "/"),
            expires=data.get("expires"),
            http_only=data.get("httpOnly", False),
            secure=data.get("secure", False),
            same_site=data.get("sameSite", "Lax"),
        )

    def to_playwright_cookie(self) -> Dict[str, Any]:
        """Convert to Playwright cookie format."""
        cookie = {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "path": self.path,
            "httpOnly": self.http_only,
            "secure": self.secure,
            "sameSite": self.same_site,
        }
        if self.expires:
            cookie["expires"] = self.expires
        return cookie

    @classmethod
    def from_playwright_cookie(cls, data: Dict[str, Any]) -> "Cookie":
        """Create Cookie from Playwright cookie format."""
        return cls(
            name=data["name"],
            value=data["value"],
            domain=data["domain"],
            path=data.get("path", "/"),
            expires=data.get("expires"),
            http_only=data.get("httpOnly", False),
            secure=data.get("secure", False),
            same_site=data.get("sameSite", "Lax"),
        )


@dataclass
class CookieProfile:
    """A named collection of cookies."""
    name: str
    cookies: List[Cookie] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_cookie(self, cookie: Cookie):
        """Add or update a cookie."""
        # Remove existing cookie with same name and domain
        self.cookies = [
            c for c in self.cookies
            if not (c.name == cookie.name and c.domain == cookie.domain)
        ]
        self.cookies.append(cookie)
        self.updated_at = time.time()

    def get_cookie(self, name: str, domain: str) -> Optional[Cookie]:
        """Get a specific cookie."""
        for cookie in self.cookies:
            if cookie.name == name and cookie.domain == domain:
                return cookie
        return None

    def get_cookies_for_domain(self, domain: str) -> List[Cookie]:
        """Get all cookies that match a domain."""
        matching = []
        for cookie in self.cookies:
            # Match exact domain or parent domain
            # Cookie domain ".example.com" matches "example.com" and "www.example.com"
            cookie_domain = cookie.domain.lstrip(".")
            if domain == cookie_domain or domain.endswith("." + cookie_domain):
                if not cookie.is_expired():
                    matching.append(cookie)
        return matching

    def remove_expired(self) -> int:
        """Remove expired cookies. Returns count removed."""
        original_count = len(self.cookies)
        self.cookies = [c for c in self.cookies if not c.is_expired()]
        removed = original_count - len(self.cookies)
        if removed > 0:
            self.updated_at = time.time()
        return removed

    def clear_domain(self, domain: str) -> int:
        """Clear all cookies for a domain. Returns count removed."""
        original_count = len(self.cookies)

        def matches_domain(cookie_domain: str) -> bool:
            """Check if cookie domain matches the requested domain."""
            cookie_domain = cookie_domain.lstrip(".")
            return domain == cookie_domain or domain.endswith("." + cookie_domain)

        self.cookies = [c for c in self.cookies if not matches_domain(c.domain)]
        removed = original_count - len(self.cookies)
        if removed > 0:
            self.updated_at = time.time()
        return removed


class CookieEncryption:
    """Handles cookie encryption/decryption."""

    def __init__(self, password: Optional[str] = None, salt: Optional[bytes] = None):
        """Initialize encryption with optional password.

        If no password is provided, generates a machine-specific key.

        Args:
            password: User password for encryption (if None, uses machine ID)
            salt: Salt bytes for password-based encryption (if None, generates new salt)
        """
        self._salt: Optional[bytes] = None
        self._password: Optional[str] = password
        if password:
            self._fernet, self._salt = self._create_fernet_from_password(password, salt)
        else:
            self._fernet = self._create_fernet_from_machine_id()

    def _create_fernet_from_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[Fernet, bytes]:
        """Create Fernet cipher from password with random salt.

        Args:
            password: User password for encryption
            salt: Optional salt bytes (if None, generates new random salt)

        Returns:
            Tuple of (Fernet cipher, salt bytes used)
        """
        # Generate random salt if not provided (16 bytes = 128 bits)
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key), salt

    def _create_fernet_from_machine_id(self) -> Fernet:
        """Create Fernet cipher from machine-specific identifier.

        P0-SEC: Uses a random salt stored in a separate file for better security.
        The salt file is created once per machine and reused for consistency.
        """
        # Use combination of machine identifiers
        machine_id_parts = []

        # Try to get machine ID from various sources
        try:
            # Linux machine-id
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    machine_id_parts.append(f.read().strip())
        except OSError as e:
            logger.debug("Failed to read /etc/machine-id: %s", e)

        try:
            # Windows machine GUID
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography"
            )
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            machine_id_parts.append(machine_guid)
        except (ImportError, OSError) as e:
            logger.debug("Failed to read Windows MachineGuid: %s", e)

        # Fallback to hostname + user
        if not machine_id_parts:
            import socket
            import getpass
            machine_id_parts.append(socket.gethostname())
            machine_id_parts.append(getpass.getuser())

        machine_id = ":".join(machine_id_parts)

        # P0-SEC: Use per-installation random salt instead of fixed salt
        # Salt is stored in a file so it persists across restarts
        salt_file = Path.home() / ".blackreach" / ".cookie_salt"
        try:
            salt_file.parent.mkdir(parents=True, exist_ok=True)
            if salt_file.exists():
                salt = salt_file.read_bytes()
                if len(salt) != 16:
                    # Invalid salt file, regenerate
                    salt = os.urandom(16)
                    salt_file.write_bytes(salt)
                    os.chmod(salt_file, 0o600)
            else:
                # Generate new random salt
                salt = os.urandom(16)
                salt_file.write_bytes(salt)
                os.chmod(salt_file, 0o600)
        except OSError as e:
            # Fallback to fixed salt if file operations fail
            logger.debug("Failed to read/write cookie salt file, using fallback salt: %s", e)
            salt = b"blackreach_machine_salt_v1"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
        return Fernet(key)

    @property
    def salt(self) -> Optional[bytes]:
        """Get the salt used for password-based encryption."""
        return self._salt

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data.

        For password-based encryption, prepends the salt to encrypted data.
        """
        encrypted = self._fernet.encrypt(data)
        if self._salt:
            # Prepend salt (16 bytes) to encrypted data for later decryption
            return self._salt + encrypted
        return encrypted

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data.

        For password-based encryption, extracts salt from data first
        and recreates the cipher with the correct salt.
        """
        if self._salt is not None:
            # Password-based encryption: salt is prepended to data
            if len(data) <= 16:
                raise ValueError("Data too short - missing salt")
            stored_salt = data[:16]
            encrypted = data[16:]
            # If the stored salt differs from our salt, recreate the cipher
            if stored_salt != self._salt:
                self._fernet, self._salt = self._create_fernet_from_password(
                    self._password, stored_salt
                )
            return self._fernet.decrypt(encrypted)
        return self._fernet.decrypt(data)

    @classmethod
    def decrypt_with_password(cls, data: bytes, password: str) -> bytes:
        """Decrypt data using password, extracting salt from data.

        Args:
            data: Encrypted data with prepended salt
            password: Password used for encryption

        Returns:
            Decrypted bytes
        """
        if len(data) < 16:
            raise ValueError("Data too short - missing salt")
        salt = data[:16]
        encrypted = data[16:]
        instance = cls(password=password, salt=salt)
        return instance._fernet.decrypt(encrypted)


class CookieManager:
    """
    Manages cookie persistence across browser sessions.

    Features:
    - Multiple named profiles
    - Encrypted storage
    - Automatic expiration handling
    - Domain filtering
    - Import/export in various formats
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        password: Optional[str] = None,
        encrypt: bool = True
    ):
        """
        Initialize CookieManager.

        Args:
            storage_dir: Directory to store cookies (default: ~/.blackreach/cookies)
            password: Password for encryption (uses machine-specific key if None)
            encrypt: Whether to encrypt stored cookies
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".blackreach" / "cookies"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.encrypt = encrypt
        if encrypt:
            self._encryption = CookieEncryption(password)
        else:
            self._encryption = None

        self._profiles: Dict[str, CookieProfile] = {}
        self._default_profile = "default"

    def _get_profile_path(self, name: str) -> Path:
        """Get file path for a profile."""
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
        suffix = ".enc" if self.encrypt else ".json"
        return self.storage_dir / f"cookies_{safe_name}{suffix}"

    def create_profile(self, name: str, metadata: Optional[Dict] = None) -> CookieProfile:
        """Create a new cookie profile."""
        profile = CookieProfile(
            name=name,
            metadata=metadata or {}
        )
        self._profiles[name] = profile
        return profile

    def get_profile(self, name: str = None) -> CookieProfile:
        """Get a profile by name, creating if it doesn't exist."""
        name = name or self._default_profile
        if name not in self._profiles:
            # Try to load from disk
            self.load_profile(name)

        if name not in self._profiles:
            self._profiles[name] = self.create_profile(name)

        return self._profiles[name]

    def save_profile(self, name: str = None):
        """Save a profile to disk."""
        name = name or self._default_profile
        profile = self._profiles.get(name)
        if not profile:
            return

        # Convert to JSON
        data = {
            "name": profile.name,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "metadata": profile.metadata,
            "cookies": [c.to_dict() for c in profile.cookies]
        }
        json_data = json.dumps(data, indent=2).encode()

        # Encrypt if enabled
        if self.encrypt and self._encryption:
            json_data = self._encryption.encrypt(json_data)

        # Write to file
        path = self._get_profile_path(name)
        with open(path, "wb") as f:
            f.write(json_data)

    def load_profile(self, name: str = None) -> Optional[CookieProfile]:
        """Load a profile from disk."""
        name = name or self._default_profile
        path = self._get_profile_path(name)

        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                data = f.read()

            # Decrypt if needed
            if self.encrypt and self._encryption:
                data = self._encryption.decrypt(data)

            parsed = json.loads(data.decode())

            profile = CookieProfile(
                name=parsed["name"],
                created_at=parsed.get("created_at", time.time()),
                updated_at=parsed.get("updated_at", time.time()),
                metadata=parsed.get("metadata", {})
            )

            for cookie_data in parsed.get("cookies", []):
                cookie = Cookie.from_dict(cookie_data)
                if not cookie.is_expired():
                    profile.cookies.append(cookie)

            self._profiles[name] = profile
            return profile

        except Exception as e:
            # Broad catch: profile loading can fail from I/O, decryption, or corrupt JSON
            logger.debug("Failed to load cookie profile '%s': %s", name, e)
            return None

    def delete_profile(self, name: str):
        """Delete a profile from memory and disk."""
        if name in self._profiles:
            del self._profiles[name]

        path = self._get_profile_path(name)
        if path.exists():
            path.unlink()

    def list_profiles(self) -> List[str]:
        """List all available profiles."""
        profiles = set(self._profiles.keys())

        # Also check disk
        for path in self.storage_dir.glob("cookies_*"):
            name = path.stem.replace("cookies_", "")
            profiles.add(name)

        return sorted(profiles)

    # Browser integration methods

    def save_from_context(self, context, profile_name: str = None):
        """
        Save cookies from a Playwright BrowserContext.

        Args:
            context: Playwright BrowserContext
            profile_name: Profile to save to
        """
        profile = self.get_profile(profile_name)
        cookies = context.cookies()

        for cookie_data in cookies:
            cookie = Cookie.from_playwright_cookie(cookie_data)
            profile.add_cookie(cookie)

        self.save_profile(profile_name)

    def load_to_context(self, context, profile_name: str = None, domains: Optional[List[str]] = None):
        """
        Load cookies into a Playwright BrowserContext.

        Args:
            context: Playwright BrowserContext
            profile_name: Profile to load from
            domains: Optional list of domains to filter cookies
        """
        profile = self.get_profile(profile_name)
        profile.remove_expired()

        cookies_to_add = []
        for cookie in profile.cookies:
            # Filter by domain if specified
            if domains:
                if not any(
                    domain == cookie.domain or domain.endswith("." + cookie.domain.lstrip("."))
                    for domain in domains
                ):
                    continue

            cookies_to_add.append(cookie.to_playwright_cookie())

        if cookies_to_add:
            context.add_cookies(cookies_to_add)

    def add_cookie(
        self,
        name: str,
        value: str,
        domain: str,
        profile_name: str = None,
        **kwargs
    ):
        """Add a cookie directly."""
        profile = self.get_profile(profile_name)
        cookie = Cookie(name=name, value=value, domain=domain, **kwargs)
        profile.add_cookie(cookie)

    def get_cookies(self, domain: str = None, profile_name: str = None) -> List[Cookie]:
        """Get cookies, optionally filtered by domain."""
        profile = self.get_profile(profile_name)
        profile.remove_expired()

        if domain:
            return profile.get_cookies_for_domain(domain)
        return profile.cookies.copy()

    def clear_cookies(self, domain: str = None, profile_name: str = None):
        """Clear cookies, optionally for a specific domain."""
        profile = self.get_profile(profile_name)
        if domain:
            profile.clear_domain(domain)
        else:
            profile.cookies.clear()
            profile.updated_at = time.time()
        self.save_profile(profile_name)

    # Import/Export methods

    def export_netscape(self, profile_name: str = None) -> str:
        """Export cookies in Netscape format (for curl, wget, etc.)."""
        profile = self.get_profile(profile_name)
        lines = ["# Netscape HTTP Cookie File"]
        lines.append("# https://curl.se/docs/http-cookies.html")
        lines.append("")

        for cookie in profile.cookies:
            if cookie.is_expired():
                continue

            # Format: domain, include_subdomains, path, secure, expiry, name, value
            include_subdomains = "TRUE" if cookie.domain.startswith(".") else "FALSE"
            secure = "TRUE" if cookie.secure else "FALSE"
            expiry = str(int(cookie.expires)) if cookie.expires else "0"

            line = "\t".join([
                cookie.domain,
                include_subdomains,
                cookie.path,
                secure,
                expiry,
                cookie.name,
                cookie.value
            ])
            lines.append(line)

        return "\n".join(lines)

    def import_netscape(self, content: str, profile_name: str = None):
        """Import cookies from Netscape format."""
        profile = self.get_profile(profile_name)

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) < 7:
                continue

            domain, _, path, secure, expiry, name, value = parts[:7]

            cookie = Cookie(
                name=name,
                value=value,
                domain=domain,
                path=path,
                secure=(secure.upper() == "TRUE"),
                expires=float(expiry) if expiry != "0" else None
            )
            profile.add_cookie(cookie)

        self.save_profile(profile_name)

    def export_json(self, profile_name: str = None) -> str:
        """Export cookies as JSON."""
        profile = self.get_profile(profile_name)
        cookies = [c.to_dict() for c in profile.cookies if not c.is_expired()]
        return json.dumps(cookies, indent=2)

    def import_json(self, content: str, profile_name: str = None):
        """Import cookies from JSON."""
        profile = self.get_profile(profile_name)
        cookies = json.loads(content)

        for cookie_data in cookies:
            cookie = Cookie.from_dict(cookie_data)
            if not cookie.is_expired():
                profile.add_cookie(cookie)

        self.save_profile(profile_name)


# Singleton instance
_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager(
    storage_dir: Optional[Path] = None,
    password: Optional[str] = None,
    encrypt: bool = True
) -> CookieManager:
    """Get or create the global CookieManager instance."""
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager(
            storage_dir=storage_dir,
            password=password,
            encrypt=encrypt
        )
    return _cookie_manager


def reset_cookie_manager():
    """Reset the global CookieManager instance."""
    global _cookie_manager
    _cookie_manager = None
