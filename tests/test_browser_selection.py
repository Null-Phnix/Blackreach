"""Backend policy tests that do not allocate a browser session."""

from blackreach.browser import _choose_backend


def test_explicit_starsearch_is_never_downgraded_by_availability_probe():
    assert _choose_backend("starsearch", starsearch_available=False) == "starsearch"


def test_auto_uses_starsearch_when_available():
    assert _choose_backend("auto", starsearch_available=True) == "starsearch"


def test_auto_and_explicit_playwright_keep_compatibility_fallback():
    assert _choose_backend("auto", starsearch_available=False) == "playwright"
    assert _choose_backend("playwright", starsearch_available=True) == "playwright"
