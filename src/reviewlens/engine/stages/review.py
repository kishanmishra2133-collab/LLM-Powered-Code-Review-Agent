"""Review stage: invokes Gemini with structured JSON output schema."""

from pathlib import Path

from pydantic import BaseModel, Field

from reviewlens.clients.gemini import GeminiClient
from reviewlens.engine.stages.annotate import format_annotated_diff_for_prompt
from reviewlens.models import DiffFile, NodeUsage, PRMeta, RawFinding

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "review_v1.md"


class RawFindingsResponse(BaseModel):
    """Schema expected from Gemini review call."""

    findings: list[RawFinding] = Field(default_factory=list)


def _load_prompt_template() -> tuple[str, str]:
    """Load system instruction and user prompt template from markdown."""
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


async def review_stage(
    files: list[DiffFile],
    meta: PRMeta | None,
    gemini_client: GeminiClient,
) -> tuple[list[RawFinding], NodeUsage]:
    """Generate raw findings for the given diff using Gemini."""
    if not files:
        return [], NodeUsage()

    annotated_diff = format_annotated_diff_for_prompt(files)
    sys_instruction, template = _load_prompt_template()

    title = meta.title if meta else "Untitled PR"
    author = meta.author if meta else "unknown"
    body = meta.body if meta else ""

    user_prompt = (
        template.replace("{{title}}", title)
        .replace("{{author}}", author)
        .replace("{{body}}", body)
        .replace("{{diff}}", annotated_diff)
    )

    response, usage = await gemini_client.generate_structured(
        contents=user_prompt,
        response_schema=RawFindingsResponse,
        system_instruction=sys_instruction,
        temperature=0.2,
    )

    return response.findings, usage
