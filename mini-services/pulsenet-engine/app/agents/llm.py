"""Gemini client wrapper + tolerant JSON parsing.

Two clients (Key A / Key B) power the Alpha/Beta consensus. If a key is missing,
that agent is "dark" and the caller falls back to deterministic parsing — the
pipeline never hard-fails on a missing credential.

Uses google-genai SDK (google.genai) — the modern replacement for the deprecated
google.generativeai package.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings
from app.logging import get_logger

logger = get_logger("agents.llm")


class GeminiClient:
    """Thin async wrapper around google-genai for one API key."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.available = bool(api_key)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw JSON string, or '' on any failure (logged).

        Forces JSON-only output via response_mime_type — no markdown fences,
        no prose, just valid JSON. Uses fewer tokens and avoids parsing failures.
        """
        if not self.available:
            return ""
        try:
            import asyncio
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            )

            def _call() -> str:
                response = client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config,
                )
                return response.text or ""

            output_text = await asyncio.to_thread(_call)
            logger.debug(
                "gemini completion",
                extra={"extra": {"model": self.model, "response_len": len(output_text)}},
            )
            return output_text
        except Exception as err:  # noqa: BLE001
            logger.warning("gemini completion failed", extra={"extra": {"err": str(err)}})
            return ""

    async def complete_object(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Call complete() and parse result as a single JSON object."""
        raw = await self.complete(system_prompt, user_prompt)
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}


def build_clients() -> tuple[GeminiClient, GeminiClient]:
    """Construct the Alpha (Key A) and Beta (Key B) clients from settings."""
    s = get_settings()
    alpha = GeminiClient(s.gemini_api_key_a, s.gemini_model)
    beta = GeminiClient(s.gemini_api_key_b, s.gemini_model)
    return alpha, beta


def parse_json_array(raw: str) -> list[dict[str, Any]]:
    """Tolerant parser: strips markdown fences, extracts the first [...] block."""
    if not raw:
        return []
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```\s*$", "", text).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []
