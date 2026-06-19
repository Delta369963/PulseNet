"""API smoke tests via FastAPI TestClient (ripple + ledger + health)."""

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


def test_ripple_endpoint_runs(seeded_db):
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


def test_ledger_endpoint(seeded_db):
    client = _client()
    # Run a ripple first so a ledger row exists.
    client.post("/ripple", json={"shockId": seeded_db["shockId"]})
    res = client.get("/ledger")
    assert res.status_code == 200
    assert "ledger" in res.json()
