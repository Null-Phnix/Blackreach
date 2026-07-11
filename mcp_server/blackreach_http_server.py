"""
Blackreach HTTP Server — Async Job Queue Architecture

Runs Blackreach as a persistent Flask server with full network access.
Start this ONCE from your terminal, then Claude Code's MCP can call it over localhost.

Usage:
  python /mnt/AI_Projects/Blackreach/mcp_server/blackreach_http_server.py

Runs on: http://localhost:7434  (7432 is owned by the Huginn/BlackCrawl container)

Architecture:
  - POST /browse, /search, /scrape-jobs  → returns job_id immediately (non-blocking)
  - GET  /jobs/{job_id}                  → poll for result
  - GET  /jobs                           → list all jobs
  - GET  /health                         → server status

Why async jobs?
  Claude Code MCP tool calls time out after ~30 seconds.
  Blackreach can take 2-5 minutes. The MCP tool submits the job and polls for completion.
"""
import sys
import os
import queue
import threading
import uuid
import time
from pathlib import Path
from enum import Enum

from flask import Flask, request, jsonify, send_file
from blackreach.api import BlackreachAPI, ApiConfig

app = Flask(__name__)

# Use project root relative to this file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = _PROJECT_ROOT / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Per-job page screenshots, captured each step so clients (Mimir) can show a
# live view of what the agent is doing.
_SHOT_DIR = _PROJECT_ROOT / "downloads" / "_shots"
_SHOT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Job Store ────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"


_jobs: dict[str, dict] = {}  # job_id → job dict
_job_queue: queue.Queue[str] = queue.Queue()
_jobs_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
try:
    _MAX_RETAINED_JOBS = max(
        10, int(os.environ.get("BLACKREACH_MAX_RETAINED_JOBS", "500"))
    )
except ValueError:
    _MAX_RETAINED_JOBS = 500


def _make_api(max_steps: int = 60) -> BlackreachAPI:
    return BlackreachAPI(ApiConfig(
        download_dir=DOWNLOAD_DIR,
        headless=True,
        max_steps=max_steps,
        verbose=True,
    ))


def _worker_loop():
    """Single background thread that runs jobs one at a time."""
    while True:
        job_id = _job_queue.get()
        api = None

        with _jobs_lock:
            job = _jobs.get(job_id)
            if job:
                job["status"] = JobStatus.RUNNING
                job["started_at"] = time.time()

        try:
            goal      = job["goal"]
            start_url = job.get("start_url")
            max_steps = job.get("max_steps", 60)

            api = _make_api(max_steps=max_steps)

            # Capture a page screenshot each step so clients can show a live view.
            agent = api._get_agent()
            _shot_path = _SHOT_DIR / f"{job_id}.png"

            def _grab_shot(*_args, _agent=agent, _path=_shot_path):
                try:
                    if _agent.hand is not None:
                        _agent.hand.screenshot(path=str(_path))
                except Exception:
                    pass  # best-effort; never break the run on a screenshot

            # Capture on both step phases (observe/think/step) and every action
            # (navigation/click/type). on_action fires on the agent's very first
            # navigation, so the live view fills in early instead of showing
            # "waiting" for most of a short run. Callbacks run in the agent's own
            # thread, so this is Playwright-safe.
            agent.callbacks.on_step = _grab_shot
            agent.callbacks.on_action = _grab_shot

            result = api.browse(goal=goal, start_url=start_url)

            with _jobs_lock:
                _jobs[job_id].update({
                    "status":        JobStatus.DONE,
                    "finished_at":   time.time(),
                    "success":       result.success,
                    "pages_visited": result.pages_visited,
                    "steps_taken":   result.steps_taken,
                    "downloads":     result.downloads,
                    "errors":        result.errors,
                    "session_id":    result.session_id,
                    "result":        result.result,
                })

        except Exception as e:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id].update({
                        "status":      JobStatus.FAILED,
                        "finished_at": time.time(),
                        "errors":      [str(e)],
                    })
        finally:
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass
            _job_queue.task_done()


def _start_worker():
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="blackreach-worker")
        _worker_thread.start()


def _submit_job(goal: str, start_url: str | None = None, max_steps: int = 60) -> str:
    job_id = str(uuid.uuid4())[:8]
    with _jobs_lock:
        overflow = len(_jobs) - _MAX_RETAINED_JOBS + 1
        if overflow > 0:
            terminal = sorted(
                (
                    job for job in _jobs.values()
                    if job.get("status") in (JobStatus.DONE, JobStatus.FAILED)
                ),
                key=lambda job: job.get("finished_at", job.get("created_at", 0)),
            )
            for old_job in terminal[:overflow]:
                old_id = old_job["job_id"]
                _jobs.pop(old_id, None)
                (_SHOT_DIR / f"{old_id}.png").unlink(missing_ok=True)
        _jobs[job_id] = {
            "job_id":     job_id,
            "status":     JobStatus.PENDING,
            "goal":       goal,
            "start_url":  start_url,
            "max_steps":  max_steps,
            "created_at": time.time(),
        }
        _job_queue.put(job_id)
    _start_worker()
    return job_id


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    with _jobs_lock:
        running = sum(1 for j in _jobs.values() if j["status"] == JobStatus.RUNNING)
        pending = sum(1 for j in _jobs.values() if j["status"] == JobStatus.PENDING)
        retained = len(_jobs)
    return jsonify({
        "status": "ok",
        "service": "blackreach",
        "running": running,
        "pending": pending,
        "retained_jobs": retained,
    })


