"""
Tests for Metadata Extraction System
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime
import struct
import zipfile
import io

from blackreach.metadata_extract import (
    MetadataExtractor, PDFMetadata, EPUBMetadata, ImageMetadata, FileMetadata,
    ExtractionResult, MetadataType, compute_checksum, extract_pdf_metadata,
    extract_epub_metadata, get_metadata_extractor
)


@pytest.fixture
def extractor():
    """Create a MetadataExtractor instance."""
    return MetadataExtractor()


class TestMetadataExtractor:
    """Tests for MetadataExtractor class."""

    def test_compute_hashes(self, extractor):
        """Test hash computation."""
        data = b"Hello, World!"
        md5, sha256 = extractor.compute_hashes(data)

        assert len(md5) == 32  # MD5 is 32 hex chars
        assert len(sha256) == 64  # SHA256 is 64 hex chars
        assert md5 == "65a8e27d8879283831b664bd8b7f0ad4"

    def test_detect_type_pdf(self, extractor):
        """Test detecting PDF files."""
        pdf_data = b'%PDF-1.4 fake pdf content'
        assert extractor._detect_type(pdf_data) == "pdf"

    def test_detect_type_jpeg(self, extractor):
        """Test detecting JPEG files."""
        jpeg_data = b'\xff\xd8\xff\xe0fake jpeg'
        assert extractor._detect_type(jpeg_data) == "jpeg"

    def test_detect_type_png(self, extractor):
        """Test detecting PNG files."""
        png_data = b'\x89PNG\r\n\x1a\nfake png'
        assert extractor._detect_type(png_data) == "png"

    def test_detect_type_zip(self, extractor):
        """Test detecting ZIP files."""
        # Create a minimal ZIP
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            zf.writestr('test.txt', 'content')
        zip_data = buffer.getvalue()

        assert extractor._detect_type(zip_data) == "zip"

    def test_extract_from_data_generic(self, extractor):
        """Test extracting metadata from generic data."""
        data = b"Just some text content"
        result = extractor.extract_from_data(data)

        assert result.success is True
        assert result.file_metadata.file_size == len(data)
        assert result.file_metadata.md5_hash != ""
        assert result.file_metadata.sha256_hash != ""


class TestPDFMetadataExtraction:
    """Tests for PDF metadata extraction."""

    @pytest.fixture
    def minimal_pdf(self):
        """Create minimal PDF-like data for testing."""
        # This is a simplified PDF structure for testing
        pdf = b'''\
%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
>>
endobj
xref
0 4
trailer
<<
/Root 1 0 R
>>
startxref
0
%%EOF'''
        return pdf

    def test_extract_pdf_version(self, extractor, minimal_pdf):
        """Test extracting PDF version."""
        result = extractor.extract_from_data(minimal_pdf)

        assert result.success is True
        assert result.metadata_type == MetadataType.PDF
        assert isinstance(result.specific_metadata, PDFMetadata)
        assert result.specific_metadata.pdf_version == "1.4"

    def test_pdf_metadata_fields(self, extractor, minimal_pdf):
        """Test PDF metadata fields exist."""
        result = extractor.extract_from_data(minimal_pdf)
        meta = result.specific_metadata

        assert hasattr(meta, 'title')
        assert hasattr(meta, 'author')
        assert hasattr(meta, 'page_count')
        assert hasattr(meta, 'pdf_version')

    def test_pdf_metadata_to_dict(self):
        """Test PDFMetadata to_dict method."""
        meta = PDFMetadata(
            title="Test Book",
            author="Test Author",
            page_count=100,
            pdf_version="1.7"
        )
        d = meta.to_dict()

        assert d["title"] == "Test Book"
        assert d["author"] == "Test Author"
        assert d["page_count"] == 100


class TestEPUBMetadataExtraction:
    """Tests for EPUB metadata extraction."""

    @pytest.fixture
    def minimal_epub(self):
        """Create minimal EPUB-like data for testing."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            # Mimetype (must be first, uncompressed)
            zf.writestr('mimetype', 'application/epub+zip')

            # Container XML
            container_xml = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)

            # OPF file
            opf_content = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test EPUB Book</dc:title>
    <dc:creator>Test Author</dc:creator>
    <dc:publisher>Test Publisher</dc:publisher>
    <dc:language>en</dc:language>
    <dc:identifier>urn:isbn:1234567890</dc:identifier>
  </metadata>
  <manifest>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter1"/>
  </spine>
