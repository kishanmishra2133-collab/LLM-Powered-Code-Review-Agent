"""LangGraph workflow state definition."""

from pydantic import BaseModel, Field

from reviewlens.config import ReviewConfig
from reviewlens.models import (
    DiffFile,
    DroppedFinding,
    Finding,
    PRMeta,
    PRRef,
    RawFinding,
    SkippedFile,
    Usage,
)


class ReviewState(BaseModel):
    """Shared state passed through each stage of the review graph."""

    pr: PRRef
    config: ReviewConfig = Field(default_factory=ReviewConfig)
    meta: PRMeta | None = None
    files: list[DiffFile] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)
    raw_findings: list[RawFinding] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    dropped: list[DroppedFinding] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
