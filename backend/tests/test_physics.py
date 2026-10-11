from backend.simulation.physics import PhysicsState
def test_physics_bounds_and_drift():
    s = PhysicsState()
    out = None
    for _ in range(20):
        out = s.step(dt=0.5, load=0.5, fault={})
    assert -10 <= out["temp"] <= 120
    assert 0 <= out["vib_rms"] <= 20
    assert 0 <= out["current"] <= 6
    assert len(out["accel"]) == 100
    assert len(out["joints"]) == 3
def test_overheat_fault_raises_temp():
    s = PhysicsState()
    for _ in range(40):
        s.step(dt=0.5, load=0.8, fault={"overheat": 8.0})
    assert s.temp > 40.0
