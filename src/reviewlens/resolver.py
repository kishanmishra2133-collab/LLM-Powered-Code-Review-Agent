"""Universal input resolver for ReviewLens.

Supports:
1. GitHub Pull Requests: https://github.com/owner/repo/pull/123
2. GitHub Files/Blobs:   https://github.com/owner/repo/blob/branch/path/to/file.ext
3. GitHub Commits:       https://github.com/owner/repo/commit/sha
4. GitHub Repos/Trees:   https://github.com/owner/repo or /tree/branch
5. Local Files:          path/to/file.py or C:/path/to/file.java
6. Local Folders:        path/to/folder or C:/path/to/project
7. Raw Code Snippets:    Direct code text with a filename
"""

import os
import re
from pathlib import Path

from reviewlens.clients.github import GitHubClient
from reviewlens.models import PRMeta, PRRef

_CODE_EXTENSIONS = {
    ".py", ".java", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
    ".sql", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".toml"
}

_IGNORED_DIRS = {
    ".git", "node_modules", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    ".venv", "venv", "__pycache__", "dist", "build", ".next", ".idea", ".vscode", "target"
}

# Regex patterns for GitHub URLs
_PR_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)/pull/(?P<number>\d+)/?.*$"
)
_BLOB_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
)
_COMMIT_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)/commit/(?P<sha>[0-9a-fA-F]+)/?$"
)
_TREE_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)/tree/(?P<ref>[^/]+)(?:/(?P<path>.*))?$"
)
_REPO_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+?)(?:\.git)?/?$"
)


def files_to_unified_diff(files: list[tuple[str, str]]) -> str:
    """Convert a collection of (filename, file_content) into a unified diff string."""
    diff_chunks: list[str] = []
    for file_path, content in files:
        clean_path = file_path.replace("\\", "/").lstrip("/")
        lines = content.splitlines()
        num_lines = len(lines)
        diff_chunks.append(f"--- /dev/null\n+++ b/{clean_path}\n@@ -0,0 +1,{num_lines} @@")
        for line in lines:
            diff_chunks.append(f"+{line}")
    return "\n".join(diff_chunks) + "\n" if diff_chunks else ""


def scan_local_folder(folder_path: str | Path, max_files: int = 20) -> list[tuple[str, str]]:
    """Scan a local directory recursively for code files and read their contents."""
    root = Path(folder_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Path is not a valid directory: {folder_path}")

    collected: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Exclude ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]

        for fname in filenames:
            ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            if ext in _CODE_EXTENSIONS:
                full_path = Path(dirpath) / fname
                try:
                    rel_path = full_path.relative_to(root).as_posix()
                    # Skip files larger than 500KB
                    if full_path.stat().st_size > 500_000:
                        continue
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    collected.append((rel_path, content))
                    if len(collected) >= max_files:
                        return collected
                except Exception:
                    continue

    return collected


def read_local_file(file_path: str | Path) -> tuple[str, str]:
    """Read a local file and return (display_path, content)."""
    p = Path(file_path).resolve()
    if not p.is_file():
        raise ValueError(f"Path is not a valid file: {file_path}")
    content = p.read_text(encoding="utf-8", errors="replace")
    return p.name, content


