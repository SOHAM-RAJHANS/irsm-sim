from backend.simulation.thresholds import classify, reset
def test_t1_normal():
    reset()
    assert classify(40.0, 2.0, 2.0)["overall"] == "Normal"
def test_t2_temp_warning():
    reset()
    for _ in range(3):
        r = classify(60.0, 2.0, 2.0)
    assert r["overall"] == "Warning"
def test_t3_critical():
    reset()
    for _ in range(3):
        r = classify(40.0, 8.0, 2.0)
    assert r["overall"] == "Maintenance Required"
def test_t4_return_normal():
    reset()
    for _ in range(3):
        classify(75.0, 2.0, 2.0)
    for _ in range(3):
        r = classify(40.0, 2.0, 2.0)
    assert r["overall"] == "Normal"
