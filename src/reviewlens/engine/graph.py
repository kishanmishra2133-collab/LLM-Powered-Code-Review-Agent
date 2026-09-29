"""LangGraph review workflow definition and runner."""

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from reviewlens.clients.gemini import GeminiClient
from reviewlens.clients.github import GitHubClient
from reviewlens.config import ReviewConfig
from reviewlens.engine.stages.annotate import (
    LineCoordinate,
    LineLookup,
    parse_diff,
)
from reviewlens.engine.stages.filter import filter_files
from reviewlens.engine.stages.finalize import finalize_stage
from reviewlens.engine.stages.review import review_stage
from reviewlens.engine.stages.validate import validate_stage
from reviewlens.engine.stages.verify import verify_stage
from reviewlens.engine.state import ReviewState
from reviewlens.models import DiffFile, PRMeta, PRRef, ReviewResult, Usage


def _build_lookup_from_files(files: list[DiffFile]) -> LineLookup:
    coords: dict[str, LineCoordinate] = {}
    for file_idx, f in enumerate(files, start=1):
        for hunk_idx, h in enumerate(f.hunks, start=1):
            for diff_line in h.lines:
                resolved_line = diff_line.new_line_no if diff_line.type in ("added", "context") else diff_line.old_line_no
                if resolved_line is None:
                    continue
                side: Literal["RIGHT", "LEFT"] = "RIGHT" if diff_line.type in ("added", "context") else "LEFT"
                coords[diff_line.id] = LineCoordinate(
                    file_idx=file_idx,
                    path=f.path,
                    line=resolved_line,
                    side=side,
                    hunk_idx=hunk_idx,
                    line_id=diff_line.id,
                    content=diff_line.content,
                )
    return LineLookup(coords)


def build_review_graph(
    github_client: GitHubClient | None = None,
    gemini_client: GeminiClient | None = None,
    raw_diff: str | None = None,
) -> CompiledStateGraph[ReviewState, Any, Any, Any]:
    """Compile the LangGraph workflow with fetch, filter, annotate, review, validate, verify, finalize."""

    async def fetch_node(state: ReviewState) -> dict[str, Any]:
        nonlocal raw_diff
        meta = state.meta
        diff_text = raw_diff

        if diff_text is None and github_client is not None:
            fetched_meta, head_sha = await github_client.get_pr_meta(state.pr)
            meta = fetched_meta
            if not state.pr.head_sha:
                # Update head SHA on PRRef if missing
                updated_pr = PRRef(
                    owner=state.pr.owner,
                    repo=state.pr.repo,
                    number=state.pr.number,
                    head_sha=head_sha,
                )
                state = state.model_copy(update={"pr": updated_pr})
            diff_text = await github_client.get_pr_diff(state.pr)

        files, _ = parse_diff(diff_text or "")
        return {"meta": meta, "files": files, "pr": state.pr}

    async def filter_node(state: ReviewState) -> dict[str, Any]:
        kept, skipped = filter_files(state.files)
        return {"files": kept, "skipped": skipped}

    async def annotate_node(state: ReviewState) -> dict[str, Any]:
        # Stable line IDs are already assigned during parse_diff
        return {"files": state.files}

    async def review_node(state: ReviewState) -> dict[str, Any]:
        if gemini_client is None or not state.files:
            return {"raw_findings": [], "usage": state.usage}

        raw_findings, node_usage = await review_stage(state.files, state.meta, gemini_client)
        new_usage = state.usage.model_copy()
        new_usage.nodes["review"] = node_usage
        return {"raw_findings": raw_findings, "usage": new_usage}

    async def validate_node(state: ReviewState) -> dict[str, Any]:
        lookup = _build_lookup_from_files(state.files)
        findings, dropped = validate_stage(state.raw_findings, lookup, state.config)
        return {"findings": findings, "dropped": state.dropped + dropped}

    def route_after_validate(state: ReviewState) -> str:
        if state.config.verify and len(state.findings) > 0:
            return "verify"
        return "finalize"

    async def verify_node(state: ReviewState) -> dict[str, Any]:
        if gemini_client is None or not state.findings:
            return {"findings": state.findings, "dropped": state.dropped}

        verified, dropped, node_usage = await verify_stage(state.findings, state.files, gemini_client)
        new_usage = state.usage.model_copy()
        new_usage.nodes["verify"] = node_usage
        return {"findings": verified, "dropped": state.dropped + dropped, "usage": new_usage}

    async def finalize_node(state: ReviewState) -> dict[str, Any]:
        # Compute final usage and redaction
        result = finalize_stage(state)
        return {
            "findings": result.findings,
            "dropped": result.dropped,
            "skipped": result.skipped,
            "usage": result.usage,
        }

    builder = StateGraph(ReviewState)
    builder.add_node("fetch", fetch_node)
    builder.add_node("filter", filter_node)
    builder.add_node("annotate", annotate_node)
    builder.add_node("review", review_node)
    builder.add_node("validate", validate_node)
    builder.add_node("verify", verify_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "fetch")
    builder.add_edge("fetch", "filter")
    builder.add_edge("filter", "annotate")
    builder.add_edge("annotate", "review")
    builder.add_edge("review", "validate")
    builder.add_conditional_edges(
        "validate",
        route_after_validate,
        {"verify": "verify", "finalize": "finalize"},
    )
    builder.add_edge("verify", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


async def run_review_workflow(
    pr: PRRef,
    config: ReviewConfig | None = None,
    github_client: GitHubClient | None = None,
    gemini_client: GeminiClient | None = None,
    raw_diff: str | None = None,
    meta: PRMeta | None = None,
) -> ReviewResult:
    """Run the complete review workflow to completion and return ReviewResult."""
    cfg = config or ReviewConfig()
    initial_state = ReviewState(pr=pr, config=cfg, meta=meta, usage=Usage())

    graph = build_review_graph(
        github_client=github_client,
        gemini_client=gemini_client,
        raw_diff=raw_diff,
    )

    final_state_dict = await graph.ainvoke(initial_state)
    final_state = ReviewState.model_validate(final_state_dict)
    return finalize_stage(final_state)
