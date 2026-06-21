"""Integration test for the ripple service using a seeded temp DB.

All tests that call evaluate_ripple() use the `mock_trade_intel` fixture
(defined in conftest.py) to avoid hitting the Gemini API during CI.
Trade intel itself is tested independently in test_trade_intel.py.
"""

import json
import pytest


def test_evaluate_ripple_produces_exposures_and_reroutes(seeded_db, temp_db, mock_trade_intel):
    """Verify ripple evaluation produces exposures and reroutes for a conflict shock.

    seeded_db: RUS + UKR supply EGY + KEN wheat (port_closure shock).
    mock_trade_intel: returns WHEAT+DIESEL disrupted → outbound exposures expected.
    """
    from app.db import models, repo
    from app.services import ripple_service

    res = ripple_service.evaluate_ripple(seeded_db["shockId"])

    assert res.ok is True
    assert res.exposuresCreated >= 2, f"Expected >=2 exposures, got {res.exposuresCreated}"
    assert res.reroutesCreated >= 1, f"Expected >=1 reroutes, got {res.reroutesCreated}"

    with temp_db.session_scope() as s:
        exposures = s.query(models.ExposedRegion).all()
        codes = {e.countryCode for e in exposures}
        assert "EGY" in codes and "KEN" in codes, f"Expected EGY+KEN exposed, got {codes}"
        # Each exposure has a human-readable causal path.
        assert all("→" in e.exposurePath for e in exposures), "All paths must contain →"

        # A ledger row with cascade DAG was written.
        ledger = repo.recent_ledger(s, limit=5)
        assert len(ledger) >= 1
        dag = json.loads(ledger[0].calculatedCascadeDag)
        assert "nodes" in dag and "edges" in dag

        # Shock status flipped to evaluated.
        shock = repo.shock_by_id(s, seeded_db["shockId"])
        assert shock.status == "evaluated"


def test_evaluate_ripple_no_suppliers_is_honest(seeded_db, temp_db, mock_trade_intel):
    """Shock with no recognizable country → 0 exposures (honest, no crash)."""
    from app.db import repo
    from app.services import ripple_service
    import app.services.ripple_service as rs
    from app.agents.trade_intel import TradeIntel

    # Override mock to also return no affected_countries_hint
    async def no_country_intel(*args, **kwargs):
        return TradeIntel(
            exports_disrupted={c: False for c in ["LPG", "DIESEL", "WHEAT", "PHARMA"]},
            needs_inbound={c: False for c in ["LPG", "DIESEL", "WHEAT", "PHARMA"]},
            commodity_priority=["DIESEL", "LPG", "WHEAT", "PHARMA"],
            context_summary="Unknown location — no supply chain impact identified.",
            affected_countries_hint=[],
            from_llm=True,
        )
    rs.query_trade_intel = no_country_intel

    with temp_db.session_scope() as s:
        shock = repo.shock_by_id(s, seeded_db["shockId"])
        shock.countryCodes = json.dumps([])
        shock.locationName = "Ocean Ridge XYZ-999"
        shock.title = "M 5.0 microearthquake — uninhabited oceanic ridge"
        s.flush()

    res = ripple_service.evaluate_ripple(seeded_db["shockId"])
    assert res.ok is True
    assert res.exposuresCreated == 0
    assert res.reroutesCreated == 0


def test_evaluate_ripple_is_idempotent(seeded_db, temp_db, mock_trade_intel):
    """Re-running evaluation clears prior results — DB count matches last run."""
    from app.db import models
    from app.services import ripple_service

    first = ripple_service.evaluate_ripple(seeded_db["shockId"])
    second = ripple_service.evaluate_ripple(seeded_db["shockId"])

    with temp_db.session_scope() as s:
        exposures = s.query(models.ExposedRegion).filter(
            models.ExposedRegion.shockId == seeded_db["shockId"]
        ).all()
        reroutes = s.query(models.RerouteSuggestion).filter(
            models.RerouteSuggestion.shockId == seeded_db["shockId"]
        ).all()

    assert len(exposures) == second.exposuresCreated, "DB must match second eval, not accumulate"
    assert len(reroutes) == second.reroutesCreated


