_counts = {"temp": 0, "vib": 0, "curr": 0, "norm": 0}
_last = {"temp": "Normal", "vib": "Normal", "curr": "Normal", "overall": "Normal"}
def _level(value, w, c):
    if value >= c: return "Maintenance Required"
    if value >= w: return "Warning"
    return "Normal"
def reset():
    for k in _counts: _counts[k] = 0
    for k in _last: _last[k] = "Normal"
def classify(temp: float, vib: float, curr: float) -> dict:
    cand = {"temp": _level(temp, 55.0, 70.0), "vib": _level(vib, 4.5, 7.1), "curr": _level(curr, 3.0, 4.0)}
    order = {"Normal": 0, "Warning": 1, "Maintenance Required": 2}
    cand_overall = max(list(cand.values())+["Normal"], key=lambda x: order[x])
    # 3-sample hysteresis
    if cand_overall == _last["overall"]:
        _counts["norm"] = 0
    else:
        _counts["norm"] += 1
        if _counts["norm"] >= 3:
            _last["overall"] = cand_overall
            _last.update(cand)
            _counts["norm"] = 0
    out = {"temp_status": _last["temp"] if _last["overall"]==cand_overall else cand["temp"],
           "vib_status": cand["vib"], "curr_status": cand["curr"], "overall": _last["overall"]}
    # keep per-channel immediate but overall hysteretic; simplify: per-channel immediate
    out = {"temp_status": cand["temp"], "vib_status": cand["vib"], "curr_status": cand["curr"], "overall": _last["overall"]}
    return out
