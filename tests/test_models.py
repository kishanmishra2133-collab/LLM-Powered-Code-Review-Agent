"""Tests for domain models."""

import pytest
from pydantic import ValidationError

from reviewlens.engine.state import ReviewState
from reviewlens.models import (
    DiffFile,
    DiffHunk,
    DiffLine,
    DroppedFinding,
    Finding,
    PRMeta,
    PRRef,
    RawFinding,
    ReviewResult,
    SkippedFile,
    Usage,
)


def test_pr_ref_immutability() -> None:
    ref = PRRef(owner="octocat", repo="hello-world", number=42, head_sha="abc1234")
    assert ref.owner == "octocat"
    assert ref.repo == "hello-world"
    assert ref.number == 42
    assert ref.head_sha == "abc1234"

    with pytest.raises(ValidationError):
        # PRRef is frozen
        ref.number = 99


def test_diff_models() -> None:
    line = DiffLine(
        id="F1:L10",
        type="added",
        old_line_no=None,
        new_line_no=10,
        content="+def hello():",
    )
    hunk = DiffHunk(
        old_start=1,
        old_lines=0,
        new_start=1,
        new_lines=5,
        header="@@ -1,0 +1,5 @@",
        lines=[line],
    )
    diff_file = DiffFile(
        path="src/main.py",
        status="modified",
        hunks=[hunk],
        patch="@@ -1,0 +1,5 @@\n+def hello():\n",
    )
    assert diff_file.path == "src/main.py"
    assert len(diff_file.hunks) == 1
    assert diff_file.hunks[0].lines[0].id == "F1:L10"


def test_finding_validation() -> None:
    finding = Finding(
        id="f-1",
        file="src/main.py",
        line=10,
        side="RIGHT",
        severity="high",
        category="bug",
        title="Uncaught exception",
        body="This function can raise an unhandled ValueError.",
        confidence=0.95,
    )
    assert finding.verified is None
    assert finding.confidence == 0.95

    # Confidence must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        Finding(
            id="f-2",
            file="src/main.py",
            line=10,
            severity="low",
            category="maintainability",
            title="Style issue",
            body="Consider renaming",
            confidence=1.5,
        )


def test_raw_and_dropped_finding() -> None:
    raw = RawFinding(
        line_id="F1:L99",
        severity="medium",
        category="performance",
        title="N+1 query",
        body="Iterating over records triggers multiple queries.",
        confidence=0.8,
    )
    dropped = DroppedFinding(finding=raw, reason="invalid_line")
    assert dropped.reason == "invalid_line"
    assert isinstance(dropped.finding, RawFinding)


def test_review_state_defaults() -> None:
    ref = PRRef(owner="org", repo="repo", number=1, head_sha="1234567")
    state = ReviewState(pr=ref)

    assert state.config.verify is False
    assert state.config.max_findings == 8
    assert state.findings == []
    assert state.dropped == []
    assert state.skipped == []
    assert state.usage.total_tokens == 0


def test_review_result() -> None:
    ref = PRRef(owner="org", repo="repo", number=1, head_sha="1234567")
    meta = PRMeta(title="Add feature", body="Implements X", author="alice")
    result = ReviewResult(
        pr=ref,
        meta=meta,
        findings=[],
        dropped=[],
        skipped=[SkippedFile(path="package-lock.json", reason="lockfile")],
        usage=Usage(total_tokens=150, cost_usd=0.001),
        summary="Review complete. 0 findings.",
    )
    assert result.skipped[0].reason == "lockfile"
    assert result.usage.cost_usd == 0.001