def test_evaluate_ripple_country_code_fallback(temp_db, mock_trade_intel):
    """Empty countryCodes resolved from shock title text → exposures produced."""
    from app.db import models, repo
    from app.services import ripple_service
    import app.services.ripple_service as rs
    from app.agents.trade_intel import TradeIntel
    from datetime import datetime, timezone
    import json as _json

    # Override mock to return RUS hint from location text (like Gemini would)
    async def russia_intel(*args, **kwargs):
        return TradeIntel(
            exports_disrupted={"LPG": False, "DIESEL": True, "WHEAT": True, "PHARMA": False},
            needs_inbound={c: False for c in ["LPG", "DIESEL", "WHEAT", "PHARMA"]},
            commodity_priority=["WHEAT", "DIESEL", "LPG", "PHARMA"],
            context_summary="Russia earthquake disrupts diesel/wheat exports.",
            affected_countries_hint=["RUS"],  # Gemini resolves from title
            from_llm=True,
        )
    rs.query_trade_intel = russia_intel

    with temp_db.session_scope() as s:
        rus = models.Country(code="RUS", name="Russia", region="Eurasia",
                             lat=61.5, lng=105.3, monitoringDensity=0.55,
                             gdpPerCapita=12200, gridDensity=0.70,
                             historicalVolatility=0.58, sri=0.6)
        egy = models.Country(code="EGY", name="Egypt", region="Africa",
                             lat=26.0, lng=30.0, monitoringDensity=0.52,
                             gdpPerCapita=3550, gridDensity=0.55,
                             historicalVolatility=0.62, sri=0.35)
        wheat = models.Commodity(code="WHEAT", name="Wheat", category="food", unit="mt")
        for obj in [rus, egy, wheat]:
            s.add(obj)
        s.flush()
        s.add(models.TradeEdge(supplierId=rus.id, consumerId=egy.id,
                               commodityId=wheat.id, volume=8800, share=0.50))
        s.flush()

        shock = repo.insert_shock(
            s,
            externalId="test-russia-empty-codes",
            source="USGS",
            title="M 6.6 earthquake — 133 km ESE of Petropavlovsk-Kamchatsky, Russia",
            description="Significant earthquake in Russia.",
            type="earthquake",
            severity="high",
            lat=52.0, lng=162.0,
            locationName="Petropavlovsk-Kamchatsky, Russia",
            countryCodes=_json.dumps([]),  # EMPTY — resolved from text fallback
            occurredAt=datetime.now(timezone.utc),
            status="new",
            confidence=0.9,
        )
        shock_id = shock.id

    res = ripple_service.evaluate_ripple(shock_id)
    assert res.ok is True
    assert res.exposuresCreated >= 1, f"Expected EGY exposure via RUS→EGY wheat, got {res.exposuresCreated}"

    with temp_db.session_scope() as s:
        exposures = s.query(models.ExposedRegion).filter_by(shockId=shock_id).all()
        codes = {e.countryCode for e in exposures}
        assert "EGY" in codes, f"Egypt should be exposed via Russia→Egypt wheat edge, got {codes}"


def test_hitl_approve_reject_recorded(seeded_db, temp_db, mock_trade_intel):
    """Approve and reject reroute suggestions — verify DB status changes correctly."""
    from app.db import models, repo
    from app.services import ripple_service
    from sqlalchemy import select

    # Run eval to produce reroutes
    res = ripple_service.evaluate_ripple(seeded_db["shockId"])
    assert res.reroutesCreated >= 1, "Need reroutes to test HITL"

    with temp_db.session_scope() as s:
        reroutes = s.scalars(
            select(models.RerouteSuggestion).where(
                models.RerouteSuggestion.shockId == seeded_db["shockId"]
            )
        ).all()
        assert all(r.status == "pending" for r in reroutes), "All fresh reroutes should be pending"

        first_id = reroutes[0].id
        second_id = reroutes[1].id if len(reroutes) > 1 else reroutes[0].id

        # Approve first
        reroutes[0].status = "approved"
        reroutes[0].decidedBy = "test-operator"
        reroutes[0].adminNote = "Approved for immediate dispatch"
        if len(reroutes) > 1:
            # Reject second
            reroutes[1].status = "rejected"
            reroutes[1].decidedBy = "test-operator"
            reroutes[1].adminNote = "Route blocked by sanctions"
        s.flush()

    # Verify status persisted correctly
    with temp_db.session_scope() as s:
        approved = s.get(models.RerouteSuggestion, first_id)
        assert approved.status == "approved"
        assert approved.decidedBy == "test-operator"
        assert "dispatch" in approved.adminNote

        if second_id != first_id:
            rejected = s.get(models.RerouteSuggestion, second_id)
            assert rejected.status == "rejected"
            assert "sanctions" in rejected.adminNote

    # Idempotent re-eval clears and re-creates reroutes — they go back to pending
    res2 = ripple_service.evaluate_ripple(seeded_db["shockId"])
    with temp_db.session_scope() as s:
        new_reroutes = s.scalars(
            select(models.RerouteSuggestion).where(
                models.RerouteSuggestion.shockId == seeded_db["shockId"]
            )
        ).all()
        assert all(r.status == "pending" for r in new_reroutes), \
            "Re-evaluation should create fresh pending reroutes"


def test_chaining_cascade_dag_written(seeded_db, temp_db, mock_trade_intel):
    """Verify cascade DAG contains nodes for downstream countries (chaining)."""
    from app.db import models, repo
    from app.services import ripple_service

    res = ripple_service.evaluate_ripple(seeded_db["shockId"])
    assert res.exposuresCreated >= 2

    with temp_db.session_scope() as s:
        ledger = repo.recent_ledger(s, limit=1)
        assert len(ledger) >= 1

        dag = json.loads(ledger[0].calculatedCascadeDag)
        assert "nodes" in dag
        assert "edges" in dag

        # Root node should be present
        node_ids = {n["id"] for n in dag["nodes"]}
        assert "root" in node_ids, "DAG must have root node"

        # Downstream nations should be in the DAG
        assert len(dag["nodes"]) >= 3, "DAG should have root + at least 2 downstream nodes"
        assert len(dag["edges"]) >= 2, "DAG should have edges connecting root to downstream"

        # All non-root nodes should have condProb < 1.0 (exposure share applied)
        downstream = [n for n in dag["nodes"] if n["id"] != "root"]
        assert all(n["condProb"] < 1.0 for n in downstream), \
            "Downstream cascade probabilities should be < 1.0 (scaled by exposure share)"

        # tradeIntel should be recorded in the ledger
        shock_vector = json.loads(ledger[0].detectedShockVector or "{}")
        ti = shock_vector.get("tradeIntel", {})
        assert ti.get("fromLLM") is True, "Trade intel should record fromLLM=True"
        assert "disrupted" in ti
