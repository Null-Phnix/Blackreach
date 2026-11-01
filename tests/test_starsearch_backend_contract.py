"""Drop-in Hand interface contracts for the production StarSearch backend."""

import socket
from unittest.mock import Mock

import pytest

from blackreach.extras import browser_starsearch
from blackreach.extras.browser_starsearch import (
    BrowserNotReadyError,
    DownloadError,
    Hand,
    ProxyConfig,
)


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeStarSearch:
    def __init__(self):
        self.options = None
        self.session = FakeSession()

    def new_session(self, **options):
        self.options = options
        return self.session

    def close(self):
        pass


def test_sleep_accepts_keep_alive_and_then_releases_session(tmp_path):
    browser = FakeStarSearch()
    hand = Hand(download_dir=tmp_path)
    hand._browser = browser
    hand.wake()

    hand.sleep(keep_alive=True)
    assert hand._session is browser.session
    assert browser.session.closed is False

    hand.sleep(keep_alive=False)
    assert hand._session is None
    assert browser.session.closed is True


def test_authenticated_proxy_reaches_starsearch_as_structured_options(tmp_path):
    browser = FakeStarSearch()
    hand = Hand(
        download_dir=tmp_path,
        proxy=ProxyConfig.from_url("http://agent:secret@proxy.example:8080"),
    )
    hand._browser = browser
    hand.wake()

    assert browser.options["proxy"] == {
        "server": "http://proxy.example:8080",
        "username": "agent",
        "password": "secret",
    }
    hand.close()


def test_missing_optional_client_fails_closed_when_session_is_needed(monkeypatch, tmp_path):
    monkeypatch.setattr(browser_starsearch, "StarSearch", None)
    hand = Hand(download_dir=tmp_path)

    with pytest.raises(BrowserNotReadyError, match="client is not installed"):
        hand.wake()


class _DownloadSession:
    def __init__(self, href: str, page: str = "https://library.example/books/index"):
        self.href = href
        self.page = page

    def evaluate(self, script: str):
        if "querySelector" in script:
            return self.href
        if "location.href" in script:
            return self.page
        return ""


def _public_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )


def test_selector_download_saves_the_link_target(monkeypatch, tmp_path):
    payload = b"%PDF-1.4\nselector-download\n%%EOF"
    response = Mock()
    response.headers = {"Content-Type": "application/pdf"}
    response.read.return_value = payload
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opened = Mock(return_value=response)
    monkeypatch.setattr(browser_starsearch, "urlopen_guarded", opened)
    _public_dns(monkeypatch)

    hand = Hand(download_dir=tmp_path)
    hand._session = _DownloadSession("/files/paper.pdf")

    result = hand.click_and_download("a.download")

    opened_url = opened.call_args.args[0].full_url
    assert opened_url == "https://library.example/files/paper.pdf"
    saved = tmp_path / "paper.pdf"
    assert result["path"] == str(saved)
    assert result["filename"] == "paper.pdf"
    assert result["size"] == len(payload)
    assert result["hash"]
    assert saved.read_bytes() == payload


def test_selector_download_without_a_file_url_does_not_pretend_success(tmp_path):
    hand = Hand(download_dir=tmp_path)
    hand._session = _DownloadSession("")

    with pytest.raises(DownloadError, match="no direct file URL"):
        hand.download_file(selector="button.download")
    assert list(tmp_path.iterdir()) == []
