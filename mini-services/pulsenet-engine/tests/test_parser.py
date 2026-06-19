"""Tests for Agent Alpha/Beta parsing (mocked Gemini, no network)."""

import pytest

from app.agents.parser import deterministic_parse, parse_items, structured_from_prestructured
from app.schemas import RawItem
from tests.conftest import FakeGemini

CATALOG = "RUS: Russia, UKR: Ukraine, EGY: Egypt"
CODES = {"RUS", "UKR", "EGY"}


def test_prestructured_passthrough():
    item = RawItem(
        source="USGS", title="M 6.7 earthquake — Test Ridge", summary="x",
        lat=28.4, lng=51.2, prestructured=True, severity="severe", shock_type="earthquake",
    )
    s = structured_from_prestructured(item)
    assert s.type == "earthquake"
    assert s.severity == "severe"
    assert s.confidence == 0.9


def test_deterministic_parse_detects_supply_event():
    item = RawItem(source="RSS", title="Port closure halts diesel shipping", summary="fuel supply")
    s = deterministic_parse(item)
    assert s is not None
    assert s.type == "port_closure"


def test_deterministic_parse_skips_irrelevant():
    item = RawItem(source="RSS", title="Local football match results", summary="sports news")
    assert deterministic_parse(item) is None


@pytest.mark.asyncio
async def test_parse_items_uses_llm_json():
    canned = (
        '[{"title":"Black Sea port closure","description":"wheat halt",'
        '"type":"port_closure","severity":"high","severity_score":7,'
        '"location_name":"Black Sea","lat":46.5,"lng":32.0,'
        '"country_codes":["RUS","UKR"],"confidence":0.8}]'
    )
    client = FakeGemini(canned=canned, available=True)
    items = [RawItem(source="RSS", title="raw news", summary="text")]
    out = await parse_items(client, items, CATALOG, CODES)
    assert len(out) == 1
    assert out[0].type == "port_closure"
    assert out[0].country_codes == ["RUS", "UKR"]


@pytest.mark.asyncio
async def test_parse_items_falls_back_when_llm_empty():
    client = FakeGemini(canned="", available=True)
    items = [RawItem(source="RSS", title="Port strike halts wheat exports", summary="supply")]
    out = await parse_items(client, items, CATALOG, CODES)
    # Deterministic fallback should still produce a shock.
    assert len(out) == 1
    assert out[0].type == "port_closure"


@pytest.mark.asyncio
async def test_parse_items_filters_invalid_country_codes():
    canned = (
        '[{"title":"x","description":"y","type":"conflict","severity":"low",'
        '"severity_score":2,"location_name":"z","lat":null,"lng":null,'
        '"country_codes":["RUS","ZZZ"],"confidence":0.5}]'
    )
    client = FakeGemini(canned=canned, available=True)
    out = await parse_items(client, [RawItem(source="RSS", title="t", summary="s")], CATALOG, CODES)
    assert out[0].country_codes == ["RUS"]  # ZZZ dropped (not in catalog)
