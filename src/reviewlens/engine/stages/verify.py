"""Verification stage: adversarial refutation of findings using Gemini."""

import asyncio
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from reviewlens.clients.gemini import GeminiClient
from reviewlens.models import DiffFile, DroppedFinding, Finding, NodeUsage

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "verify_v1.md"


class VerificationResponse(BaseModel):
    """Schema expected from Gemini verification call."""

    verdict: Literal["supported", "refuted", "unclear"]
    reason: str = Field(description="Explanation of the verdict based on code context.")


def _load_prompt_template() -> tuple[str, str]:
    text = _PROMPT_PATH.read_text(encoding="utf-8")
    sys_marker = "## System Instruction"
    user_marker = "## User Prompt Template"

    sys_part = ""
    user_part = ""
    if sys_marker in text and user_marker in text:
        after_sys = text.split(sys_marker, 1)[1]
        sys_part, user_part = after_sys.split(user_marker, 1)
    else:
        user_part = text

    return sys_part.strip(), user_part.strip()


def _extract_context(finding: Finding, files: list[DiffFile]) -> str:
    """Find hunk lines surrounding the finding's target line."""
    for file in files:
        if file.path != finding.file:
            continue
        for hunk in file.hunks:
            for line in hunk.lines:
                line_no = line.new_line_no if finding.side == "RIGHT" else line.old_line_no
                if line_no == finding.line:
                    # Found matching hunk, return entire hunk lines
                    return "\n".join(
                        f"{'+' if diff_line.type == 'added' else ('-' if diff_line.type == 'removed' else ' ')} {diff_line.content}"
                        for diff_line in hunk.lines
                    )
    return "Context unavailable."


async def _verify_single(
    finding: Finding,
    files: list[DiffFile],
    gemini_client: GeminiClient,
    sys_instruction: str,
    template: str,
) -> tuple[Finding | None, DroppedFinding | None, NodeUsage]:
    context = _extract_context(finding, files)
    line_range = f"line {finding.line}" if not finding.end_line else f"lines {finding.line}-{finding.end_line}"

    prompt = (
        template.replace("{{file}}", finding.file)
        .replace("{{line_range}}", line_range)
        .replace("{{severity}}", finding.severity)
        .replace("{{category}}", finding.category)
        .replace("{{title}}", finding.title)
        .replace("{{body}}", finding.body)
        .replace("{{suggestion}}", finding.suggestion or "None")
        .replace("{{context}}", context)
    )

    try:
        response, usage = await gemini_client.generate_structured(
            contents=prompt,
            response_schema=VerificationResponse,
            system_instruction=sys_instruction,
            temperature=0.1,
        )

        if response.verdict == "supported":
            verified_finding = finding.model_copy(update={"verified": True})
            return verified_finding, None, usage
        else:
            dropped = DroppedFinding(
                finding=finding,
                reason=f"{response.verdict}: {response.reason}",
            )
            return None, dropped, usage

    except Exception as exc:
        # If verification fails, fall back to dropping or keeping conservatively
        dropped = DroppedFinding(
            finding=finding,
            reason=f"verification_error: {exc}",
        )
        return None, dropped, NodeUsage()


async def verify_stage(
    findings: list[Finding],
    files: list[DiffFile],
    gemini_client: GeminiClient,
) -> tuple[list[Finding], list[DroppedFinding], NodeUsage]:
    """Run concurrent adversarial verification on all accepted findings."""
    if not findings:
        return [], [], NodeUsage()

    sys_instruction, template = _load_prompt_template()

    tasks = [
        _verify_single(f, files, gemini_client, sys_instruction, template)
        for f in findings
    ]
    results = await asyncio.gather(*tasks)

    verified: list[Finding] = []
    dropped: list[DroppedFinding] = []
    total_usage = NodeUsage()

    for v_find, d_find, usage in results:
        if v_find:
            verified.append(v_find)
        if d_find:
            dropped.append(d_find)

        total_usage.prompt_tokens += usage.prompt_tokens
        total_usage.candidates_tokens += usage.candidates_tokens
        total_usage.total_tokens += usage.total_tokens
        total_usage.cost_usd = round(total_usage.cost_usd + usage.cost_usd, 6)
        total_usage.latency_ms = max(total_usage.latency_ms, usage.latency_ms)

    return verified, dropped, total_usage
