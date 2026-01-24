"""
Content Verification System (v2.4.0)

Validates downloaded content to ensure it matches expectations:
- File format verification
- Content integrity checks
- Corruption detection
- Placeholder/dummy file detection
- File quality assessment
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, BinaryIO
from pathlib import Path
from enum import Enum
import hashlib
import struct
import zipfile
import io
import os


class VerificationStatus(Enum):
    """Status of content verification."""
    VALID = "valid"
    INVALID = "invalid"
    CORRUPTED = "corrupted"
    PLACEHOLDER = "placeholder"
    WRONG_FORMAT = "wrong_format"
    TOO_SMALL = "too_small"
    UNKNOWN = "unknown"


class FileType(Enum):
    """Known file types."""
    PDF = "pdf"
    EPUB = "epub"
    MOBI = "mobi"
    AZW3 = "azw3"
    DJVU = "djvu"
    HTML = "html"
    TEXT = "text"
    IMAGE = "image"
    ZIP = "zip"
    UNKNOWN = "unknown"


@dataclass
class VerificationResult:
    """Result of content verification."""
    status: VerificationStatus
    file_type: FileType
    detected_type: FileType  # What the file actually is
    message: str
    details: Dict = field(default_factory=dict)
    confidence: float = 1.0  # 0-1, how confident we are


# Magic byte signatures for file types
MAGIC_SIGNATURES = {
    b'%PDF': FileType.PDF,
    b'PK\x03\x04': FileType.ZIP,  # EPUB is ZIP-based
    b'BOOKMOBI': FileType.MOBI,
    b'\xff\xd8\xff': FileType.IMAGE,  # JPEG
    b'\x89PNG\r\n\x1a\n': FileType.IMAGE,  # PNG
    b'GIF87a': FileType.IMAGE,
    b'GIF89a': FileType.IMAGE,
    b'RIFF': FileType.IMAGE,  # WebP
    b'<!DOCTYPE': FileType.HTML,
    b'<html': FileType.HTML,
    b'<HTML': FileType.HTML,
    b'AT&TFORM': FileType.DJVU,
}

# Minimum sizes for various file types (in bytes)
MIN_SIZES = {
    FileType.PDF: 1000,      # Real PDFs are at least 1KB
    FileType.EPUB: 5000,     # Real EPUBs are at least 5KB
    FileType.MOBI: 5000,
    FileType.AZW3: 5000,
    FileType.DJVU: 1000,
    FileType.IMAGE: 500,     # Real images are at least 500B (thumbnails excluded)
}


class ContentVerifier:
    """Verifies downloaded content integrity and validity."""

    def __init__(self):
        # Patterns indicating placeholder/dummy content
        self.placeholder_patterns = [
            b'This file is not available',
            b'File removed',
            b'DMCA',
            b'Access denied',
            b'Error 404',
            b'Not found',
            b'captcha',
            b'Please wait',
            b'rate limit',
            b'try again',
        ]

    def detect_type(self, data: bytes) -> FileType:
        """Detect file type from magic bytes."""
        for signature, file_type in MAGIC_SIGNATURES.items():
            if data.startswith(signature):
                return file_type

        # Check for EPUB (ZIP file with mimetype as first file)
        if data[:2] == b'PK':
            try:
                zf = zipfile.ZipFile(io.BytesIO(data))
                if 'mimetype' in zf.namelist():
                    mimetype_content = zf.read('mimetype')
                    if b'epub' in mimetype_content.lower():
                        return FileType.EPUB
            except Exception:
                pass
            return FileType.ZIP

        # Check for text/HTML in first 1KB
        try:
            text_sample = data[:1024].decode('utf-8', errors='ignore')
            if '<html' in text_sample.lower() or '<!doctype html' in text_sample.lower():
                return FileType.HTML
            if text_sample.isprintable():
                return FileType.TEXT
        except Exception:
            pass

        return FileType.UNKNOWN

    def verify_file(self, file_path: Path, expected_type: FileType = None) -> VerificationResult:
        """Verify a downloaded file."""
        if not file_path.exists():
            return VerificationResult(
                status=VerificationStatus.INVALID,
                file_type=FileType.UNKNOWN,
                detected_type=FileType.UNKNOWN,
                message="File does not exist"
            )

        # Read file
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            return VerificationResult(
                status=VerificationStatus.INVALID,
                file_type=FileType.UNKNOWN,
                detected_type=FileType.UNKNOWN,
                message=f"Could not read file: {e}"
            )

        return self.verify_data(data, expected_type, file_path.suffix.lower())

    def verify_data(
        self,
        data: bytes,
        expected_type: FileType = None,
        extension: str = ""
    ) -> VerificationResult:
        """Verify downloaded data."""
        # Detect actual type
        detected_type = self.detect_type(data)

        # Infer expected type from extension if not provided
        if expected_type is None:
            ext_map = {
                '.pdf': FileType.PDF,
                '.epub': FileType.EPUB,
                '.mobi': FileType.MOBI,
                '.azw': FileType.MOBI,
                '.azw3': FileType.AZW3,
                '.djvu': FileType.DJVU,
                '.jpg': FileType.IMAGE,
                '.jpeg': FileType.IMAGE,
                '.png': FileType.IMAGE,
                '.gif': FileType.IMAGE,
                '.webp': FileType.IMAGE,
                '.html': FileType.HTML,
                '.htm': FileType.HTML,
                '.txt': FileType.TEXT,
            }
            expected_type = ext_map.get(extension, FileType.UNKNOWN)

        # Check for HTML masquerading as something else (common issue)
        if detected_type == FileType.HTML and expected_type not in (FileType.HTML, FileType.TEXT, FileType.UNKNOWN):
            return VerificationResult(
                status=VerificationStatus.WRONG_FORMAT,
                file_type=expected_type,
                detected_type=detected_type,
                message="Downloaded HTML page instead of expected file (landing page, not actual content)",
                confidence=0.95
            )

        # Check for placeholder content
        placeholder_result = self._check_placeholder(data)
        if placeholder_result:
            return placeholder_result

        # Check minimum size
        min_size = MIN_SIZES.get(expected_type, 100)
        if len(data) < min_size:
            return VerificationResult(
                status=VerificationStatus.TOO_SMALL,
                file_type=expected_type,
                detected_type=detected_type,
                message=f"File too small ({len(data)} bytes, expected at least {min_size})",
                details={"size": len(data), "min_size": min_size}
            )

        # Type-specific verification
        if detected_type == FileType.PDF:
            return self._verify_pdf(data, expected_type)
        elif detected_type == FileType.EPUB:
            return self._verify_epub(data, expected_type)
        elif detected_type == FileType.ZIP:
            return self._verify_zip(data, expected_type)
        elif detected_type == FileType.IMAGE:
            return self._verify_image(data, expected_type)

        # Type mismatch check
        if expected_type != FileType.UNKNOWN and expected_type != detected_type:
            # Some flexibility - ZIP can be EPUB
            if not (expected_type == FileType.EPUB and detected_type == FileType.ZIP):
                return VerificationResult(
                    status=VerificationStatus.WRONG_FORMAT,
                    file_type=expected_type,
                    detected_type=detected_type,
                    message=f"Expected {expected_type.value} but got {detected_type.value}"
                )

        # Default to valid if no issues found
        return VerificationResult(
            status=VerificationStatus.VALID,
            file_type=expected_type if expected_type != FileType.UNKNOWN else detected_type,
            detected_type=detected_type,
            message="File appears valid",
            details={"size": len(data)}
        )

    def _check_placeholder(self, data: bytes) -> Optional[VerificationResult]:
        """Check if file contains placeholder/error content."""
        # Only check text-like content
        if len(data) > 50000:  # Large files unlikely to be placeholders
            return None

        # Check beginning of file
        check_data = data[:5000].lower()

        for pattern in self.placeholder_patterns:
            if pattern.lower() in check_data:
                return VerificationResult(
                    status=VerificationStatus.PLACEHOLDER,
                    file_type=FileType.UNKNOWN,
                    detected_type=FileType.HTML if b'<html' in check_data else FileType.TEXT,
                    message=f"File appears to be a placeholder or error page",
                    details={"matched_pattern": pattern.decode('utf-8', errors='ignore')}
                )

        return None

    def _verify_pdf(self, data: bytes, expected_type: FileType) -> VerificationResult:
        """Verify PDF file integrity."""
        # Check for PDF header
        if not data.startswith(b'%PDF'):
            return VerificationResult(
                status=VerificationStatus.WRONG_FORMAT,
                file_type=expected_type,
                detected_type=self.detect_type(data),
                message="File does not start with PDF header"
            )

        # Check for EOF marker (should be near end)
        if b'%%EOF' not in data[-1024:]:
            # Might be truncated
            return VerificationResult(
                status=VerificationStatus.CORRUPTED,
                file_type=FileType.PDF,
                detected_type=FileType.PDF,
                message="PDF appears truncated (missing EOF marker)",
                confidence=0.7
            )

        # Check for basic PDF structure
        has_catalog = b'/Catalog' in data or b'/catalog' in data.lower()
        has_pages = b'/Pages' in data or b'/pages' in data.lower()

        if not has_catalog or not has_pages:
            return VerificationResult(
                status=VerificationStatus.CORRUPTED,
                file_type=FileType.PDF,
                detected_type=FileType.PDF,
                message="PDF missing essential structure (Catalog or Pages)",
                confidence=0.6
            )

        return VerificationResult(
            status=VerificationStatus.VALID,
            file_type=FileType.PDF,
            detected_type=FileType.PDF,
            message="PDF structure appears valid",
            details={"size": len(data)}
        )

    def _verify_epub(self, data: bytes, expected_type: FileType) -> VerificationResult:
        """Verify EPUB file integrity."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return VerificationResult(
                status=VerificationStatus.CORRUPTED,
                file_type=FileType.EPUB,
                detected_type=FileType.ZIP,
                message="EPUB file is not a valid ZIP archive"
            )

        # Check for required EPUB files
        namelist = zf.namelist()

        # EPUB must have mimetype file
        if 'mimetype' not in namelist:
            return VerificationResult(
                status=VerificationStatus.CORRUPTED,
                file_type=FileType.EPUB,
                detected_type=FileType.ZIP,
                message="EPUB missing mimetype file",
                confidence=0.8
            )

        # Check mimetype content
        try:
            mimetype = zf.read('mimetype')
            if b'epub' not in mimetype.lower():
                return VerificationResult(
                    status=VerificationStatus.WRONG_FORMAT,
                    file_type=FileType.EPUB,
                    detected_type=FileType.ZIP,
                    message="ZIP file does not have EPUB mimetype"
                )
        except Exception:
            pass

        # Check for META-INF/container.xml (required)
        if 'META-INF/container.xml' not in namelist:
            return VerificationResult(
                status=VerificationStatus.CORRUPTED,
                file_type=FileType.EPUB,
                detected_type=FileType.EPUB,
                message="EPUB missing container.xml",
                confidence=0.7
            )

        # Check for content files
        content_files = [n for n in namelist if n.endswith(('.xhtml', '.html', '.xml', '.opf'))]
        if not content_files:
            return VerificationResult(
                status=VerificationStatus.CORRUPTED,
                file_type=FileType.EPUB,
                detected_type=FileType.EPUB,
                message="EPUB has no content files"
            )

        zf.close()

        return VerificationResult(
            status=VerificationStatus.VALID,
            file_type=FileType.EPUB,
            detected_type=FileType.EPUB,
            message="EPUB structure appears valid",
            details={"size": len(data), "files": len(namelist)}
        )

    def _verify_zip(self, data: bytes, expected_type: FileType) -> VerificationResult:
        """Verify ZIP file integrity."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
            # Test archive integrity
            bad_file = zf.testzip()
            if bad_file:
                return VerificationResult(
                    status=VerificationStatus.CORRUPTED,
                    file_type=FileType.ZIP,
                    detected_type=FileType.ZIP,
                    message=f"ZIP archive has corrupted file: {bad_file}"
                )
            zf.close()
        except zipfile.BadZipFile:
            return VerificationResult(
                status=VerificationStatus.CORRUPTED,
                file_type=FileType.ZIP,
                detected_type=FileType.ZIP,
                message="Invalid ZIP archive"
            )

        return VerificationResult(
            status=VerificationStatus.VALID,
            file_type=expected_type if expected_type != FileType.UNKNOWN else FileType.ZIP,
            detected_type=FileType.ZIP,
            message="ZIP archive appears valid",
            details={"size": len(data)}
        )

    def _verify_image(self, data: bytes, expected_type: FileType) -> VerificationResult:
        """Verify image file integrity."""
        # JPEG check
        if data.startswith(b'\xff\xd8\xff'):
            # Check for JPEG end marker
            if not data.endswith(b'\xff\xd9'):
                return VerificationResult(
                    status=VerificationStatus.CORRUPTED,
                    file_type=FileType.IMAGE,
                    detected_type=FileType.IMAGE,
                    message="JPEG appears truncated (missing end marker)",
                    confidence=0.7
                )

        # PNG check
        elif data.startswith(b'\x89PNG\r\n\x1a\n'):
            # Check for IEND chunk
            if b'IEND' not in data[-20:]:
                return VerificationResult(
                    status=VerificationStatus.CORRUPTED,
                    file_type=FileType.IMAGE,
                    detected_type=FileType.IMAGE,
                    message="PNG appears truncated (missing IEND)",
                    confidence=0.7
                )

        return VerificationResult(
            status=VerificationStatus.VALID,
            file_type=FileType.IMAGE,
            detected_type=FileType.IMAGE,
            message="Image appears valid",
            details={"size": len(data)}
        )


def compute_hash(data: bytes) -> str:
    """Compute SHA-256 hash of data."""
    return hashlib.sha256(data).hexdigest()


def compute_md5(data: bytes) -> str:
    """Compute MD5 hash of data."""
    return hashlib.md5(data).hexdigest()


def compute_checksums(data: bytes) -> Dict[str, str]:
    """Compute both MD5 and SHA256 checksums.

    Returns:
        Dictionary with 'md5' and 'sha256' keys.
    """
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest()
    }


def compute_file_checksums(file_path: Path) -> Dict[str, str]:
    """Compute checksums from file path efficiently.

    Uses streaming to handle large files without loading into memory.

    Returns:
        Dictionary with 'md5' and 'sha256' keys.
    """
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()

    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            md5.update(chunk)
            sha256.update(chunk)

    return {
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest()
    }


def verify_checksum(
    file_path: Path = None,
    data: bytes = None,
    expected_md5: str = None,
    expected_sha256: str = None
) -> Tuple[bool, str]:
    """Verify file or data against expected checksum(s).

    Args:
        file_path: Path to file to verify
        data: Raw bytes to verify (alternative to file_path)
        expected_md5: Expected MD5 hash (optional)
        expected_sha256: Expected SHA256 hash (optional)

    Returns:
        Tuple of (is_valid, message)
    """
    if file_path is not None:
        checksums = compute_file_checksums(file_path)
    elif data is not None:
        checksums = compute_checksums(data)
    else:
        return False, "No file or data provided"

    # Check SHA256 first (more secure)
    if expected_sha256:
        if checksums["sha256"].lower() != expected_sha256.lower():
            return False, f"SHA256 mismatch: expected {expected_sha256[:16]}..., got {checksums['sha256'][:16]}..."
        return True, "SHA256 checksum verified"

    # Check MD5 if no SHA256 provided
    if expected_md5:
        if checksums["md5"].lower() != expected_md5.lower():
            return False, f"MD5 mismatch: expected {expected_md5}, got {checksums['md5']}"
        return True, "MD5 checksum verified"

    return False, "No expected checksum provided"


@dataclass
class IntegrityResult:
    """Result of integrity verification."""
    is_valid: bool
    md5_hash: str
    sha256_hash: str
    verification_status: VerificationStatus
    message: str
    file_size: int = 0


class IntegrityVerifier:
    """Comprehensive file integrity verification."""

    def __init__(self):
        self.content_verifier = ContentVerifier()

    def verify_with_checksum(
        self,
        file_path: Path,
        expected_md5: str = None,
        expected_sha256: str = None,
        expected_type: FileType = None
    ) -> IntegrityResult:
        """Verify file integrity with optional checksum validation.

        Args:
            file_path: Path to file
            expected_md5: Expected MD5 hash (optional)
            expected_sha256: Expected SHA256 hash (optional)
            expected_type: Expected file type (optional)

        Returns:
            IntegrityResult with verification details.
        """
        if not file_path.exists():
            return IntegrityResult(
                is_valid=False,
                md5_hash="",
                sha256_hash="",
                verification_status=VerificationStatus.INVALID,
                message="File does not exist"
            )

        # Compute checksums
        checksums = compute_file_checksums(file_path)
        file_size = file_path.stat().st_size

        # Verify checksum if provided
        if expected_sha256:
            if checksums["sha256"].lower() != expected_sha256.lower():
                return IntegrityResult(
                    is_valid=False,
                    md5_hash=checksums["md5"],
                    sha256_hash=checksums["sha256"],
                    verification_status=VerificationStatus.CORRUPTED,
                    message="SHA256 checksum mismatch - file may be corrupted or incomplete",
                    file_size=file_size
                )

        if expected_md5:
            if checksums["md5"].lower() != expected_md5.lower():
                return IntegrityResult(
                    is_valid=False,
                    md5_hash=checksums["md5"],
                    sha256_hash=checksums["sha256"],
                    verification_status=VerificationStatus.CORRUPTED,
                    message="MD5 checksum mismatch - file may be corrupted or incomplete",
                    file_size=file_size
                )

        # Perform content verification
        content_result = self.content_verifier.verify_file(file_path, expected_type)

        return IntegrityResult(
            is_valid=content_result.status == VerificationStatus.VALID,
            md5_hash=checksums["md5"],
            sha256_hash=checksums["sha256"],
            verification_status=content_result.status,
            message=content_result.message,
            file_size=file_size
        )

    def verify_data_with_checksum(
        self,
        data: bytes,
        expected_md5: str = None,
        expected_sha256: str = None,
        expected_type: FileType = None,
        extension: str = ""
    ) -> IntegrityResult:
        """Verify data integrity with optional checksum validation."""
        checksums = compute_checksums(data)

        # Verify checksum if provided
        if expected_sha256:
            if checksums["sha256"].lower() != expected_sha256.lower():
                return IntegrityResult(
                    is_valid=False,
                    md5_hash=checksums["md5"],
                    sha256_hash=checksums["sha256"],
                    verification_status=VerificationStatus.CORRUPTED,
                    message="SHA256 checksum mismatch",
                    file_size=len(data)
                )

        if expected_md5:
            if checksums["md5"].lower() != expected_md5.lower():
                return IntegrityResult(
                    is_valid=False,
                    md5_hash=checksums["md5"],
                    sha256_hash=checksums["sha256"],
                    verification_status=VerificationStatus.CORRUPTED,
                    message="MD5 checksum mismatch",
                    file_size=len(data)
                )

        # Perform content verification
        content_result = self.content_verifier.verify_data(data, expected_type, extension)

        return IntegrityResult(
            is_valid=content_result.status == VerificationStatus.VALID,
            md5_hash=checksums["md5"],
            sha256_hash=checksums["sha256"],
            verification_status=content_result.status,
            message=content_result.message,
            file_size=len(data)
        )


def get_integrity_verifier() -> IntegrityVerifier:
    """Get an integrity verifier instance."""
    return IntegrityVerifier()


def quick_verify(file_path: Path) -> Tuple[bool, str]:
    """Quick verification - returns (is_valid, message)."""
    verifier = ContentVerifier()
    result = verifier.verify_file(file_path)
    return (result.status == VerificationStatus.VALID, result.message)


# Global verifier instance
_verifier: Optional[ContentVerifier] = None


def get_verifier() -> ContentVerifier:
    """Get the global content verifier instance."""
    global _verifier
    if _verifier is None:
        _verifier = ContentVerifier()
    return _verifier
