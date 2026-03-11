"""
Tests for Enhanced Content Verification System
Tests for MD5/SHA256 checksum verification functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path

from blackreach.content_verify import (
    ContentVerifier, VerificationStatus, FileType,
    compute_hash, compute_md5, compute_checksums, compute_file_checksums,
    verify_checksum, IntegrityVerifier, IntegrityResult, get_integrity_verifier
)


class TestChecksumFunctions:
    """Tests for checksum computation functions."""

    def test_compute_hash_sha256(self):
        """Test SHA256 hash computation."""
        data = b"Hello, World!"
        hash_value = compute_hash(data)

        assert len(hash_value) == 64
        assert hash_value == "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"

    def test_compute_md5(self):
        """Test MD5 hash computation."""
        data = b"Hello, World!"
        hash_value = compute_md5(data)

        assert len(hash_value) == 32
        assert hash_value == "65a8e27d8879283831b664bd8b7f0ad4"

    def test_compute_checksums(self):
        """Test computing both checksums."""
        data = b"Test data for checksums"
        checksums = compute_checksums(data)

        assert "md5" in checksums
        assert "sha256" in checksums
        assert len(checksums["md5"]) == 32
        assert len(checksums["sha256"]) == 64

    def test_compute_file_checksums(self):
        """Test computing checksums from file."""
        content = b"File content for hashing test"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            checksums = compute_file_checksums(temp_path)

            # Compare with in-memory computation
            expected = compute_checksums(content)
            assert checksums["md5"] == expected["md5"]
            assert checksums["sha256"] == expected["sha256"]
        finally:
            temp_path.unlink()

    def test_compute_file_checksums_large_file(self):
        """Test checksums on larger file (tests streaming)."""
        # Create 1MB of data
        content = b"x" * (1024 * 1024)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            checksums = compute_file_checksums(temp_path)
            expected = compute_checksums(content)

            assert checksums["md5"] == expected["md5"]
            assert checksums["sha256"] == expected["sha256"]
        finally:
            temp_path.unlink()


class TestVerifyChecksum:
    """Tests for checksum verification function."""

    def test_verify_sha256_match(self):
        """Test verifying matching SHA256."""
        data = b"Test data"
        expected = compute_checksums(data)["sha256"]

        is_valid, message = verify_checksum(data=data, expected_sha256=expected)
        assert is_valid is True
        assert "SHA256" in message

    def test_verify_sha256_mismatch(self):
        """Test detecting SHA256 mismatch."""
        data = b"Test data"

        is_valid, message = verify_checksum(data=data, expected_sha256="wrong_hash")
        assert is_valid is False
        assert "mismatch" in message.lower()

    def test_verify_md5_match(self):
        """Test verifying matching MD5."""
        data = b"Test data"
        expected = compute_checksums(data)["md5"]

        is_valid, message = verify_checksum(data=data, expected_md5=expected)
        assert is_valid is True
        assert "MD5" in message

    def test_verify_md5_mismatch(self):
        """Test detecting MD5 mismatch."""
        data = b"Test data"

        is_valid, message = verify_checksum(data=data, expected_md5="wrong_hash")
        assert is_valid is False
        assert "mismatch" in message.lower()

    def test_verify_file_sha256(self):
        """Test verifying file SHA256."""
        content = b"File content to verify"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            expected = compute_checksums(content)["sha256"]
            is_valid, message = verify_checksum(file_path=temp_path, expected_sha256=expected)
            assert is_valid is True
        finally:
            temp_path.unlink()

    def test_verify_no_checksum_provided(self):
        """Test error when no expected checksum provided."""
        data = b"Some data"
        is_valid, message = verify_checksum(data=data)
        assert is_valid is False
        assert "No expected checksum" in message

    def test_verify_no_data_provided(self):
        """Test error when no data or file provided."""
        is_valid, message = verify_checksum(expected_sha256="some_hash")
        assert is_valid is False


class TestIntegrityVerifier:
    """Tests for IntegrityVerifier class."""

    @pytest.fixture
    def verifier(self):
        """Create IntegrityVerifier instance."""
        return IntegrityVerifier()

    @pytest.fixture
    def temp_pdf(self):
        """Create a temp PDF-like file that passes size validation."""
        # Create PDF content large enough to pass min size check (1000 bytes)
        pdf_header = b'''\
%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R >> endobj
'''
        # Pad with comments to reach minimum size
        padding = b'% ' + b'x' * 900 + b'\n'
        pdf_footer = b'%%EOF'
        pdf_content = pdf_header + padding + pdf_footer

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(pdf_content)
            temp_path = Path(f.name)
        yield temp_path, pdf_content
        temp_path.unlink()

    def test_verify_with_checksum_valid(self, verifier, temp_pdf):
        """Test integrity verification with valid checksum."""
        temp_path, content = temp_pdf
        expected_sha256 = compute_checksums(content)["sha256"]

        result = verifier.verify_with_checksum(
            temp_path,
            expected_sha256=expected_sha256
        )

        assert result.is_valid is True
        assert result.sha256_hash == expected_sha256

    def test_verify_with_checksum_invalid(self, verifier, temp_pdf):
        """Test integrity verification with invalid checksum."""
        temp_path, _ = temp_pdf

        result = verifier.verify_with_checksum(
            temp_path,
            expected_sha256="invalid_hash_value"
        )

        assert result.is_valid is False
        assert result.verification_status == VerificationStatus.CORRUPTED

    def test_verify_nonexistent_file(self, verifier):
        """Test verification of non-existent file."""
        result = verifier.verify_with_checksum(Path("/nonexistent/file.pdf"))

        assert result.is_valid is False
        assert "not exist" in result.message

    def test_verify_data_with_checksum(self, verifier):
        """Test data verification with checksum."""
        data = b'%PDF-1.4 test pdf content %%EOF'
        checksums = compute_checksums(data)

        result = verifier.verify_data_with_checksum(
            data,
            expected_sha256=checksums["sha256"]
        )

        assert result.md5_hash == checksums["md5"]
        assert result.sha256_hash == checksums["sha256"]

    def test_verify_computes_all_hashes(self, verifier, temp_pdf):
        """Test that verification computes all hashes."""
        temp_path, content = temp_pdf
        expected = compute_checksums(content)

        result = verifier.verify_with_checksum(temp_path)

        assert result.md5_hash == expected["md5"]
        assert result.sha256_hash == expected["sha256"]
        assert result.file_size > 0


class TestIntegrityResult:
    """Tests for IntegrityResult dataclass."""

    def test_integrity_result_creation(self):
        """Test creating IntegrityResult."""
        result = IntegrityResult(
            is_valid=True,
            md5_hash="abc123",
            sha256_hash="def456",
            verification_status=VerificationStatus.VALID,
            message="All good",
            file_size=1024
        )

        assert result.is_valid is True
        assert result.md5_hash == "abc123"
        assert result.file_size == 1024


class TestGetIntegrityVerifier:
    """Tests for get_integrity_verifier function."""

    def test_get_integrity_verifier(self):
        """Test getting integrity verifier instance."""
        verifier = get_integrity_verifier()
        assert isinstance(verifier, IntegrityVerifier)

    def test_integrity_verifier_has_content_verifier(self):
        """Test that integrity verifier has content verifier."""
        verifier = get_integrity_verifier()
        assert hasattr(verifier, 'content_verifier')
        assert isinstance(verifier.content_verifier, ContentVerifier)
