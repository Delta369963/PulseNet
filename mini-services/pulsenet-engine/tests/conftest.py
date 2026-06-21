"""Shared pytest fixtures: temp DB, seeded graph, fake Gemini client."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

# Force a temp DB before any app import reads settings.
os.environ.setdefault("DATABASE_PATH", "/tmp/pulsenet_test_placeholder.db")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create an isolated SQLite DB with the schema built from the ORM models."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))

    from app.config import get_settings
    from app.db import session as session_mod
    from app.db.models import Base

    get_settings.cache_clear()
    session_mod.reset_engine()
    engine = session_mod.get_engine()
    Base.metadata.create_all(engine)
    yield session_mod
    session_mod.reset_engine()


@pytest.fixture
def seeded_db(temp_db):
    """Populate a minimal trade graph: RUS/UKR suppliers → EGY/KEN wheat."""
    from app.db import models, repo

    with temp_db.session_scope() as s:
        countries = [
            models.Country(code="RUS", name="Russia", region="Eurasia", lat=61.5, lng=105.3,
                           monitoringDensity=0.55, gdpPerCapita=12200, gridDensity=0.70,
                           historicalVolatility=0.58, sri=0.6),
            models.Country(code="UKR", name="Ukraine", region="Eurasia", lat=48.4, lng=31.2,
                           monitoringDensity=0.42, gdpPerCapita=4530, gridDensity=0.48,
                           historicalVolatility=0.88, sri=0.3),
            models.Country(code="EGY", name="Egypt", region="North Africa", lat=26.8, lng=30.8,
                           monitoringDensity=0.62, gdpPerCapita=3770, gridDensity=0.58,
                           historicalVolatility=0.62, sri=0.45),
            models.Country(code="KEN", name="Kenya", region="East Africa", lat=-0.0, lng=37.9,
                           monitoringDensity=0.43, gdpPerCapita=2090, gridDensity=0.38,
                           historicalVolatility=0.66, sri=0.3),
            models.Country(code="IND", name="India", region="South Asia", lat=21.0, lng=79.0,
                           monitoringDensity=0.72, gdpPerCapita=2480, gridDensity=0.62,
                           historicalVolatility=0.45, sri=0.5),
        ]
        for c in countries:
            s.add(c)
        s.flush()
        wheat = models.Commodity(code="WHEAT", name="Wheat", category="food", unit="kt")
        s.add(wheat)
        s.flush()
        by_code = {c.code: c for c in countries}
        edges = [
            ("RUS", "EGY", 0.50), ("UKR", "EGY", 0.26), ("USA_skip", "EGY", 0.0),
            ("RUS", "KEN", 0.35), ("UKR", "KEN", 0.20),
            ("IND", "EGY", 0.10),  # alternative (non-shocked) supplier
            ("IND", "KEN", 0.15),
        ]
        for sup, con, share in edges:
            if sup not in by_code:
                continue
            s.add(models.TradeEdge(supplierId=by_code[sup].id, consumerId=by_code[con].id,
                                   commodityId=wheat.id, volume=1000, share=share))
        s.flush()
        shock = repo.insert_shock(
            s,
            externalId="test-blacksea",
            source="WebSearch",
            sourceUrl="https://example.com/blacksea",
            title="Black Sea port closure (test)",
            description="Test shock.",
            type="port_closure",
            severity="high",
            lat=46.5,
            lng=32.0,
            locationName="Black Sea",
            countryCodes='["RUS", "UKR"]',
            occurredAt=datetime.now(timezone.utc),
            status="new",
            confidence=0.8,
        )
        shock_id = shock.id
    return {"shockId": shock_id}


class FakeGemini:
    """Fake GeminiClient: records prompts, returns a canned JSON array string."""

    def __init__(self, canned: str = "", available: bool = True):
        self.canned = canned
        self.available = available
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.canned


@pytest.fixture
def fake_gemini():
    return FakeGemini


@pytest.fixture
def mock_trade_intel(monkeypatch):
    """Patch query_trade_intel at the ripple_service import site.

    This avoids hitting the Gemini API during pytest runs (free tier: 20 req/day).
    Returns a TradeIntel configured for a conflict shock with WHEAT+DIESEL disrupted,
    which matches the seeded_db graph (RUS/UKR supply EGY/KEN wheat).

    Patches at app.services.ripple_service.query_trade_intel — the name that
    ripple_service resolved when it did 'from app.agents.trade_intel import query_trade_intel'.
    """
    from app.agents.trade_intel import TradeIntel

    async def _fake(*args, **kwargs):
        shock_type = kwargs.get("shock_type") or (args[1] if len(args) > 1 else "conflict")
        if shock_type in ("conflict", "port_closure", "strike", "border_restriction"):
            return TradeIntel(
                exports_disrupted={"LPG": False, "DIESEL": True, "WHEAT": True, "PHARMA": False},
                needs_inbound={"LPG": False, "DIESEL": False, "WHEAT": False, "PHARMA": True},
                commodity_priority=["WHEAT", "DIESEL", "PHARMA", "LPG"],
                context_summary="Conflict disrupts wheat and diesel exports; PHARMA aid needed.",
                affected_countries_hint=kwargs.get("country_codes") or [],
                from_llm=True,
            )
        elif shock_type == "earthquake":
            return TradeIntel(
                exports_disrupted={"LPG": False, "DIESEL": False, "WHEAT": False, "PHARMA": False},
                needs_inbound={"LPG": False, "DIESEL": False, "WHEAT": False, "PHARMA": False},
                commodity_priority=["DIESEL", "LPG", "PHARMA", "WHEAT"],
                context_summary="Minor earthquake — no major supply chain disruption expected.",
                affected_countries_hint=kwargs.get("country_codes") or [],
                from_llm=True,
            )
        else:
            return TradeIntel(
                exports_disrupted={"LPG": False, "DIESEL": True, "WHEAT": True, "PHARMA": False},
                needs_inbound={"LPG": False, "DIESEL": False, "WHEAT": False, "PHARMA": True},
                commodity_priority=["WHEAT", "DIESEL", "PHARMA", "LPG"],
                context_summary="Generic shock — WHEAT and DIESEL exports disrupted.",
                affected_countries_hint=kwargs.get("country_codes") or [],
                from_llm=True,
            )

    # Patch at the site where ripple_service resolved the name
    import app.services.ripple_service as rs
    monkeypatch.setattr(rs, "query_trade_intel", _fake)
    return _fake

