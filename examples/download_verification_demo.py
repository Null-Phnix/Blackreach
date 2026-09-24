"""Offline action-boundary demo. No browser, network, model, or real user state.

Run from the source checkout: python examples/download_verification_demo.py
The transport is a fixture; verification and download bookkeeping use the actual
AgentActionsMixin. This is not an autonomous browsing benchmark.
"""

import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blackreach.agent_actions import AgentActionsMixin
from blackreach.content_verify import ContentVerifier


def fixture_pdf():
    """Create a one-page PDF with a correct cross-reference table."""
    stream = b"BT /F1 12 Tf 30 100 Td (Blackreach verification fixture) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 150] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data = b"%PDF-1.4\n% " + b"fixture padding " * 80 + b"\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(number).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return (
        data
        + b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref).encode()
        + b"\n%%EOF\n"
    )


def run_case(directory, name, data, expected="pdf"):
    path = directory / name
    if data is not None:
        path.write_bytes(data)
    result = dict(
        path=str(path),
        filename=name,
        size=len(data or b""),
        hash=hashlib.sha256(data or b"").hexdigest(),
        url="https://example.org/download",
    )
    memory = Mock()
    memory.has_downloaded.return_value = False
    agent = SimpleNamespace(
        hand=SimpleNamespace(
            download_link=lambda url: result, get_url=lambda: "https://example.org/article"
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
    try:
        outcome = AgentActionsMixin._execute_action(
            agent, "download", {"url": result["url"], "expected_type": expected}
        )
        status = outcome.get("reason", "accepted")
    except Exception as exc:
        status = type(exc).__name__ + ": " + str(exc)
    return dict(
        case=name,
        expected=expected,
        status=status,
        recorded=agent._record_download.call_count,
        retained=path.exists(),
    )


def main():
    html = b"<!DOCTYPE html><html><body>" + b"Article landing page. " * 100 + b"</body></html>"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("readme.txt", "Not a PDF. " * 200)
    with tempfile.TemporaryDirectory(prefix="blackreach-verification-demo-") as directory:
        rows = [
            run_case(Path(directory), *case)
            for case in [
                ("landing.html", html),
                ("extensionless", html),
                ("wrong.zip", archive.getvalue()),
                ("missing.pdf", None),
                ("valid.pdf", fixture_pdf()),
                ("requested-page.html", html, "html"),
            ]
        ]
    print("OFFLINE FIXTURE DEMO: real action handler; simulated transport; no LLM/browser.")
    print(f'{"Artifact":24} {"Expected":10} {"Result":18} {"Recorded":9} Retained')
    for row in rows:
        print(
            f'{row["case"]:24} {row["expected"]:10} {row["status"]:18} {row["recorded"]:<9} {row["retained"]}'
        )
    print("\nFormat/structure validation does not prove document identity or relevance.")
    print(json.dumps(rows, indent=2))
    expected = ["wrong_format", "wrong_format", "wrong_format", "invalid", "accepted", "accepted"]
    return (
        0
        if [r["status"] for r in rows] == expected
        and [r["recorded"] for r in rows] == [0, 0, 0, 0, 1, 1]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
