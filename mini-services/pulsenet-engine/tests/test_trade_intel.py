"""Tests for trade intelligence agent.

Verifies that:
- Default intel is correct for each shock type (no Gemini needed)
- Gemini response is parsed correctly when available
- TradeIntel priority + inbound properties work correctly
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.trade_intel import (
    TradeIntel,
    _default_intel,
    query_trade_intel,
    TRACKED,
)
from app.agents.llm import GeminiClient


# ─────────── Default intel correctness ────────────────────────────────────────

class TestDefaultIntel:
    def test_earthquake_no_surge(self):
        """Small/moderate earthquake → no default humanitarian surge."""
        intel = _default_intel("earthquake")
        assert intel.inbound_commodities == []
        assert intel.disrupted_export_commodities == []
        assert not intel.from_llm

    def test_conflict_pharma_diesel_priority(self):
        """Conflict events default to PHARMA + DIESEL as primary needs."""
        intel = _default_intel("conflict")
        inbound = intel.inbound_commodities
        assert "PHARMA" in inbound, "PHARMA should be needed for conflict"
        assert "DIESEL" in inbound, "DIESEL should be needed for conflict"
        # PHARMA should rank higher than WHEAT for conflict
        if "WHEAT" in inbound:
            assert inbound.index("PHARMA") < inbound.index("WHEAT")
        assert not intel.from_llm

    def test_flood_cyclone_pharma_priority(self):
        """Natural disasters default to PHARMA as highest need."""
        for shock_type in ("flood", "cyclone"):
            intel = _default_intel(shock_type)
            assert "PHARMA" in intel.inbound_commodities, f"{shock_type} should need PHARMA"

    def test_priority_has_all_commodities(self):
        """commodity_priority always lists all 4 tracked commodities."""
        for shock_type in ("earthquake", "conflict", "flood", "cyclone"):
            intel = _default_intel(shock_type)
            assert set(intel.commodity_priority) == set(TRACKED), \
                f"{shock_type}: missing commodities in priority"


# ─────────── TradeIntel property methods ──────────────────────────────────────

class TestTradeIntelProperties:
    def test_inbound_commodities_ordered_by_priority(self):
        intel = TradeIntel(
            needs_inbound={"PHARMA": True, "DIESEL": True, "WHEAT": False, "LPG": False},
            commodity_priority=["DIESEL", "PHARMA", "WHEAT", "LPG"],
        )
        # DIESEL should come first as it's higher in priority list
        result = intel.inbound_commodities
        assert result[0] == "DIESEL"
        assert result[1] == "PHARMA"

    def test_disrupted_excludes_false(self):
        intel = TradeIntel(
            exports_disrupted={"WHEAT": True, "DIESEL": False, "PHARMA": False, "LPG": True},
            commodity_priority=["WHEAT", "LPG", "DIESEL", "PHARMA"],
        )
        disrupted = intel.disrupted_export_commodities
        assert "WHEAT" in disrupted
        assert "LPG" in disrupted
        assert "DIESEL" not in disrupted

    def test_empty_inbound_when_all_false(self):
        intel = TradeIntel(
            needs_inbound={"PHARMA": False, "DIESEL": False, "WHEAT": False, "LPG": False},
        )
        assert intel.inbound_commodities == []


# ─────────── Gemini integration (mocked) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_query_trade_intel_parses_gemini_response():
    """Verify that a valid Gemini JSON response is parsed into TradeIntel."""
    gemini_json = """{
      "exports_disrupted": {"LPG": false, "DIESEL": true, "WHEAT": true, "PHARMA": false},
      "needs_inbound": {"LPG": false, "DIESEL": true, "PHARMA": true, "WHEAT": false},
      "commodity_priority": ["PHARMA", "DIESEL", "WHEAT", "LPG"],
      "context_summary": "Ukraine conflict disrupts wheat exports; country needs PHARMA and diesel.",
      "affected_countries_hint": ["UKR"]
    }"""

    mock_client = AsyncMock(spec=GeminiClient)
    mock_client.available = True
    mock_client.complete = AsyncMock(return_value=gemini_json)

    intel = await query_trade_intel(
        client=mock_client,
        shock_type="conflict",
        shock_title="Russia-Ukraine war intensifies",
        shock_location="Kyiv, Ukraine",
        severity="high",
        country_codes=["UKR"],
        country_names=["Ukraine"],
    )

    assert intel.from_llm is True
    assert intel.exports_disrupted["WHEAT"] is True
    assert intel.exports_disrupted["DIESEL"] is True
    assert intel.exports_disrupted["PHARMA"] is False
    assert intel.needs_inbound["PHARMA"] is True
    assert intel.needs_inbound["DIESEL"] is True
    assert intel.commodity_priority[0] == "PHARMA"
    assert "UKR" in intel.affected_countries_hint


@pytest.mark.asyncio
async def test_query_trade_intel_falls_back_on_empty_response():
    """When Gemini returns empty string, fall back to defaults."""
    mock_client = AsyncMock(spec=GeminiClient)
    mock_client.available = True
    mock_client.complete = AsyncMock(return_value="")

    intel = await query_trade_intel(
        client=mock_client,
        shock_type="flood",
        shock_title="Flooding in Bangladesh",
        shock_location="Dhaka, Bangladesh",
        severity="moderate",
        country_codes=["BGD"],
        country_names=["Bangladesh"],
    )
    assert not intel.from_llm
    # Should fall back to flood defaults
    assert "PHARMA" in intel.inbound_commodities


@pytest.mark.asyncio
async def test_query_trade_intel_dark_client_uses_defaults():
    """Dark client (no API key) → defaults immediately."""
    dark_client = AsyncMock(spec=GeminiClient)
    dark_client.available = False

    intel = await query_trade_intel(
        client=dark_client,
        shock_type="earthquake",
        shock_title="M 7.2 earthquake in Turkey",
        shock_location="Ankara, Turkey",
        severity="severe",
        country_codes=["TUR"],
        country_names=["Turkey"],
    )
    assert not intel.from_llm


@pytest.mark.asyncio
async def test_russia_earthquake_does_not_get_wheat_surge():
    """Russia earthquake should NOT produce a wheat import surge (Russia exports wheat)."""
    # Gemini correctly identifies Russia doesn't need wheat imported
    gemini_json = """{
      "exports_disrupted": {"LPG": false, "DIESEL": false, "WHEAT": false, "PHARMA": false},
      "needs_inbound": {"LPG": false, "DIESEL": false, "PHARMA": false, "WHEAT": false},
      "commodity_priority": ["DIESEL", "LPG", "PHARMA", "WHEAT"],
      "context_summary": "Minor earthquake in remote Russia; no significant supply chain impact.",
      "affected_countries_hint": ["RUS"]
    }"""
    mock_client = AsyncMock(spec=GeminiClient)
    mock_client.available = True
    mock_client.complete = AsyncMock(return_value=gemini_json)

    intel = await query_trade_intel(
        client=mock_client,
        shock_type="earthquake",
        shock_title="M 5.8 earthquake in Russia",
        shock_location="Petropavlovsk-Kamchatsky, Russia",
        severity="moderate",
        country_codes=["RUS"],
        country_names=["Russia"],
    )

    assert intel.needs_inbound.get("WHEAT") is False, "Russia should NOT need wheat imports"
    assert intel.inbound_commodities == [], "No commodities should be surged to Russia for a small quake"
