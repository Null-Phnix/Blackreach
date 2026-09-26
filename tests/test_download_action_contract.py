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


# qpdf --object-streams=generate leaves /Root in the trailer and compresses
# /Catalog and /Pages. A structural check that requires those literals deletes it.
OBJECT_STREAM_PDF = (
    b"%PDF-1.5\n"
    b"1 0 obj\n<< /Type /XRef /Root 2 0 R /Size 3 /Filter /FlateDecode >>\n"
    b"stream\n" + (b"\x00" * 1100) + b"\nendstream\nendobj\nstartxref\n9\n%%EOF\n"
)


def test_object_stream_pdf_is_kept(tmp_path):
    assert b"/Catalog" not in OBJECT_STREAM_PDF
    assert b"/Pages" not in OBJECT_STREAM_PDF
    path = tmp_path / "paper.pdf"
    agent = make_agent(path, OBJECT_STREAM_PDF)
    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "/download", "expected_type": "pdf"}
    )
    assert not result.get("skipped")
    assert path.exists()
    agent._record_download.assert_called_once()


def test_pdf_without_root_or_page_tree_is_still_rejected():
    data = b"%PDF-1.7\n" + (b"\x00" * 1200) + b"\n%%EOF"
    result = ContentVerifier().verify_data(data, expected_type=FileType.PDF)
    assert result.status == VerificationStatus.CORRUPTED
