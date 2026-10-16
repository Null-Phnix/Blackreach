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


def test_missing_recorded_file_is_downloaded_again(tmp_path):
    """A database row must not block replacing a file the user already deleted."""
    path = tmp_path / "paper.pdf"
    path.write_bytes(PDF)
    agent = make_agent(path, PDF)
    agent.config = SimpleNamespace(download_dir=tmp_path)
    agent.persistent_memory.has_downloaded.side_effect = lambda **kw: True
    agent.persistent_memory.find_downloads.side_effect = lambda **kw: [
        {"filename": "paper.pdf", "url": "https://example.org/paper.pdf", "file_hash": "abc"}
    ]
    path.unlink()

    def write_replacement(_url):
        path.write_bytes(PDF)
        return dict(
            path=str(path),
            filename=path.name,
            size=len(PDF),
            hash=hashlib.sha256(PDF).hexdigest(),
            url="https://example.org/paper.pdf",
        )

    agent.hand.download_link = Mock(side_effect=write_replacement)

    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "https://example.org/paper.pdf", "expected_type": "pdf"}
    )

    assert not result.get("skipped")
    assert path.read_bytes() == PDF
    agent._record_download.assert_called_once()


def test_recorded_file_still_on_disk_is_not_fetched_again(tmp_path):
    path = tmp_path / "paper.pdf"
    path.write_bytes(PDF)
    agent = make_agent(path, PDF)
    agent.config = SimpleNamespace(download_dir=tmp_path)
    agent.persistent_memory.has_downloaded.side_effect = lambda **kw: "url" in kw
    agent.persistent_memory.find_downloads.side_effect = lambda **kw: [
        {"filename": "paper.pdf", "url": "https://example.org/paper.pdf", "file_hash": "abc"}
    ]

    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "https://example.org/paper.pdf", "expected_type": "pdf"}
    )

    assert result["reason"] == "already downloaded"
    agent.hand.download_link.assert_not_called()
    assert path.read_bytes() == PDF


def test_same_hash_keeps_replacement_when_original_is_gone(tmp_path):
    original = tmp_path / "original.pdf"
    replacement = tmp_path / "mirror.pdf"
    replacement.write_bytes(PDF)
    agent = make_agent(replacement, PDF, duplicate=True)
    agent.config = SimpleNamespace(download_dir=tmp_path)
    agent.persistent_memory.find_downloads.side_effect = lambda **kw: [
        {"filename": original.name, "url": "https://mirror.example/original.pdf", "file_hash": "abc"}
    ]

    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "https://mirror.example/original.pdf", "expected_type": "pdf"}
    )

    assert not result.get("skipped")
    assert replacement.read_bytes() == PDF
    agent._record_download.assert_called_once()


def test_same_hash_still_drops_a_second_copy(tmp_path):
    original = tmp_path / "original.pdf"
    original.write_bytes(PDF)
    replacement = tmp_path / "mirror.pdf"
    replacement.write_bytes(PDF)
    agent = make_agent(replacement, PDF, duplicate=True)
    agent.config = SimpleNamespace(download_dir=tmp_path)
    agent.persistent_memory.find_downloads.side_effect = lambda **kw: [
        {"filename": original.name, "url": "https://mirror.example/original.pdf", "file_hash": "abc"}
    ]

    result = AgentActionsMixin._execute_action(
        agent, "download", {"url": "https://mirror.example/copy.pdf", "expected_type": "pdf"}
    )

    assert result["reason"] == "duplicate content"
    assert not replacement.exists()
    assert original.read_bytes() == PDF
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
