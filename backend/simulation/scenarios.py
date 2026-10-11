SCENARIOS = {
    "Normal": {},
    "healthy": {},
    "Overload": {"load": 0.95},
    "overload": {"load": 0.95},
    "BearingWear": {"wear": 1.0},
    "bearing": {"wear": 1.0},
    "Overheat": {"overheat": 8.0},
    "overheat": {"overheat": 8.0},
    "PowerSurge": {"surge": 1.2},
    "electrical": {"surge": 1.2},
    "Combined": {"wear": 0.7, "overheat": 5.0, "load": 0.9},
    "cascade": {"wear": 0.7, "overheat": 5.0, "load": 0.9},
    "lube": {"wear": 0.4, "overheat": 3.0, "load": 0.7},
    "network": {"load": 0.5},
    "sensor": {"load": 0.5}
}

def get_fault(name: str) -> dict:
    s = SCENARIOS.get(name, {})
    return {
        "wear": s.get("wear", 0.0),
        "overheat": s.get("overheat", 0.0),
        "surge": s.get("surge", 0.0),
        "vib_boost": 0.0,
        "load": s.get("load", 0.5)
    }
