"""Gemini API client using the official google-genai SDK directly."""

import asyncio
import json
import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from reviewlens.models import NodeUsage

T = TypeVar("T", bound=BaseModel)

# Default pricing per token for Gemini Flash models
# $0.075 per 1M prompt tokens, $0.30 per 1M candidate tokens
_PROMPT_PRICE_PER_TOKEN = 0.075 / 1_000_000
_CANDIDATES_PRICE_PER_TOKEN = 0.30 / 1_000_000


class GeminiError(Exception):
    """Base exception for Gemini API errors."""


class GeminiClient:
    """Async client wrapping the official google-genai SDK with cost accounting."""

    def __init__(self, api_key: str, model_id: str = "gemini-3-flash-preview") -> None:
        self.api_key = api_key
        self.model_id = model_id
        self._client = genai.Client(api_key=api_key)

    async def generate_structured(
        self,
        contents: str,
        response_schema: type[T],
        system_instruction: str = "",
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> tuple[T, NodeUsage]:
        """Generate structured JSON output validated against a Pydantic schema."""
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            system_instruction=system_instruction if system_instruction else None,
            temperature=temperature,
        )

        models_to_try = [self.model_id]
        for fallback in ("gemini-3-flash-preview", "gemini-3.8-flash", "gemini-3.5-flash"):
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_exc: Exception | None = None
        for current_model in models_to_try:
            for attempt in range(max_retries):
                start_time = time.perf_counter()
                try:
                    response = await self._client.aio.models.generate_content(
                        model=current_model,
                        contents=contents,
                        config=config,
                    )
                    latency_ms = int((time.perf_counter() - start_time) * 1000)

                    prompt_tokens = 0
                    candidates_tokens = 0
                    total_tokens = 0

                    if response.usage_metadata:
                        prompt_tokens = response.usage_metadata.prompt_token_count or 0
                        candidates_tokens = response.usage_metadata.candidates_token_count or 0
                        total_tokens = response.usage_metadata.total_token_count or (prompt_tokens + candidates_tokens)

                    cost_usd = (prompt_tokens * _PROMPT_PRICE_PER_TOKEN) + (
                        candidates_tokens * _CANDIDATES_PRICE_PER_TOKEN
                    )

                    usage = NodeUsage(
                        prompt_tokens=prompt_tokens,
                        candidates_tokens=candidates_tokens,
                        total_tokens=total_tokens,
                        cost_usd=round(cost_usd, 6),
                        latency_ms=latency_ms,
                    )

                    # Parse JSON response into target schema
                    text = response.text or "{}"
                    parsed_data = json.loads(text)
                    validated_obj = response_schema.model_validate(parsed_data)

                    return validated_obj, usage

                except Exception as exc:
                    last_exc = exc
                    err_str = str(exc).lower()
                    # If model is deprecated (404) or experiencing high demand (503), try next model immediately
                    if "404" in err_str or "503" in err_str or "unavailable" in err_str or "not found" in err_str:
                        break
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1.0 * (2**attempt))
                        continue
                    break

        raise GeminiError(f"Gemini generation failed: {last_exc}") from last_exc
