"""Extensionless gzip responses must stay gzip archives, not zip files."""
import gzip
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from blackreach.browser_playwright import Hand
from blackreach.content_verify import ContentVerifier, VerificationStatus
from blackreach.extras.browser_starsearch import Hand as StarSearchHand


class _Response:
    def __init__(self, payload: bytes, content_type: str):
        self.headers = {"Content-Type": content_type}
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _gzip_payload() -> bytes:
    return gzip.compress(os.urandom(4000))


@pytest.fixture
def playwright_hand(monkeypatch):
    monkeypatch.setattr("blackreach.browser_playwright._is_ssrf_safe", lambda url: True)
    hand = Hand.__new__(Hand)
    hand.stealth = SimpleNamespace(get_random_user_agent=lambda: "test-agent")
    return hand


@pytest.fixture
def starsearch_hand(monkeypatch):
    monkeypatch.setattr("blackreach.extras.browser_starsearch._is_ssrf_safe", lambda url: True)
    return StarSearchHand.__new__(StarSearchHand)


@pytest.mark.parametrize("content_type", ["application/gzip", "application/x-gzip", "Application/GZIP"])
@pytest.mark.parametrize(
    ("hand_fixture", "module"),
    [
        ("playwright_hand", "blackreach.browser_playwright"),
        ("starsearch_hand", "blackreach.extras.browser_starsearch"),
    ],
)
def test_extensionless_gzip_is_saved_as_gzip(tmp_path, monkeypatch, request, content_type, hand_fixture, module):
    payload = _gzip_payload()
    hand = request.getfixturevalue(hand_fixture)
    monkeypatch.setattr(
        f"{module}.urlopen_guarded",
        lambda req, timeout=30: _Response(payload, content_type),
    )
    hand.download_dir = tmp_path

    result = hand._fetch_file_directly("https://example.com/archives/42")

    saved = Path(result["path"])
    assert saved.name == "42.gz"
    assert saved.read_bytes() == payload
    assert gzip.decompress(saved.read_bytes())
    verification = ContentVerifier().verify_file(saved)
    assert verification.status == VerificationStatus.VALID
    assert [path.name for path in tmp_path.iterdir()] == ["42.gz"]


def test_extensionless_zip_is_still_zip(tmp_path, monkeypatch, playwright_hand):
    payload = b"PK\x03\x04" + os.urandom(200)
    monkeypatch.setattr(
        "blackreach.browser_playwright.urlopen_guarded",
        lambda req, timeout=30: _Response(payload, "application/zip"),
    )
    playwright_hand.download_dir = tmp_path

    result = playwright_hand._fetch_file_directly("https://example.com/archives/42")

    saved = Path(result["path"])
    assert saved.name == "42.zip"
    assert saved.read_bytes() == payload
    assert [path.name for path in tmp_path.iterdir()] == ["42.zip"]
