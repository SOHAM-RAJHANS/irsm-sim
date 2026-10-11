import sys, os
_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _base not in sys.path:
    sys.path.insert(0, _base)

from fastapi import FastAPI, WebSocket, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, JSONResponse
from contextlib import asynccontextmanager
import asyncio, sqlite3, time, math
from backend.simulation.physics import PhysicsState
from backend.simulation.thresholds import classify
from backend.simulation.stats import rolling, fft_spectrum, rul_heuristic, cp_cpk
from backend.simulation.scenarios import SCENARIOS, get_fault

state = PhysicsState()
current_scenario = {"name": "Normal"}
history: list = []
events: list = []
start_time = time.time()
active_connections: set[WebSocket] = set()

DB = os.path.join(os.path.dirname(__file__), "irsm.db")

def _db():
    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("CREATE TABLE IF NOT EXISTS telemetry(ts REAL, temp REAL, vib REAL, curr REAL, status TEXT)")
    return con

# Active threshold configuration matching industry ISO / IEC standards
threshold_config = {
    "temp": {"warn": 55.0, "crit": 70.0},
    "vib": {"warn": 4.5, "crit": 7.1},
    "cur": {"warn": 3.0, "crit": 4.0},
    "pwr": {"warn": 85.0, "crit": 115.0},
    "hyst": 1.5,
    "debounce": 3,
    "evalMode": "worst",
    "publishRateHz": 2
}

# Pre-populate some historical telemetry so charts immediately show data
t_now = time.time()
for i in range(120):
    t_hist = t_now - (120 - i) * 0.5
    f_hist = get_fault("Normal")
    step_out = state.step(dt=0.5, load=f_hist.get("load", 0.5), fault=f_hist)
    c_hist = classify(step_out["temp"], step_out["vib_rms"], step_out["current"])
    pkt_hist = {
        "ts": t_hist,
        "temp": step_out["temp"],
        "vib_rms": step_out["vib_rms"],
        "current": step_out["current"],
        "status": c_hist["overall"],
        "joints": step_out["joints"],
        "phase": step_out["phase"]
    }
    history.append(pkt_hist)

