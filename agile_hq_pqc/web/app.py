"""Flask + Socket.IO web command center for Agile-HQ-PQC."""
from __future__ import annotations

import csv
import io
import json
import os
import threading
import time
from pathlib import Path

import numpy as np
from flask import Flask, Response, g, jsonify, request, send_from_directory
from flask_socketio import SocketIO, join_room

from ..core.probe import STRESS_PRESETS
from ..core.tiers import TIERS, SLA_MS
from ..gateway import HealthGateway
from ..privacy.data import synthetic_ecg, synthetic_ehr
from ..privacy.dp import laplace_mechanism
from ..privacy.mondrian import mondrian_anonymize, verify_k_l
from ..security import auth
from ..security.audit import AuditLog

EXPORT_MIN_K, EXPORT_MIN_L = 5, 3
LIVE_ALPHA = 0.5   # EWMA smoothing of live probes (evaluation uses 1.0 = off)

DEMO_PHASES = [  # (label, preset, steps)
    ("Phase 1 - Peacetime (clear network)", "calm", 8),
    ("Phase 2a - Stress injected (heavy congestion)", "heavy", 10),
    ("Phase 2b - Severe congestion + CPU spike", "severe", 12),
    ("Phase 3 - Recovery (stress cleared)", "calm", 16),
]


class Runtime:
    """Owns the gateway, the control loop thread and the guided demo."""

    def __init__(self, socketio: SocketIO, step_interval: float, audit: AuditLog):
        self.sio, self.interval, self.audit = socketio, step_interval, audit
        self.gateway = HealthGateway(audit=audit, smoothing_alpha=LIVE_ALPHA)
        self.running = False
        self.demo = dict(active=False, phase=None, started=None)
        self._demo_stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            t0 = time.time()
            with self._lock:
                try:
                    ev = self.gateway.step()
                    ev["demo"] = dict(self.demo)
                    self.sio.emit("tick", ev, to="monitor")
                except Exception as exc:  # keep the loop alive
                    self.sio.emit("server_error", {"error": str(exc)}, to="monitor")
            time.sleep(max(0.0, self.interval - (time.time() - t0)))

    def set_mode(self, adaptive: bool, static_tier: int = 5):
        with self._lock:
            old = self.gateway
            self.gateway = HealthGateway(adaptive=adaptive, static_tier=static_tier, audit=self.audit,
                                         smoothing_alpha=LIVE_ALPHA)
            old.close()
            self.audit.append("admin", "mode_change", dict(adaptive=adaptive, static_tier=static_tier))

    def start_demo(self):
        if self.demo["active"]:
            return False
        self._demo_stop.clear()
        self.demo["active"] = True   # set before the thread starts so a second click can't race it
        threading.Thread(target=self._run_demo, daemon=True).start()
        return True

    def stop_demo(self):
        """Cancel a running guided demo; it restores the calm preset on exit."""
        self._demo_stop.set()

    def _run_demo(self):
        self.audit.append("admin", "demo_start", {})
        self.demo.update(active=True, started=time.time())
        try:
            for label, preset, steps in DEMO_PHASES:
                self.demo["phase"] = label
                self.gateway.set_stress(preset)
                self.sio.emit("demo_phase", dict(label=label, preset=preset), to="monitor")
                if self._demo_stop.wait(steps * self.interval):
                    break
        finally:
            self.gateway.set_stress("calm")
            self.demo.update(active=False, phase="Demo complete")
            self.sio.emit("demo_phase", dict(label="Demo complete", preset="calm", done=True), to="monitor")
            self.audit.append("admin", "demo_end", {})


