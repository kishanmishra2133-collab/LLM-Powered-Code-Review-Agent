"""Tests for configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from reviewlens.config import ReviewConfig, Settings


def test_review_config_defaults() -> None:
    config = ReviewConfig()
    assert config.verify is False
    assert config.confidence_threshold == 0.7
    assert config.max_findings == 8
    assert config.model_id == "gemini-3-flash-preview"
    assert config.review_prompt_version == "review_v1"
    assert config.verify_prompt_version == "verify_v1"


def test_review_config_validation() -> None:
    with pytest.raises(ValidationError):
        ReviewConfig(confidence_threshold=1.5)

    with pytest.raises(ValidationError):
        ReviewConfig(max_findings=0)


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    settings = Settings(_env_file=None)
    assert settings.gemini_api_key == ""
    assert settings.github_token == ""
    assert settings.daily_budget_usd == 5.0
    assert settings.cache_dir == Path("data/cache")


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GITHUB_TOKEN", "test-gh-token")
    monkeypatch.setenv("DAILY_BUDGET_USD", "10.5")

    settings = Settings()
    assert settings.gemini_api_key == "test-gemini-key"
    assert settings.github_token == "test-gh-token"
    assert settings.daily_budget_usd == 10.5
