/* IRSM dashboard: WS live + Plotly trends/gauges/FFT/hist/heatmap/SPC/3D/RUL + Three.js twin + events */
(function () {
  "use strict";
  var MAX = 2000;
  var TS = [], T = [], V = [], C = [], ST = [], J = [];
  var backoff = 500;
  var backoffMax = 10000;
  var lastPkt = null;
  var tcpTrace = [];

  function $(id) { return document.getElementById(id); }

  function displayN() {
    var el = $("range");
    var n = el ? parseInt(el.value, 10) : 300;
    if (!n || n <= 0) n = 300;
    var lbl = $("range-label");
    if (lbl) lbl.textContent = String(n);
    return n;
  }
  var rangeEl = $("range");
  if (rangeEl) rangeEl.addEventListener("change", function () { renderTrend(); });

  ["tgl-temp", "tgl-vib", "tgl-curr"].forEach(function (id) {
    var el = $(id);
    if (el) el.addEventListener("change", renderTrend);
  });
  var logEl = $("tgl-log");

  // ---------- status badge ----------
  function setBadge(status) {
    var b = $("status-badge");
    if (!b) return;
    b.textContent = status;
    b.className = "badge " + (status === "Normal" ? "badge-green"
      : status === "Warning" ? "badge-amber" : "badge-red");
  }

  // ---------- trend ----------
  var dark = { paper_bgcolor: "#111c33", plot_bgcolor: "#111c33", font: { color: "#e2e8f0" } };
  function renderTrend() {
    var n = displayN();
    var ts = TS.slice(-n), t = T.slice(-n), v = V.slice(-n), c = C.slice(-n);
    var traces = [];
    if ($("tgl-temp") && $("tgl-temp").checked) traces.push({ x: ts, y: t, name: "temp C", mode: "lines", line: { color: "#f87171" } });
    if ($("tgl-vib") && $("tgl-vib").checked) traces.push({ x: ts, y: v, name: "vib rms", mode: "lines", line: { color: "#60a5fa" } });
    if ($("tgl-curr") && $("tgl-curr").checked) traces.push({ x: ts, y: c, name: "current A", mode: "lines", line: { color: "#34d399" } });
    if (!traces.length) traces.push({ x: [], y: [], name: "hidden" });
    Plotly.react("trend", traces, Object.assign({ title: "Live telemetry", margin: { t: 30, r: 10, b: 30, l: 40 } }, dark), { displayModeBar: false });
  }

  // ---------- gauges ----------
  function gauge(id, value, title, range, thresholds) {
    var steps = [];
    if (thresholds && thresholds.length === 2) {
      steps = [
        { range: [range[0], thresholds[0]], color: "#065f46" },
        { range: [thresholds[0], thresholds[1]], color: "#78350f" },
        { range: [thresholds[1], range[1]], color: "#7f1d1d" }
      ];
    }
    var data = [{
      type: "indicator", mode: "gauge+number",
      value: value, title: { text: title },
      gauge: { axis: { range: range }, steps: steps, bar: { color: "#e2e8f0" } }
    }];
    Plotly.react(id, data, Object.assign({ margin: { t: 30, b: 10, l: 20, r: 20 } }, dark), { displayModeBar: false });
  }
  function renderGauges(p) {
    gauge("gauge-temp", p.temp, "Temp C", [0, 120], [55, 70]);
    gauge("gauge-vib", p.vib_rms, "Vib RMS", [0, 10], [4.5, 7.1]);
    gauge("gauge-curr", p.current, "Current A", [0, 6], [3.0, 4.0]);
  }

  // ---------- WS with reconnect backoff ----------
  function connect() {
    var proto = location.protocol === "https:" ? "wss://" : "ws://";
    var ws;
    try { ws = new WebSocket(proto + location.host + "/ws/live"); } catch (e) { schedule(); return; }
    ws.onopen = function () { backoff = 500; };
    ws.onmessage = function (e) {
      try {
        var p = JSON.parse(e.data);
        lastPkt = p;
        TS.push(p.ts); T.push(p.temp); V.push(p.vib_rms); C.push(p.current);
        ST.push(p.status); J.push(p.joints);
        if (TS.length > MAX) { TS.splice(0, TS.length - MAX); T.splice(0, T.length - MAX); V.splice(0, V.length - MAX); C.splice(0, C.length - MAX); ST.splice(0, ST.length - MAX); J.splice(0, J.length - MAX); }
        setBadge(p.status);
        renderTrend();
        renderGauges(p);
        updateTwin(p.joints);
      } catch (err) { /* ignore malformed pkt */ }
    };
    ws.onclose = schedule;
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }
  function schedule() {
    setTimeout(connect, backoff);
    backoff = Math.min(backoffMax, backoff * 2);
  }

  // ---------- REST polls ----------
  function statusColor(s) {
    if (s === "Warning") return "#f59e0b";
    if (s === "Maintenance Required") return "#ef4444";
    return "#10b981";
  }

  async function pollSpectrum() {
    try {
      var s = await (await fetch("/api/spectrum")).json();
      var log = logEl && logEl.checked;
      Plotly.react("fft", [{ x: s.freqs, y: s.mags, type: "scatter", mode: "lines", line: { color: "#a78bfa" } }],
        Object.assign({ title: "FFT dom " + Number(s.dominant || 0).toFixed(1) + " Hz", margin: { t: 30, r: 10, b: 40, l: 50 }, yaxis: { type: log ? "log" : "linear" }, xaxis: { title: "Hz" } }, dark),
        { displayModeBar: false });
    } catch (e) { /* backend may be idle */ }
  }
  if (logEl) logEl.addEventListener("change", pollSpectrum);

  function mean(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : 0; }
  function std(a) {
    if (a.length < 2) return 0;
    var m = mean(a);
    return Math.sqrt(a.reduce(function (x, y) { return x + (y - m) * (y - m); }, 0) / a.length);
  }
  function corr(a, b) {
    if (a.length < 2 || a.length !== b.length) return 0;
    var ma = mean(a), mb = mean(b), sa = std(a), sb = std(b);
    if (!sa || !sb) return 0;
    var s = 0;
    for (var i = 0; i < a.length; i++) s += (a[i] - ma) * (b[i] - mb);
    return s / (a.length * sa * sb);
  }

  async function pollHistory() {
    try {
      var h = await (await fetch("/api/telemetry/history?limit=300")).json();
      if (!Array.isArray(h) || !h.length) return;
      var t = h.map(function (p) { return p.temp; });
      var v = h.map(function (p) { return p.vib_rms; });
      var c = h.map(function (p) { return p.current; });
      var st = h.map(function (p) { return p.status || "Normal"; });
      // hist + box (temp histogram)
      Plotly.react("hist", [{ x: t, type: "histogram", marker: { color: "#60a5fa" }, name: "temp" }],
        Object.assign({ title: "Temp distribution", margin: { t: 30, r: 10, b: 40, l: 40 } }, dark), { displayModeBar: false });
      // correlation heatmap 3x3
      var m = [
        [1, corr(t, v), corr(t, c)],
        [corr(v, t), 1, corr(v, c)],
        [corr(c, t), corr(c, v), 1]
      ];
      Plotly.react("heatmap", [{ z: m, x: ["temp", "vib", "curr"], y: ["temp", "vib", "curr"], type: "heatmap", colorscale: "Blues" }],
        Object.assign({ title: "Correlation", margin: { t: 30, r: 10, b: 40, l: 60 } }, dark), { displayModeBar: false });
      // SPC X-bar: mean +/- 3 sigma on temp
      var mu = mean(t), sg = std(t);
      var ucl = mu + 3 * sg, lcl = mu - 3 * sg;
      var idx = t.map(function (_, i) { return i; });
      Plotly.react("spc", [
        { x: idx, y: t, mode: "lines", name: "temp", line: { color: "#e2e8f0" } },
        { x: idx, y: idx.map(function () { return mu; }), mode: "lines", name: "mean", line: { color: "#34d399", dash: "dash" } },
        { x: idx, y: idx.map(function () { return ucl; }), mode: "lines", name: "UCL", line: { color: "#ef4444", dash: "dot" } },
        { x: idx, y: idx.map(function () { return lcl; }), mode: "lines", name: "LCL", line: { color: "#ef4444", dash: "dot" } }
      ], Object.assign({ title: "SPC X-bar mu=" + mu.toFixed(1) + " sig=" + sg.toFixed(2), margin: { t: 30, r: 10, b: 30, l: 40 } }, dark), { displayModeBar: false });
      // 3D scatter colored by status string
      Plotly.react("scatter3d", [{
        x: t, y: v, z: c, mode: "markers", type: "scatter3d",
        marker: { size: 3, color: st.map(statusColor) }
      }], Object.assign({ title: "Temp/Vib/Current", margin: { t: 30, r: 10, b: 10, l: 10 } }, dark), { displayModeBar: false });
    } catch (e) { /* ignore */ }
  }

  async function pollStats() {
    try {
      var s = await (await fetch("/api/stats")).json();
      var rul = Number(s.rul || 0);
      Plotly.react("health", [{
        type: "indicator", mode: "gauge+number", value: rul, title: { text: "RUL %" },
        gauge: { axis: { range: [0, 100] }, bar: { color: rul > 60 ? "#10b981" : rul > 30 ? "#f59e0b" : "#ef4444" } }
      }], Object.assign({ margin: { t: 30, b: 10, l: 20, r: 20 } }, dark), { displayModeBar: false });
    } catch (e) { /* ignore */ }
  }

  async function pollEvents() {
    try {
      var ev = await (await fetch("/api/events")).json();
      var ul = $("events");
      if (!ul || !Array.isArray(ev)) return;
      ul.innerHTML = "";
      ev.slice(-30).reverse().forEach(function (e) {
        var li = document.createElement("li");
        var ts = e.ts ? new Date(e.ts * 1000).toLocaleTimeString() : "";
        li.textContent = ts + " " + (e.msg || JSON.stringify(e));
        ul.appendChild(li);
      });
    } catch (e) { /* ignore */ }
  }

  // ---------- scenario buttons ----------
  document.querySelectorAll("[data-scenario]").forEach(function (b) {
    b.addEventListener("click", function () {
      fetch("/api/scenario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: b.dataset.scenario }) }).catch(function () {});
      document.querySelectorAll("[data-scenario]").forEach(function (x) { x.classList.remove("active"); });
      b.classList.add("active");
    });
  });

  // ---------- Three.js 3-link arm + TCP trace ----------
  var scene, camera, renderer, links = [], tcpDot, traceLine;
  function initTwin() {
    var canvas = $("twin");
    if (!canvas || typeof THREE === "undefined") return;
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    renderer.setSize(canvas.clientWidth || 300, 320, false);
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111c33);
    camera = new THREE.PerspectiveCamera(50, (canvas.clientWidth || 300) / 320, 0.1, 100);
    camera.position.set(3, 2.5, 4);
    camera.lookAt(0, 1, 0);
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    var dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(3, 5, 2);
    scene.add(dir);
    var grid = new THREE.GridHelper(4, 8, 0x3b82f6, 0x1e2d4d);
    scene.add(grid);
    var mat = new THREE.MeshStandardMaterial({ color: 0x3b82f6 });
    for (var i = 0; i < 3; i++) {
      var g = new THREE.BoxGeometry(0.18, 1.0, 0.18);
      g.translate(0, 0.5, 0);
      var mesh = new THREE.Mesh(g, mat.clone());
      scene.add(mesh);
      links.push(mesh);
    }
    tcpDot = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 12), new THREE.MeshStandardMaterial({ color: 0x10b981 }));
    scene.add(tcpDot);
    var tg = new THREE.BufferGeometry().setFromPoints([]);
    traceLine = new THREE.Line(tg, new THREE.LineBasicMaterial({ color: 0xf59e0b }));
    scene.add(traceLine);
    window.addEventListener("resize", function () {
      var w = canvas.clientWidth || 300;
      renderer.setSize(w, 320, false);
      camera.aspect = w / 320;
      camera.updateProjectionMatrix();
    });
    (function animate() {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    })();
  }
  function updateTwin(joints) {
    if (!scene || !joints || joints.length < 3) return;
    var rad = joints.map(function (d) { return d * Math.PI / 180; });
    var px = 0, py = 0, pz = 0, ang = 0;
    var lens = [1.0, 0.8, 0.6];
    for (var i = 0; i < 3; i++) {
      var link = links[i];
      link.position.set(px, py, pz);
      link.rotation.z = rad[i] / 2;
      ang += rad[i] / 2;
      px += Math.sin(ang) * lens[i];
      py += Math.cos(ang) * lens[i];
    }
    tcpDot.position.set(px, py, pz);
    tcpTrace.push(new THREE.Vector3(px, py, pz));
    if (tcpTrace.length > 200) tcpTrace.shift();
    traceLine.geometry.setFromPoints(tcpTrace);
  }

  // ---------- boot ----------
  initTwin();
  connect();
  pollSpectrum(); pollHistory(); pollStats(); pollEvents();
  setInterval(pollSpectrum, 2000);
  setInterval(pollHistory, 4000);
  setInterval(pollStats, 4000);
  setInterval(pollEvents, 3000);
})();
