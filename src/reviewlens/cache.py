"""JSON file-based caching and daily budget tracking."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reviewlens.models import PRRef, ReviewResult


class ReviewCache:
    """File-based cache for review results."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(self, pr: PRRef, prompt_version: str) -> str:
        safe_owner = pr.owner.replace("/", "_")
        safe_repo = pr.repo.replace("/", "_")
        return f"{safe_owner}__{safe_repo}__{pr.number}__{pr.head_sha}__{prompt_version}.json"

    def get(self, pr: PRRef, prompt_version: str) -> ReviewResult | None:
        """Retrieve cached review result if it exists."""
        key = self._make_key(pr, prompt_version)
        cache_path = self.cache_dir / key
        if not cache_path.is_file():
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            return ReviewResult.model_validate(data)
        except Exception:
            return None

    def set(self, pr: PRRef, prompt_version: str, result: ReviewResult) -> None:
        """Save review result to cache file."""
        key = self._make_key(pr, prompt_version)
        cache_path = self.cache_dir / key
        temp_path = self.cache_dir / f"{key}.tmp"

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(mode="json"), f, indent=2)
        temp_path.replace(cache_path)


class DailyBudgetTracker:
    """Tracks dollar spend per calendar day (UTC) in a local JSON file."""

    def __init__(self, budget_file: Path, daily_cap_usd: float = 5.0) -> None:
        self.budget_file = budget_file
        self.daily_cap_usd = daily_cap_usd
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)

    def _today(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _load(self) -> tuple[str, float]:
        if not self.budget_file.is_file():
            return self._today(), 0.0

        try:
            with open(self.budget_file, encoding="utf-8") as f:
                data = json.load(f)
            recorded_date = data.get("date", self._today())
            spent = float(data.get("spent_usd", 0.0))
            if recorded_date != self._today():
                return self._today(), 0.0
            return recorded_date, spent
        except Exception:
            return self._today(), 0.0

    def _save(self, date_str: str, spent_usd: float) -> None:
        temp_file = self.budget_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({"date": date_str, "spent_usd": round(spent_usd, 6)}, f, indent=2)
        temp_file.replace(self.budget_file)

    def record_spend(self, cost_usd: float) -> float:
        """Add to today's spend and return the updated total."""
        date_str, spent = self._load()
        new_total = round(spent + max(0.0, cost_usd), 6)
        self._save(date_str, new_total)
        return new_total

    def is_exhausted(self) -> bool:
        """Check if today's spend has reached or exceeded the cap."""
        _, spent = self._load()
        return spent >= self.daily_cap_usd

    def current_spend(self) -> float:
        """Get today's total spend in USD."""
        _, spent = self._load()
        return spent
