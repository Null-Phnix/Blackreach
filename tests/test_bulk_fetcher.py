"""BulkFetcher must be importable without httpx and must not drop its client."""

import subprocess
import sys
from types import SimpleNamespace

import blackreach.bulk_fetcher as bulk_fetcher
from blackreach.bulk_fetcher import BulkFetcher, FetchResult


class _FakeResponse:
    status_code = 200
    headers = {"content-type": "text/html"}
    text = "<html>ok</html>"


class _FakeClient:
    live = []

    def __init__(self, **kwargs):
        self.closed = False
        self.gets = []
        _FakeClient.live.append(self)

    def get(self, url):
        self.gets.append(url)
        return _FakeResponse()

    def close(self):
        self.closed = True


def _install_fake_httpx(monkeypatch):
    _FakeClient.live = []
    monkeypatch.setattr(bulk_fetcher, "HTTPX_AVAILABLE", True)
    monkeypatch.setattr(
        bulk_fetcher,
        "httpx",
        SimpleNamespace(Client=_FakeClient),
        raising=False,
    )


def test_fetch_result_imports_when_httpx_is_missing():
    """The optional httpx import must not make FetchResult unimportable."""
    script = """
import sys

class _BlockHttpx:
    def find_spec(self, name, path, target=None):
        if name == "httpx" or name.startswith("httpx."):
            raise ImportError("httpx blocked")
        return None

sys.meta_path.insert(0, _BlockHttpx())
from blackreach.bulk_fetcher import BulkFetcher, FetchResult
result = FetchResult(url="https://example.test", status=200, html="<html></html>")
assert result.url == "https://example.test"
try:
    BulkFetcher()
except ImportError as exc:
    assert "httpx" in str(exc)
else:
    raise SystemExit("BulkFetcher() should require httpx")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_fetch_without_context_manager_returns_the_page(monkeypatch):
    _install_fake_httpx(monkeypatch)
    result = BulkFetcher().fetch("https://example.com/a")
    assert result.status == 200
    assert result.html == "<html>ok</html>"
    assert len(_FakeClient.live) == 1
    assert _FakeClient.live[0].closed is True
    assert _FakeClient.live[0].gets == ["https://example.com/a"]


def test_fetch_many_preserves_order_and_closes_its_client(monkeypatch):
    _install_fake_httpx(monkeypatch)
    results = BulkFetcher().fetch_many(
        ["https://example.com/b", "https://example.com/a"]
    )
    assert [item.url for item in results] == [
        "https://example.com/b",
        "https://example.com/a",
    ]
    assert all(item.ok for item in results)
    assert len(_FakeClient.live) == 1
    assert _FakeClient.live[0].closed is True


def test_fetch_many_keeps_the_callers_client_open(monkeypatch):
    _install_fake_httpx(monkeypatch)
    fetcher = BulkFetcher()
    with fetcher:
        held = _FakeClient.live[0]
        many = fetcher.fetch_many(["https://example.com/a"])
        assert many[0].ok
        assert fetcher._client is held
        assert held.closed is False
        one = fetcher.fetch("https://example.com/c")
        assert one.html == "<html>ok</html>"
        assert fetcher._client is held
        assert held.closed is False
    assert held.closed is True
    assert len(_FakeClient.live) == 1


def test_fetch_generator_empty_is_empty(monkeypatch):
    _install_fake_httpx(monkeypatch)
    assert list(BulkFetcher().fetch_generator([])) == []
    assert _FakeClient.live == []


def test_fetch_generator_yields_and_closes(monkeypatch):
    _install_fake_httpx(monkeypatch)
    pages = list(BulkFetcher().fetch_generator(["https://example.com/a"]))
    assert len(pages) == 1
    assert isinstance(pages[0], FetchResult)
    assert pages[0].ok
    assert _FakeClient.live[0].closed is True
