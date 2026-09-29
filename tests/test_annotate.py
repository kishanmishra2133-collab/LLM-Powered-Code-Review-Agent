"""Comprehensive unit tests for diff parsing and line annotation."""

import pytest

from reviewlens.engine.stages.annotate import (
    DiffParseError,
    format_annotated_diff_for_prompt,
    parse_diff,
)


def test_parse_diff_empty() -> None:
    files, lookup = parse_diff("")
    assert files == []
    assert len(lookup) == 0

    files, lookup = parse_diff("   \n  ")
    assert files == []
    assert len(lookup) == 0


def test_parse_diff_added_removed_context() -> None:
    diff_text = """--- a/calculator.py
+++ b/calculator.py
@@ -10,3 +10,4 @@
 def calculate(a, b):
-    return a / b
+    if b == 0:
+        raise ValueError("division by zero")
     return a / b
"""
    files, lookup = parse_diff(diff_text)
    assert len(files) == 1
    f = files[0]
    assert f.path == "calculator.py"
    assert f.status == "modified"
    assert len(f.hunks) == 1

    hunk = f.hunks[0]
    assert hunk.old_start == 10
    assert hunk.old_lines == 3
    assert hunk.new_start == 10
    assert hunk.new_lines == 4

    # Context line 10
    c10 = lookup.get("F1:L10")
    assert c10 is not None
    assert c10.side == "RIGHT"
    assert c10.line == 10
    assert c10.content == "def calculate(a, b):"

    # Removed line 11 (old line 11)
    d11 = lookup.get("F1:D11")
    assert d11 is not None
    assert d11.side == "LEFT"
    assert d11.line == 11
    assert d11.content == "    return a / b"

    # Added lines 11, 12, 13
    l11 = lookup.get("F1:L11")
    assert l11 is not None
    assert l11.side == "RIGHT"
    assert l11.line == 11
    assert l11.content == "    if b == 0:"

    l12 = lookup.get("F1:L12")
    assert l12 is not None
    assert l12.side == "RIGHT"
    assert l12.line == 12
    assert l12.content == '        raise ValueError("division by zero")'

    l13 = lookup.get("F1:L13")
    assert l13 is not None
    assert l13.side == "RIGHT"
    assert l13.line == 13
    assert l13.content == "    return a / b"


def test_parse_diff_multiple_hunks() -> None:
    diff_text = """--- a/service.py
+++ b/service.py
@@ -5,2 +5,3 @@
 import os
+import sys
 import logging
@@ -20,2 +21,2 @@
 def run():
-    start()
+    start_service()
"""
    files, lookup = parse_diff(diff_text)
    assert len(files) == 1
    f = files[0]
    assert len(f.hunks) == 2

    # Hunk 1
    assert lookup.get("F1:L6") is not None
    assert lookup.get("F1:L6").hunk_idx == 1  # type: ignore[union-attr]

    # Hunk 2
    assert lookup.get("F1:D21") is not None
    assert lookup.get("F1:D21").hunk_idx == 2  # type: ignore[union-attr]
    assert lookup.get("F1:L22") is not None
    assert lookup.get("F1:L22").hunk_idx == 2  # type: ignore[union-attr]


def test_parse_diff_no_newline_marker() -> None:
    diff_text = """--- a/greet.txt
+++ b/greet.txt
@@ -1 +1 @@
-Hello
+Hello World
\\ No newline at end of file
"""
    files, lookup = parse_diff(diff_text)
    assert len(files) == 1
    assert len(lookup) == 2

    d1 = lookup.get("F1:D1")
    assert d1 is not None
    assert d1.content == "Hello"

    l1 = lookup.get("F1:L1")
    assert l1 is not None
    assert l1.content == "Hello World"


def test_parse_diff_renamed_file() -> None:
    diff_text = """diff --git a/old_utils.py b/new_utils.py
similarity index 90%
rename from old_utils.py
rename to new_utils.py
--- a/old_utils.py
+++ b/new_utils.py
@@ -1 +1 @@
-def util(): return 1
+def util(): return 2
"""
    files, lookup = parse_diff(diff_text)
    assert len(files) == 1
    f = files[0]
    assert f.status == "renamed"
    assert f.path == "new_utils.py"
    assert f.old_path == "old_utils.py"

    coord = lookup.get("F1:L1")
    assert coord is not None
    assert coord.path == "new_utils.py"
    assert coord.content == "def util(): return 2"


def test_parse_diff_added_and_deleted_files() -> None:
    diff_text = """--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,2 @@
+def new():
+    pass
--- a/deleted_file.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def old():
-    pass
"""
    files, lookup = parse_diff(diff_text)
    assert len(files) == 2

    # Added file
    assert files[0].path == "new_file.py"
    assert files[0].status == "added"
    assert files[0].old_path is None
    coord_add = lookup.get("F1:L1")
    assert coord_add is not None
    assert coord_add.side == "RIGHT"

    # Deleted file
    assert files[1].path == "deleted_file.py"
    assert files[1].status == "deleted"
    coord_del = lookup.get("F2:D1")
    assert coord_del is not None
    assert coord_del.side == "LEFT"


def test_line_lookup_validation_range() -> None:
    diff_text = """--- a/app.py
+++ b/app.py
@@ -1,2 +1,5 @@
 def run():
+    x = 1
+    y = 2
+    z = 3
     return
@@ -20,2 +23,2 @@
 def helper():
-    old_fn()
+    new_fn()
"""
    files, lookup = parse_diff(diff_text)

    # Valid single line
    res_single = lookup.validate_range("F1:L2")
    assert res_single is not None
    coord, end_line = res_single
    assert coord.line == 2
    assert end_line is None

    # Valid multi-line range within same hunk
    res_range = lookup.validate_range("F1:L2", "F1:L4")
    assert res_range is not None
    coord, end_line = res_range
    assert coord.line == 2
    assert end_line == 4

    # Invalid: non-existent start ID
    assert lookup.validate_range("F1:L999") is None

    # Invalid: non-existent end ID
    assert lookup.validate_range("F1:L2", "F1:L999") is None

    # Invalid: cross-hunk range
    assert lookup.validate_range("F1:L2", "F1:L23") is None

    # Invalid: reversed range (start > end)
    assert lookup.validate_range("F1:L4", "F1:L2") is None


def test_format_annotated_diff_for_prompt() -> None:
    diff_text = """--- a/mod.py
+++ b/mod.py
@@ -1 +1 @@
-x = 1
+x = 2
"""
    files, _ = parse_diff(diff_text)
    prompt_diff = format_annotated_diff_for_prompt(files)

    assert "=== File 1: mod.py (modified) ===" in prompt_diff
    assert "[F1:D1] - x = 1" in prompt_diff
    assert "[F1:L1] + x = 2" in prompt_diff


def test_diff_parse_error_on_truncated_hunk() -> None:
    with pytest.raises(DiffParseError):
        # Hunk header declares 5 lines but only 1 provided
        parse_diff("--- a/f\n+++ b/f\n@@ -1,5 +1,5 @@\n-only one line\n")