@app.route("/jobs", methods=["GET"])
def list_jobs():
    with _jobs_lock:
        return jsonify(list(_jobs.values()))


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


@app.route("/jobs/<job_id>/screenshot", methods=["GET"])
def get_job_screenshot(job_id: str):
    """Latest page screenshot for a job (PNG), for a live view of the agent."""
    path = _SHOT_DIR / f"{job_id}.png"
    if not path.exists():
        return jsonify({"error": "no screenshot yet"}), 404
    resp = send_file(str(path), mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store"  # always fetch the newest frame
    return resp


@app.route("/browse", methods=["POST"])
def browse():
    data      = request.get_json(force=True)
    goal      = data.get("goal", "")
    start_url = data.get("start_url") or None
    try:
        max_steps = int(data.get("max_steps", 60))
    except (TypeError, ValueError):
        return jsonify({"error": "max_steps must be an integer"}), 400

    if not goal:
        return jsonify({"error": "goal is required"}), 400
    if not 1 <= max_steps <= 200:
        return jsonify({"error": "max_steps must be between 1 and 200"}), 400

    job_id = _submit_job(goal=goal, start_url=start_url, max_steps=max_steps)
    return jsonify({"job_id": job_id, "status": "pending"}), 202


@app.route("/search", methods=["POST"])
def search():
    data       = request.get_json(force=True)
    query      = data.get("query", "")
    try:
        num_results = int(data.get("num_results", 10))
    except (TypeError, ValueError):
        return jsonify({"error": "num_results must be an integer"}), 400

    if not query:
        return jsonify({"error": "query is required"}), 400
    if not 1 <= num_results <= 50:
        return jsonify({"error": "num_results must be between 1 and 50"}), 400

    # Primary path: Huginn /v1/seek (fast, no browser). BlackreachAPI.search()
    # is a thin Huginn client — it starts no agent unless we fall back below.
    try:
        sr = _make_api().search(query, max_results=num_results)
    except Exception:
        sr = None
    if sr and sr.results:
        return jsonify({
            "source":      sr.source,
            "query":       query,
            "results":     sr.results,
            "total_found": sr.total_found,
        }), 200

    # Fallback: agent-driven browse search when both Huginn and its direct
    # StarSearch fallback are unavailable.
    goal = (
        f"Search the web for: {query}\n"
        f"Extract the top {num_results} results.\n"
        f"For each result return: title, URL, and a brief description.\n"
        f"Format as a numbered list."
    )
    job_id = _submit_job(goal=goal)
    return jsonify({"job_id": job_id, "status": "pending", "query": query, "source": "agent-fallback"}), 202


@app.route("/scrape-jobs", methods=["POST"])
def scrape_jobs():
    role    = request.args.get("role", "AI engineer")
    site    = request.args.get("site", "wellfound.com")
    filters = request.args.get("filters", "remote")

    goal = (
        f"Go to {site} and search for '{role}' jobs.\n"
        f"Filter by: {filters}.\n"
        f"For each job listing extract: job title, company name, salary range if shown, "
        f"location/remote status, and the direct URL to the job posting.\n"
        f"Return at least 15 results formatted as a numbered list.\n"
        f"If one page doesn't work, try another URL or search approach on the same site."
    )

    job_id = _submit_job(goal=goal, start_url=f"https://{site}", max_steps=80)
    return jsonify({"job_id": job_id, "status": "pending", "role": role, "site": site}), 202


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for `blackreach-server` console script."""
    import argparse
    parser = argparse.ArgumentParser(description="Blackreach HTTP Server (Async Job Queue)")
    parser.add_argument("--port", type=int, default=7434, help="Port to listen on (default: 7434; 7432 is Huginn/BlackCrawl)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--no-banner", action="store_true", help="Suppress startup banner")
    args = parser.parse_args()

    if not args.no_banner:
        print("=" * 60)
        print("Blackreach HTTP Server (Async Job Queue)")
        print(f"Listening on http://{args.host}:{args.port}")
        print("Keep this running while using Claude Code.")
        print("Stop with Ctrl+C")
        print("=" * 60)
    _start_worker()
    app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
