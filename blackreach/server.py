"""
Blackreach REST API Server

FastAPI wrapper around the Blackreach agent programmatic API.
Provides HTTP endpoints for browse, search, download, and page fetch.

Usage:
    blackreach serve                    # Loopback only, default port
    blackreach serve --port 8080        # Custom port
    # Listening beyond loopback requires BLACKREACH_API_KEY.

Or programmatically:
    from blackreach.server import create_app
    app = create_app()
"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from blackreach import __version__
from blackreach.api import (
    ApiConfig,
    BlackreachAPI,
    BrowseResult,
    download,
    get_page,
    safe_browse_error,
    search,
)

# ─── Config ─────────────────────────────────────────────────────────────────

DEFAULT_PORT = int(os.getenv("BLACKREACH_PORT", "7433"))
DEFAULT_HOST = "127.0.0.1"


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class BrowseRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="The goal for the agent to accomplish")
    start_url: str = Field("", description="Optional starting URL")
    max_steps: int = Field(50, ge=1, le=200, description="Maximum steps before giving up")
    headless: bool = Field(False, description="Run browser headless")
    verbose: bool = Field(False, description="Verbose logging")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    num_results: int = Field(10, ge=1, le=50)


class DownloadRequest(BaseModel):
    query: str = Field(..., min_length=1, description="What to download")
    count: int = Field(1, ge=1, le=20)


class PageRequest(BaseModel):
    url: str = Field(..., min_length=1, description="URL to fetch")


class ApiResponse(BaseModel):
    success: bool
    data: dict[str, Any]
    elapsed_ms: int


# ─── App Factory ─────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: log startup/shutdown."""
    yield
    # Cleanup handled by agent internals


def _load_api_key() -> str:
    """Return the configured bearer token, or empty when auth is not configured.

    A configured key file that cannot be read fails closed. An unset key leaves
    loopback use open, matching the local agent gateway.
    """
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


def _is_loopback_host(host: str) -> bool:
    """True only for hosts that cannot accept off-machine connections."""
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_loopback_host_header(host_header: str) -> bool:
    """True when an HTTP Host header names this machine (``host[:port]``)."""
    if not host_header:
        return False
    try:
        hostname = urlsplit(f"//{host_header}").hostname
    except ValueError:
        return False
    return bool(hostname) and _is_loopback_host(hostname)


def ensure_network_bind_requires_api_key(host: str) -> None:
    """Refuse to expose the agent API on a routable address without a token."""
    if _is_loopback_host(host):
        return
    if not _load_api_key():
        raise RuntimeError(
            "Refusing to listen on a non-loopback address without BLACKREACH_API_KEY"
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Blackreach API",
        description="Autonomous browser agent via HTTP",
        version="5.0.0-beta.2",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def authenticate_request(request: Request, call_next):
        """Health stays probeable. With a key, data routes need the bearer token;
        without one, they only answer requests addressed to a loopback Host."""
        if request.url.path == "/health":
            return await call_next(request)
        try:
            api_key = _load_api_key()
        except RuntimeError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=503)
        if not api_key:
            # Without a key the only protection is that the server is bound to
            # loopback. A web page can still reach 127.0.0.1 by pointing its
            # own domain there (DNS rebinding); its requests then carry that
            # domain in Host, so only loopback Host names are accepted.
            if not _is_loopback_host_header(request.headers.get("host", "")):
                return JSONResponse(
                    {"detail": "Host not allowed without BLACKREACH_API_KEY"},
                    status_code=421,
                )
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        scheme, _, candidate = authorization.partition(" ")
        if (
            scheme.lower() != "bearer"
            or not candidate
            or not hmac.compare_digest(candidate, api_key)
        ):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/browse", response_model=ApiResponse)
    async def browse_endpoint(req: BrowseRequest) -> ApiResponse:
        """Run the Blackreach agent with a goal."""
        import time
        start = time.time()
        try:
            def run_browse() -> BrowseResult:
                with BlackreachAPI(ApiConfig(
                    headless=req.headless,
                    max_steps=req.max_steps,
                    verbose=req.verbose,
                )) as api:
                    return api.browse(req.goal, start_url=req.start_url or None)

            result = await asyncio.to_thread(run_browse)
            elapsed = int((time.time() - start) * 1000)
            return ApiResponse(
                success=result.success,
                data={
                    "goal": result.goal,
                    "result": result.result,
                    "downloads": result.downloads,
                    "pages_visited": result.pages_visited,
                    "steps_taken": result.steps_taken,
                    "errors": result.errors,
                    "session_id": result.session_id,
                    "metadata": result.metadata,
                    **result.outcome(),
                },
                elapsed_ms=elapsed,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_browse_error(e)) from None

    @app.post("/v1/search", response_model=ApiResponse)
    async def search_endpoint(req: SearchRequest) -> ApiResponse:
        """Search the web."""
        import time
        start = time.time()
        try:
            result = await asyncio.to_thread(
                search, req.query, max_results=req.num_results
            )
            elapsed = int((time.time() - start) * 1000)
            return ApiResponse(
                success=True,
                data={
                    "query": result.query,
                    "results": result.results,
                    "source": result.source,
                    "total_found": result.total_found,
                },
                elapsed_ms=elapsed,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/download", response_model=ApiResponse)
    async def download_endpoint(req: DownloadRequest) -> ApiResponse:
        """Download files matching a query."""
        import time
        start = time.time()
        try:
            results = await asyncio.to_thread(download, req.query, req.count)
            elapsed = int((time.time() - start) * 1000)
            return ApiResponse(
                success=all(r.success for r in results),
                data={
                    "query": req.query,
                    "downloads": [
                        {
                            "success": r.success,
                            "url": r.url,
                            "filename": r.filename,
                            "path": r.path,
                            "size": r.size,
                            "error": r.error,
                        }
                        for r in results
                    ],
                },
                elapsed_ms=elapsed,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/page", response_model=ApiResponse)
    async def page_endpoint(req: PageRequest) -> ApiResponse:
        """Fetch raw page data."""
        import time
        start = time.time()
        try:
            result = await asyncio.to_thread(get_page, req.url)
            elapsed = int((time.time() - start) * 1000)
            return ApiResponse(success=True, data=result, elapsed_ms=elapsed)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# ─── CLI Entry ───────────────────────────────────────────────────────────────

def main(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    import uvicorn
    ensure_network_bind_requires_api_key(host)
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
