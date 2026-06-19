"""Agent Alpha/Beta — parse raw feed items into StructuredShock objects.

Both agents share this code; only their GeminiClient (Key A vs Key B) differs.
Pre-structured items (USGS) bypass the LLM. RSS items go through the LLM; if the
LLM is dark/failed, a deterministic keyword parser keeps the pipeline alive.

Deterministic fallback improvements:
  - Matches geopolitical/conflict terms (airstrike, shelling, invasion, etc.)
  - Auto-tags country_codes by scanning text for known country names/aliases
  - Does NOT gate on supply-chain keywords for conflict/disaster types
"""

from __future__ import annotations

import re

from app.agents.llm import GeminiClient, parse_json_array
from app.agents.prompts import (
    EVENT_TYPES,
    SEVERITIES,
    ingestion_system_prompt,
    ingestion_user_prompt,
)
from app.logging import get_logger
from app.schemas import RawItem, StructuredShock

logger = get_logger("agents.parser")

# Keyword → event type for the deterministic fallback.
_KEYWORDS: list[tuple[str, str]] = [
    ("earthquake", "earthquake"),
    ("seismic", "earthquake"),
    ("flood", "flood"),
    ("flooding", "flood"),
    ("cyclone", "cyclone"),
    ("hurricane", "cyclone"),
    ("typhoon", "cyclone"),
    ("storm", "cyclone"),
    ("port", "port_closure"),
    ("strait", "port_closure"),
    ("blockade", "border_restriction"),
    ("border", "border_restriction"),
    ("strike", "strike"),
    ("grid", "grid_failure"),
    ("blackout", "grid_failure"),
    ("powerout", "grid_failure"),
    # Geopolitical / conflict terms
    ("conflict", "conflict"),
    ("war", "conflict"),
    ("attack", "conflict"),
    ("airstrike", "conflict"),
    ("shelling", "conflict"),
    ("missile", "conflict"),
    ("bomb", "conflict"),
    ("bombing", "conflict"),
    ("invasion", "conflict"),
    ("offensive", "conflict"),
    ("combat", "conflict"),
    ("coup", "conflict"),
    ("assassination", "conflict"),
    ("troops", "conflict"),
    ("military", "conflict"),
    ("ceasefire", "conflict"),
    ("casualties", "conflict"),
    ("refugees", "conflict"),
    ("displaced", "conflict"),
    ("humanitarian", "conflict"),
    ("crisis", "conflict"),
    ("sanctions", "border_restriction"),
]

# Commodity-supply hints — only used as an ADDITIONAL filter for non-disaster types
_SUPPLY_HINTS = frozenset((
    "supply", "shortage", "fuel", "lpg", "diesel", "wheat", "grain", "pharma",
    "shipping", "export", "import", "port", "refinery", "cargo", "food",
    "medicine", "aid", "relief", "logistics", "refugee", "displaced",
))

# Event types that pass through without needing supply-chain keywords
_ALWAYS_INCLUDE_TYPES = frozenset((
    "conflict", "cyclone", "flood", "earthquake", "port_closure", "grid_failure",
    "border_restriction",
))


def _severity_to_score(sev: str) -> int:
    return {"low": 2, "moderate": 5, "high": 7, "severe": 9}.get(sev, 5)


def structured_from_prestructured(item: RawItem) -> StructuredShock:
    """USGS-style items already have type/severity/coords — no LLM."""
    return StructuredShock(
        source=item.source,
        title=item.title,
        description=item.summary,
        type=item.shock_type or "earthquake",
        severity=item.severity or "moderate",
        severity_score=_severity_to_score(item.severity or "moderate"),
        location_name=item.title.split("—")[-1].strip() if "—" in item.title else item.title,
        lat=item.lat,
        lng=item.lng,
        country_codes=item.country_codes,
        confidence=0.9,
    )


