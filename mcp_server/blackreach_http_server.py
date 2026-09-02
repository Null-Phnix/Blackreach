"""
Blackreach HTTP Server — Async Job Queue Architecture

Runs Blackreach as a persistent Flask server with full network access.
Start this ONCE from your terminal, then Claude Code's MCP can call it over localhost.

Usage:
  python -m mcp_server.blackreach_http_server

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
import hmac
import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from enum import Enum
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from blackreach.api import ApiConfig, BlackreachAPI

app = Flask(__name__)
logger = logging.getLogger(__name__)


def _load_api_key() -> str:
    direct = os.environ.get("BLACKREACH_API_KEY", "").strip()
    if direct:
        return direct
    key_file = os.environ.get("BLACKREACH_API_KEY_FILE")
    if not key_file:
        return ""
    try:
        token = Path(key_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read BLACKREACH_API_KEY_FILE {key_file}: {exc}") from exc
    if not token:
        raise RuntimeError(f"BLACKREACH_API_KEY_FILE {key_file} is empty")
    return token


_API_KEY = _load_api_key()


@app.before_request
def authenticate_request():
    """Health stays probeable; every stateful or data-bearing route is authenticated."""
    if request.path == "/health" or not _API_KEY:
        return None
    authorization = request.headers.get("Authorization", "")
    scheme, _, candidate = authorization.partition(" ")
    if scheme.lower() != "bearer" or not candidate or not hmac.compare_digest(candidate, _API_KEY):
        return jsonify({"error": "unauthorized", "code": "unauthorized"}), 401
    return None

# Use project root relative to this file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = _PROJECT_ROOT / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Per-job page screenshots, captured each step so clients (Mimir) can show a
# live view of what the agent is doing.
_SHOT_DIR = _PROJECT_ROOT / "downloads" / "_shots"
_SHOT_DIR.mkdir(parents=True, exist_ok=True)
_JOB_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def _job_screenshot_path(job_id: str) -> Path:
    """Return the owned screenshot path for one generated job identifier."""
    if not _JOB_ID_RE.fullmatch(job_id):
        raise ValueError("invalid job id")
    return _SHOT_DIR / f"{job_id}.png"


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
_STATE_FILE = Path(
    os.environ.get(
        "BLACKREACH_JOB_STATE_FILE",
        "~/.local/state/blackreach/jobs.json",
    )
).expanduser()
_state_error: str | None = None
try:
    _MAX_RETAINED_JOBS = max(
        10, int(os.environ.get("BLACKREACH_MAX_RETAINED_JOBS", "500"))
    )
except ValueError:
    _MAX_RETAINED_JOBS = 500


class JobStateError(RuntimeError):
    """The on-disk agent job journal could not be read or committed."""


@app.errorhandler(JobStateError)
def handle_job_state_error(_error):
    return jsonify({
        "error": "agent job journal is unavailable",
        "code": "job_store_unavailable",
    }), 503


def _persist_jobs_locked() -> None:
    """Atomically persist the current job snapshot. Caller holds _jobs_lock."""
    global _state_error
    if _state_error:
        raise JobStateError(_state_error)

    temp_path = None
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp_path = _STATE_FILE.with_name(
            f".{_STATE_FILE.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        payload = {
            "version": 1,
            "jobs": list(_jobs.values()),
        }
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temp_path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, _STATE_FILE)
        _STATE_FILE.chmod(0o600)
        directory_descriptor = os.open(
            _STATE_FILE.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except (OSError, TypeError, ValueError) as exc:
        _state_error = "agent job journal is not writable"
        logger.exception("Could not persist Blackreach job state to %s", _STATE_FILE)
        try:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise JobStateError(_state_error) from exc


def _persist_background_update_locked() -> None:
    """Persist worker progress while keeping an already-running job alive."""
    try:
        _persist_jobs_locked()
    except JobStateError:
        # Health reports the degraded store. Killing the in-flight browser here
        # would lose more information than allowing it to finish in memory.
        pass


def _load_jobs() -> None:
    """Load retained results and mark interrupted work explicitly failed."""
    global _state_error
    if not _STATE_FILE.exists():
        return

    try:
        payload = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("unsupported agent job journal schema")
        records = payload.get("jobs", [])
        if not isinstance(records, list):
            raise ValueError("jobs must be an array")

        loaded = {}
        recovered = False
        now = time.time()
        for record in records:
            if not isinstance(record, dict) or not record.get("job_id"):
                raise ValueError("invalid agent job journal record")
            job = dict(record)
            if not isinstance(job["job_id"], str) or not _JOB_ID_RE.fullmatch(job["job_id"]):
                raise ValueError("invalid agent job id")
            if job.get("status") not in {
                JobStatus.PENDING,
                JobStatus.RUNNING,
                JobStatus.DONE,
                JobStatus.FAILED,
            }:
                raise ValueError("invalid agent job status")
            if job.get("status") in (JobStatus.PENDING, JobStatus.RUNNING):
                job.update({
                    "status": JobStatus.FAILED,
                    "finished_at": now,
                    "success": False,
                    "error_code": "service_restarted",
                    "errors": ["Blackreach restarted before this job completed"],
                })
                recovered = True
            loaded[str(job["job_id"])] = job

        retained = sorted(
            loaded.values(),
            key=lambda job: job.get("finished_at", job.get("created_at", 0)),
        )[-_MAX_RETAINED_JOBS:]
        _jobs.update({str(job["job_id"]): job for job in retained})
        if recovered or len(retained) != len(loaded):
            with _jobs_lock:
                _persist_jobs_locked()
    except (OSError, ValueError, TypeError, json.JSONDecodeError, JobStateError):
        _state_error = "agent job journal could not be loaded"
        logger.exception("Could not load Blackreach job state from %s", _STATE_FILE)


_load_jobs()


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
                _persist_background_update_locked()

        try:
            goal      = job["goal"]
            start_url = job.get("start_url")
            max_steps = job.get("max_steps", 60)

            api = _make_api(max_steps=max_steps)

            # Capture a page screenshot each step so clients can show a live view.
            agent = api._get_agent()
            _shot_path = _job_screenshot_path(job_id)

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
                _persist_background_update_locked()

        except Exception as e:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id].update({
                        "status":      JobStatus.FAILED,
                        "finished_at": time.time(),
                        "errors":      [str(e)],
                    })
                    _persist_background_update_locked()
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
    removed_job_ids = []
    with _jobs_lock:
        previous_jobs = dict(_jobs)
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
                removed_job_ids.append(old_id)
        _jobs[job_id] = {
            "job_id":     job_id,
            "status":     JobStatus.PENDING,
            "goal":       goal,
            "start_url":  start_url,
            "max_steps":  max_steps,
            "created_at": time.time(),
        }
        try:
            _persist_jobs_locked()
        except JobStateError:
            _jobs.clear()
            _jobs.update(previous_jobs)
            raise
        _job_queue.put(job_id)
    for old_id in removed_job_ids:
        _job_screenshot_path(old_id).unlink(missing_ok=True)
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
        "job_store": "degraded" if _state_error else "ok",
        "job_store_persistent": True,
    })


@app.route("/jobs", methods=["GET"])
def list_jobs():
    with _jobs_lock:
        return jsonify(list(_jobs.values()))


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    with _jobs_lock:
        stored_job = _jobs.get(job_id)
        job = dict(stored_job) if stored_job is not None else None
    if job is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


@app.route("/jobs/<job_id>/screenshot", methods=["GET"])
def get_job_screenshot(job_id: str):
    """Latest page screenshot for a job (PNG), for a live view of the agent."""
    with _jobs_lock:
        stored_job = _jobs.get(job_id)
        owned_id = stored_job.get("job_id") if isinstance(stored_job, dict) else None
    if not isinstance(owned_id, str) or not _JOB_ID_RE.fullmatch(owned_id):
        return jsonify({"error": "job not found"}), 404
    response = send_from_directory(
        _SHOT_DIR,
        f"{owned_id}.png",
        mimetype="image/png",
    )
    response.headers["Cache-Control"] = "no-store"  # always fetch the newest frame
    return response


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

    from waitress import serve

    parser = argparse.ArgumentParser(description="Blackreach HTTP Server (Async Job Queue)")
    parser.add_argument("--port", type=int, default=7434, help="Port to listen on (default: 7434; 7432 is Huginn/BlackCrawl)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--threads", type=int, default=4, choices=range(2, 33), metavar="2-32", help="HTTP worker threads (default: 4)")
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
    serve(app, host=args.host, port=args.port, threads=args.threads)


if __name__ == "__main__":
    main()
