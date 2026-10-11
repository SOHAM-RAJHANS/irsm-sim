import math, random
class PhysicsState:
    def __init__(self):
        self.temp = 32.0
        self.t = 0.0
        self.cycle = 12.0
        self.tau = 180.0
        self.tamb = 26.0
        self.accel_buf = [0.0]*400
    def _phase(self):
        p = (self.t % self.cycle) / self.cycle
        if p < 0.15: return "idle", 0.2
        if p < 0.35: return "accel", 0.9
        if p < 0.65: return "constant", 0.7
        if p < 0.85: return "decel", 0.85
        return "idle", 0.2
    def step(self, dt: float, load: float, fault: dict):
        self.t += dt
        phase, duty = self._phase()
        torque = load * (0.5 + 0.5*duty)
        current = 1.8 + 1.6*torque + 0.01*(self.temp-32.0) + random.gauss(0, 0.05)
        current += fault.get("surge", 0.0)
        r = 0.8
        cth = 900.0
        p_loss = (current**2)*r*0.35 + duty*2.0
        dT = (p_loss/cth)*dt*60.0 - ((self.temp-self.tamb)/self.tau)*dt
        dT += fault.get("overheat", 0.0)*dt*0.15
        self.temp = max(-10.0, min(120.0, self.temp + dT))
        f1, f2 = 25.0, 50.0
        wear = fault.get("wear", 0.0)
        base = 1.2 + 0.8*duty + 1.5*load*duty
        n = 100
        acc = []
        for i in range(n):
            tt = self.t + i*0.005
            v = math.sin(2*math.pi*f1*tt)*0.6 + math.sin(2*math.pi*f2*tt)*0.3
            v += math.sin(2*math.pi*86.0*tt)*wear*1.2 + math.sin(2*math.pi*134.0*tt)*wear*0.8
            v += random.gauss(0, 0.15)
            acc.append(v)
        self.accel_buf = (self.accel_buf + acc)[-400:]
        vib_rms = max(0.0, min(20.0, base + wear*4.0 + abs(random.gauss(0, 0.2)) + fault.get("vib_boost", 0.0)))
        current = max(0.0, min(6.0, current))
        a = (self.t % self.cycle)/self.cycle*360.0
        joints = [a % 180.0, (a*0.7) % 120.0, (a*0.4) % 90.0]
        return {"temp": round(self.temp,2), "vib_rms": round(vib_rms,2), "current": round(current,2), "accel": acc, "joints": joints, "phase": phase}
