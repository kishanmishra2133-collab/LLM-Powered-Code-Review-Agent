"""FastAPI web API serving the demo page and SSE review streams."""

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from reviewlens.cache import DailyBudgetTracker, ReviewCache
from reviewlens.clients.gemini import GeminiClient
from reviewlens.clients.github import GitHubClient, PRNotFoundError
from reviewlens.config import ReviewConfig, Settings
from reviewlens.engine.graph import run_review_workflow
from reviewlens.models import ReviewResult

app = FastAPI(
    title="ReviewLens API",
    description="Backend for the ReviewLens code review agent demo.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()
review_cache = ReviewCache(settings.cache_dir)
budget_tracker = DailyBudgetTracker(
    budget_file=Path("data/budget.json"),
    daily_cap_usd=settings.daily_budget_usd,
)


def _sse_format(event: str, data: Any) -> str:
    payload = json.dumps(data) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {payload}\n\n"


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint and budget status."""
    return {
        "status": "ok",
        "budget_exhausted": budget_tracker.is_exhausted(),
        "daily_spend_usd": round(budget_tracker.current_spend(), 4),
        "daily_cap_usd": budget_tracker.daily_cap_usd,
    }


@app.get("/api/examples")
async def list_examples() -> list[dict[str, Any]]:
    """Return curated example PRs with pre-computed cached results."""
    examples_file = Path("data/cache/examples/examples.json")
    if examples_file.is_file():
        try:
            with open(examples_file, encoding="utf-8") as f:
                data: list[dict[str, Any]] = json.load(f)
                return data
        except Exception:
            pass

    return [
        {
            "id": "example-bug",
            "title": "Fix off-by-one error in pagination slice",
            "repo": "psf/requests",
            "pr_url": "https://github.com/psf/requests/pull/6000",
            "description": "A PR with a concrete bug and high-confidence finding.",
        },
        {
            "id": "example-clean",
            "title": "Update README documentation with installation steps",
            "repo": "pallets/flask",
            "pr_url": "https://github.com/pallets/flask/pull/5000",
            "description": "A clean PR with 0 findings, showing precision over noise.",
        },
        {
            "id": "example-large",
            "title": "Refactor auth and bump dependencies",
            "repo": "tiangolo/fastapi",
            "pr_url": "https://github.com/tiangolo/fastapi/pull/4000",
            "description": "A larger PR with lockfile noise automatically skipped.",
        },
    ]


class ReviewRequest(BaseModel):
    """Payload for initiating a code review."""

    target: str = ""
    pr_url: str = ""
    code: str | None = None
    filename: str | None = None
    files: list[dict[str, str]] | None = None
    verify: bool = True
    model: str = "gemini-3-flash-preview"


async def _run_review_stream(
    target_input: str,
    verify: bool = True,
    model: str = "gemini-3-flash-preview",
    code_content: str | None = None,
    filename: str | None = None,
    uploaded_files: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Shared generator for streaming review events."""
    current_settings = Settings()
    if not current_settings.gemini_api_key or current_settings.gemini_api_key.strip().startswith("your_"):
        yield _sse_format(
            "error",
            {
                "code": "API_KEY_MISSING",
                "message": "GEMINI_API_KEY is not configured or is a placeholder in .env. Please set a valid Gemini API key.",
            },
        )
        return

    github_client = GitHubClient(token=current_settings.github_token or None)
    gemini_client = GeminiClient(api_key=current_settings.gemini_api_key, model_id=model)
    config = ReviewConfig(verify=verify, model_id=model)

    # 1. Resolve Target
    try:
        from reviewlens.resolver import resolve_target

        pr_ref, meta, raw_diff = await resolve_target(
            target_input=target_input,
            github_client=github_client,
            code_content=code_content,
            filename=filename,
            uploaded_files=uploaded_files,
        )
    except Exception as err:
        yield _sse_format("error", {"code": "INVALID_URL", "message": str(err)})
        return

    # 2. Check Cache
    if raw_diff is None:
        cached_result = review_cache.get(pr_ref, config.review_prompt_version)
        if cached_result:
            yield _sse_format("stage", {"name": "cache", "status": "hit"})
            for finding in cached_result.findings:
                yield _sse_format("finding", finding.model_dump(mode="json"))
            yield _sse_format("summary", cached_result.model_dump(mode="json"))
            yield _sse_format("done", {})
            return

    # 3. Run review workflow
    try:
        yield _sse_format("stage", {"name": "fetch", "status": "running"})

        result: ReviewResult = await run_review_workflow(
            pr=pr_ref,
            config=config,
            github_client=github_client,
            gemini_client=gemini_client,
            raw_diff=raw_diff,
            meta=meta,
        )

        # Cache the result if applicable
        if pr_ref.head_sha and raw_diff is None:
            review_cache.set(pr_ref, config.review_prompt_version, result)

        # Stream findings and summary
        for f in result.findings:
            yield _sse_format("finding", f.model_dump(mode="json"))

        yield _sse_format("summary", result.model_dump(mode="json"))
        yield _sse_format("done", {})

    except PRNotFoundError:
        yield _sse_format(
            "error",
            {
                "code": "PR_NOT_FOUND",
                "message": "Resource not found or repository is private. If this is a private repo, ensure your GITHUB_TOKEN is set in .env with 'repo' scope.",
            },
        )
    except Exception as exc:
        yield _sse_format(
            "error",
            {"code": "INTERNAL_ERROR", "message": f"Review failed: {exc}"},
        )


@app.get("/api/review")
async def stream_review_get(
    target: str = Query("", description="PR URL, GitHub file/repo/commit URL, or local path"),
    pr_url: str | None = Query(None, description="Legacy parameter for PR URL"),
    code: str | None = Query(None, description="Direct code snippet text"),
    filename: str | None = Query(None, description="Filename for direct code snippet"),
    verify: bool = Query(True, description="Enable verification node"),
    model: str = Query("gemini-3-flash-preview", description="Model ID"),
) -> StreamingResponse:
    """Stream review execution progress and findings via SSE (GET)."""
    effective_target = target or pr_url or ""
    return StreamingResponse(
        _run_review_stream(
            target_input=effective_target,
            verify=verify,
            model=model,
            code_content=code,
            filename=filename,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/review")
async def stream_review_post(req: ReviewRequest) -> StreamingResponse:
    """Stream review execution progress and findings via SSE (POST for large snippets/files)."""
    effective_target = req.target or req.pr_url or ""
    return StreamingResponse(
        _run_review_stream(
            target_input=effective_target,
            verify=req.verify,
            model=req.model,
            code_content=req.code,
            filename=req.filename,
            uploaded_files=req.files,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Mount static files for web frontend
web_dir = Path("web")
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory="web", html=True), name="web")