</package>'''
            zf.writestr('OEBPS/content.opf', opf_content)

            # Chapter file
            zf.writestr('OEBPS/chapter1.xhtml', '<html><body>Chapter 1</body></html>')

        return buffer.getvalue()

    def test_extract_epub_metadata(self, extractor, minimal_epub):
        """Test extracting EPUB metadata."""
        result = extractor.extract_from_data(minimal_epub)

        assert result.success is True
        assert result.metadata_type == MetadataType.EPUB
        assert isinstance(result.specific_metadata, EPUBMetadata)

    def test_epub_title_extraction(self, extractor, minimal_epub):
        """Test extracting EPUB title."""
        result = extractor.extract_from_data(minimal_epub)
        meta = result.specific_metadata

        assert meta.title == "Test EPUB Book"

    def test_epub_author_extraction(self, extractor, minimal_epub):
        """Test extracting EPUB author."""
        result = extractor.extract_from_data(minimal_epub)
        meta = result.specific_metadata

        assert meta.author == "Test Author"

    def test_epub_metadata_to_dict(self):
        """Test EPUBMetadata to_dict method."""
        meta = EPUBMetadata(
            title="My Book",
            author="Author Name",
            publisher="Publisher Co",
            chapter_count=10
        )
        d = meta.to_dict()

        assert d["title"] == "My Book"
        assert d["publisher"] == "Publisher Co"
        assert d["chapter_count"] == 10


class TestImageMetadataExtraction:
    """Tests for image metadata extraction."""

    @pytest.fixture
    def minimal_png(self):
        """Create minimal PNG data for testing."""
        # PNG signature + minimal IHDR chunk
        signature = b'\x89PNG\r\n\x1a\n'
        # IHDR: width=100, height=200, bit_depth=8, color_type=2 (RGB)
        ihdr_data = struct.pack('>IIBBBBB', 100, 200, 8, 2, 0, 0, 0)
        ihdr_crc = b'\x00\x00\x00\x00'  # Fake CRC
        ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + ihdr_crc
        # IEND chunk
        iend_chunk = struct.pack('>I', 0) + b'IEND' + b'\x00\x00\x00\x00'

        return signature + ihdr_chunk + iend_chunk

    @pytest.fixture
    def minimal_jpeg(self):
        """Create minimal JPEG-like data for testing."""
        # SOI + APP0 + SOF0 (simplified) + EOI
        soi = b'\xff\xd8'
        # SOF0 marker with dimensions
        # Format: marker(2) + length(2) + precision(1) + height(2) + width(2) + components(1)
        sof0 = b'\xff\xc0\x00\x0b\x08' + struct.pack('>HH', 480, 640) + b'\x03'
        eoi = b'\xff\xd9'
        return soi + sof0 + eoi

    def test_extract_png_dimensions(self, extractor, minimal_png):
        """Test extracting PNG dimensions."""
        result = extractor.extract_from_data(minimal_png)

        assert result.success is True
        assert result.metadata_type == MetadataType.IMAGE
        meta = result.specific_metadata

        assert meta.format == "PNG"
        assert meta.width == 100
        assert meta.height == 200
        assert meta.color_mode == "RGB"

    def test_extract_jpeg_dimensions(self, extractor, minimal_jpeg):
        """Test extracting JPEG dimensions."""
        result = extractor.extract_from_data(minimal_jpeg)

        assert result.success is True
        meta = result.specific_metadata

        assert meta.format == "JPEG"
        assert meta.width == 640
        assert meta.height == 480

    def test_image_metadata_to_dict(self):
        """Test ImageMetadata to_dict method."""
        meta = ImageMetadata(
            format="PNG",
            width=800,
            height=600,
            color_mode="RGBA",
            has_alpha=True
        )
        d = meta.to_dict()

        assert d["format"] == "PNG"
        assert d["width"] == 800
        assert d["has_alpha"] is True


class TestFileMetadata:
    """Tests for FileMetadata dataclass."""

    def test_file_metadata_creation(self):
        """Test creating FileMetadata."""
        meta = FileMetadata(
            file_path=Path("/test/file.pdf"),
            file_size=1024,
            file_type="pdf",
            md5_hash="abc123",
            sha256_hash="def456",
            extension=".pdf"
        )

        assert meta.file_size == 1024
        assert meta.file_type == "pdf"

    def test_file_metadata_to_dict(self):
        """Test FileMetadata to_dict method."""
        meta = FileMetadata(
            file_path=Path("/test/file.pdf"),
            file_size=2048,
            file_type="pdf",
            md5_hash="md5hash",
            sha256_hash="sha256hash",
            extension=".pdf"
        )
        d = meta.to_dict()

        assert d["file_size"] == 2048
        assert d["md5_hash"] == "md5hash"


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_compute_checksum_sha256(self):
        """Test computing SHA256 checksum."""
        data = b"test data for hashing"
        checksum = compute_checksum(data=data, algorithm="sha256")

        assert len(checksum) == 64

    def test_compute_checksum_md5(self):
        """Test computing MD5 checksum."""
        data = b"test data for hashing"
        checksum = compute_checksum(data=data, algorithm="md5")

        assert len(checksum) == 32

    def test_compute_checksum_from_file(self):
        """Test computing checksum from file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"file content for hashing")
            temp_path = Path(f.name)

        try:
            checksum = compute_checksum(file_path=temp_path, algorithm="sha256")
            assert len(checksum) == 64
        finally:
            temp_path.unlink()

    def test_get_metadata_extractor(self):
        """Test getting global extractor instance."""
        ext1 = get_metadata_extractor()
        ext2 = get_metadata_extractor()

        assert ext1 is ext2  # Should be same instance


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_extraction_result_to_dict(self):
        """Test ExtractionResult to_dict method."""
        file_meta = FileMetadata(
            file_path=Path("/test/file.pdf"),
            file_size=1024,
            file_type="pdf",
            md5_hash="abc",
            sha256_hash="def"
        )
        pdf_meta = PDFMetadata(title="Test", page_count=10)

        result = ExtractionResult(
            success=True,
            metadata_type=MetadataType.PDF,
            file_metadata=file_meta,
            specific_metadata=pdf_meta
        )

        d = result.to_dict()
        assert d["success"] is True
        assert d["metadata_type"] == "pdf"
        assert "file_metadata" in d
        assert "specific_metadata" in d
