"""Unit tests for GitHubClient and GeminiClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import respx
from httpx import Response
from pydantic import BaseModel

from reviewlens.clients.gemini import GeminiClient
from reviewlens.clients.github import GitHubClient, PRNotFoundError
from reviewlens.models import PRRef


@pytest.mark.asyncio
@respx.mock
async def test_github_client_get_pr_meta_and_diff() -> None:
    client = GitHubClient(token="fake-token")
    pr = PRRef(owner="owner", repo="repo", number=42, head_sha="")

    # Mock PR metadata endpoint
    respx.get("https://api.github.com/repos/owner/repo/pulls/42").mock(
        return_value=Response(
            200,
            json={
                "title": "Fix memory leak",
                "body": "Resolves issue #10",
                "user": {"login": "dev_user"},
                "head": {"sha": "head12345678"},
            },
        )
    )

    meta, head_sha = await client.get_pr_meta(pr)
    assert meta.title == "Fix memory leak"
    assert meta.author == "dev_user"
    assert head_sha == "head12345678"


@pytest.mark.asyncio
@respx.mock
async def test_github_client_pr_not_found() -> None:
    client = GitHubClient()
    pr = PRRef(owner="owner", repo="repo", number=999, head_sha="")

    respx.get("https://api.github.com/repos/owner/repo/pulls/999").mock(
        return_value=Response(404, text="Not Found")
    )
    respx.get("https://api.github.com/repos/owner/repo/issues/999").mock(
        return_value=Response(404, text="Not Found")
    )

    with pytest.raises(PRNotFoundError, match="not found"):
        await client.get_pr_meta(pr)


@pytest.mark.asyncio
@respx.mock
async def test_github_client_issue_not_pr() -> None:
    client = GitHubClient()
    pr = PRRef(owner="owner", repo="repo", number=6000, head_sha="")

    respx.get("https://api.github.com/repos/owner/repo/pulls/6000").mock(
        return_value=Response(404, text="Not Found")
    )
    respx.get("https://api.github.com/repos/owner/repo/issues/6000").mock(
        return_value=Response(200, json={"title": "Some issue title"})
    )

    with pytest.raises(PRNotFoundError, match="is an Issue"):
        await client.get_pr_meta(pr)


@pytest.mark.asyncio
@respx.mock
async def test_github_client_has_review_for_commit() -> None:
    client = GitHubClient()
    pr = PRRef(owner="owner", repo="repo", number=1, head_sha="sha999")

    # Has review marker
    respx.get("https://api.github.com/repos/owner/repo/pulls/1/reviews?per_page=100").mock(
        return_value=Response(
            200,
            json=[
                {"body": "LGTM! <!-- reviewlens:sha999 -->"},
                {"body": "Earlier review"},
            ],
        )
    )

    has_review = await client.has_review_for_commit(pr, "sha999")
    assert has_review is True

    has_other = await client.has_review_for_commit(pr, "different_sha")
    assert has_other is False


class SimpleSchema(BaseModel):
    summary: str
    score: int


@pytest.mark.asyncio
async def test_gemini_client_generate_structured() -> None:
    gemini = GeminiClient(api_key="fake-key")

    mock_response = MagicMock()
    mock_response.text = '{"summary": "Test summary", "score": 10}'
    mock_response.usage_metadata.prompt_token_count = 100
    mock_response.usage_metadata.candidates_token_count = 50
    mock_response.usage_metadata.total_token_count = 150

    gemini._client.aio.models.generate_content = AsyncMock(return_value=mock_response)  # type: ignore[method-assign]

    obj, usage = await gemini.generate_structured(
        contents="Review this code",
        response_schema=SimpleSchema,
    )

    assert obj.summary == "Test summary"
    assert obj.score == 10
    assert usage.prompt_tokens == 100
    assert usage.candidates_tokens == 50
    assert usage.cost_usd > 0
    assert usage.latency_ms >= 0
