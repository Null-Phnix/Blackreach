"""Exercise the real action handler with fixture transport, not a live browser."""

import hashlib
import io
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from blackreach.agent_actions import AgentActionsMixin
from blackreach.content_verify import ContentVerifier, FileType, VerificationStatus
from blackreach.exceptions import InvalidActionArgsError

HTML = b"<!DOCTYPE html><html><body>" + b"Article landing page. " * 100 + b"</body></html>"
# Structural verifier fixture; not a full PDF renderer/conformance fixture.
PDF = b"%PDF-1.7\n/Catalog /Pages\n" + b" " * 1500 + b"\n%%EOF"


def make_agent(path, data=HTML, missing=False, duplicate=False):
    if not missing:
        path.write_bytes(data)
    receipt = dict(
        path=str(path),
        filename=path.name,
        size=len(data),
        hash=hashlib.sha256(data).hexdigest(),
        url="https://example.org/download",
    )
    memory = Mock()
    memory.has_downloaded.side_effect = lambda **kw: duplicate and "file_hash" in kw
    return SimpleNamespace(
        hand=SimpleNamespace(
            download_link=Mock(return_value=receipt),
            click_and_download=Mock(return_value=receipt),
            get_url=lambda: "https://example.org/article",
        ),
        persistent_memory=memory,
        session_memory=Mock(),
        _failed_download_urls=set(),
        content_verifier=ContentVerifier(),
        _record_download=Mock(),
        _record_failure=Mock(),
        _get_domain=lambda: "example.org",
        nav_context=Mock(),
        _selector_click_counts={},
        _clicked_selectors=set(),
    )


@pytest.mark.parametrize(
    "target", [{"url": "https://example.org/download"}, {"selector": "#download"}]
)
@pytest.mark.parametrize("name", ["article.html", "article"])
def test_requested_pdf_rejects_html_before_recording(tmp_path, target, name):
    path = tmp_path / name
    agent = make_agent(path)
    result = AgentActionsMixin._execute_action(
        agent, "download", {**target, "expected_type": "pdf"}
    )
    assert result["skipped"] and result["reason"] == "wrong_format"
    assert not path.exists()
    agent._record_download.assert_not_called()
    agent.persistent_memory.add_download.assert_not_called()


def test_url_pdf_expectation_survives_server_html_filename(tmp_path):
    agent = make_agent(tmp_path / "landing.html")
    result = AgentActionsMixin._execute_action(agent, "download", {"url": "/paper.pdf?download=1"})
    assert result["reason"] == "wrong_format"
    agent._record_download.assert_not_called()


def test_valid_pdf_is_recorded(tmp_path):
    agent = make_agent(tmp_path / "paper.bin", PDF)
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/download", "expected_type": "pdf"}
    )
    assert not result.get("skipped")
    agent._record_download.assert_called_once()
    agent.persistent_memory.add_download.assert_called_once()


def test_missing_file_is_not_recorded(tmp_path):
    agent = make_agent(tmp_path / "missing.pdf", missing=True)
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/download", "expected_type": "pdf"}
    )
    assert result["reason"] == "invalid"
    agent._record_download.assert_not_called()


def test_explicit_html_download_still_allowed(tmp_path):
    agent = make_agent(tmp_path / "page.html")
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/download", "expected_type": "html"}
    )
    assert not result.get("skipped")
    agent._record_download.assert_called_once()


def test_duplicate_content_is_not_recorded_twice(tmp_path):
    path = tmp_path / "copy.pdf"
    agent = make_agent(path, PDF, duplicate=True)
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/download", "expected_type": "pdf"}
    )
    assert result["reason"] == "duplicate content"
    assert not path.exists()
    agent._record_download.assert_not_called()


@pytest.mark.parametrize("expected", ["pfd", "", "unknown", 123, []])
def test_invalid_expectation_fails_before_transport(tmp_path, expected):
    agent = make_agent(tmp_path / "page.html")
    with pytest.raises(InvalidActionArgsError):
        AgentActionsMixin._execute_action(
            agent, "download", {"url": "/download", "expected_type": expected}
        )
    agent.hand.download_link.assert_not_called()


def test_archive_cannot_satisfy_requested_pdf():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("readme.txt", "archive content " * 200)
    result = ContentVerifier().verify_data(stream.getvalue(), expected_type=FileType.PDF)
    assert result.status == VerificationStatus.WRONG_FORMAT


