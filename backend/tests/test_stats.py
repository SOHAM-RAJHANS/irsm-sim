from backend.simulation.stats import rolling, fft_spectrum, cp_cpk
def test_rolling():
    h = [{"temp": 40+i*0.1, "vib_rms": 2.0, "current": 2.0} for i in range(10)]
    r = rolling(h)
    assert abs(r["temp_mean"] - 40.45) < 0.01
def test_fft():
    import math
    acc = [math.sin(2*math.pi*25*t/200.0) for t in range(400)]
    s = fft_spectrum(acc, 200.0)
    assert 20.0 <= s["dominant"] <= 30.0
def test_cp():
    assert cp_cpk([40.0]*20, 70.0, 20.0)["cp"] > 1.0
