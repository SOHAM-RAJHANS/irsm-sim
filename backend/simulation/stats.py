import math
def _mean(x): return sum(x)/len(x) if x else 0.0
def _std(x):
    m = _mean(x)
    return math.sqrt(sum((v-m)**2 for v in x)/len(x)) if len(x)>1 else 0.0
def rolling(history):
    t=[h["temp"] for h in history]; v=[h["vib_rms"] for h in history]; c=[h["current"] for h in history]
    return {"temp_mean": _mean(t), "temp_std": _std(t), "vib_mean": _mean(v), "vib_std": _std(v),
            "curr_mean": _mean(c), "curr_std": _std(c),
            "temp_min": min(t) if t else 0, "temp_max": max(t) if t else 0}
def fft_spectrum(accel, fs=200.0):
    n=len(accel)
    mags=[]
    freqs=[k*fs/n for k in range(n//2)]
    for k in range(n//2):
        re=sum(accel[j]*math.cos(2*math.pi*k*j/n) for j in range(n))/n
        im=sum(accel[j]*math.sin(2*math.pi*k*j/n) for j in range(n))/n
        mags.append(math.sqrt(re*re+im*im))
    dom=freqs[mags.index(max(mags))] if mags else 0.0
    return {"freqs": freqs[::4], "mags": mags[::4], "dominant": dom}
def cp_cpk(data, usl, lsl):
    m=_mean(data); s=_std(data) or 1e-6
    cp=(usl-lsl)/(6*s); cpu=(usl-m)/(3*s); cpl=(m-lsl)/(3*s)
    return {"cp": cp, "cpk": min(cpu, cpl)}
def rul_heuristic(temp, vib):
    score=100.0 - max(0.0, temp-45.0)*2.0 - max(0.0, vib-3.0)*8.0
    return max(0.0, min(100.0, score))
