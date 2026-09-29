"""Tests for security utilities: URL parsing and secret redaction."""

import pytest

from reviewlens.security import parse_pr_url, redact_secrets


def test_parse_pr_url_valid() -> None:
    ref = parse_pr_url("https://github.com/octocat/Hello-World/pull/42")
    assert ref.owner == "octocat"
    assert ref.repo == "Hello-World"
    assert ref.number == 42
    assert ref.head_sha == ""

    ref_with_sha = parse_pr_url("https://github.com/psf/black/pull/123/", head_sha="abc1234")
    assert ref_with_sha.owner == "psf"
    assert ref_with_sha.repo == "black"
    assert ref_with_sha.number == 123
    assert ref_with_sha.head_sha == "abc1234"


def test_parse_pr_url_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
        parse_pr_url("https://gitlab.com/owner/repo/merge_requests/1")

    with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
        parse_pr_url("https://github.com/owner/repo/issues/1")

    with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
        parse_pr_url("not a url")


def test_redact_secrets() -> None:
    text = (
        "Here is my github token: ghp_123456789012345678901234567890123456 "
        "and my google key: AIzaSyD1234567890123456789012345678901 "
        "and auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token"
    )
    redacted = redact_secrets(text)
    assert "ghp_" not in redacted
    assert "AIzaSyD" not in redacted
    assert "Bearer" not in redacted
    assert "[REDACTED_SECRET]" in redacted
