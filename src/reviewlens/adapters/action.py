"""GitHub Action adapter: runs ReviewLens and posts inline review comments."""

import asyncio
import json
import os
import sys

from reviewlens.clients.gemini import GeminiClient
from reviewlens.clients.github import GitHubClient
from reviewlens.config import ReviewConfig
from reviewlens.engine.graph import run_review_workflow
from reviewlens.models import PRRef


async def run_action() -> None:
    """Execute ReviewLens GitHub Action from environment context."""
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("::error::GITHUB_EVENT_PATH is not set or file does not exist.")
        sys.exit(1)

    with open(event_path, encoding="utf-8") as f:
        event = json.load(f)

    pr_data = event.get("pull_request")
    if not pr_data:
        print("::warning::Action triggered on non-pull_request event. Exiting.")
        sys.exit(0)

    repo_full = event.get("repository", {}).get("full_name", "")
    if "/" not in repo_full:
        print("::error::Cannot determine repository full name.")
        sys.exit(1)

    owner, repo = repo_full.split("/", 1)
    pr_number = pr_data.get("number")
    head_sha = pr_data.get("head", {}).get("sha", "")

    if not pr_number or not head_sha:
        print("::error::Missing PR number or head SHA.")
        sys.exit(1)

    pr_ref = PRRef(owner=owner, repo=repo, number=pr_number, head_sha=head_sha)

    token = os.getenv("INPUT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN") or ""
    gemini_key = os.getenv("INPUT_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    model = os.getenv("INPUT_MODEL", "gemini-3-flash-preview")
    verify_str = os.getenv("INPUT_VERIFY", "true").lower()
    verify = verify_str in ("true", "1", "yes")

    if not gemini_key:
        print("::error::GEMINI_API_KEY is required.")
        sys.exit(1)

    github_client = GitHubClient(token=token or None)
    gemini_client = GeminiClient(api_key=gemini_key, model_id=model)
    config = ReviewConfig(verify=verify, model_id=model)

    print(f"ReviewLens running on {owner}/{repo}#{pr_number} (commit: {head_sha[:8]})...")

    # Idempotency check: don't post duplicate review on the same commit
    already_reviewed = await github_client.has_review_for_commit(pr_ref, head_sha)
    if already_reviewed:
        print(f"ReviewLens already reviewed commit {head_sha[:8]}. Skipping.")
        sys.exit(0)

    result = await run_review_workflow(
        pr=pr_ref,
        config=config,
        github_client=github_client,
        gemini_client=gemini_client,
    )

    comments: list[dict[str, object]] = []
    for finding in result.findings:
        body = f"### [{finding.severity.upper()}] {finding.title}\n\n{finding.body}"
        if finding.suggestion:
            body += f"\n\n```suggestion\n{finding.suggestion}\n```"
        if finding.verified:
            body += "\n\n*Verified by ReviewLens*"

        comment: dict[str, object] = {
            "path": finding.file,
            "line": finding.end_line or finding.line,
            "side": finding.side,
            "body": body,
        }
        if finding.end_line and finding.end_line != finding.line:
            comment["start_line"] = finding.line
            comment["start_side"] = finding.side

        comments.append(comment)

    summary_body = (
        f"## ReviewLens Summary\n\n"
        f"- **Findings:** {len(result.findings)}\n"
        f"- **Files skipped:** {len(result.skipped)}\n"
        f"- **Model:** `{model}`\n"
        f"- **Cost:** `${result.usage.cost_usd:.4f}`\n\n"
        f"*{result.summary}*"
    )

    await github_client.post_review(
        pr=pr_ref,
        head_sha=head_sha,
        body=summary_body,
        comments=comments,
    )

    print(f"Review posted successfully with {len(comments)} comment(s).")


def main() -> None:
    asyncio.run(run_action())


if __name__ == "__main__":
    main()
