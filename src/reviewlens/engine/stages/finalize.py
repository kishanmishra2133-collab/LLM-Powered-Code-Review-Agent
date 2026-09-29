"""Finalize stage: redacts secrets, calculates total metrics, and builds ReviewResult."""

from reviewlens.engine.state import ReviewState
from reviewlens.models import Finding, ReviewResult
from reviewlens.security import redact_secrets


def finalize_stage(state: ReviewState) -> ReviewResult:
    """Sanitize findings, sum usage metrics, and create the final ReviewResult."""
    sanitized_findings: list[Finding] = []

    for f in state.findings:
        sanitized = f.model_copy(
            update={
                "title": redact_secrets(f.title),
                "body": redact_secrets(f.body),
                "suggestion": redact_secrets(f.suggestion) if f.suggestion else None,
            }
        )
        sanitized_findings.append(sanitized)

    # Compute aggregate usage across all nodes
    total_prompt = sum(n.prompt_tokens for n in state.usage.nodes.values())
    total_candidates = sum(n.candidates_tokens for n in state.usage.nodes.values())
    total_tokens = sum(n.total_tokens for n in state.usage.nodes.values())
    total_cost = sum(n.cost_usd for n in state.usage.nodes.values())
    total_latency = sum(n.latency_ms for n in state.usage.nodes.values())

    usage = state.usage.model_copy(
        update={
            "prompt_tokens": total_prompt,
            "candidates_tokens": total_candidates,
            "total_tokens": total_tokens,
            "cost_usd": round(total_cost, 6),
            "latency_ms": total_latency,
        }
    )

    finding_count = len(sanitized_findings)
    dropped_count = len(state.dropped)
    skipped_count = len(state.skipped)

    summary = (
        f"Review complete: {finding_count} finding{'s' if finding_count != 1 else ''}, "
        f"{dropped_count} dropped, {skipped_count} skipped file{'s' if skipped_count != 1 else ''}. "
        f"Latency: {usage.latency_ms}ms."
    )

    return ReviewResult(
        pr=state.pr,
        meta=state.meta,
        findings=sanitized_findings,
        dropped=state.dropped,
        skipped=state.skipped,
        usage=usage,
        summary=summary,
    )
