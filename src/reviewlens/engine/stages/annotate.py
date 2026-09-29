"""Diff parsing and stable line annotation stage."""

from dataclasses import dataclass
from typing import Literal

from unidiff.constants import (
    LINE_TYPE_ADDED,
    LINE_TYPE_CONTEXT,
    LINE_TYPE_NO_NEWLINE,
    LINE_TYPE_REMOVED,
)
from unidiff.errors import UnidiffParseError
from unidiff.patch import PatchSet

from reviewlens.models import DiffFile, DiffHunk, DiffLine


class DiffParseError(Exception):
    """Raised when raw unified diff cannot be parsed."""


@dataclass(frozen=True)
class LineCoordinate:
    """Resolved coordinate for a stable line identifier."""

    file_idx: int
    path: str
    line: int
    side: Literal["RIGHT", "LEFT"]
    hunk_idx: int
    line_id: str
    content: str


class LineLookup:
    """Lookup index mapping stable line IDs to file coordinates."""

    def __init__(self, coordinates: dict[str, LineCoordinate]) -> None:
        self._coords: dict[str, LineCoordinate] = dict(coordinates)

    def get(self, line_id: str) -> LineCoordinate | None:
        """Get the coordinate for a given line ID."""
        return self._coords.get(line_id)

    def contains(self, line_id: str) -> bool:
        """Check if a line ID exists in the diff."""
        return line_id in self._coords

    def validate_range(
        self, start_id: str, end_id: str | None = None
    ) -> tuple[LineCoordinate, int | None] | None:
        """Validate a single line or multi-line range.

        Returns (start_coord, end_line_number) if valid, or None if invalid.
        Multi-line ranges must reside in the same file, same hunk, same side,
        and start_line <= end_line.
        """
        start_coord = self.get(start_id)
        if start_coord is None:
            return None

        if end_id is None or end_id == start_id:
            return (start_coord, None)

        end_coord = self.get(end_id)
        if end_coord is None:
            return None

        # Both endpoints must be in the same file, hunk, and side
        if start_coord.file_idx != end_coord.file_idx:
            return None
        if start_coord.hunk_idx != end_coord.hunk_idx:
            return None
        if start_coord.side != end_coord.side:
            return None
        if start_coord.line > end_coord.line:
            return None

        return (start_coord, end_coord.line)

    def __len__(self) -> int:
        return len(self._coords)


def _clean_path(path_str: str, prefix: str) -> str:
    """Strip git diff prefix (e.g., 'a/' or 'b/') if present."""
    if path_str.startswith(prefix):
        return path_str[len(prefix) :]
    return path_str


def parse_diff(raw_diff: str) -> tuple[list[DiffFile], LineLookup]:
    """Parse raw unified diff and assign stable line IDs.

    - Added / context lines (RIGHT side): F{file_idx}:L{new_line_no}
    - Removed lines (LEFT side): F{file_idx}:D{old_line_no}
    """
    if not raw_diff or not raw_diff.strip():
        return [], LineLookup({})

    try:
        patch_set = PatchSet(raw_diff)
    except (UnidiffParseError, Exception) as exc:
        raise DiffParseError(f"Failed to parse unified diff: {exc}") from exc

    diff_files: list[DiffFile] = []
    line_coords: dict[str, LineCoordinate] = {}

    for file_idx, patched_file in enumerate(patch_set, start=1):
        clean_target = _clean_path(patched_file.target_file, "b/")
        clean_source = _clean_path(patched_file.source_file, "a/")

        if patched_file.is_added_file:
            status: Literal["added", "modified", "deleted", "renamed"] = "added"
            file_path = clean_target
            old_path = None
        elif patched_file.is_removed_file:
            status = "deleted"
            file_path = clean_source
            old_path = clean_source
        elif patched_file.is_rename:
            status = "renamed"
            file_path = clean_target
            old_path = clean_source
        else:
            status = "modified"
            file_path = clean_target or clean_source
            old_path = clean_source if clean_source != file_path else None

        hunks: list[DiffHunk] = []

        for hunk_idx, hunk in enumerate(patched_file, start=1):
            diff_lines: list[DiffLine] = []

            for line in hunk:
                # Ignore '\ No newline at end of file' markers
                if line.line_type == LINE_TYPE_NO_NEWLINE:
                    continue

                if line.line_type == LINE_TYPE_ADDED:
                    assert line.target_line_no is not None
                    line_id = f"F{file_idx}:L{line.target_line_no}"
                    line_type: Literal["context", "added", "removed"] = "added"
                    side: Literal["RIGHT", "LEFT"] = "RIGHT"
                    resolved_line_no = line.target_line_no
                elif line.line_type == LINE_TYPE_REMOVED:
                    assert line.source_line_no is not None
                    line_id = f"F{file_idx}:D{line.source_line_no}"
                    line_type = "removed"
                    side = "LEFT"
                    resolved_line_no = line.source_line_no
                elif line.line_type == LINE_TYPE_CONTEXT:
                    assert line.target_line_no is not None
                    line_id = f"F{file_idx}:L{line.target_line_no}"
                    line_type = "context"
                    side = "RIGHT"
                    resolved_line_no = line.target_line_no
                else:
                    continue

                diff_line = DiffLine(
                    id=line_id,
                    type=line_type,
                    old_line_no=line.source_line_no,
                    new_line_no=line.target_line_no,
                    content=line.value.rstrip("\r\n"),
                )
                diff_lines.append(diff_line)

                coord = LineCoordinate(
                    file_idx=file_idx,
                    path=file_path,
                    line=resolved_line_no,
                    side=side,
                    hunk_idx=hunk_idx,
                    line_id=line_id,
                    content=diff_line.content,
                )
                line_coords[line_id] = coord

            diff_hunk = DiffHunk(
                old_start=hunk.source_start,
                old_lines=hunk.source_length,
                new_start=hunk.target_start,
                new_lines=hunk.target_length,
                header=hunk.section_header,
                lines=diff_lines,
            )
            hunks.append(diff_hunk)

        diff_files.append(
            DiffFile(
                path=file_path,
                old_path=old_path,
                status=status,
                is_binary=patched_file.is_binary_file,
                hunks=hunks,
                patch=str(patched_file),
            )
        )

    return diff_files, LineLookup(line_coords)


def format_annotated_diff_for_prompt(files: list[DiffFile]) -> str:
    """Format parsed diff into an annotated text representation for LLM prompts."""
    output: list[str] = []

    for file_idx, file in enumerate(files, start=1):
        if file.is_binary:
            output.append(f"=== File {file_idx}: {file.path} (binary, skipped) ===")
            continue

        status_desc: str = file.status
        if file.status == "renamed" and file.old_path:
            status_desc = f"renamed from {file.old_path}"

        output.append(f"=== File {file_idx}: {file.path} ({status_desc}) ===")

        for hunk in file.hunks:
            output.append(
                f"@@ -{hunk.old_start},{hunk.old_lines} +{hunk.new_start},{hunk.new_lines} @@ {hunk.header}".rstrip()
            )
            for line in hunk.lines:
                prefix = "+" if line.type == "added" else ("-" if line.type == "removed" else " ")
                output.append(f"[{line.id}] {prefix} {line.content}")

    return "\n".join(output)
