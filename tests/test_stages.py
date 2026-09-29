"""Tests for review engine stages and the LangGraph workflow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from reviewlens.clients.gemini import GeminiClient
from reviewlens.config import ReviewConfig
from reviewlens.engine.graph import run_review_workflow
from reviewlens.engine.stages.annotate import parse_diff
from reviewlens.engine.stages.filter import filter_files
from reviewlens.engine.stages.finalize import finalize_stage
from reviewlens.engine.stages.validate import validate_stage
from reviewlens.engine.stages.verify import VerificationResponse, verify_stage
from reviewlens.engine.state import ReviewState
from reviewlens.models import Finding, NodeUsage, PRMeta, PRRef, RawFinding, Usage


def test_filter_files_noise_and_size() -> None:
    diff_text = """--- a/package-lock.json
+++ b/package-lock.json
@@ -1 +1 @@
-{"name": "a"}
+{"name": "b"}
--- a/src/index.min.js
+++ b/src/index.min.js
@@ -1 +1 @@
-function a(){}
+function b(){}
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-x = 1
+x = 2
"""
    files, _ = parse_diff(diff_text)
    kept, skipped = filter_files(files)

    assert len(kept) == 1
    assert kept[0].path == "src/app.py"
    assert len(skipped) == 2
    reasons = {s.reason for s in skipped}
    assert "lockfile" in reasons
    assert "generated or minified file" in reasons


def test_validate_stage_threshold_and_dedupe() -> None:
    diff_text = """--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def test():
+    x = 1
     return
"""
    files, lookup = parse_diff(diff_text)
    config = ReviewConfig(confidence_threshold=0.7, max_findings=2)

    raw_findings = [
        # Valid high confidence
        RawFinding(
            line_id="F1:L2",
            severity="high",
            category="bug",
            title="Bug 1",
            body="First bug",
            confidence=0.9,
        ),
        # Low confidence -> should be dropped
        RawFinding(
            line_id="F1:L2",
            severity="low",
            category="maintainability",
            title="Low conf",
            body="Minor issue",
            confidence=0.4,
        ),
        # Duplicate location -> should be dropped
        RawFinding(
            line_id="F1:L2",
            severity="medium",
            category="performance",
            title="Duplicate bug",
            body="Same line bug",
            confidence=0.8,
        ),
        # Invalid line -> should be dropped
        RawFinding(
            line_id="F9:L999",
            severity="high",
            category="bug",
            title="Fake line",
            body="Invented coordinate",
            confidence=0.99,
        ),
    ]

    accepted, dropped = validate_stage(raw_findings, lookup, config)

    assert len(accepted) == 1
    assert accepted[0].title == "Bug 1"
    assert len(dropped) == 3

    drop_reasons = [d.reason for d in dropped]
    assert any("low_confidence" in r for r in drop_reasons)
    assert any("duplicate_location" in r for r in drop_reasons)
    assert any("invalid_line" in r for r in drop_reasons)


@pytest.mark.asyncio
async def test_verify_stage_refutation() -> None:
    diff_text = """--- a/math_utils.py
+++ b/math_utils.py
@@ -1,2 +1,3 @@
 def divide(a, b):
+    # added check
     return a / b
"""
    files, _ = parse_diff(diff_text)
    finding = Finding(
        id="f-1",
        file="math_utils.py",
        line=2,
        side="RIGHT",
        severity="high",
        category="bug",
        title="Division by zero",
        body="Does not check b == 0",
        confidence=0.9,
    )

    mock_gemini = MagicMock(spec=GeminiClient)
    # Refute the finding
    mock_gemini.generate_structured = AsyncMock(
        return_value=(
            VerificationResponse(verdict="refuted", reason="Handled in caller"),
            NodeUsage(prompt_tokens=50, candidates_tokens=20, cost_usd=0.0001, latency_ms=100),
        )
    )

    verified, dropped, usage = await verify_stage([finding], files, mock_gemini)
    assert len(verified) == 0
    assert len(dropped) == 1
    assert "refuted: Handled in caller" in dropped[0].reason
    assert usage.prompt_tokens == 50


def test_finalize_stage_redaction() -> None:
    pr = PRRef(owner="org", repo="repo", number=1, head_sha="123")
    finding = Finding(
        id="f-1",
        file="config.py",
        line=1,
        severity="high",
        category="security",
        title="Exposed token: ghp_123456789012345678901234567890123456",
        body="Found secret AIzaSyD1234567890123456789012345678901 in code",
        confidence=0.95,
    )
    state = ReviewState(
        pr=pr,
        findings=[finding],
        usage=Usage(nodes={"review": NodeUsage(prompt_tokens=100, cost_usd=0.001, latency_ms=250)}),
    )

    result = finalize_stage(state)
    assert "[REDACTED_SECRET]" in result.findings[0].title
    assert "ghp_" not in result.findings[0].title
    assert "[REDACTED_SECRET]" in result.findings[0].body
    assert "AIza" not in result.findings[0].body
    assert result.usage.prompt_tokens == 100
    assert result.usage.cost_usd == 0.001


@pytest.mark.asyncio
async def test_end_to_end_graph_execution() -> None:
    diff_text = """--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,3 @@
 def add(a, b):
+    res = a + b
     return res
"""
    pr = PRRef(owner="test", repo="test", number=1, head_sha="abc")
    meta = PRMeta(title="Add calc", body="Implements addition", author="dev")

    # Run workflow with offline diff
    result = await run_review_workflow(
        pr=pr,
        raw_diff=diff_text,
        meta=meta,
    )

    assert result.pr == pr
    assert result.meta == meta
    assert len(result.findings) == 0  # No gemini client provided -> 0 findings
    assert "Review complete" in result.summary
