from backend.simulation.scenarios import get_fault, SCENARIOS
def test_scenarios_exist():
    assert "Normal" in SCENARIOS and "BearingWear" in SCENARIOS
def test_wear_fault():
    assert get_fault("BearingWear")["wear"] > 0
