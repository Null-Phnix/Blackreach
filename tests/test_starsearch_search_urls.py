"""URL-boundary tests for direct StarSearch Bing result parsing."""

import base64
import urllib.parse

from blackreach.starsearch_search import _decode_bing_url


def _wrapped(target: str, host: str = "www.bing.com") -> str:
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    return f"https://{host}/ck/a?u=a1{urllib.parse.quote(encoded)}"


def test_bing_wrapper_requires_exact_domain_boundary():
    url = _wrapped("https://example.com/", host="evilbing.com")
    assert _decode_bing_url(url) == url


def test_bing_wrapper_decodes_absolute_http_destination():
    assert _decode_bing_url(_wrapped("https://example.com/docs")) == "https://example.com/docs"


def test_bing_wrapper_rejects_non_http_destination():
    assert _decode_bing_url(_wrapped("javascript:alert(1)")) == ""


def test_bing_wrapper_rejects_browser_ambiguous_authority():
    assert _decode_bing_url("https://evil.example\\@bing.com/ck/a?u=a1bad") == ""


def test_non_wrapper_result_requires_http_url():
    assert _decode_bing_url("javascript:alert(1)") == ""