# Background Telemetry Broadcaster & Multi-client WebSocket Loop
async def simulation_loop():
    while True:
        try:
            f = get_fault(current_scenario["name"])
            out = state.step(dt=0.5, load=f.get("load", 0.5), fault=f)
            c = classify(out["temp"], out["vib_rms"], out["current"])
            pkt = {
                "ts": time.time(),
                "temp": out["temp"],
                "vib_rms": out["vib_rms"],
                "current": out["current"],
                "status": c["overall"],
                "joints": out["joints"],
                "phase": out["phase"]
            }
            history.append(pkt)
            if len(history) > 2000:
                del history[:500]
            try:
                con = _db()
                con.execute("INSERT INTO telemetry VALUES(?,?,?,?,?)", (pkt["ts"], pkt["temp"], pkt["vib_rms"], pkt["current"], pkt["status"]))
                con.commit()
                con.close()
            except Exception:
                pass

            dead = set()
            for ws in list(active_connections):
                try:
                    await ws.send_json(pkt)
                except Exception:
                    dead.add(ws)
            active_connections.difference_update(dead)
        except Exception:
            pass
        await asyncio.sleep(0.5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(simulation_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="IRSM Sim - Industrial Robotics Monitoring System",
    version="2.4.1",
    lifespan=lifespan
)

# --- Standard v0 / Legacy Endpoints (Contract Preserved) ---
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/telemetry/latest")
def latest():
    if not history:
        return {"temp": 32.0, "vib_rms": 1.2, "current": 1.8, "status": "Normal"}
    return history[-1]

@app.get("/api/telemetry/history")
def hist(limit: int = 300):
    return history[-limit:]

@app.get("/api/spectrum")
def spectrum():
    acc = state.accel_buf[-400:]
    return fft_spectrum(acc, 200.0)

@app.get("/api/stats")
def stats():
    h = history[-120:]
    r = rolling(h) if h else {}
    last_temp = history[-1]["temp"] if history else 32.0
    last_vib = history[-1]["vib_rms"] if history else 1.2
    r["rul"] = rul_heuristic(last_temp, last_vib)
    return r

@app.get("/api/events")
def ev():
    return events[-100:]

@app.get("/api/scenarios")
def sc():
    return list(SCENARIOS.keys())

@app.post("/api/scenario")
def set_sc(p: dict):
    name = p.get("name", "Normal")
    current_scenario["name"] = name
    events.append({"ts": time.time(), "msg": f"Scenario -> {current_scenario['name']}"})
    return {"ok": True, "scenario": current_scenario["name"]}

@app.get("/api/export.csv")
def export():
    lines = ["ts,temp,vib,current,status"]
    for h in history:
        lines.append(f"{h.get('ts',0)},{h.get('temp',0)},{h.get('vib_rms',0)},{h.get('current',0)},{h.get('status','')}")
    return PlainTextResponse("\n".join(lines), media_type="text/csv")

# --- Enterprise v1 Endpoints (for Dashboard Console & External Integration) ---
@app.get("/api/v1/health")
def v1_health():
    return {
        "status": "UP",
        "simTime": round(state.t, 2),
        "uptime": round(time.time() - start_time, 1),
        "engine": "running",
        "broker": "connected",
        "version": "2.4.1"
    }

@app.get("/api/v1/device")
def v1_device():
    cur = history[-1] if history else {"status": "Normal", "temp": 32.0, "vib_rms": 1.2}
    health_idx = rul_heuristic(cur.get("temp", 32.0), cur.get("vib_rms", 1.2))
    return {
        "deviceId": "esp32-arm01",
        "asset": "ARM-01",
        "cell": "CELL-A",
        "line": "LINE-3",
        "firmware": "IRMS v2.4",
        "ip": "10.20.4.117",
        "rssi": -52.0,
        "lastSeen": round(time.time(), 2),
        "status": cur.get("status", "Normal"),
        "health": round(health_idx, 2)
    }

@app.get("/api/v1/telemetry/latest")
def v1_latest():
    cur = history[-1] if history else {"ts": time.time(), "temp": 32.0, "vib_rms": 1.2, "current": 1.8, "status": "Normal"}
    st = cur.get("status", "Normal")
    lvl = 2 if "Maintenance" in st else (1 if "Warning" in st else 0)
    current_val = cur.get("current", 1.8)
    bus_v = 24.0
    return {
        "ts": round(cur.get("ts", time.time()), 2),
        "temperature": round(cur.get("temp", 32.0), 3),
        "vibration": round(cur.get("vib_rms", 1.2), 3),
        "current": round(current_val, 3),
        "voltage": bus_v,
        "power": round(bus_v * current_val, 1),
        "kurtosis": 3.0,
        "healthIndex": round(rul_heuristic(cur.get("temp", 32.0), cur.get("vib_rms", 1.2)), 2),
        "status": st.upper(),
        "level": lvl
    }

@app.get("/api/v1/telemetry/history")
def v1_telemetry_history(channel: str = Query("temp"), limit: int = Query(100)):
    lim = min(limit, len(history))
    data = []
    ch_key = channel.lower()
    for h in history[-lim:]:
        if ch_key in ["temp", "temperature"]:
            val = h.get("temp", 0.0)
        elif ch_key in ["vib", "vibration"]:
            val = h.get("vib_rms", 0.0)
        elif ch_key in ["cur", "curr", "current"]:
            val = h.get("current", 0.0)
        elif ch_key in ["pwr", "power"]:
            val = 24.0 * h.get("current", 0.0)
        else:
            val = h.get("temp", 0.0)
        data.append({"ts": round(h.get("ts", 0), 2), "v": round(val, 4)})
    return {
        "channel": channel,
        "count": len(data),
        "series": f"{channel.capitalize()} Historical Telemetry",
        "data": data
    }

@app.get("/api/v1/stats/summary")
def v1_stats_summary():
    h = history[-600:] if len(history) >= 600 else history
    temps = [p["temp"] for p in h] if h else [32.0]
    vibs = [p["vib_rms"] for p in h] if h else [1.2]
    currs = [p["current"] for p in h] if h else [1.8]
    pwrs = [c * 24.0 for c in currs]
    hlths = [rul_heuristic(t, v) for t, v in zip(temps, vibs)]

    def calc(arr):
        n = len(arr)
        if not n:
            return {}
        m = sum(arr) / n
        var = sum((x - m)**2 for x in arr) / max(1, n - 1)
        sd = math.sqrt(var)
        s_arr = sorted(arr)
        return {
            "n": n,
            "mean": round(m, 4),
            "sd": round(sd, 4),
            "min": round(min(arr), 3),
            "max": round(max(arr), 3),
            "p95": round(s_arr[int(0.95 * (n - 1))], 3),
            "skew": 0.0,
            "kurt": 3.0
        }

    return {
        "window": len(h),
        "stats": {
            "temp": calc(temps),
            "vib": calc(vibs),
            "cur": calc(currs),
            "pwr": calc(pwrs),
            "health": calc(hlths)
        }
    }

@app.get("/api/v1/alerts")
def v1_alerts(limit: int = 25):
    alerts = []
    for idx, e in enumerate(events[-limit:]):
        alerts.append({
            "id": idx + 1,
            "simTime": round(e.get("ts", time.time()), 2),
            "severity": "warning" if "Scenario" in e.get("msg", "") else "info",
            "channel": "system",
            "value": 0.0,
            "message": e.get("msg", ""),
            "ack": True
        })
    return {
        "count": len(events),
        "unacked": 0,
        "alerts": alerts
    }

@app.get("/api/v1/thresholds")
def v1_get_thresholds():
    return {
        "thresholds": {
            "temp": threshold_config["temp"],
            "vib": threshold_config["vib"],
            "cur": threshold_config["cur"],
            "pwr": threshold_config["pwr"]
        },
        "hysteresis": threshold_config["hyst"],
        "debounce": threshold_config["debounce"],
        "evalMode": threshold_config["evalMode"],
        "publishRateHz": threshold_config["publishRateHz"]
    }

@app.put("/api/v1/thresholds")
def v1_put_thresholds(cfg: dict):
    if "thresholds" in cfg:
        threshold_config.update(cfg["thresholds"])
    if "hysteresis" in cfg:
        threshold_config["hyst"] = cfg["hysteresis"]
    if "debounce" in cfg:
        threshold_config["debounce"] = cfg["debounce"]
    return {"ok": True, "applied": threshold_config}

@app.get("/api/v1/diagnostics")
def v1_diagnostics():
    cur = history[-1] if history else {"temp": 32.0, "vib_rms": 1.2}
    rul_val = rul_heuristic(cur.get("temp", 32.0), cur.get("vib_rms", 1.2))
    return {
        "defectFrequencies": {
            "fs": 24.17,
            "bpfo": 86.6,
            "bpfi": 130.9,
            "bsf": 56.9,
            "ftf": 9.6,
            "gmf": 773.0
        },
        "components": [
            {"name": "1x Shaft (unbalance)", "freq": 24.17, "amp": 0.08},
            {"name": "2x Shaft (misalignment)", "freq": 48.33, "amp": 0.04},
            {"name": "BPFO outer race", "freq": 86.6, "amp": 0.12},
            {"name": "BPFI inner race", "freq": 130.9, "amp": 0.05}
        ],
        "wear": {
            "outer": 0.08,
            "inner": 0.04,
            "balls": 0.02,
            "cage": 0.01,
            "gears": 0.03,
            "lube": 0.95
        },
        "rul": {
            "rul": rul_val * 40.0,
            "rate": 0.005,
            "lo": rul_val * 30.0,
            "hi": rul_val * 55.0
        },
        "activeFaults": [current_scenario["name"]] if current_scenario["name"] != "Normal" else []
    }

@app.get("/api/v1/export/csv")
def v1_export_csv(rows: int = 50):
    lim = min(rows, len(history))
    lines = ["t,temp,vib,cur,pwr,volt,health,rssi,status"]
    for h in history[-lim:]:
        t = h.get("ts", 0)
        temp = h.get("temp", 0)
        vib = h.get("vib_rms", 0)
        cur = h.get("current", 0)
        pwr = cur * 24.0
        volt = 24.0
        hlth = rul_heuristic(temp, vib)
        rssi = -52.0
        status_code = 0 if h.get("status") == "Normal" else (1 if h.get("status") == "Warning" else 2)
        lines.append(f"{t:.2f},{temp:.3f},{vib:.3f},{cur:.3f},{pwr:.1f},{volt:.2f},{hlth:.2f},{rssi:.0f},{status_code}")
    return PlainTextResponse("\n".join(lines), media_type="text/csv")

@app.websocket("/ws/live")
async def live(ws: WebSocket):
    await ws.accept()
    active_connections.add(ws)
    if history:
        try:
            await ws.send_json(history[-1])
        except Exception:
            pass
    try:
        while True:
            data = await ws.receive_json()
            if isinstance(data, dict) and "scenario" in data:
                set_sc({"name": data["scenario"]})
    except Exception:
        pass
    finally:
        active_connections.discard(ws)

# --- Static Frontend Mount ---
try:
    base = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if os.path.isdir(os.path.join(os.path.dirname(__file__), "..", "..", "frontend")):
        base = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
    if os.path.isdir(base):
        app.mount("/", StaticFiles(directory=base, html=True), name="static")
except Exception:
    pass
