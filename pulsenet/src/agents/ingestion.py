"""Agent 1 — Ingestion Filter: raw feed text → structured event JSON."""

import json
import re
from typing import Dict, Optional

from src.config import GEMINI_INGESTION_API_KEY, USE_GEMINI
from src.feeds.connectors import _guess_country, _parse_gdacs_type, _parse_gdacs_severity

GEMINI_PROMPT = """Extract structured event data from this shock signal text.
Return ONLY valid JSON with these fields:
{
  "event_type": "earthquake|flood|cyclone|conflict|geopolitical|supply_chain|disaster",
  "country_code": "3-letter ISO code or null",
  "latitude": number or null,
  "longitude": number or null,
  "severity": "red|orange|green",
  "confidence": 0.0-1.0,
  "summary": "one sentence summary"
}

Text:
"""


def _rule_based_extract(raw_event: Dict) -> Dict:
    """Deterministic fallback when Gemini is unavailable."""
    title = raw_event.get("title", "")
    description = raw_event.get("description", "")
    combined = f"{title} {description}"

    event_type = raw_event.get("event_type") or _parse_gdacs_type(title)
    country = raw_event.get("country_code") or _guess_country(combined)
    severity = raw_event.get("severity") or _parse_gdacs_severity(title, description)
    confidence = raw_event.get("confidence", 0.7)

    lat = raw_event.get("latitude")
    lon = raw_event.get("longitude")

    if lat is None or lon is None:
        coord_match = re.search(
            r"lat[itude]*[:=\s]+([-\d.]+).*lon[gitude]*[:=\s]+([-\d.]+)",
            combined, re.I,
        )
        if coord_match:
            lat, lon = float(coord_match.group(1)), float(coord_match.group(2))

    return {
        **raw_event,
        "event_type": event_type,
        "country_code": country,
        "latitude": lat,
        "longitude": lon,
        "severity": severity,
        "confidence": confidence,
        "summary": title[:200],
        "extraction_method": "rule_based",
    }


def _gemini_extract(raw_event: Dict) -> Dict:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_INGESTION_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        text = raw_event.get("raw_text", "") or f"{raw_event.get('title', '')}\n{raw_event.get('description', '')}"
        response = model.generate_content(GEMINI_PROMPT + text)
        content = response.text.strip()

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {
                **raw_event,
                "event_type": parsed.get("event_type", raw_event.get("event_type")),
                "country_code": parsed.get("country_code") or raw_event.get("country_code"),
                "latitude": parsed.get("latitude") or raw_event.get("latitude"),
                "longitude": parsed.get("longitude") or raw_event.get("longitude"),
                "severity": parsed.get("severity", raw_event.get("severity")),
                "confidence": parsed.get("confidence", raw_event.get("confidence")),
                "summary": parsed.get("summary", raw_event.get("title")),
                "extraction_method": "gemini",
            }
    except Exception as e:
        print(f"Gemini extraction failed: {e}")

    return _rule_based_extract(raw_event)


def ingest_event(raw_event: Dict) -> Dict:
    """Run ingestion filter on a raw feed event."""
    if USE_GEMINI and GEMINI_INGESTION_API_KEY:
        return _gemini_extract(raw_event)
    return _rule_based_extract(raw_event)
