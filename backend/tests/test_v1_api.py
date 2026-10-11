from fastapi.testclient import TestClient
from backend.app import app

def test_v1_endpoints():
    c = TestClient(app)
    assert c.get("/api/v1/health").status_code == 200
    assert c.get("/api/v1/device").status_code == 200
    assert c.get("/api/v1/telemetry/latest").status_code == 200
    assert c.get("/api/v1/telemetry/history?channel=temp&limit=10").status_code == 200
    assert c.get("/api/v1/stats/summary").status_code == 200
    assert c.get("/api/v1/alerts").status_code == 200
    assert c.get("/api/v1/thresholds").status_code == 200
    assert c.get("/api/v1/diagnostics").status_code == 200
    assert c.get("/api/v1/export/csv?rows=10").status_code == 200
