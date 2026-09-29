"""Tests for file-based cache and budget tracker."""

from pathlib import Path

from reviewlens.cache import DailyBudgetTracker, ReviewCache
from reviewlens.models import PRRef, ReviewResult


def test_review_cache(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path)
    ref = PRRef(owner="owner", repo="repo", number=1, head_sha="sha123")

    # Miss
    assert cache.get(ref, "v1") is None

    result = ReviewResult(pr=ref, summary="Looks good!")
    cache.set(ref, "v1", result)

    # Hit
    cached = cache.get(ref, "v1")
    assert cached is not None
    assert cached.summary == "Looks good!"
    assert cached.pr.head_sha == "sha123"

    # Different prompt version miss
    assert cache.get(ref, "v2") is None


def test_daily_budget_tracker(tmp_path: Path) -> None:
    budget_file = tmp_path / "budget.json"
    tracker = DailyBudgetTracker(budget_file, daily_cap_usd=0.05)

    assert tracker.current_spend() == 0.0
    assert not tracker.is_exhausted()

    # Spend within cap
    spent = tracker.record_spend(0.02)
    assert spent == 0.02
    assert not tracker.is_exhausted()

    # Spend reaching cap
    spent = tracker.record_spend(0.035)
    assert spent == 0.055
    assert tracker.is_exhausted()