async def resolve_target(
    target_input: str,
    github_client: GitHubClient | None = None,
    code_content: str | None = None,
    filename: str | None = None,
    uploaded_files: list[dict[str, str]] | list[tuple[str, str]] | None = None,
) -> tuple[PRRef, PRMeta, str | None]:
    """Resolve any input type (PR URL, file URL, repo URL, local file, folder, snippet, uploaded files).

    Returns:
        (pr_ref, pr_meta, raw_diff)
        If raw_diff is None, the review graph's fetch node will fetch PR diff via github_client.
    """
    # 0. Direct list of uploaded files
    if uploaded_files:
        items = [
            (f["path"] if isinstance(f, dict) else f[0], f["content"] if isinstance(f, dict) else f[1])
            for f in uploaded_files
        ]
        diff = files_to_unified_diff(items)
        name = items[0][0] if len(items) == 1 else f"{len(items)} files"
        pr_ref = PRRef(owner="upload", repo="files", number=0, head_sha="local")
        meta = PRMeta(title=f"Uploaded: {name}", body=f"Review of {len(items)} uploaded source files", author="user")
        return pr_ref, meta, diff

    raw_input = target_input.strip()

    # 1. Direct code snippet provided
    if code_content is not None and code_content.strip():
        fname = filename or "snippet.code"
        diff = files_to_unified_diff([(fname, code_content)])
        pr_ref = PRRef(owner="local", repo="snippet", number=0, head_sha="raw")
        meta = PRMeta(title=f"Code snippet: {fname}", body="Direct code input review", author="local")
        return pr_ref, meta, diff

    # 2. Local file on filesystem
    if os.path.isfile(raw_input):
        fname, content = read_local_file(raw_input)
        diff = files_to_unified_diff([(fname, content)])
        pr_ref = PRRef(owner="local", repo=fname, number=0, head_sha="local")
        meta = PRMeta(title=f"Local file: {fname}", body=f"Path: {raw_input}", author="local")
        return pr_ref, meta, diff

    # 3. Local folder on filesystem
    if os.path.isdir(raw_input):
        folder_name = os.path.basename(os.path.abspath(raw_input))
        files = scan_local_folder(raw_input)
        if not files:
            raise ValueError(f"No supported code files found in directory: {raw_input}")
        diff = files_to_unified_diff(files)
        pr_ref = PRRef(owner="local", repo=folder_name, number=0, head_sha="local")
        meta = PRMeta(
            title=f"Local directory: {folder_name} ({len(files)} files)",
            body=f"Full path: {raw_input}",
            author="local",
        )
        return pr_ref, meta, diff

    # 4. GitHub PR URL
    pr_match = _PR_PATTERN.match(raw_input)
    if pr_match:
        owner = pr_match.group("owner")
        repo = pr_match.group("repo")
        number = int(pr_match.group("number"))
        pr_ref = PRRef(owner=owner, repo=repo, number=number, head_sha="")
        meta = PRMeta(title=f"{owner}/{repo}#{number}", body="", author="")
        return pr_ref, meta, None

    # For other GitHub URLs, a GitHubClient is required
    client = github_client or GitHubClient()

    # 5. GitHub Single File / Blob URL
    blob_match = _BLOB_PATTERN.match(raw_input)
    if blob_match:
        owner = blob_match.group("owner")
        repo = blob_match.group("repo")
        ref = blob_match.group("ref")
        file_path = blob_match.group("path")
        content = await client.get_file_content(owner, repo, file_path, ref=ref)
        diff = files_to_unified_diff([(file_path, content)])
        pr_ref = PRRef(owner=owner, repo=repo, number=0, head_sha=ref)
        meta = PRMeta(
            title=f"GitHub file: {file_path}",
            body=f"From {owner}/{repo} on branch/commit {ref}",
            author=owner,
        )
        return pr_ref, meta, diff

    # 6. GitHub Commit URL
    commit_match = _COMMIT_PATTERN.match(raw_input)
    if commit_match:
        owner = commit_match.group("owner")
        repo = commit_match.group("repo")
        sha = commit_match.group("sha")
        meta, diff = await client.get_commit_diff(owner, repo, sha)
        pr_ref = PRRef(owner=owner, repo=repo, number=0, head_sha=sha)
        return pr_ref, meta, diff

    # 7. GitHub Tree URL (e.g. /tree/branch/subfolder)
    tree_match = _TREE_PATTERN.match(raw_input)
    if tree_match:
        owner = tree_match.group("owner")
        repo = tree_match.group("repo")
        branch = tree_match.group("ref")
        subpath = tree_match.group("path") or ""
        files = await client.get_repo_files(owner, repo, branch=branch, path_prefix=subpath)
        if not files:
            raise ValueError(f"No source code files found in GitHub path: {raw_input}")
        diff = files_to_unified_diff(files)
        pr_ref = PRRef(owner=owner, repo=repo, number=0, head_sha=branch)
        meta = PRMeta(
            title=f"GitHub tree: {owner}/{repo} ({len(files)} files)",
            body=f"Branch: {branch}, Path: {subpath or '/'}",
            author=owner,
        )
        return pr_ref, meta, diff

    # 8. GitHub Repository Root URL (e.g. https://github.com/owner/repo)
    repo_match = _REPO_PATTERN.match(raw_input)
    if repo_match:
        owner = repo_match.group("owner")
        repo = repo_match.group("repo")
        files = await client.get_repo_files(owner, repo)
        if not files:
            raise ValueError(f"No source code files found in repository {owner}/{repo}")
        diff = files_to_unified_diff(files)
        pr_ref = PRRef(owner=owner, repo=repo, number=0, head_sha="main")
        meta = PRMeta(
            title=f"Repository: {owner}/{repo} ({len(files)} files)",
            body=f"Full scan of {owner}/{repo}",
            author=owner,
        )
        return pr_ref, meta, diff

    # If it reached here, check if user provided a file or folder that doesn't exist
    if "/" in raw_input or "\\" in raw_input:
        raise ValueError(
            f"Target '{raw_input}' could not be resolved. If specifying a local path, ensure the file or folder exists. "
            f"If specifying a GitHub URL, check the repository, branch, or pull request."
        )

    raise ValueError(
        f"Unrecognized input: '{raw_input}'. "
        f"Please provide a GitHub URL (PR, repo, file, or commit), a local file/folder path, or code snippet."
    )
