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
    """A shock with unmapped countries yields zero exposure (honest, not a crash)."""
    from app.db import repo
    from app.services import ripple_service

    with temp_db.session_scope() as s:
        shock = repo.shock_by_id(s, seeded_db["shockId"])
        shock.countryCodes = json.dumps(["ZZZ"])  # not in graph
        s.flush()

    res = ripple_service.evaluate_ripple(seeded_db["shockId"])
    assert res.exposuresCreated == 0
    assert res.reroutesCreated == 0
    assert res.note is not None


def test_evaluate_ripple_is_idempotent(seeded_db):
    """Re-running evaluation clears prior results (no duplicates)."""
    from app.services import ripple_service

    first = ripple_service.evaluate_ripple(seeded_db["shockId"])
    second = ripple_service.evaluate_ripple(seeded_db["shockId"])
    assert first.exposuresCreated == second.exposuresCreated
