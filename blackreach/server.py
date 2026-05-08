"""
Blackreach REST API Server

FastAPI wrapper around the Blackreach agent programmatic API.
Provides HTTP endpoints for browse, search, download, and page fetch.

Usage:
    blackreach serve                    # Start server on default port
    blackreach serve --port 8080        # Custom port

Or programmatically:
    from blackreach.server import create_app
    app = create_app()
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from blackreach.api import browse, search, download, get_page, BrowseResult, SearchResult, DownloadResult

# ─── Config ─────────────────────────────────────────────────────────────────

DEFAULT_PORT = int(os.getenv("BLACKREACH_PORT", "7433"))


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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Blackreach API",
        description="Autonomous browser agent via HTTP",
        version="5.0.0-beta.1",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "5.0.0-beta.1"}

    @app.post("/v1/browse", response_model=ApiResponse)
    async def browse_endpoint(req: BrowseRequest) -> ApiResponse:
        """Run the Blackreach agent with a goal."""
        import time
        start = time.time()
        try:
            # browse() is sync and may take minutes — run in threadpool
            loop = asyncio.get_event_loop()
            result: BrowseResult = await loop.run_in_executor(
                None,
                browse,
                req.goal,
            )
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
                },
                elapsed_ms=elapsed,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/search", response_model=ApiResponse)
    async def search_endpoint(req: SearchRequest) -> ApiResponse:
        """Search the web."""
        import time
        start = time.time()
        try:
            loop = asyncio.get_event_loop()
            result: SearchResult = await loop.run_in_executor(
                None,
                search,
                req.query,
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
            loop = asyncio.get_event_loop()
            results: list[DownloadResult] = await loop.run_in_executor(
                None,
                download,
                req.query,
                req.count,
            )
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
            loop = asyncio.get_event_loop()
            result: dict = await loop.run_in_executor(None, get_page, req.url)
            elapsed = int((time.time() - start) * 1000)
            return ApiResponse(success=True, data=result, elapsed_ms=elapsed)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# ─── CLI Entry ───────────────────────────────────────────────────────────────

def main(host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
