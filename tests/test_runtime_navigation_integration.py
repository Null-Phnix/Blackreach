"""Real ephemeral Chromium navigation against localhost, without any model."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest
from playwright.sync_api import sync_playwright

from blackreach.agent import Agent, BrowserMode


@pytest.mark.integration
def test_lightweight_keeps_origin_relative_script_and_link(tmp_path):
    (tmp_path / "index.html").write_text(
        "<html><head><title>Source</title><script src='/app.js'></script></head>"
        "<body><a id='next' href='/next.html'>Next</a></body></html>"
    )
    (tmp_path / "app.js").write_text("window.sourceScriptLoaded = location.origin;")
    (tmp_path / "next.html").write_text("<html><title>Next source</title><body>Next</body></html>")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path)))
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                agent = Agent.__new__(Agent)
                agent.config = SimpleNamespace(use_adaptive=True)
                agent._router = SimpleNamespace(plan_for=lambda _: SimpleNamespace(mode=BrowserMode.LIGHTWEIGHT))
                agent.hand = SimpleNamespace(goto=page.goto, page=page)
                origin = f"http://127.0.0.1:{server.server_port}"
                assert agent._navigate_with_scan(origin + "/index.html") is True
                assert page.url == origin + "/index.html"
                assert page.evaluate("window.sourceScriptLoaded") == origin
                assert page.locator("#next").evaluate("node => node.href") == origin + "/next.html"
                page.locator("#next").click()
                assert page.url == origin + "/next.html"
                assert page.title() == "Next source"
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