@pytest.mark.parametrize("epub", [False, True])
def test_epub_exception_requires_epub_structure(epub):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("chapter.xhtml", "<p>" + "book text " * 600 + "</p>")
        if epub:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("META-INF/container.xml", "<container/>")
    result = ContentVerifier().verify_data(stream.getvalue(), expected_type=FileType.EPUB)
    assert result.status == (VerificationStatus.VALID if epub else VerificationStatus.CORRUPTED)


def test_valid_pdf_cannot_satisfy_requested_zip():
    result = ContentVerifier().verify_data(PDF, expected_type=FileType.ZIP)
    assert result.status == VerificationStatus.WRONG_FORMAT


def _jpeg(*, close=True, trailing=b""):
    """Minimal marker layout: comment padding, one scan, optional EOI."""
    comment = b"x" * 520
    segment = b"\xff\xfe" + (len(comment) + 2).to_bytes(2, "big") + comment
    scan_header = b"\x01\x01\x00\x00\x3f\x00"
    scan = b"\xff\xda" + (len(scan_header) + 2).to_bytes(2, "big") + scan_header
    entropy = b"\x12\x34\xff\x00\x56"
    eoi = b"\xff\xd9" if close else b""
    return b"\xff\xd8" + segment + scan + entropy + eoi + trailing


def _png(*, iend=True, trailing=b""):
    signature = b"\x89PNG\r\n\x1a\n"
    image_data = b"\x00" * 512
    idat = (
        len(image_data).to_bytes(4, "big")
        + b"IDAT"
        + image_data
        + b"\x00\x00\x00\x00"
    )
    ending = b"\x00\x00\x00\x00IEND\xaeB`\x82" if iend else b""
    return signature + idat + ending + trailing


def test_jpeg_with_trailing_metadata_is_kept(tmp_path):
    """Extended XMP sits after EOI. That file is complete and must be kept."""
    data = _jpeg(trailing=b'\n<?xpacket begin="W5M0MpCehiHzreSzNTczkc9d"?>' + b"<x:xmpmeta/>")
    path = tmp_path / "photo.jpg"
    agent = make_agent(path, data)
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/photo.jpg", "expected_type": "image"}
    )
    assert not result.get("skipped")
    assert path.read_bytes() == data
    agent._record_download.assert_called_once()


def test_jpeg_that_ends_on_eoi_is_kept():
    result = ContentVerifier().verify_data(_jpeg(), extension=".jpg")
    assert result.status == VerificationStatus.VALID


def test_jpeg_restart_markers_and_trailing_bytes_are_kept():
    """Restart markers are inside the scan, and bytes after EOI stay with the file."""
    base = _jpeg(close=False)
    data = base + b"\xff\xd0\x11\xff\xd7\x22\xff\xd9" + b"\n" * 24
    result = ContentVerifier().verify_data(data, extension=".jpg")
    assert result.status == VerificationStatus.VALID


def test_truncated_jpeg_is_still_deleted(tmp_path):
    """A scan that never reaches EOI is still rejected, even if a thumbnail has one."""
    thumb = b"\xff\xd8" + b"\x00" * 16 + b"\xff\xd9"
    app1 = b"\xff\xe1" + (len(thumb) + 2).to_bytes(2, "big") + thumb
    data = b"\xff\xd8" + app1 + _jpeg(close=False)[2:]
    assert b"\xff\xd9" in data
    path = tmp_path / "photo.jpg"
    agent = make_agent(path, data)
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/photo.jpg", "expected_type": "image"}
    )
    assert result["reason"] == "corrupted"
    assert not path.exists()
    agent._record_download.assert_not_called()


def test_png_with_trailing_bytes_is_kept(tmp_path):
    data = _png(trailing=b"\n" * 32 + b"camera-padding")
    path = tmp_path / "photo.png"
    agent = make_agent(path, data)
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/photo.png", "expected_type": "image"}
    )
    assert not result.get("skipped")
    assert path.read_bytes() == data


def test_truncated_png_is_still_deleted(tmp_path):
    path = tmp_path / "photo.png"
    agent = make_agent(path, _png(iend=False))
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/photo.png", "expected_type": "image"}
    )
    assert result["reason"] == "corrupted"
    assert not path.exists()
