"""Evaluation scoring metrics for ReviewLens."""

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class Label:
    """Ground truth label for a pull request."""

    file: str
    line_start: int
    line_end: int
    category: str
    note: str = ""


@dataclass
class EvalCase:
    """A test case in the evaluation dataset."""

    id: str
    repo: str
    pr: int
    head_sha: str
    diff_path: str
    labels: list[Label]
    clean: bool


def matches_label(
    finding_file: str,
    finding_line: int,
    finding_end_line: int | None,
    label: Label,
    tolerance: int = 3,
) -> bool:
    """Determine if a finding matches a ground truth label with line tolerance."""
    if finding_file.strip().lower() != label.file.strip().lower():
        return False

    f_start = finding_line
    f_end = finding_end_line if finding_end_line is not None else finding_line

    # Overlapping ranges with tolerance
    return not (f_end < label.line_start - tolerance or f_start > label.line_end + tolerance)


def compute_metrics(
    cases: list[EvalCase],
    case_results: dict[str, list[dict[str, Any]]],
    case_costs: dict[str, float],
    case_latencies: dict[str, int],
) -> dict[str, float]:
    """Compute precision, recall, F1, clean FP rate, comments per PR, cost, and latency."""
    total_findings = 0
    matched_findings = 0
    total_labels = 0
    matched_labels = 0
    clean_prs = 0
    clean_prs_with_findings = 0

    for case in cases:
        findings = case_results.get(case.id, [])
        total_findings += len(findings)

        if case.clean:
            clean_prs += 1
            if findings:
                clean_prs_with_findings += 1
        else:
            total_labels += len(case.labels)
            matched_labels_in_case: set[int] = set()

            for f in findings:
                f_file = f.get("file", "")
                f_line = f.get("line", 0)
                f_end_line = f.get("end_line")

                finding_matched = False
                for idx, lbl in enumerate(case.labels):
                    if matches_label(f_file, f_line, f_end_line, lbl):
                        finding_matched = True
                        matched_labels_in_case.add(idx)

                if finding_matched:
                    matched_findings += 1

            matched_labels += len(matched_labels_in_case)

    precision = matched_findings / total_findings if total_findings > 0 else 1.0
    recall = matched_labels / total_labels if total_labels > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    clean_fp_rate = clean_prs_with_findings / clean_prs if clean_prs > 0 else 0.0
    comments_per_pr = total_findings / len(cases) if cases else 0.0

    costs = list(case_costs.values())
    mean_cost = (sum(costs) / len(costs)) if costs else 0.0

    latencies = sorted(case_latencies.values())
    p50_latency = 0.0
    p95_latency = 0.0
    if latencies:
        import statistics

        p50_latency = float(statistics.median(latencies))
        idx_95 = int(math.ceil(0.95 * len(latencies))) - 1
        p95_latency = float(latencies[max(0, idx_95)])

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "clean_fp_rate": round(clean_fp_rate, 4),
        "comments_per_pr": round(comments_per_pr, 2),
        "mean_cost_usd": round(mean_cost, 6),
        "p50_latency_ms": round(p50_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
        "total_findings": float(total_findings),
        "matched_findings": float(matched_findings),
        "total_labels": float(total_labels),
        "matched_labels": float(matched_labels),
    }