def _extract_countries(text: str, country_name_map: dict[str, str]) -> list[str]:
    """Scan text for country names and return ISO3 codes."""
    found: list[str] = []
    text_lower = text.lower()
    # Sort by length descending so "saudi arabia" matches before "saudi"
    for name, code in sorted(country_name_map.items(), key=lambda x: -len(x[0])):
        if name in text_lower and code not in found:
            found.append(code)
    return found


def deterministic_parse(
    item: RawItem,
    country_name_map: dict[str, str] | None = None,
) -> StructuredShock | None:
    """Keyword fallback when the LLM is unavailable.

    Detects disaster/conflict events. For non-disaster types, requires
    at least one supply-chain hint in the text.
    """
    text = f"{item.title} {item.summary}".lower()
    words = set(re.findall(r"[a-z]+", text))

    shock_type = None
    for kw, typ in _KEYWORDS:
        if kw in words:
            shock_type = typ
            break

    if shock_type is None:
        return None

    # For conflict/disaster, always include; for other types need supply hint
    if shock_type not in _ALWAYS_INCLUDE_TYPES:
        if not any(h in words for h in _SUPPLY_HINTS):
            return None

    # Auto-tag countries from text when country_name_map is available
    codes = item.country_codes or []
    if not codes and country_name_map:
        codes = _extract_countries(f"{item.title} {item.summary}", country_name_map)

    # Severity heuristic from text signals
    severity = "moderate"
    if any(w in words for w in ("severe", "devastating", "catastrophic", "mass", "major")):
        severity = "high"
    if any(w in words for w in ("war", "invasion", "airstrike", "shelling", "offensive")):
        severity = "high"

    return StructuredShock(
        source=item.source,
        title=item.title[:120],
        description=(item.summary or item.title)[:240],
        type=shock_type,
        severity=severity,
        severity_score=_severity_to_score(severity),
        location_name=item.title[:80],
        lat=item.lat,
        lng=item.lng,
        country_codes=codes,
        confidence=0.55,
    )


def _coerce(raw: dict, catalog_codes: set[str]) -> StructuredShock | None:
    """Validate one LLM dict into a StructuredShock (drops invalid)."""
    try:
        typ = raw.get("type")
        sev = raw.get("severity")
        if typ not in EVENT_TYPES or sev not in SEVERITIES:
            return None
        codes = [c for c in (raw.get("country_codes") or []) if c in catalog_codes]
        return StructuredShock(
            source=str(raw.get("source", "WebSearch"))[:50],
            title=str(raw["title"])[:120],
            description=str(raw.get("description", ""))[:300],
            type=typ,
            severity=sev,
            severity_score=int(raw.get("severity_score", _severity_to_score(sev))),
            location_name=str(raw.get("location_name", "Unknown")),
            lat=raw.get("lat"),
            lng=raw.get("lng"),
            country_codes=codes,
            confidence=float(raw.get("confidence", 0.7)),
        )
    except (KeyError, ValueError, TypeError):
        return None


async def parse_items(
    client: GeminiClient,
    items: list[RawItem],
    country_catalog: str,
    catalog_codes: set[str],
    country_name_map: dict[str, str] | None = None,
) -> list[StructuredShock]:
    """Parse a batch of RSS items via one Gemini client (single batched call)."""
    if not items:
        return []
    block = "\n\n".join(
        f"{i + 1}. [{it.source}/{it.lang}] {it.title}\n{it.summary}\nURL: {it.source_url}"
        for i, it in enumerate(items)
    )
    raw = await client.complete(ingestion_system_prompt(), ingestion_user_prompt(country_catalog, block))
    parsed = parse_json_array(raw)
    out: list[StructuredShock] = []
    for d in parsed:
        shock = _coerce(d, catalog_codes)
        if shock:
            out.append(shock)
    if not out:  # LLM dark or returned nothing usable → deterministic fallback
        for it in items:
            d = deterministic_parse(it, country_name_map)
            if d:
                out.append(d)
    return out
