# Notes: Failure Analysis & Verification Impact

## Common Failure Patterns in Baseline Runs

1. **Context Blindness (Handling Elsewhere)**:
   - *Symptom*: Model flags a missing `None` or `KeyError` check in a function.
   - *Cause*: The check was already performed in the calling function or middleware not present in the diff.
   - *Verification Fix*: The adversarial verifier is instructed to mark findings as "unclear" or "refuted" if context is insufficient to prove the bug occurs in practice.

2. **Stylistic & Nitpick Findings**:
   - *Symptom*: Model suggests renaming variables or refactoring list comprehensions.
   - *Cause*: Review prompt had broad instructions.
   - *Fix*: Validation stage drops low-confidence findings (< 0.70) and strictly filters out non-bug categories unless explicitly severe.

3. **Multi-Line Hunk Boundary Violations**:
   - *Symptom*: Findings specifying a range spanning across hunks or non-contiguous lines.
   - *Fix*: `LineLookup.validate_range()` drops multi-line findings whose endpoints cross hunk or file boundaries.
