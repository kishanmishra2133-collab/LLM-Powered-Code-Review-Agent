"""Domain models for ReviewLens."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PRRef(BaseModel):
    """Reference to a specific pull request and commit."""

    model_config = ConfigDict(frozen=True)

    owner: str
    repo: str
    number: int
    head_sha: str


class PRMeta(BaseModel):
    """Metadata of a pull request."""

    title: str
    body: str = ""
    author: str = ""


class DiffLine(BaseModel):
    """A single line inside a diff hunk with a stable identifier."""

    id: str  # e.g. "F1:L42" (new/context) or "F1:D10" (removed)
    type: Literal["context", "added", "removed"]
    old_line_no: int | None = None
    new_line_no: int | None = None
    content: str


class DiffHunk(BaseModel):
    """A hunk within a diff file."""

    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str = ""
    lines: list[DiffLine] = Field(default_factory=list)


class DiffFile(BaseModel):
    """A file modified in a pull request with parsed hunks."""

    path: str
    old_path: str | None = None
    status: Literal["added", "modified", "deleted", "renamed"] = "modified"
    is_binary: bool = False
    hunks: list[DiffHunk] = Field(default_factory=list)
    patch: str = ""


class SkippedFile(BaseModel):
    """A file excluded from review due to filter rules or size limits."""

    path: str
    reason: str


class Finding(BaseModel):
    """A validated, anchored review finding ready for posting or display."""

    id: str
    file: str
    line: int  # new-file line (or old-file line if side == "LEFT")
    end_line: int | None = None
    side: Literal["RIGHT", "LEFT"] = "RIGHT"
    severity: Literal["high", "medium", "low"]
    category: Literal["bug", "security", "performance", "tests", "maintainability"]
    title: str  # one line, plain language
    body: str  # rationale referencing the code
    suggestion: str | None = None  # concrete replacement code
    confidence: float = Field(ge=0.0, le=1.0)
    verified: bool | None = None  # None when verification is disabled


class RawFinding(BaseModel):
    """Initial finding emitted by the LLM before diff coordinate validation."""

    line_id: str
    end_line_id: str | None = None
    severity: Literal["high", "medium", "low"]
    category: Literal["bug", "security", "performance", "tests", "maintainability"]
    title: str
    body: str
    suggestion: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class DroppedFinding(BaseModel):
    """A finding discarded during validation or verification."""

    finding: RawFinding | Finding
    reason: str


class NodeUsage(BaseModel):
    """Token and execution metrics for an individual graph node."""

    prompt_tokens: int = 0
    candidates_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class Usage(BaseModel):
    """Aggregate token, cost, and latency metrics across all stages."""

    prompt_tokens: int = 0
    candidates_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    nodes: dict[str, NodeUsage] = Field(default_factory=dict)


class ReviewResult(BaseModel):
    """The final outcome of a review workflow."""

    pr: PRRef
    meta: PRMeta | None = None
    findings: list[Finding] = Field(default_factory=list)
    dropped: list[DroppedFinding] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    summary: str = ""
