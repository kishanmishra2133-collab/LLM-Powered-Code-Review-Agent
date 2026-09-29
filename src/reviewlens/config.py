"""Configuration management for ReviewLens."""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReviewConfig(BaseModel):
    """Configuration options controlling the review workflow behavior."""

    verify: bool = False
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_findings: int = Field(default=8, ge=1)
    model_id: str = "gemini-3-flash-preview"
    review_prompt_version: str = "review_v1"
    verify_prompt_version: str = "verify_v1"


class Settings(BaseSettings):
    """Application-level settings loaded from environment or .env file."""

    gemini_api_key: str = ""
    github_token: str = ""
    daily_budget_usd: float = 5.0
    cache_dir: Path = Path("data/cache")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
