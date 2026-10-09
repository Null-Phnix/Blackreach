"""Controlled Linux engine proof: real Chromium + SQLite, scripted decisions.

No external website, model, account, or user browsing profile is used. This
checks engine plumbing and recovery, not autonomous model task performance.
Run: python examples/engine_recovery_demo.py
"""
import contextlib
import io
import json
import os
import sys
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

os.environ["BLACKREACH_BROWSER_BACKEND"] = "playwright"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blackreach.agent import Agent, AgentConfig
from blackreach.exceptions import ProviderError


class FixtureBrain:
    """A deterministic two-page script, explicitly not a model."""
    def __init__(self):
        self.calls = 0
        self.config = SimpleNamespace(context_size="large")

    def generate(self, system, observation):
        self.calls += 1
        if "Reference: BR-LOCAL-42" in observation:
            return json.dumps({"action": "done", "args": {
                "reason": "Read the fixture report", "result": "BR-LOCAL-42"}})
        return json.dumps({"action": "click", "args": {"selector": "#report"}})


class RejectedBrain:
    def __init__(self):
        self.calls = 0
        self.config = SimpleNamespace(context_size="large")

    def generate(self, *_):
        self.calls += 1
        error = ProviderError("fixture", "Model access denied (simulated)")
        error.recoverable = False
        raise error


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    with tempfile.TemporaryDirectory(prefix="blackreach-proof-") as root:
        root = Path(root)
        web = root / "web"
        web.mkdir()
        body = "This is a local controlled report used to verify engine state and navigation. " * 8
        (web / "index.html").write_text(f"<html><title>Fixture index</title><body><h1>Reports</h1><p>{body}</p><a id='report' href='/report.html'>Read report</a></body></html>")
        (web / "report.html").write_text(f"<html><title>Fixture report</title><body><h1>Reference: BR-LOCAL-42</h1><p>{body}</p></body></html>")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(web)))
        server.daemon_threads = True
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/index.html"
        agents = []
        try:
            # All session logs and data stay inside the disposable fixture root.
            with patch("blackreach.logging.LOG_DIR", root / "logs"), \
                 patch("blackreach.agent.STEP_PAUSE_SECONDS", 0), \
                 contextlib.redirect_stdout(io.StringIO()):
                brain = FixtureBrain()
                with patch("blackreach.agent.LLM", return_value=brain):
                    first = Agent(agent_config=AgentConfig(max_steps=1, headless=True,
                        use_adaptive=False, memory_db=root / "memory.db", download_dir=root / "downloads"))
                agents.append(first)
                stopped = first.run("Read the fixture report and return its reference", quiet=True, start_url=url)
                assert stopped["status"] == "max_steps", stopped
                assert stopped["resumable"] is True
                assert stopped["steps_taken"] == stopped["actions_taken"] == 1
                assert first.persistent_memory.load_session_state(first.session_id)["current_url"].endswith("/report.html")
                first.persistent_memory.close()

                # New agent instance and new browser read the saved SQLite state.
                with patch("blackreach.agent.LLM", return_value=brain):
                    second = Agent(agent_config=AgentConfig(max_steps=3, headless=True,
                        use_adaptive=False, memory_db=root / "memory.db", download_dir=root / "downloads"))
                agents.append(second)
                observations = []
                second.callbacks.on_observe = observations.append
                completed = second.resume(stopped["session_id"], quiet=True, max_steps=3)
                assert completed["success"] and completed["result"] == "BR-LOCAL-42", completed
                assert completed["steps_taken"] == 2 and completed["actions_taken"] == 1
                assert any("Fixture report" in observation for observation in observations)
                assert second.persistent_memory.load_session_state(stopped["session_id"]) is None

                rejected = RejectedBrain()
                with patch("blackreach.agent.LLM", return_value=rejected):
                    third = Agent(agent_config=AgentConfig(max_steps=5, headless=True,
                        use_adaptive=False, memory_db=root / "error.db", download_dir=root / "error-downloads"))
                agents.append(third)
                failed = third.run("Read this fixture", quiet=True, start_url=url)
                assert failed["status"] == "error" and failed["success"] is False, failed
                assert failed["steps_taken"] == 1 and rejected.calls == 1
                assert "Model access denied" in failed["error"]
                events = [json.loads(line) for p in (root / "logs").glob("*.jsonl") for line in p.read_text().splitlines()]
                assert any(event.get("event") == "session_end" and event.get("data", {}).get("stop_reason") == "permanent_error" for event in events)
            print(json.dumps({
                "mode": "controlled localhost Chromium; scripted decisions; no live model",
                "checkpoint": {key: stopped[key] for key in ("status", "steps_taken", "actions_taken", "resumable")},
                "fresh_agent_resume": {key: completed[key] for key in ("status", "steps_taken", "actions_taken", "result")},
                "provider_rejection": {key: failed[key] for key in ("status", "stop_reason", "steps_taken", "error")},
                "scripted_decision_calls": brain.calls,
                "rejected_provider_calls": rejected.calls,
                "checks_passed": True,
            }, indent=2))
        finally:
            for agent in agents:
                if agent.hand:
                    agent.hand.sleep()
                agent.persistent_memory.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
