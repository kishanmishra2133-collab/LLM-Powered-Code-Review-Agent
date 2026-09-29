"""Evaluation runner for benchmark dataset."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.score import EvalCase, Label, compute_metrics
from reviewlens.clients.gemini import GeminiClient
from reviewlens.config import ReviewConfig, Settings
from reviewlens.engine.graph import run_review_workflow
from reviewlens.models import PRRef


def load_dataset(dataset_path: Path) -> list[EvalCase]:
    """Load evaluation cases from cases.jsonl."""
    cases: list[EvalCase] = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            labels = [
                Label(
                    file=lbl["file"],
                    line_start=lbl["line_start"],
                    line_end=lbl["line_end"],
                    category=lbl["category"],
                    note=lbl.get("note", ""),
                )
                for lbl in data.get("labels", [])
            ]
            cases.append(
                EvalCase(
                    id=data["id"],
                    repo=data["repo"],
                    pr=data["pr"],
                    head_sha=data["head_sha"],
                    diff_path=data["diff_path"],
                    labels=labels,
                    clean=data.get("clean", False),
                )
            )
    return cases


def run_evaluation(
    tag: str = "baseline",
    model: str = "gemini-3-flash-preview",
    dataset_path: Path = Path("eval/dataset/cases.jsonl"),
    output_dir: Path = Path("eval/runs"),
) -> Path:
    """Run evaluation over the dataset and record metrics."""
    settings = Settings()
    cases = load_dataset(dataset_path)

    gemini_client: GeminiClient | None = None
    if settings.gemini_api_key:
        gemini_client = GeminiClient(api_key=settings.gemini_api_key, model_id=model)

    verify = tag == "verify"
    config = ReviewConfig(verify=verify, model_id=model)

    case_results: dict[str, list[dict[str, Any]]] = {}
    case_costs: dict[str, float] = {}
    case_latencies: dict[str, int] = {}

    async def _evaluate_all() -> None:
        for case in cases:
            diff_file = Path(case.diff_path)
            diff_text = diff_file.read_text(encoding="utf-8") if diff_file.is_file() else ""

            owner, repo_name = case.repo.split("/", 1)
            pr_ref = PRRef(
                owner=owner,
                repo=repo_name,
                number=case.pr,
                head_sha=case.head_sha,
            )

            result = await run_review_workflow(
                pr=pr_ref,
                config=config,
                raw_diff=diff_text,
                gemini_client=gemini_client,
            )

            case_results[case.id] = [f.model_dump(mode="json") for f in result.findings]
            case_costs[case.id] = result.usage.cost_usd
            case_latencies[case.id] = result.usage.latency_ms

    asyncio.run(_evaluate_all())

    metrics = compute_metrics(cases, case_results, case_costs, case_latencies)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{tag}-{timestamp}.json"

    run_record = {
        "tag": tag,
        "model": model,
        "timestamp": timestamp,
        "config": config.model_dump(mode="json"),
        "metrics": metrics,
        "cases": case_results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(run_record, f, indent=2)

    return output_file
