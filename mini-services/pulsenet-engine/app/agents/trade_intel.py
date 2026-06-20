"""Trade Intelligence — Gemini-powered per-shock commodity analysis.

Replaces hardcoded WHEAT/PHARMA assumptions with a live query to Gemini that
asks, for a given shock and affected country set:

  1. What are this country's main export commodities?  Will the shock disrupt those
     exports, and which downstream countries will be affected?
  2. What does this country NEED as emergency imports given the crisis type?
  3. In what order should we prioritise the 4 tracked commodities?

The result drives ripple_service logic:
  - exports_disrupted → outbound exposure (which countries lose supply)
  - needs_inbound     → humanitarian surge (who sends aid)
  - commodity_priority → sort order of exposure/reroute cards shown to the user
  - affected_countries_hint → Gemini-resolved country codes when DB had [] for codes
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.agents.llm import GeminiClient, parse_json_array
from app.logging import get_logger

logger = get_logger("agents.trade_intel")

TRACKED = ["LPG", "DIESEL", "WHEAT", "PHARMA"]


@dataclass
class TradeIntel:
    """Gemini-resolved trade context for one shock."""

    # commodity → bool: will the shock meaningfully disrupt this country's EXPORTS?
    exports_disrupted: dict[str, bool] = field(default_factory=dict)

    # commodity → bool: does the country need emergency IMPORTS of this commodity?
    needs_inbound: dict[str, bool] = field(default_factory=dict)

    # Ordered list of commodities by priority for this shock context
    commodity_priority: list[str] = field(default_factory=lambda: list(TRACKED))

    # Short Gemini-written context summary (shown in reroute rationale)
    context_summary: str = ""

    # Country codes that Gemini resolved from shock title/location (fallback)
    affected_countries_hint: list[str] = field(default_factory=list)

    # Whether Gemini was actually reachable (if False, everything is default)
    from_llm: bool = False

    @property
    def inbound_commodities(self) -> list[str]:
        """Return commodity codes that need inbound/humanitarian routing, ordered."""
        priority_map = {c: i for i, c in enumerate(self.commodity_priority)}
        return sorted(
            [c for c, v in self.needs_inbound.items() if v],
            key=lambda c: priority_map.get(c, 99),
        )

    @property
    def disrupted_export_commodities(self) -> list[str]:
        """Return commodity codes with disrupted exports, ordered by priority."""
        priority_map = {c: i for i, c in enumerate(self.commodity_priority)}
        return sorted(
            [c for c, v in self.exports_disrupted.items() if v],
            key=lambda c: priority_map.get(c, 99),
        )


_SYSTEM = """You are a supply-chain and geopolitical trade analyst for PulseNet.

Given a shock event and a set of affected countries, you must output a single JSON object.

JSON schema:
{
  "exports_disrupted": {"LPG": bool, "DIESEL": bool, "WHEAT": bool, "PHARMA": bool},
  "needs_inbound": {"LPG": bool, "DIESEL": bool, "WHEAT": bool, "PHARMA": bool},
  "commodity_priority": ["ordered", "list", "of", "4", "commodities"],
  "context_summary": "1-2 sentence summary of the key supply impact",
  "affected_countries_hint": ["ISO3", "codes", "of", "countries", "primarily", "affected"]
}

RULES:
- exports_disrupted[X] = true if the shock will meaningfully reduce exports of commodity X FROM the affected country.
  Example: Ukraine conflict → WHEAT=true (Ukraine is a major wheat exporter), PHARMA=false
