"""Drop-in Hand interface contracts for the production StarSearch backend."""

import pytest

from blackreach.extras import browser_starsearch
from blackreach.extras.browser_starsearch import BrowserNotReadyError, Hand, ProxyConfig


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
