"""Bounded regressions for CVE-2026-85999 and CVE-2026-86000."""

import subprocess
import sys

import pytest

_SELECTOR_PROBE = r'''
import sys
from soupsieve import SelectorSyntaxError
from blackreach.bulk_fetcher import FetchResult

kind = sys.argv[1]
result = FetchResult(
    url='https://example.test', status=200,
    html='<div class="note"><span data-code="one two">kept</span></div>',
)
selector = {
    'control': 'div.note > span[data-code="one two"]',
    'value': '[a=' + 'a' * 100000,
    'identifier': 'a' * 100000 + '!',
    'whitespace': 'div' + ' ' * 100000 + 'span',
    'comments': 'div ' + '/*x*/' * 20000 + ' span',
}[kind]

try:
    nodes = result.soup().select(selector)
except SelectorSyntaxError:
    assert kind in ('identifier', 'value'), 'A valid selector was rejected'
else:
    assert kind not in ('identifier', 'value'), 'A malformed selector was accepted'
    assert [node.get_text() for node in nodes] == ['kept']
'''


@pytest.mark.parametrize("kind", ["control", "identifier", "value", "whitespace", "comments"])
def test_fetch_result_selector_processing_is_bounded(kind):
    # A subprocess can be killed even while the regex engine holds the GIL.
    # Ten seconds allows cold imports on CI; patched parsing is normally fast.
    result = subprocess.run(
        [sys.executable, "-c", _SELECTOR_PROBE, kind],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
