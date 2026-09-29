# Notes: Competitor Analysis & Why ReviewLens Was Built

## The Problem with Current LLM Review Tools
Tools like CodeRabbit and PR-Agent often suffer from two major drawbacks:
1. **Comment Spam / Low Precision**: Commercial tools prioritize high recall, commenting on harmless stylistic differences, trivial docstring rewrites, or theoretical issues that are already handled elsewhere in the codebase.
2. **Coordinate Drift**: Hallucinated or miscalculated line coordinates that result in review comments landing on the wrong lines or referencing code outside of modified hunks.
3. **Unmeasured Quality Claims**: Marketing claims like "cuts review time by 50%" are rarely backed by reproducible precision, recall, and cost figures on a public labeled dataset.

## How ReviewLens Differs
- **Strict Line ID Tagging**: Diff lines are assigned stable identifiers (`F1:L42`, `F1:D10`) before the LLM sees them. Findings citing non-existent lines or cross-hunk ranges are dropped at the validation stage.
- **Adversarial Verification Node**: A second LLM pass actively attempts to refute each accepted finding before it is ever posted.
- **Reproducible Evaluation**: Every quality claim is measured on labeled PRs with precision, recall, F1, and clean-PR false positive rates tracked across runs.
