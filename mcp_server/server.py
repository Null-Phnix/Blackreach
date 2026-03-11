"""
Blackreach MCP Server

Exposes the Blackreach autonomous browser agent as Claude tool calls.
Better than WebFetch for: JS-rendered sites, paginated content,
sites with anti-bot measures, multi-step navigation.

Architecture: Submits jobs to the Blackreach HTTP server (localhost:7432),
then polls for completion. This avoids MCP tool call timeouts since Blackreach
can take 2-5 minutes per job.

Start the HTTP server first in your terminal:
  blackreach-server

Keep that terminal tab open, then use these tools normally.
"""
import time
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("blackreach")

HTTP_BASE   = "http://127.0.0.1:7432"
SUBMIT_TIMEOUT = 10    # seconds to submit job
POLL_INTERVAL  = 5     # seconds between polls
MAX_WAIT       = 600   # 10 min max wait


def _not_running_msg() -> str:
    return (
        "Blackreach HTTP server is not running. Start it first:\n\n"
        "  blackreach-server\n\n"
        "Keep that terminal tab open, then retry."
    )


def _submit(endpoint: str, **kwargs) -> str | dict:
    """Submit a job and return job_id, or error string."""
    try:
        resp = httpx.post(f"{HTTP_BASE}/{endpoint}", json=kwargs, timeout=SUBMIT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        return _not_running_msg()
    except Exception as e:
        return f"Error submitting job: {e}"


def _poll(job_id: str) -> str:
    """Poll until job completes, return formatted result string."""
    deadline = time.time() + MAX_WAIT
    dots = 0

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            resp = httpx.get(f"{HTTP_BASE}/jobs/{job_id}", timeout=SUBMIT_TIMEOUT)
            resp.raise_for_status()
            job = resp.json()
        except Exception as e:
            return f"Error polling job {job_id}: {e}"

        status = job.get("status")

        if status in ("done", "failed"):
            lines = [
                f"Success: {job.get('success')}",
                f"Pages visited: {job.get('pages_visited', 0)}",
                f"Steps taken: {job.get('steps_taken', 0)}",
            ]
            # The actual extracted content
            extracted = job.get("result") or ""
            if extracted:
                lines.append(f"\n--- EXTRACTED CONTENT ---\n{extracted}\n--- END ---")

            downloads = job.get("downloads") or []
            if downloads:
                lines.append(f"\nDownloads ({len(downloads)}):")
                for d in downloads:
                    lines.append(f"  {d}")
            errors = job.get("errors") or []
            if errors:
                lines.append("\nErrors:")
                for e in errors:
                    lines.append(f"  {e}")
            elapsed = int((job.get("finished_at", time.time()) - job.get("created_at", time.time())))
            lines.append(f"\nCompleted in ~{elapsed}s")
            return "\n".join(lines)

        # Still pending/running — keep polling
        dots = (dots + 1) % 4
        dot_str = "." * (dots + 1)
        print(f"[blackreach] Job {job_id} {status}{dot_str}", flush=True)

    return f"Timed out waiting for job {job_id} after {MAX_WAIT}s. Check /jobs/{job_id} manually."


@mcp.tool()
def blackreach_browse(goal: str, start_url: str = "") -> str:
    """
    Run the Blackreach autonomous browser agent to accomplish a goal.

    Use this instead of WebFetch when:
    - The site uses JavaScript to render content
    - You need to navigate multiple pages or handle pagination
    - The site has Cloudflare or other anti-bot protection
    - You need to interact with forms, buttons, or dynamic elements
    - WebFetch returned empty, blocked, or incomplete content

    NOTE: This can take 2-5 minutes. It submits the job and waits for completion.

    Args:
        goal: Natural language description of what to research, find, or download.
              Be specific. E.g. "Find all remote AI engineer jobs on wellfound.com
              posted in the last 7 days and return title, company, salary, and URL"
        start_url: Optional starting URL. Agent will search for the right URL if not provided.

    Returns:
        Summary of what was accomplished, pages visited, steps taken, and any downloads.
    """
    payload = {"goal": goal}
    if start_url:
        payload["start_url"] = start_url

    result = _submit("browse", **payload)
    if isinstance(result, str):
        return result  # error message

    job_id = result.get("job_id")
    if not job_id:
        return f"Unexpected response: {result}"

    return f"Job submitted: {job_id}\nWaiting for Blackreach to complete...\n\n" + _poll(job_id)


@mcp.tool()
def blackreach_search(query: str, num_results: int = 10) -> str:
    """
    Use Blackreach to perform a web search and extract structured results.

    Better than WebFetch for search because it handles JS-rendered results
    and can follow pagination. Takes 2-5 minutes.

    Args:
        query: Search query string
        num_results: How many results to return (default 10)

    Returns:
        Search results with titles, URLs, and descriptions
    """
    result = _submit("search", query=query, num_results=num_results)
    if isinstance(result, str):
        return result

    job_id = result.get("job_id")
    if not job_id:
        return f"Unexpected response: {result}"

    return f"Search job submitted: {job_id}\n\n" + _poll(job_id)


@mcp.tool()
def blackreach_scrape_jobs(
    role: str,
    site: str = "wellfound.com",
    filters: str = "remote, posted last 7 days"
) -> str:
    """
    Scrape job listings from a job board using Blackreach.

    Handles JS-rendered job boards that WebFetch can't access.
    Takes 3-8 minutes depending on the site.

    Args:
        role: Job title to search for (e.g. "AI engineer", "Python developer")
        site: Job board domain (default: wellfound.com)
        filters: Additional filters to apply (default: "remote, posted last 7 days")

    Returns:
        List of job listings with title, company, salary (if shown), location, and URL
    """
    try:
        resp = httpx.post(
            f"{HTTP_BASE}/scrape-jobs",
            params={"role": role, "site": site, "filters": filters},
            timeout=SUBMIT_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
    except httpx.ConnectError:
        return _not_running_msg()
    except Exception as e:
        return f"Error submitting job scrape: {e}"

    job_id = result.get("job_id")
    if not job_id:
        return f"Unexpected response: {result}"

    return f"Job scrape submitted: {job_id} — {role} on {site}\n\n" + _poll(job_id)


if __name__ == "__main__":
    mcp.run()
