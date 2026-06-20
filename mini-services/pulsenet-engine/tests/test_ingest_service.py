"""Integration test for the ingestion service (feeds + agents mocked)."""

import pytest

from app.schemas import RawItem
from tests.conftest import FakeGemini


@pytest.mark.asyncio
async def test_run_ingestion_inserts_shocks_and_ledger(seeded_db, temp_db, monkeypatch):
    from app.db import models
    from app.services import ingest_service

    # Mock feeds: one USGS (prestructured) + one RSS item.
    fake_items = [
        RawItem(
            source="USGS", source_url="https://usgs", title="M 6.6 earthquake — Test Sea",
            summary="seismic", lat=46.5, lng=32.0, prestructured=True,
            severity="high", shock_type="earthquake",
        ),
        RawItem(source="GDACS", source_url="https://gdacs", title="Port closure halts wheat", summary="supply"),
    ]

    async def fake_fetch_all(_sources):
        return fake_items

    monkeypatch.setattr(ingest_service, "load_sources", lambda: [])
    monkeypatch.setattr(ingest_service, "fetch_all", fake_fetch_all)

    canned = (
        '[{"title":"Port closure halts wheat","description":"wheat halt",'
        '"type":"port_closure","severity":"high","severity_score":7,'
        '"location_name":"Black Sea","lat":46.5,"lng":32.0,'
        '"country_codes":["RUS"],"confidence":0.8}]'
    )
    monkeypatch.setattr(
        ingest_service, "build_clients",
        lambda: (FakeGemini(canned=canned), FakeGemini(canned=canned)),
    )

    res = await ingest_service.run_ingestion()

    assert res.ok is True
    assert res.inserted >= 1
    assert res.ledgerRows >= 1
    assert res.correlationId

    with temp_db.session_scope() as s:
        shocks = s.query(models.ShockEvent).all()
        # seeded shock + newly ingested
        assert len(shocks) >= 2
        ledger = s.query(models.SystemicConsensusLedger).all()
        assert len(ledger) >= 1


@pytest.mark.asyncio
async def test_run_ingestion_dedupes(seeded_db, temp_db, monkeypatch):
    from app.services import ingest_service

    fake_items = [
        RawItem(source="USGS", source_url="https://usgs-unique-url", title="M 7.0 earthquake — Dup Ridge",
                summary="x", lat=10.0, lng=10.0, prestructured=True,
                severity="severe", shock_type="earthquake"),
    ]

    async def fake_fetch_all(_sources):
        return fake_items

    monkeypatch.setattr(ingest_service, "load_sources", lambda: [])
    monkeypatch.setattr(ingest_service, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(ingest_service, "build_clients", lambda: (FakeGemini(), FakeGemini()))

    first = await ingest_service.run_ingestion()
    second = await ingest_service.run_ingestion()
    assert first.inserted >= 1
    # Second run: either pre-deduped (url known) OR externalId dedupe fires
    assert second.inserted == 0 or second.skipped >= 1
