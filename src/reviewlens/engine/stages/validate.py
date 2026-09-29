"""Validation stage: resolves line coordinates, dedupes, thresholds, and caps findings."""

import uuid

from reviewlens.config import ReviewConfig
from reviewlens.engine.stages.annotate import LineLookup
from reviewlens.models import DroppedFinding, Finding, RawFinding

_SEVERITY_ORDER = {
    "high": 3,
    "medium": 2,
    "low": 1,
}


def validate_stage(
    raw_findings: list[RawFinding],
    lookup: LineLookup,
    config: ReviewConfig,
) -> tuple[list[Finding], list[DroppedFinding]]:
    """Validate and filter raw findings against the real diff coordinates.

    - Resolves stable line IDs to file, line number, and side.
    - Drops invalid line references with reason 'invalid_line'.
    - Drops findings below the confidence threshold.
    - Deduplicates findings targeting the same file and line.
    - Sorts by severity descending, then confidence descending.
    - Caps accepted findings at config.max_findings (default 8).
    """
    valid_candidates: list[Finding] = []
    dropped: list[DroppedFinding] = []
    seen_locations: set[tuple[str, int, str]] = set()

    for rf in raw_findings:
        # 1. Coordinate resolution
        range_res = lookup.validate_range(rf.line_id, rf.end_line_id)
        if range_res is None:
            dropped.append(DroppedFinding(finding=rf, reason="invalid_line"))
            continue

        start_coord, end_line = range_res

        # 2. Confidence thresholding
        if rf.confidence < config.confidence_threshold:
            dropped.append(
                DroppedFinding(
                    finding=rf,
                    reason=f"low_confidence: {rf.confidence:.2f} < {config.confidence_threshold:.2f}",
                )
            )
            continue

        # 3. Deduplication
        loc_key = (start_coord.path, start_coord.line, start_coord.side)
        if loc_key in seen_locations:
            dropped.append(DroppedFinding(finding=rf, reason="duplicate_location"))
            continue

        seen_locations.add(loc_key)

        finding = Finding(
            id=f"finding-{uuid.uuid4().hex[:8]}",
            file=start_coord.path,
            line=start_coord.line,
            end_line=end_line,
            side=start_coord.side,
            severity=rf.severity,
            category=rf.category,
            title=rf.title,
            body=rf.body,
            suggestion=rf.suggestion,
            confidence=rf.confidence,
            verified=None,
        )
        valid_candidates.append(finding)

    # 4. Sorting: severity descending, then confidence descending
    valid_candidates.sort(
        key=lambda f: (_SEVERITY_ORDER.get(f.severity, 0), f.confidence),
        reverse=True,
    )

    # 5. Capping at max_findings
    accepted: list[Finding] = []
    for f in valid_candidates:
        if len(accepted) < config.max_findings:
            accepted.append(f)
        else:
            dropped.append(
                DroppedFinding(
                    finding=f,
                    reason=f"max_findings_cap: exceeded limit of {config.max_findings}",
                )
            )

    return accepted, dropped
