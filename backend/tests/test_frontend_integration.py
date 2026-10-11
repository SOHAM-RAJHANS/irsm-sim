import pytest
from fastapi.testclient import TestClient
from backend.app import app

def test_frontend_served_and_contains_integrations():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    html = r.text
    # Verify title
    assert "Industrial Robotics Monitoring System" in html
    # Verify Three.js is loaded
    assert "three.min.js" in html
    # Verify backend badge and scenario controls
    assert "backendBadge" in html
    assert "backendScenarioSel" in html
    # Verify 3D digital twin canvas
    assert 'id="twin"' in html
    # Verify WebSocket integration code is present
    assert "initBackendWS" in html
    assert "wsBackend" in html

def test_websocket_streaming():
    c = TestClient(app)
    with c.websocket_connect("/ws/live") as ws:
        data = ws.receive_json()
        assert "temp" in data
        assert "vib_rms" in data
        assert "current" in data
        assert "status" in data
        assert "joints" in data
        assert len(data["joints"]) == 3
