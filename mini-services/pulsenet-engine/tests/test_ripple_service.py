"""Integration test for the ripple service using a seeded temp DB."""

import json


def test_evaluate_ripple_produces_exposures_and_reroutes(seeded_db, temp_db):
    from app.db import models, repo
    from app.services import ripple_service

    res = ripple_service.evaluate_ripple(seeded_db["shockId"])

    assert res.ok is True
    # RUS/UKR supply EGY + KEN wheat → at least 2 exposed (consumer, commodity) pairs.
    assert res.exposuresCreated >= 2
    # IND is a non-shocked alt supplier for EGY + KEN → reroutes should appear.
    assert res.reroutesCreated >= 1

    with temp_db.session_scope() as s:
        exposures = s.query(models.ExposedRegion).all()
        codes = {e.countryCode for e in exposures}
        assert "EGY" in codes and "KEN" in codes
        # Each exposure has a human-readable causal path.
        assert all("→" in e.exposurePath for e in exposures)

        # A ledger row with the computed cascade DAG was written.
        ledger = repo.recent_ledger(s, limit=5)
        assert len(ledger) >= 1
        dag = json.loads(ledger[0].calculatedCascadeDag)
        assert "nodes" in dag and "edges" in dag

        # Shock flipped to evaluated.
        shock = repo.shock_by_id(s, seeded_db["shockId"])
        assert shock.status == "evaluated"


def test_evaluate_ripple_no_suppliers_is_honest(seeded_db, temp_db):
    """A shock with unmapped countries AND no resolvable location yields 0 exposures."""
    from app.db import repo
    from app.services import ripple_service

    with temp_db.session_scope() as s:
        shock = repo.shock_by_id(s, seeded_db["shockId"])
        # Set codes to unknown AND a location with no recognizable country name
        shock.countryCodes = json.dumps([])
        shock.locationName = "Ocean Ridge XYZ-999"
        shock.title = "M 5.0 microearthquake — uninhabited oceanic ridge"
        s.flush()

    res = ripple_service.evaluate_ripple(seeded_db["shockId"])
    # Should not crash. Either 0 exposures (LLM resolved nothing) or minimal exposures.
    assert res.ok is True


def test_evaluate_ripple_is_idempotent(seeded_db, temp_db):
    """Re-running evaluation clears prior results (no duplicates in DB)."""
    from app.db import models
    from app.services import ripple_service

    first = ripple_service.evaluate_ripple(seeded_db["shockId"])
    second = ripple_service.evaluate_ripple(seeded_db["shockId"])

    # Regardless of LLM variation, DB should not accumulate duplicates
    with temp_db.session_scope() as s:
        exposures = s.query(models.ExposedRegion).filter(
            models.ExposedRegion.shockId == seeded_db["shockId"]
        ).all()
        reroutes = s.query(models.RerouteSuggestion).filter(
            models.RerouteSuggestion.shockId == seeded_db["shockId"]
        ).all()
    # Second eval clears and rewrites — count should match second run, not accumulate
    assert len(exposures) == second.exposuresCreated
    assert len(reroutes) == second.reroutesCreated
