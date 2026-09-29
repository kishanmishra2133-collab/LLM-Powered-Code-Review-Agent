"""Fetch stage: retrieves PR metadata and diff from GitHub."""

from reviewlens.clients.github import GitHubClient
from reviewlens.models import PRMeta, PRRef


async def fetch_stage(pr: PRRef, github_client: GitHubClient) -> tuple[PRMeta, str, str]:
    """Fetch PR metadata and unified diff text.

    Returns (PRMeta, head_sha, raw_diff).
    """
    meta, head_sha = await github_client.get_pr_meta(pr)
    raw_diff = await github_client.get_pr_diff(pr)
    return meta, head_sha, raw_diff
