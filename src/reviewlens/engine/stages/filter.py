"""Filter stage: removes noise files and enforces diff size limits."""

import fnmatch
from pathlib import Path

from reviewlens.models import DiffFile, SkippedFile

# Noise patterns
_LOCKFILE_PATTERNS = [
    "*lock*",
    "*.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
]

_GENERATED_PATTERNS = [
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.bundle.js",
    "*.bundle.css",
    "*.generated.*",
    "*_generated.*",
    "*.pb.go",
    "*_pb2.py",
]

_VENDOR_PATTERNS = [
    "node_modules/*",
    "vendor/*",
    "third_party/*",
    "3rdparty/*",
    ".venv/*",
    "venv/*",
    "dist/*",
    "build/*",
]

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".whl", ".pyc",
    ".woff", ".woff2", ".ttf", ".eot",
}

# Maximum size budget for a review
DEFAULT_MAX_FILES = 30
DEFAULT_MAX_CHANGED_LINES = 800


def _matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    filename = Path(normalized).name
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(filename, pattern):
            return True
    return False


def is_noise_file(file: DiffFile) -> tuple[bool, str]:
    """Check if a file matches noise filters (lockfiles, generated, vendored, binary)."""
    if file.is_binary:
        return True, "binary file"

    ext = Path(file.path).suffix.lower()
    if ext in _BINARY_EXTENSIONS:
        return True, "binary extension"

    if _matches_any(file.path, _LOCKFILE_PATTERNS):
        return True, "lockfile"

    if _matches_any(file.path, _GENERATED_PATTERNS):
        return True, "generated or minified file"

    if _matches_any(file.path, _VENDOR_PATTERNS):
        return True, "vendored or third-party directory"

    return False, ""


def count_changed_lines(file: DiffFile) -> int:
    """Count added and removed lines in a file's hunks."""
    count = 0
    for hunk in file.hunks:
        for line in hunk.lines:
            if line.type in ("added", "removed"):
                count += 1
    return count


def filter_files(
    files: list[DiffFile],
    max_files: int = DEFAULT_MAX_FILES,
    max_changed_lines: int = DEFAULT_MAX_CHANGED_LINES,
) -> tuple[list[DiffFile], list[SkippedFile]]:
    """Filter out noise and enforce diff size budget."""
    candidates: list[DiffFile] = []
    skipped: list[SkippedFile] = []

    for file in files:
        is_noise, reason = is_noise_file(file)
        if is_noise:
            skipped.append(SkippedFile(path=file.path, reason=reason))
        else:
            candidates.append(file)

    # If within limits, return candidates
    total_lines = sum(count_changed_lines(f) for f in candidates)
    if len(candidates) <= max_files and total_lines <= max_changed_lines:
        return candidates, skipped

    # Over budget: prioritize source code over docs/configs, bigger hunks first
    def file_priority(f: DiffFile) -> tuple[int, int]:
        ext = Path(f.path).suffix.lower()
        # 0 = code, 1 = config, 2 = docs
        category = 0
        if ext in (".md", ".txt", ".rst", ".adoc"):
            category = 2
        elif ext in (".json", ".yaml", ".yml", ".toml", ".ini", ".xml"):
            category = 1
        return (category, -count_changed_lines(f))

    sorted_candidates = sorted(candidates, key=file_priority)

    kept: list[DiffFile] = []
    current_lines = 0

    for file in sorted_candidates:
        file_lines = count_changed_lines(file)
        if len(kept) >= max_files or (current_lines + file_lines > max_changed_lines and kept):
            skipped.append(SkippedFile(path=file.path, reason="size budget exceeded"))
        else:
            kept.append(file)
            current_lines += file_lines

    return kept, skipped