def create_app(autostart: bool = True, step_interval: float = 0.5,
               audit_path: str | None = None) -> tuple[Flask, SocketIO, Runtime]:
    here = Path(__file__).parent
    app = Flask(__name__, static_folder=str(here / "static"))
    sio = SocketIO(app, async_mode="threading", cors_allowed_origins=[])
    audit = AuditLog(audit_path)
    rt = Runtime(sio, step_interval, audit)
    app.config["RUNTIME"] = rt

    # ---------------------------------------------------------------- pages
    react_dir = here / "static" / "app"

    @app.get("/")
    def index():
        # The React build (frontend/ -> `npm run build`) is the only UI.
        if (react_dir / "index.html").exists():
            return send_from_directory(react_dir, "index.html")
        return Response("Frontend not built: run `cd frontend && npm install && npm run build`.",
                        status=503, mimetype="text/plain")

    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True)

    # ------------------------------------------------------------------ auth
    @app.post("/api/login")
    def login():
        body = request.get_json(silent=True) or {}
        tok = auth.authenticate(str(body.get("username", "")), str(body.get("password", "")))
        if not tok:
            audit.append(str(body.get("username", "?"))[:32], "login_failed", {"ip": request.remote_addr})
            return jsonify(error="invalid credentials"), 401
        claims = auth.decode(tok)
        audit.append(claims["sub"], "login", {"role": claims["role"]})
        return jsonify(token=tok, role=claims["role"], user=claims["sub"],
                       permissions=sorted(auth.PERMISSIONS[claims["role"]]))

    @app.get("/api/me")
    @auth.require(None)
    def me():
        return jsonify(user=g.user, role=g.role, permissions=sorted(auth.PERMISSIONS[g.role]))

    # ------------------------------------------------------------ monitoring
    @app.get("/api/state")
    @auth.require("monitor")
    def state():
        gw = rt.gateway
        return jsonify(history=list(gw.history)[-120:], counters=gw.counters, adaptive=gw.adaptive,
                       tiers={k: v.to_dict() for k, v in TIERS.items()},
                       presets=list(STRESS_PRESETS), demo=rt.demo, sla_ms=SLA_MS,
                       demo_phases=[dict(label=lb, preset=pr, steps=n) for lb, pr, n in DEMO_PHASES],
                       step_interval=rt.interval)

    @app.post("/api/stress")
    @auth.require("stress")
    def stress():
        body = request.get_json(silent=True) or {}
        preset = body.get("preset", "calm")
        if preset not in STRESS_PRESETS:
            return jsonify(error="unknown preset"), 400
        rt.gateway.set_stress(preset)
        return jsonify(ok=True, preset=preset)

    @app.post("/api/demo/start")
    @auth.require("stress")
    def demo_start():
        return jsonify(started=rt.start_demo(), phases=[p[0] for p in DEMO_PHASES])

    @app.post("/api/demo/stop")
    @auth.require("stress")
    def demo_stop():
        was = bool(rt.demo["active"])
        rt.stop_demo()
        return jsonify(stopped=was)

    @app.post("/api/mode")
    @auth.require("policy")
    def mode():
        body = request.get_json(silent=True) or {}
        tier = int(body.get("static_tier", 5))
        if tier not in TIERS:
            return jsonify(error="bad tier"), 400
        rt.set_mode(bool(body.get("adaptive", True)), tier)
        return jsonify(ok=True, adaptive=rt.gateway.adaptive)

    # ------------------------------------------------- inspector / tamper lab
    @app.get("/api/trace")
    @auth.require("inspect")
    def trace():
        return jsonify(rt.gateway.last_trace or {})

    @app.post("/api/tamper")
    @auth.require("tamper")
    def tamper():
        body = request.get_json(silent=True) or {}
        return jsonify(rt.gateway.tamper(str(body.get("target", "ciphertext")),
                                         int(body.get("bit", 0))))

    # ------------------------------------------------------------- operator
    @app.post("/api/ingest")
    @auth.require("ingest")
    def ingest():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="JSON object required"), 400
        try:
            return jsonify(rt.gateway.ingest(body))
        except ValueError as e:
            return jsonify(error=str(e)), 413

    @app.get("/api/exchange")
    @auth.require("exchange")
    def exchange():
        gw = rt.gateway
        cl = gw.sessions.get("clinical")
        return jsonify(peer="Hospital-B (Vellore CMC gateway)", local="Hospital-A (VIT clinic gateway)",
                       clinical_suite=cl.tier.suite if cl else None,
                       packets=gw.counters["packets"],
                       sla_violations=gw.counters["sla_violations_clinical"])

    # ------------------------------------------------------ privacy visualizer
    @app.get("/api/privacy/ecg")
    @auth.require("privacy_view")
    def privacy_ecg():
        t, ecg = synthetic_ecg(seconds=2.0, seed=3)
        out = dict(t=[round(float(x), 4) for x in t], series={})
        raw_ok = "privacy_raw" in auth.PERMISSIONS[g.role]
        if raw_ok:
            out["series"]["raw"] = [round(float(x), 4) for x in ecg]
        rng = np.random.default_rng(11)
        for eps in (0.1, 0.5, 1.0):
            r = laplace_mechanism(ecg, eps, sensitivity=0.5, rng=rng)
            out["series"][f"eps_{eps}"] = [round(float(x), 4) for x in r.noisy]
            out.setdefault("snr_db", {})[str(eps)] = round(r.snr_db, 2)
        out["raw_visible"] = raw_ok
        if request.args.get("eps"):   # one series at a caller-chosen epsilon (privacy slider)
            try:
                eps = min(2.0, max(0.05, float(request.args["eps"])))
            except ValueError:
                return jsonify(error="bad eps"), 400
            r = laplace_mechanism(ecg, eps, sensitivity=0.5, rng=np.random.default_rng(11))
            out.update(eps=eps, dp=[round(float(x), 4) for x in r.noisy],
                       snr_db=round(r.snr_db, 2), scale=round(r.scale, 3))
        return jsonify(out)

    tradeoff_cache: dict[int, list] = {}

    @app.get("/api/privacy/tradeoff")
    @auth.require("privacy_view")
    def privacy_tradeoff():
        l = max(1, min(5, int(request.args.get("l", 2))))
        _, ecg = synthetic_ecg(seconds=2.0, seed=3)
        eps_curve = []
        for eps in np.geomspace(0.05, 2.0, 24):
            r = laplace_mechanism(ecg, float(eps), sensitivity=0.5, rng=np.random.default_rng(11))
            eps_curve.append(dict(epsilon=round(float(eps), 3), snr_db=round(r.snr_db, 2)))
        if l not in tradeoff_cache:
            data = synthetic_ehr(200, seed=7)
            tradeoff_cache[l] = [dict(k=k, info_loss=round(mondrian_anonymize(data, k, l).info_loss, 4))
                                 for k in range(max(2, l), 11)]
        tiers = [dict(tier=t.level, epsilon=t.epsilon, k=t.k, l=t.l) for t in TIERS.values()]
        return jsonify(eps_curve=eps_curve, k_curve=tradeoff_cache[l], l=l, tiers=tiers)

    @app.get("/api/privacy/ehr")
    @auth.require("privacy_view")
    def privacy_ehr():
        k = max(2, min(10, int(request.args.get("k", 3))))
        l = max(1, min(k, int(request.args.get("l", 2))))
        data = synthetic_ehr(200, seed=7)
        an = mondrian_anonymize(data, k, l)
        raw_ok = "privacy_raw" in auth.PERMISSIONS[g.role]
        raw = [{kk: r[kk] for kk in ("patient_id", "age", "zip", "sex", "diagnosis")} for r in data[:14]]
        return jsonify(raw=raw if raw_ok else None, anonymized=an.rows[:14], k=k, l=l,
                       classes=an.classes, min_class=an.min_class_size,
                       avg_class=round(an.avg_class_size, 1), info_loss=round(an.info_loss, 4),
                       satisfied=an.satisfied,
                       verified=verify_k_l(an.rows, k, l, ("age", "zip", "sex"), "diagnosis"))

    # ------------------------------------------------------- researcher export
    @app.get("/api/export/deid")
    @auth.require("export_deid")
    def export_deid():
        gw = rt.gateway
        tier = TIERS[gw.controller.active_tier]
        k, l = max(EXPORT_MIN_K, tier.k), max(EXPORT_MIN_L, tier.l)   # floor K=5, L=3
        an = mondrian_anonymize(synthetic_ehr(400, seed=7), k, l)
        ok = verify_k_l(an.rows, k, l, ("age", "zip", "sex"), "diagnosis")
        audit.append(g.user, "export_deid", dict(k=k, l=l, rows=len(an.rows), verified=ok))
        if not (an.satisfied and ok):
            return jsonify(error="could not satisfy (K,L) - export refused"), 422
        if request.args.get("format") == "csv":
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=["age", "zip", "sex", "diagnosis"])
            w.writeheader(); w.writerows(an.rows)
            return Response(buf.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=deid_export.csv"})
        return jsonify(k=k, l=l, rows=an.rows, classes=an.classes, info_loss=round(an.info_loss, 4),
                       verified=ok, count=len(an.rows))

    # ------------------------------------------------------ evaluation results
    results_path = here.parents[1] / "reports" / "results.json"

    @app.get("/api/results")
    @auth.require(None)
    def results():
        if not results_path.exists():
            return jsonify(error="reports/results.json not found - run evaluation/run_eval.py"), 404
        d = json.loads(results_path.read_text())
        return jsonify({k: d[k] for k in ("schedule", "trials", "summary", "tests", "sweep") if k in d})

    # ----------------------------------------------------------------- audit
    @app.get("/api/audit")
    @auth.require("audit_read")
    def audit_tail():
        return jsonify(entries=audit.tail(int(request.args.get("n", 100))), verify=audit.verify())

    @app.get("/api/audit/verify")
    @auth.require("audit_read")
    def audit_verify():
        return jsonify(audit.verify())

    # -------------------------------------------------------------- sockets
    @sio.on("connect")
    def on_connect(a=None):
        token = (a or {}).get("token") if isinstance(a, dict) else None
        claims = auth.decode(token or "")
        if not claims or "monitor" not in auth.PERMISSIONS.get(claims["role"], set()):
            return False
        join_room("monitor")

    if autostart:
        rt.start()
    return app, sio, rt


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app, sio, rt = create_app(audit_path=os.environ.get("AUDIT_PATH", "data/audit.jsonl"))
    print(f"\n  Agile-HQ-PQC Command Center -> http://{host}:{port}\n"
          "  demo logins: admin/admin@pqc  auditor/audit@pqc  researcher/research@pqc  operator/operator@pqc\n")
    sio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
