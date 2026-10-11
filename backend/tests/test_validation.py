from fastapi.testclient import TestClient
from backend.app import app
from backend.simulation.thresholds import classify, reset
def test_validation_suite():
    reset()
    assert classify(40,2,2)["overall"]=="Normal"
    for _ in range(3): r=classify(60,2,2)
    assert r["overall"]=="Warning"
    for _ in range(3): r=classify(40,8,2)
    assert r["overall"]=="Maintenance Required"
    c=TestClient(app)
    assert c.get("/api/health").status_code==200
