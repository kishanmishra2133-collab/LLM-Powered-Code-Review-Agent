"""Unit tests for FastAPI endpoints."""

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from reviewlens.adapters.api import app
from reviewlens.models import Finding, PRRef, ReviewResult


@pytest.mark.asyncio
async def test_api_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "daily_spend_usd" in data
        assert "budget_exhausted" in data


@pytest.mark.asyncio
async def test_api_examples() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/examples")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        assert "pr_url" in data[0]


@pytest.mark.asyncio
async def test_api_stream_review_invalid_url() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/review?pr_url=invalid-url")
        assert response.status_code == 200
        text = response.text
        assert "INVALID_URL" in text


@pytest.mark.asyncio
async def test_api_stream_review_cached_hit(tmp_path: Path) -> None:
    pr = PRRef(owner="psf", repo="requests", number=100, head_sha="sha100")
    finding = Finding(
        id="f-1",
        file="auth.py",
        line=42,
        severity="high",
        category="security",
        title="Token leak",
        body="Sensitive token is logged",
        confidence=0.9,
    )
    result = ReviewResult(pr=pr, findings=[finding], summary="Cached review")

    with patch("reviewlens.adapters.api.review_cache.get", return_value=result):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/review?pr_url=https://github.com/psf/requests/pull/100")
            assert response.status_code == 200
            content = response.text
            assert "event: stage" in content
            assert "event: finding" in content
            assert "Token leak" in content
            assert "event: summary" in content
            assert "event: done" in content
