"""Unit tests for evaluation scoring and metrics computation."""

from eval.score import EvalCase, Label, compute_metrics, matches_label


def test_matches_label_within_tolerance() -> None:
    label = Label(file="app/views.py", line_start=40, line_end=45, category="bug")

    # Exact match
    assert matches_label("app/views.py", 42, None, label) is True

    # Within 3-line tolerance
    assert matches_label("app/views.py", 38, None, label) is True
    assert matches_label("app/views.py", 48, None, label) is True

    # Outside tolerance
    assert matches_label("app/views.py", 35, None, label) is False
    assert matches_label("app/views.py", 55, None, label) is False

    # Different file
    assert matches_label("app/other.py", 42, None, label) is False


def test_compute_metrics_perfect() -> None:
    cases = [
        EvalCase(
            id="case-1",
            repo="org/repo",
            pr=1,
            head_sha="sha1",
            diff_path="",
            labels=[Label(file="main.py", line_start=10, line_end=15, category="bug")],
            clean=False,
        ),
        EvalCase(
            id="case-2",
            repo="org/repo",
            pr=2,
            head_sha="sha2",
            diff_path="",
            labels=[],
            clean=True,
        ),
    ]

    case_results = {
        "case-1": [{"file": "main.py", "line": 12, "end_line": None}],
        "case-2": [],
    }
    case_costs = {"case-1": 0.005, "case-2": 0.001}
    case_latencies = {"case-1": 1200, "case-2": 400}

    metrics = compute_metrics(cases, case_results, case_costs, case_latencies)

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["clean_fp_rate"] == 0.0
    assert metrics["comments_per_pr"] == 0.5
    assert metrics["mean_cost_usd"] == 0.003
    assert metrics["p50_latency_ms"] == 800.0


def test_compute_metrics_false_positives() -> None:
    cases = [
        EvalCase(
            id="case-clean",
            repo="org/repo",
            pr=1,
            head_sha="sha1",
            diff_path="",
            labels=[],
            clean=True,
        )
    ]

    # Clean PR received an unwanted finding (false positive)
    case_results = {
        "case-clean": [{"file": "main.py", "line": 1, "end_line": None}],
    }

    metrics = compute_metrics(cases, case_results, {"case-clean": 0.002}, {"case-clean": 500})
    assert metrics["clean_fp_rate"] == 1.0
    assert metrics["precision"] == 0.0
