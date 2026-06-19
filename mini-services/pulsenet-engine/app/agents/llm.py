"""Gemini client wrapper + tolerant JSON parsing.

Two clients (Key A / Key B) power the Alpha/Beta consensus. If a key is missing,
that agent is "dark" and the caller falls back to deterministic parsing — the
pipeline never hard-fails on a missing credential.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings
from app.logging import get_logger

logger = get_logger("agents.llm")


class GeminiClient:
    """Thin async wrapper around google-generativeai for one API key."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.available = bool(api_key)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw JSON string, or '' on any failure (logged).

        Forces JSON-only output via response_mime_type — no markdown fences,
        no prose, just valid JSON. This uses fewer tokens and avoids parsing
        failures from the tolerant parser.
        """
        if not self.available:
            return ""
        try:
            import asyncio

            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            generation_config = genai.GenerationConfig(
                response_mime_type="application/json",
            )
            model = genai.GenerativeModel(
                self.model,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )
            # google-generativeai is sync; run in a thread to stay async-friendly.
            resp = await asyncio.to_thread(model.generate_content, user_prompt)
            output_text = resp.text or ""
            print(f"\\n--- GEMINI REQUEST ({self.model}) ---")
            print(f"SYSTEM PROMPT:\\n{system_prompt}\\n")
            print(f"USER PROMPT:\\n{user_prompt}\\n")
            print(f"--- GEMINI RESPONSE ---\\n{output_text}\\n------------------------\\n", flush=True)
            return output_text
        except Exception as err:  # noqa: BLE001
            logger.warning("gemini completion failed", extra={"extra": {"err": str(err)}})
            return ""



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
