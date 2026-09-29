"""GitHub REST API client using httpx with retries and backoff."""

import asyncio
from typing import Any

import httpx

from reviewlens.models import PRMeta, PRRef


class GitHubError(Exception):
    """Base exception for GitHub API errors."""


class PRNotFoundError(GitHubError):
    """Raised when a pull request does not exist or is private without credentials."""


class GitHubRateLimitError(GitHubError):
    """Raised when GitHub rate limit is exceeded."""


class GitHubClient:
    """Async client for interacting with the GitHub REST API."""

    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com") -> None:
        self.base_url = base_url.rstrip("/")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ReviewLens-Agent/0.1.0",
        }
        if token and token.strip() and not token.strip().startswith("your_"):
            headers["Authorization"] = f"Bearer {token.strip()}"
        self._headers = headers

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._headers, timeout=30.0)

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_data: Any = None,
        max_retries: int = 3,
    ) -> httpx.Response:
        req_headers = dict(self._headers)
        if headers:
            req_headers.update(headers)

        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(headers=req_headers, timeout=30.0) as client:
                    response = await client.request(method, url, json=json_data)

                if response.status_code == 404:
                    raise PRNotFoundError(f"Resource not found at {url}")
                if response.status_code == 403 and "rate limit" in response.text.lower():
                    raise GitHubRateLimitError("GitHub API rate limit exceeded")

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue

                response.raise_for_status()
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise GitHubError(f"GitHub request failed: {exc}") from exc

        raise GitHubError(f"Request failed after {max_retries} attempts: {last_exc}")

    async def get_pr_meta(self, pr: PRRef) -> tuple[PRMeta, str]:
        """Fetch PR metadata (title, body, author) and head commit SHA.

        Returns (PRMeta, head_sha).
        """
        url = f"{self.base_url}/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}"
        try:
            response = await self._request_with_retry("GET", url)
        except PRNotFoundError as err:
            # Check if this is an Issue rather than a Pull Request
            issue_url = f"{self.base_url}/repos/{pr.owner}/{pr.repo}/issues/{pr.number}"
            try:
                async with httpx.AsyncClient(headers=self._headers, timeout=10.0) as client:
                    issue_resp = await client.get(issue_url)
                if issue_resp.status_code == 200:
                    issue_data = issue_resp.json()
                    if "pull_request" not in issue_data:
                        issue_title = issue_data.get("title", "")
                        raise PRNotFoundError(
                            f"#{pr.number} on {pr.owner}/{pr.repo} is an Issue ('{issue_title}'), NOT a Pull Request. "
                            f"ReviewLens only reviews pull requests because they contain code changes/diffs."
                        ) from err
            except PRNotFoundError:
                raise
            except Exception:
                pass
            raise PRNotFoundError(
                f"Pull request #{pr.number} was not found on {pr.owner}/{pr.repo}. "
                f"Please verify the repository name and PR number, or check if the repo is private."
            ) from err

        data = response.json()

        meta = PRMeta(
            title=data.get("title", ""),
            body=data.get("body", "") or "",
            author=data.get("user", {}).get("login", ""),
        )
        head_sha = str(data.get("head", {}).get("sha", ""))
        return meta, head_sha

    async def get_pr_diff(self, pr: PRRef) -> str:
        """Fetch unified diff text for a pull request."""
        url = f"{self.base_url}/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}"
        response = await self._request_with_retry(
            "GET", url, headers={"Accept": "application/vnd.github.v3.diff"}
        )
        return response.text

    async def has_review_for_commit(self, pr: PRRef, head_sha: str) -> bool:
        """Check if ReviewLens already posted a review for this head commit."""
        marker = f"<!-- reviewlens:{head_sha} -->"
        url = f"{self.base_url}/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}/reviews?per_page=100"

        try:
            response = await self._request_with_retry("GET", url)
            reviews = response.json()
            for rev in reviews:
                body = rev.get("body", "") or ""
                if marker in body:
                    return True
            return False
        except Exception:
            return False

    async def post_review(
        self,
        pr: PRRef,
        head_sha: str,
        body: str,
        comments: list[dict[str, Any]],
        event: str = "COMMENT",
    ) -> None:
        """Post a batch review (summary + line comments) to GitHub."""
        url = f"{self.base_url}/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}/reviews"
        marker = f"<!-- reviewlens:{head_sha} -->"
        full_body = f"{body}\n\n{marker}"

        payload: dict[str, Any] = {
            "commit_id": head_sha,
            "body": full_body,
            "event": event,
        }
        if comments:
            payload["comments"] = comments

        await self._request_with_retry("POST", url, json_data=payload)

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = "") -> str:
        """Fetch raw content of a file from a GitHub repository."""
        clean_path = path.lstrip("/")
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{clean_path}"
        if ref:
            url += f"?ref={ref}"
        response = await self._request_with_retry(
            "GET", url, headers={"Accept": "application/vnd.github.raw"}
        )
        return response.text

    async def get_commit_diff(self, owner: str, repo: str, commit_sha: str) -> tuple[PRMeta, str]:
        """Fetch commit message metadata and unified diff for a single commit."""
        meta_url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_sha}"
        meta_resp = await self._request_with_retry("GET", meta_url)
        data = meta_resp.json()
        commit_info = data.get("commit", {})
        message = commit_info.get("message", "")
        author = commit_info.get("author", {}).get("name", "")

        first_line = message.splitlines()[0] if message else f"Commit {commit_sha[:8]}"
        meta = PRMeta(title=first_line, body=message, author=author)

        diff_resp = await self._request_with_retry(
            "GET", meta_url, headers={"Accept": "application/vnd.github.v3.diff"}
        )
        return meta, diff_resp.text

    async def get_repo_files(
        self, owner: str, repo: str, branch: str = "", path_prefix: str = "", max_files: int = 15
    ) -> list[tuple[str, str]]:
        """Fetch top source code files from a repository branch/tree."""
        code_exts = {
            ".py", ".java", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".hpp",
            ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
            ".sql", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".toml"
        }
        ignored_names = {
            "node_modules", ".git", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
            ".venv", "venv", "__pycache__", "dist", "build", ".next", ".idea"
        }

        # Determine target branch
        target_branch = branch
        if not target_branch:
            repo_info_resp = await self._request_with_retry("GET", f"{self.base_url}/repos/{owner}/{repo}")
            target_branch = repo_info_resp.json().get("default_branch", "main")

        tree_url = f"{self.base_url}/repos/{owner}/{repo}/git/trees/{target_branch}?recursive=1"
        tree_resp = await self._request_with_retry("GET", tree_url)
        tree_items = tree_resp.json().get("tree", [])

        clean_prefix = path_prefix.strip("/")
        matching_paths: list[str] = []

        for item in tree_items:
            if item.get("type") != "blob":
                continue
            path: str = item.get("path", "")
            if clean_prefix and not path.startswith(clean_prefix):
                continue
            parts = path.split("/")
            if any(p in ignored_names for p in parts):
                continue
            ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if ext in code_exts:
                matching_paths.append(path)
                if len(matching_paths) >= max_files:
                    break

        results: list[tuple[str, str]] = []
        for path in matching_paths:
            try:
                content = await self.get_file_content(owner, repo, path, ref=target_branch)
                results.append((path, content))
            except Exception:
                continue

        return results

