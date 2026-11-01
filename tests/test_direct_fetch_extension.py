"""Extensionless downloads must keep the type named by Content-Type."""

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

from blackreach.browser_playwright import Hand as PlaywrightHand
from blackreach.content_verify import ContentVerifier, VerificationStatus
from blackreach.extras.browser_starsearch import Hand as StarSearchHand


def _epub_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", "<container/>")
        archive.writestr("chapter.xhtml", "<p>" + "book text " * 600 + "</p>")
    return stream.getvalue()


class _Response:
    def __init__(self, payload: bytes, content_type: str):
        self._payload = payload
        self.headers = {"Content-Type": content_type}

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _fetch(hand, tmp_path: Path, payload: bytes, content_type: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    hand.download_dir = tmp_path
    module = hand.__class__.__module__
    response = _Response(payload, content_type)
    with patch(f"{module}._is_ssrf_safe", return_value=True), patch(
        f"{module}.urlopen_guarded", return_value=response
    ):
        return hand._fetch_file_directly("https://example.org/download/42")


def test_extensionless_epub_is_not_saved_as_zip(tmp_path):
    payload = _epub_bytes()
    for hand in (PlaywrightHand(download_dir=tmp_path / "pw"), StarSearchHand(download_dir=tmp_path / "ss")):
        dest = tmp_path / hand.__class__.__module__
        result = _fetch(hand, dest, payload, "application/epub+zip")
        saved = Path(result["path"])
        assert saved.name == "42.epub"
        assert saved.read_bytes() == payload
        assert [path.name for path in dest.iterdir()] == ["42.epub"]
        verified = ContentVerifier().verify_file(saved)
        assert verified.status == VerificationStatus.VALID


def test_extensionless_zip_and_pdf_keep_their_types(tmp_path):
    pdf = b"%PDF-1.7\n/Catalog /Pages\n" + b" " * 1500 + b"\n%%EOF"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("readme.txt", "archive content " * 200)
    cases = (
        (pdf, "application/pdf", "42.pdf"),
        (stream.getvalue(), "application/zip", "42.zip"),
    )
    for payload, content_type, filename in cases:
        dest = tmp_path / filename
        result = _fetch(StarSearchHand(), dest, payload, content_type)
        assert Path(result["path"]).name == filename
        assert [path.name for path in dest.iterdir()] == [filename]
