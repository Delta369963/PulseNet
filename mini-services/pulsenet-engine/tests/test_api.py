"""API smoke tests via FastAPI TestClient (ripple + ledger + health + debug)."""

from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def test_health_reports_features(temp_db):
    client = _client()
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "features" in body
    assert "dual_consensus" in body["features"]


def test_ripple_endpoint_runs(seeded_db, mock_trade_intel):
    """Smoke test for POST /ripple — uses mock_trade_intel to avoid Gemini quota."""
    client = _client()
    res = client.post("/ripple", json={"shockId": seeded_db["shockId"]})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["exposuresCreated"] >= 2


def test_ripple_unknown_shock_404(temp_db):
    client = _client()
    res = client.post("/ripple", json={"shockId": "does-not-exist"})
    assert res.status_code == 404


def test_ledger_endpoint(seeded_db, mock_trade_intel):
    """Smoke test for GET /ledger after running ripple evaluation."""
    client = _client()
    client.post("/ripple", json={"shockId": seeded_db["shockId"]})
    res = client.get("/ledger")
    assert res.status_code == 200
    assert "ledger" in res.json()


def test_debug_shocks_endpoint(seeded_db, mock_trade_intel):
    """GET /debug/shocks returns all shocks with evaluation summary."""
    client = _client()
    res = client.get("/debug/shocks")
    assert res.status_code == 200
    body = res.json()
    assert "shocks" in body
    assert "total" in body
    assert body["total"] >= 1
    shock = body["shocks"][0]
    assert "id" in shock and "type" in shock and "severity" in shock
    assert "exposureCount" in shock and "rerouteCount" in shock


def test_debug_shock_detail_endpoint(seeded_db, mock_trade_intel):
    """GET /debug/shock/{id} returns full detail with exposures and reroutes."""
    client = _client()
    shock_id = seeded_db["shockId"]
    # Evaluate first so detail has data
    client.post("/ripple", json={"shockId": shock_id})

    res = client.get(f"/debug/shock/{shock_id}")
    assert res.status_code == 200
    body = res.json()
    assert "shock" in body
    assert "exposures" in body
    assert "reroutes" in body
    assert len(body["exposures"]) >= 2
    assert len(body["reroutes"]) >= 1


def test_debug_evaluate_endpoint(seeded_db, mock_trade_intel):
    """POST /debug/evaluate/{id} re-evaluates and returns full trace."""
    client = _client()
    shock_id = seeded_db["shockId"]
    res = client.post(f"/debug/evaluate/{shock_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["exposuresCreated"] >= 2


def test_debug_feeds_endpoint(temp_db):
    """GET /debug/feeds returns configured feed sources."""
    client = _client()
    res = client.get("/debug/feeds")
    assert res.status_code == 200
    body = res.json()
    assert "feeds" in body
    assert "total" in body
    assert body["total"] >= 1
