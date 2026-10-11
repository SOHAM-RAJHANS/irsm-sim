from fastapi.testclient import TestClient
from backend.app import app
def test_latest_and_scenario():
    c = TestClient(app)
    assert c.get("/api/telemetry/latest").status_code == 200
    r = c.post("/api/scenario", json={"name": "Overheat"})
    assert r.status_code == 200
    assert c.get("/api/export.csv").status_code == 200