- needs_inbound[X] = true if the affected country NOW NEEDS emergency imports of X due to the crisis.
  Example: Ukraine conflict → PHARMA=true (hospitals need medicine), DIESEL=true (military/civilian fuel)
  Example: Russia earthquake in uninhabited region → WHEAT=false (Russia exports wheat, small quake doesn't change that)
- commodity_priority: list all 4 commodities, most relevant to this shock first.
- context_summary: 1-2 sentences. Focus on which specific supply chains are at risk and why.
- affected_countries_hint: ISO-3 codes for countries primarily affected by this shock.
  If the shock title says "Russia" and codes are empty, include "RUS".

Be factual about actual world trade relationships. Russia exports wheat, oil/diesel.
Ukraine exports wheat, sunflower oil. Saudi Arabia exports LPG/diesel. 
India exports PHARMA. Germany exports PHARMA. China exports manufactured goods."""


def _user_prompt(shock_type: str, shock_title: str, shock_location: str,
                 severity: str, country_codes: list[str], country_names: list[str]) -> str:
    codes_str = ", ".join(country_codes) if country_codes else "unknown"
    names_str = ", ".join(country_names) if country_names else shock_location
    return (
        f"Shock type: {shock_type}\n"
        f"Severity: {severity}\n"
        f"Title: {shock_title}\n"
        f"Location: {shock_location}\n"
        f"Affected countries (ISO-3): {codes_str}\n"
        f"Affected country names: {names_str}\n\n"
        "Output the JSON trade intelligence object."
    )


def _default_intel(shock_type: str) -> TradeIntel:
    """Conservative defaults when Gemini is unavailable."""
    if shock_type == "conflict":
        return TradeIntel(
            exports_disrupted={"LPG": True, "DIESEL": True, "WHEAT": True, "PHARMA": False},
            needs_inbound={"PHARMA": True, "DIESEL": True, "LPG": False, "WHEAT": True},
            commodity_priority=["PHARMA", "DIESEL", "LPG", "WHEAT"],
            context_summary="Conflict event — PHARMA and fuel are primary humanitarian priorities.",
            from_llm=False,
        )
    elif shock_type in ("flood", "cyclone"):
        return TradeIntel(
            exports_disrupted={"LPG": False, "DIESEL": False, "WHEAT": True, "PHARMA": False},
            needs_inbound={"PHARMA": True, "DIESEL": False, "LPG": False, "WHEAT": False},
            commodity_priority=["PHARMA", "WHEAT", "DIESEL", "LPG"],
            context_summary="Natural disaster — PHARMA is the primary humanitarian priority.",
            from_llm=False,
        )
    elif shock_type == "earthquake":
        return TradeIntel(
            exports_disrupted={"LPG": False, "DIESEL": False, "WHEAT": False, "PHARMA": False},
            needs_inbound={"PHARMA": False, "DIESEL": False, "LPG": False, "WHEAT": False},
            commodity_priority=["DIESEL", "PHARMA", "LPG", "WHEAT"],
            context_summary="Earthquake — impact on supply chains depends on affected region.",
            from_llm=False,
        )
    return TradeIntel(
        exports_disrupted={c: False for c in TRACKED},
        needs_inbound={c: False for c in TRACKED},
        commodity_priority=list(TRACKED),
        from_llm=False,
    )


async def query_trade_intel(
    client: GeminiClient,
    shock_type: str,
    shock_title: str,
    shock_location: str,
    severity: str,
    country_codes: list[str],
    country_names: list[str],
) -> TradeIntel:
    """Query Gemini for trade intelligence about this shock.

    Falls back to conservative defaults if Gemini is unavailable.
    """
    if not client.available:
        logger.info("trade_intel: LLM dark, using defaults", extra={"extra": {"type": shock_type}})
        return _default_intel(shock_type)

    user_prompt = _user_prompt(shock_type, shock_title, shock_location, severity, country_codes, country_names)

    try:
        raw = await client.complete(_SYSTEM, user_prompt)
        if not raw:
            return _default_intel(shock_type)

        # Parse as object (not array)
        import re
        text = raw.strip()
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```\s*$", "", text).strip()
        # Extract first {...} block
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return _default_intel(shock_type)

        data = json.loads(text[start : end + 1])

        exports = {c: bool(data.get("exports_disrupted", {}).get(c, False)) for c in TRACKED}
        inbound = {c: bool(data.get("needs_inbound", {}).get(c, False)) for c in TRACKED}
        priority = data.get("commodity_priority", list(TRACKED))
        # Ensure all 4 commodities present
        for c in TRACKED:
            if c not in priority:
                priority.append(c)

        result = TradeIntel(
            exports_disrupted=exports,
            needs_inbound=inbound,
            commodity_priority=priority[:4],
            context_summary=str(data.get("context_summary", ""))[:300],
            affected_countries_hint=data.get("affected_countries_hint", []),
            from_llm=True,
        )
        logger.info(
            "trade_intel: ok",
            extra={"extra": {
                "type": shock_type,
                "disrupted": result.disrupted_export_commodities,
                "inbound": result.inbound_commodities,
                "from_llm": True,
            }},
        )
        return result

    except Exception as err:  # noqa: BLE001
        logger.warning("trade_intel: parse failed", extra={"extra": {"err": str(err)}})
        return _default_intel(shock_type)
