"""
Metadata Extraction System (v1.0.0)

Extracts metadata from downloaded files:
- PDF metadata (title, author, pages, creation date)
- EPUB metadata (title, author, publisher, description)
- Image metadata (dimensions, format, EXIF)
- General file metadata (size, hash, type)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, BinaryIO
from datetime import datetime
from pathlib import Path
from enum import Enum
import hashlib
import struct
import zipfile
import io
import re
import xml.etree.ElementTree as ET


class MetadataType(Enum):
    """Type of metadata source."""
    PDF = "pdf"
    EPUB = "epub"
    IMAGE = "image"
    DOCUMENT = "document"
    GENERIC = "generic"


@dataclass
class FileMetadata:
    """Generic file metadata."""
    file_path: Path
    file_size: int
    file_type: str
    md5_hash: str
    sha256_hash: str
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    extension: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "file_path": str(self.file_path),
            "file_size": self.file_size,
            "file_type": self.file_type,
            "md5_hash": self.md5_hash,
            "sha256_hash": self.sha256_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "extension": self.extension
        }


@dataclass
class PDFMetadata:
    """PDF-specific metadata."""
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
    pdf_version: str = ""
    is_encrypted: bool = False
    has_embedded_fonts: bool = False
    file_size: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "keywords": self.keywords,
            "creator": self.creator,
            "producer": self.producer,
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "modification_date": self.modification_date.isoformat() if self.modification_date else None,
            "page_count": self.page_count,
            "pdf_version": self.pdf_version,
            "is_encrypted": self.is_encrypted,
            "has_embedded_fonts": self.has_embedded_fonts,
            "file_size": self.file_size
        }


@dataclass
class EPUBMetadata:
    """EPUB-specific metadata."""
    title: str = ""
    author: str = ""
    authors: List[str] = field(default_factory=list)
    publisher: str = ""
    description: str = ""
    language: str = ""
    isbn: str = ""
    publication_date: Optional[datetime] = None
    rights: str = ""
    subjects: List[str] = field(default_factory=list)
    chapter_count: int = 0
    file_size: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "authors": self.authors,
            "publisher": self.publisher,
            "description": self.description,
            "language": self.language,
            "isbn": self.isbn,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "rights": self.rights,
            "subjects": self.subjects,
            "chapter_count": self.chapter_count,
            "file_size": self.file_size
        }


@dataclass
class ImageMetadata:
    """Image-specific metadata."""
    format: str = ""
    width: int = 0
    height: int = 0
    color_mode: str = ""
    bit_depth: int = 0
    has_alpha: bool = False
    file_size: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "color_mode": self.color_mode,
            "bit_depth": self.bit_depth,
            "has_alpha": self.has_alpha,
            "file_size": self.file_size
        }


@dataclass
class ExtractionResult:
    """Result of metadata extraction."""
    success: bool
    metadata_type: MetadataType
    file_metadata: FileMetadata
    specific_metadata: Union[PDFMetadata, EPUBMetadata, ImageMetadata, None]
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {
            "success": self.success,
            "metadata_type": self.metadata_type.value,
            "file_metadata": self.file_metadata.to_dict(),
            "error": self.error,
            "warnings": self.warnings
        }
        if self.specific_metadata:
            result["specific_metadata"] = self.specific_metadata.to_dict()
        return result


class MetadataExtractor:
    """Extracts metadata from various file types."""

    def __init__(self):
        self._pypdf_available = self._check_pypdf()

    def _check_pypdf(self) -> bool:
        """Check if PyPDF2/pypdf is available."""
        try:
            import pypdf
            return True
        except ImportError:
            try:
                import PyPDF2
                return True
            except ImportError:
                return False

    def compute_hashes(self, data: bytes) -> tuple:
        """Compute MD5 and SHA256 hashes of data.

        Returns:
            Tuple of (md5_hash, sha256_hash)
        """
        md5_hash = hashlib.md5(data).hexdigest()
        sha256_hash = hashlib.sha256(data).hexdigest()
        return md5_hash, sha256_hash

    def compute_file_hashes(self, file_path: Path) -> tuple:
        """Compute hashes from file path.

        Returns:
            Tuple of (md5_hash, sha256_hash)
        """
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                md5.update(chunk)
                sha256.update(chunk)

        return md5.hexdigest(), sha256.hexdigest()

    def extract_from_file(self, file_path: Path) -> ExtractionResult:
        """Extract metadata from a file."""
        if not file_path.exists():
            return ExtractionResult(
                success=False,
                metadata_type=MetadataType.GENERIC,
                file_metadata=FileMetadata(
                    file_path=file_path,
                    file_size=0,
                    file_type="unknown",
                    md5_hash="",
                    sha256_hash=""
                ),
                specific_metadata=None,
                error="File does not exist"
            )

        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            return self.extract_from_data(data, file_path)
        except Exception as e:
            return ExtractionResult(
                success=False,
                metadata_type=MetadataType.GENERIC,
                file_metadata=FileMetadata(
                    file_path=file_path,
                    file_size=0,
                    file_type="unknown",
                    md5_hash="",
                    sha256_hash=""
                ),
                specific_metadata=None,
                error=f"Failed to read file: {e}"
            )

    def extract_from_data(
        self,
        data: bytes,
        file_path: Path = None
    ) -> ExtractionResult:
        """Extract metadata from raw data."""
        md5_hash, sha256_hash = self.compute_hashes(data)

        file_metadata = FileMetadata(
            file_path=file_path or Path("unknown"),
            file_size=len(data),
            file_type=self._detect_type(data),
            md5_hash=md5_hash,
            sha256_hash=sha256_hash,
            extension=file_path.suffix.lower() if file_path else ""
        )

        # Try to get file timestamps
        if file_path and file_path.exists():
            stat = file_path.stat()
            file_metadata.created_at = datetime.fromtimestamp(stat.st_ctime)
            file_metadata.modified_at = datetime.fromtimestamp(stat.st_mtime)

        # Extract type-specific metadata
        if data.startswith(b'%PDF'):
            return self._extract_pdf(data, file_metadata)
        elif data[:2] == b'PK':
            # Could be EPUB or ZIP
            if self._is_epub(data):
                return self._extract_epub(data, file_metadata)
        elif self._is_image(data):
            return self._extract_image(data, file_metadata)

        # Generic result
        return ExtractionResult(
            success=True,
            metadata_type=MetadataType.GENERIC,
            file_metadata=file_metadata,
            specific_metadata=None
        )

    def _detect_type(self, data: bytes) -> str:
        """Detect file type from magic bytes."""
        if data.startswith(b'%PDF'):
            return "pdf"
        elif data[:2] == b'PK':
            if self._is_epub(data):
                return "epub"
            return "zip"
        elif data.startswith(b'\xff\xd8\xff'):
            return "jpeg"
        elif data.startswith(b'\x89PNG\r\n\x1a\n'):
            return "png"
        elif data.startswith((b'GIF87a', b'GIF89a')):
            return "gif"
        elif data.startswith(b'RIFF') and b'WEBP' in data[:16]:
            return "webp"
        elif data.startswith(b'BOOKMOBI'):
            return "mobi"
        return "unknown"

    def _is_epub(self, data: bytes) -> bool:
        """Check if ZIP data is an EPUB."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
            if 'mimetype' in zf.namelist():
                mimetype = zf.read('mimetype')
                return b'epub' in mimetype.lower()
        except Exception:
            pass
        return False

    def _is_image(self, data: bytes) -> bool:
        """Check if data is an image."""
        return (
            data.startswith(b'\xff\xd8\xff') or  # JPEG
            data.startswith(b'\x89PNG\r\n\x1a\n') or  # PNG
            data.startswith((b'GIF87a', b'GIF89a')) or  # GIF
            (data.startswith(b'RIFF') and b'WEBP' in data[:16])  # WebP
        )

    def _extract_pdf(
        self,
        data: bytes,
        file_metadata: FileMetadata
    ) -> ExtractionResult:
        """Extract PDF metadata."""
        pdf_meta = PDFMetadata(file_size=len(data))
        warnings = []

        # Extract PDF version
        version_match = re.search(rb'%PDF-(\d+\.\d+)', data[:100])
        if version_match:
            pdf_meta.pdf_version = version_match.group(1).decode('utf-8')

        # Check if encrypted
        pdf_meta.is_encrypted = b'/Encrypt' in data

        # Try using pypdf/PyPDF2 for full metadata extraction
        if self._pypdf_available:
            try:
                pdf_meta = self._extract_pdf_with_pypdf(data, pdf_meta)
            except Exception as e:
                warnings.append(f"PyPDF extraction failed: {e}")
                # Fall back to manual extraction
                pdf_meta = self._extract_pdf_manual(data, pdf_meta)
        else:
            warnings.append("PyPDF not available, using basic extraction")
            pdf_meta = self._extract_pdf_manual(data, pdf_meta)

        return ExtractionResult(
            success=True,
            metadata_type=MetadataType.PDF,
            file_metadata=file_metadata,
            specific_metadata=pdf_meta,
            warnings=warnings
        )

    def _extract_pdf_with_pypdf(
        self,
        data: bytes,
        pdf_meta: PDFMetadata
    ) -> PDFMetadata:
        """Extract PDF metadata using pypdf/PyPDF2."""
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
        except ImportError:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(data))

        # Page count
        pdf_meta.page_count = len(reader.pages)

        # Document info
        if reader.metadata:
            meta = reader.metadata
            pdf_meta.title = str(meta.get('/Title', '') or '')
            pdf_meta.author = str(meta.get('/Author', '') or '')
            pdf_meta.subject = str(meta.get('/Subject', '') or '')
            pdf_meta.keywords = str(meta.get('/Keywords', '') or '')
            pdf_meta.creator = str(meta.get('/Creator', '') or '')
            pdf_meta.producer = str(meta.get('/Producer', '') or '')

            # Parse dates
            creation_date = meta.get('/CreationDate')
            if creation_date:
                pdf_meta.creation_date = self._parse_pdf_date(str(creation_date))

            mod_date = meta.get('/ModDate')
            if mod_date:
                pdf_meta.modification_date = self._parse_pdf_date(str(mod_date))

        return pdf_meta

    def _extract_pdf_manual(
        self,
        data: bytes,
        pdf_meta: PDFMetadata
    ) -> PDFMetadata:
        """Manual PDF metadata extraction (fallback)."""
        # Count pages by looking for /Type /Page entries
        page_pattern = rb'/Type\s*/Page[^s]'
        page_matches = re.findall(page_pattern, data)
        pdf_meta.page_count = len(page_matches)

        # Try to find Info dictionary entries
        info_patterns = {
            'title': rb'/Title\s*\(([^)]+)\)',
            'author': rb'/Author\s*\(([^)]+)\)',
            'subject': rb'/Subject\s*\(([^)]+)\)',
            'creator': rb'/Creator\s*\(([^)]+)\)',
            'producer': rb'/Producer\s*\(([^)]+)\)',
        }

        for field, pattern in info_patterns.items():
            match = re.search(pattern, data)
            if match:
                value = match.group(1).decode('utf-8', errors='ignore')
                setattr(pdf_meta, field, value)

        return pdf_meta

    def _parse_pdf_date(self, date_str: str) -> Optional[datetime]:
        """Parse PDF date format (D:YYYYMMDDHHmmSS...)."""
        if not date_str:
            return None

        # Remove D: prefix if present
        date_str = date_str.replace("D:", "")

        # Try various formats
        formats = [
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y%m%d",
            "%Y%m",
            "%Y"
        ]

        # Clean the date string
        date_str = re.sub(r"[+-]\d{2}'\d{2}'?$", "", date_str)
        date_str = date_str.replace("'", "")

        for fmt in formats:
            try:
                return datetime.strptime(date_str[:len(fmt.replace('%', ''))], fmt)
            except (ValueError, IndexError):
                continue

        return None

    def _extract_epub(
        self,
        data: bytes,
        file_metadata: FileMetadata
    ) -> ExtractionResult:
        """Extract EPUB metadata."""
        epub_meta = EPUBMetadata(file_size=len(data))
        warnings = []

        try:
            zf = zipfile.ZipFile(io.BytesIO(data))

            # Find the OPF file (content.opf)
            opf_path = self._find_opf_path(zf)
            if not opf_path:
                warnings.append("Could not find OPF file")
                return ExtractionResult(
                    success=True,
                    metadata_type=MetadataType.EPUB,
                    file_metadata=file_metadata,
                    specific_metadata=epub_meta,
                    warnings=warnings
                )

            # Parse OPF
            opf_content = zf.read(opf_path)
            epub_meta = self._parse_opf(opf_content, epub_meta)

            # Count chapters (HTML/XHTML files)
            html_files = [
                n for n in zf.namelist()
                if n.endswith(('.xhtml', '.html', '.htm'))
            ]
            epub_meta.chapter_count = len(html_files)

            zf.close()

        except Exception as e:
            warnings.append(f"EPUB extraction error: {e}")

        return ExtractionResult(
            success=True,
            metadata_type=MetadataType.EPUB,
            file_metadata=file_metadata,
            specific_metadata=epub_meta,
            warnings=warnings
        )

    def _find_opf_path(self, zf: zipfile.ZipFile) -> Optional[str]:
        """Find the OPF file path in EPUB."""
        # Check container.xml first
        try:
            container = zf.read('META-INF/container.xml')
            # Find rootfile path
            match = re.search(rb'full-path="([^"]+\.opf)"', container)
            if match:
                return match.group(1).decode('utf-8')
        except Exception:
            pass

        # Fallback: look for any .opf file
        for name in zf.namelist():
            if name.endswith('.opf'):
                return name

        return None

    def _parse_opf(self, opf_content: bytes, epub_meta: EPUBMetadata) -> EPUBMetadata:
        """Parse OPF content for metadata."""
        try:
            # Parse XML, handling namespaces
            root = ET.fromstring(opf_content)

            # Define namespaces
            ns = {
                'opf': 'http://www.idpf.org/2007/opf',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }

            # Find metadata element
            metadata = root.find('.//opf:metadata', ns)
            if metadata is None:
                metadata = root.find('.//{http://www.idpf.org/2007/opf}metadata')
            if metadata is None:
                # Try without namespace
                metadata = root.find('.//metadata')

            if metadata is not None:
                # Title
                title = metadata.find('dc:title', ns)
                if title is None:
                    title = metadata.find('.//{http://purl.org/dc/elements/1.1/}title')
                if title is not None and title.text:
                    epub_meta.title = title.text.strip()

                # Authors
                authors = metadata.findall('dc:creator', ns)
                if not authors:
                    authors = metadata.findall('.//{http://purl.org/dc/elements/1.1/}creator')
                for author in authors:
                    if author.text:
                        epub_meta.authors.append(author.text.strip())
                if epub_meta.authors:
                    epub_meta.author = epub_meta.authors[0]

                # Publisher
                publisher = metadata.find('dc:publisher', ns)
                if publisher is None:
                    publisher = metadata.find('.//{http://purl.org/dc/elements/1.1/}publisher')
                if publisher is not None and publisher.text:
                    epub_meta.publisher = publisher.text.strip()

                # Description
                description = metadata.find('dc:description', ns)
                if description is None:
                    description = metadata.find('.//{http://purl.org/dc/elements/1.1/}description')
                if description is not None and description.text:
                    epub_meta.description = description.text.strip()

                # Language
                language = metadata.find('dc:language', ns)
                if language is None:
                    language = metadata.find('.//{http://purl.org/dc/elements/1.1/}language')
                if language is not None and language.text:
                    epub_meta.language = language.text.strip()

                # Rights
                rights = metadata.find('dc:rights', ns)
                if rights is None:
                    rights = metadata.find('.//{http://purl.org/dc/elements/1.1/}rights')
                if rights is not None and rights.text:
                    epub_meta.rights = rights.text.strip()

                # Subjects
                subjects = metadata.findall('dc:subject', ns)
                if not subjects:
                    subjects = metadata.findall('.//{http://purl.org/dc/elements/1.1/}subject')
                for subject in subjects:
                    if subject.text:
                        epub_meta.subjects.append(subject.text.strip())

                # ISBN (look in identifier)
                identifiers = metadata.findall('dc:identifier', ns)
                if not identifiers:
                    identifiers = metadata.findall('.//{http://purl.org/dc/elements/1.1/}identifier')
                for identifier in identifiers:
                    if identifier.text and 'isbn' in identifier.text.lower():
                        # Extract ISBN digits
                        isbn = re.sub(r'[^0-9X]', '', identifier.text.upper())
                        if len(isbn) in (10, 13):
                            epub_meta.isbn = isbn
                            break

                # Date
                date_elem = metadata.find('dc:date', ns)
                if date_elem is None:
                    date_elem = metadata.find('.//{http://purl.org/dc/elements/1.1/}date')
                if date_elem is not None and date_elem.text:
                    epub_meta.publication_date = self._parse_date(date_elem.text)

        except ET.ParseError:
            pass

        return epub_meta

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%d",
            "%Y-%m",
            "%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
        ]

        date_str = date_str.strip()

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _extract_image(
        self,
        data: bytes,
        file_metadata: FileMetadata
    ) -> ExtractionResult:
        """Extract image metadata."""
        img_meta = ImageMetadata(file_size=len(data))
        warnings = []

        try:
            if data.startswith(b'\x89PNG\r\n\x1a\n'):
                img_meta = self._extract_png_metadata(data, img_meta)
            elif data.startswith(b'\xff\xd8\xff'):
                img_meta = self._extract_jpeg_metadata(data, img_meta)
            elif data.startswith((b'GIF87a', b'GIF89a')):
                img_meta = self._extract_gif_metadata(data, img_meta)
        except Exception as e:
            warnings.append(f"Image metadata extraction failed: {e}")

        return ExtractionResult(
            success=True,
            metadata_type=MetadataType.IMAGE,
            file_metadata=file_metadata,
            specific_metadata=img_meta,
            warnings=warnings
        )

    def _extract_png_metadata(
        self,
        data: bytes,
        img_meta: ImageMetadata
    ) -> ImageMetadata:
        """Extract PNG image metadata."""
        img_meta.format = "PNG"

        # IHDR chunk starts at byte 8 (after signature)
        # Format: width (4), height (4), bit depth (1), color type (1)
        if len(data) >= 24:
            width = struct.unpack('>I', data[16:20])[0]
            height = struct.unpack('>I', data[20:24])[0]
            bit_depth = data[24]
            color_type = data[25]

            img_meta.width = width
            img_meta.height = height
            img_meta.bit_depth = bit_depth

            color_modes = {
                0: "Grayscale",
                2: "RGB",
                3: "Indexed",
                4: "Grayscale+Alpha",
                6: "RGBA"
            }
            img_meta.color_mode = color_modes.get(color_type, "Unknown")
            img_meta.has_alpha = color_type in (4, 6)

        return img_meta

    def _extract_jpeg_metadata(
        self,
        data: bytes,
        img_meta: ImageMetadata
    ) -> ImageMetadata:
        """Extract JPEG image metadata."""
        img_meta.format = "JPEG"

        # Find SOF0/SOF2 marker for dimensions
        i = 2
        while i < len(data) - 8:
            if data[i] == 0xFF:
                marker = data[i + 1]
                # SOF markers (Start of Frame)
                if marker in (0xC0, 0xC1, 0xC2):
                    height = struct.unpack('>H', data[i + 5:i + 7])[0]
                    width = struct.unpack('>H', data[i + 7:i + 9])[0]
                    components = data[i + 9]

                    img_meta.width = width
                    img_meta.height = height

                    if components == 1:
                        img_meta.color_mode = "Grayscale"
                    elif components == 3:
                        img_meta.color_mode = "RGB"
                    elif components == 4:
                        img_meta.color_mode = "CMYK"

                    break

                # Skip to next marker
                if marker == 0xD8:  # SOI
                    i += 2
                elif marker == 0xD9:  # EOI
                    break
                elif marker in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7):
                    i += 2
                else:
                    length = struct.unpack('>H', data[i + 2:i + 4])[0]
                    i += 2 + length
            else:
                i += 1

        return img_meta

    def _extract_gif_metadata(
        self,
        data: bytes,
        img_meta: ImageMetadata
    ) -> ImageMetadata:
        """Extract GIF image metadata."""
        img_meta.format = "GIF"

        if len(data) >= 10:
            img_meta.width = struct.unpack('<H', data[6:8])[0]
            img_meta.height = struct.unpack('<H', data[8:10])[0]
            img_meta.color_mode = "Indexed"
            img_meta.bit_depth = 8

        return img_meta


# Utility functions

def compute_checksum(
    file_path: Path = None,
    data: bytes = None,
    algorithm: str = "sha256"
) -> str:
    """Compute checksum of file or data.

    Args:
        file_path: Path to file
        data: Raw bytes data
        algorithm: 'md5' or 'sha256'

    Returns:
        Hex digest of hash.
    """
    if algorithm == "md5":
        hasher = hashlib.md5()
    else:
        hasher = hashlib.sha256()

    if data is not None:
        hasher.update(data)
    elif file_path is not None:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
    else:
        raise ValueError("Either file_path or data must be provided")

    return hasher.hexdigest()


def extract_pdf_metadata(file_path: Path) -> Optional[PDFMetadata]:
    """Quick helper to extract PDF metadata."""
    extractor = MetadataExtractor()
    result = extractor.extract_from_file(file_path)
    if result.success and isinstance(result.specific_metadata, PDFMetadata):
        return result.specific_metadata
    return None


def extract_epub_metadata(file_path: Path) -> Optional[EPUBMetadata]:
    """Quick helper to extract EPUB metadata."""
    extractor = MetadataExtractor()
    result = extractor.extract_from_file(file_path)
    if result.success and isinstance(result.specific_metadata, EPUBMetadata):
        return result.specific_metadata
    return None


# Global instance
_extractor: Optional[MetadataExtractor] = None


def get_metadata_extractor() -> MetadataExtractor:
    """Get the global metadata extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = MetadataExtractor()
    return _extractor
