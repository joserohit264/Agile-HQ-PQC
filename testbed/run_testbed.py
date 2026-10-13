#!/usr/bin/env python3
"""Real-link testbed for Agile-HQ-PQC (Linux, root).

What is REAL here
  * two network namespaces joined by a veth pair, kernel tbf bandwidth shaping both ways
  * real TCP sockets; the bytes sent are the actual packets produced by the project's
    channel code (AEAD + Ed25519 + ML-DSA epoch signatures, real FIPS 203/204 sizes)
  * RTT is measured by an echo probe over the same shaped link (queueing included)
  * CPU is read from the host while real busy-loop processes load it

What is still EMULATED / omitted (kernel netem is unavailable in this environment)
  * propagation delay: the receiver holds each reply for `delay_ms` (value stated per phase)
  * packet loss: not modelled (veth is lossless)
  * PQ compute is not charged to latency (native liboqs cost is measured separately, <0.3 ms)

Usage:  python testbed/run_testbed.py [--reps 6] [--sweep-reps 4] [--quick]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import socket
import struct
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "testbed"))
import netns_link as L                                    # noqa: E402
from agile_hq_pqc.core.cada import CadaController         # noqa: E402
from agile_hq_pqc.core.tiers import TIERS, SLA_MS         # noqa: E402
from agile_hq_pqc.crypto.channel import SecureSender      # noqa: E402
from agile_hq_pqc.crypto.hybrid import Identity, hybrid_handshake  # noqa: E402
from agile_hq_pqc.privacy.data import synthetic_ecg, vitals_sample  # noqa: E402

PORT_DATA_C, PORT_DATA_R, PORT_PROBE = 9001, 9002, 9003
HDR = struct.Struct(">IH")          # body length, receiver hold time (ms)
POOL = 64
CYCLE_S = 0.25

PHASES = {   # name: (bandwidth Mbit/s or None, receiver hold ms, busy-loop processes)
    "calm":     (None, 0, 0),
    "moderate": (20, 85, 0),
    "heavy":    (5, 125, 1),
    "severe":   (2, 150, 2),
}
SCHEDULE = [("calm", 12), ("moderate", 10), ("heavy", 10), ("severe", 12), ("calm", 16)]
CONFIGS = {
    "adaptive":        dict(adaptive=True, epoch=1),
    "static_t5":       dict(adaptive=False, tier=5, epoch=1),
    "static_t3":       dict(adaptive=False, tier=3, epoch=1),
    "adaptive_batch":  dict(adaptive=True, epoch=8),
    "static_t5_batch": dict(adaptive=False, tier=5, epoch=8),
}


# ------------------------------------------------------------------ receiver (runs inside pqcB)
def _recvn(c: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        d = c.recv(min(65536, n - len(buf)))
        if not d:
            raise EOFError
        buf += d
    return bytes(buf)


def _serve(c: socket.socket):
    c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        while True:
            n, hold = HDR.unpack(_recvn(c, HDR.size))
            _recvn(c, n)
            if hold:
                time.sleep(hold / 1000.0)
            c.sendall(b"k")
    except (EOFError, OSError):
        pass
    finally:
        c.close()


def receiver_main():
    L.enter(L.NS_B)
    socks = []
    for port in (PORT_DATA_C, PORT_DATA_R, PORT_PROBE):
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((L.IP_B, port)); s.listen(4); socks.append(s)

    def acc(s):
        while True:
            c, _ = s.accept()
            threading.Thread(target=_serve, args=(c,), daemon=True).start()
    for s in socks:
        threading.Thread(target=acc, args=(s,), daemon=True).start()
    while True:
        time.sleep(3600)


# ------------------------------------------------------------------ packet pools (real channel bytes)
def build_pools(epochs=(1, 8)):
    print("building packet pools (pure-Python ML-DSA signing, one-off) ...", flush=True)
    _, ecg = synthetic_ecg(seconds=30, seed=1)
    rng = np.random.default_rng(1)
    ids = {lv: Identity.generate(f"tb-{lv}", t) for lv, t in TIERS.items()}
    hs_bytes, pools = {}, {}
    for lv, t in TIERS.items():
        hs = hybrid_handshake(t, ids[lv])
        hs_bytes[lv] = hs.total_bytes
        for ep in epochs:
            for dom in ("clinical", "research"):
                tx = SecureSender(t, hs.master_secret, hs.session_id, ids[lv], ep)
                out = []
                for i in range(POOL):
                    chunk = ecg[(i * 25) % (len(ecg) - 25):][:25]
                    rec = dict(pid="P00042", ts=1.0, vitals=vitals_sample(rng),
                               ecg_mv=[round(float(x), 4) for x in chunk])
                    pkt, _ = tx.send(json.dumps(rec, separators=(",", ":")).encode(), aad=dom.encode())
                    out.append(pkt.to_wire())
                pools[(lv, ep, dom)] = out
    return pools, hs_bytes


# ------------------------------------------------------------------ sender side
class Link:
    def __init__(self):
        self.conns = {}
        for name, port in (("clinical", PORT_DATA_C), ("research", PORT_DATA_R), ("probe", PORT_PROBE)):
            c = socket.create_connection((L.IP_B, port))
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.conns[name] = c

    def xfer(self, name: str, payload: bytes, hold_ms: int) -> float:
        c = self.conns[name]
        t = time.perf_counter()
        c.sendall(HDR.pack(len(payload), hold_ms) + payload)
        c.recv(1)
        return (time.perf_counter() - t) * 1000.0

    def close(self):
        for c in self.conns.values():
            c.close()


def _burn():
    x = 0
    while True:
        x = (x * 1103515245 + 12345) & 0xFFFFFFFF


class Burners:
    def __init__(self):
        self.procs = []

    def set(self, n: int):
        while len(self.procs) > n:
            p = self.procs.pop(); p.terminate(); p.join()
        while len(self.procs) < n:
            p = mp.Process(target=_burn, daemon=True); p.start(); self.procs.append(p)


def apply_phase(name: str, burners: Burners, bw_override=None):
    bw, hold, nburn = PHASES[name]
    L.set_rate(bw_override if bw_override else bw)
    burners.set(nburn)
    return hold


def run_trial(cfg_name, pools, hs_bytes, schedule, burners, link, bw_override=None):
    cfg = CONFIGS[cfg_name]
    ctl = CadaController(enabled=cfg["adaptive"], initial_tier=cfg.get("tier", 5))
    last_tier = {"clinical": ctl.clinical_tier_for(ctl.active_tier), "research": ctl.active_tier}
    psutil.cpu_percent(interval=None)
    rows, hold, nxt, cyc = [], 0, time.perf_counter(), 0
    for phase, n in schedule:
        hold = apply_phase(phase, burners, bw_override)
        time.sleep(0.3)                                # let the shaper/queue settle
        psutil.cpu_percent(interval=None)
        nxt = time.perf_counter()
        for _ in range(n):
            cpu = psutil.cpu_percent(interval=None)
            rtt = link.xfer("probe", b"p", hold)       # real RTT over the shaped link (+ stated hold)
            dec = ctl.decide(rtt, cpu)
            tiers = {"clinical": dec.clinical_tier, "research": dec.active_tier}
            res = {}

            def send(dom):
                lv = tiers[dom]
                wire = pools[(lv, cfg["epoch"], dom)][cyc % POOL]
                extra = hs_bytes[lv] if lv != last_tier[dom] else 0     # re-key bytes on the wire
                res[dom] = (link.xfer(dom, wire + b"\0" * extra, hold), len(wire) + extra)
            th = [threading.Thread(target=send, args=(d,)) for d in ("clinical", "research")]
            [t.start() for t in th]; [t.join() for t in th]
            last_tier.update(tiers)
            rows.append(dict(cycle=cyc, phase=phase, rtt_ms=rtt, cpu_pct=cpu, budget_ms=dec.budget_ms,
                             tier=dec.active_tier, clinical_tier=dec.clinical_tier,
                             lat_clinical=res["clinical"][0], lat_research=res["research"][0],
                             wire_clinical=res["clinical"][1], wire_research=res["research"][1]))
            cyc += 1
            nxt += CYCLE_S
            time.sleep(max(0.0, nxt - time.perf_counter()))
    return rows


def summarize(rows):
    stress = [r for r in rows if r["phase"] != "calm"]
    tiers = [r["tier"] for r in rows]
    return dict(
        viol_clinical_stress=float(np.mean([r["lat_clinical"] > SLA_MS for r in stress])) if stress else 0.0,
        viol_research_stress=float(np.mean([r["lat_research"] > SLA_MS for r in stress])) if stress else 0.0,
        viol_clinical_all=float(np.mean([r["lat_clinical"] > SLA_MS for r in rows])),
        viol_research_all=float(np.mean([r["lat_research"] > SLA_MS for r in rows])),
        p95_clinical=float(np.percentile([r["lat_clinical"] for r in rows], 95)),
        p95_research=float(np.percentile([r["lat_research"] for r in rows], 95)),
        mean_wire_clinical=float(np.mean([r["wire_clinical"] for r in rows])),
        tier_changes=sum(1 for a, b in zip(tiers, tiers[1:]) if a != b),
        mean_tier=float(np.mean(tiers)), min_clinical_tier=int(min(r["clinical_tier"] for r in rows)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--sweep-reps", type=int, default=5)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "reports" / "testbed_results.json"))
    a = ap.parse_args()
    if a.quick:
        a.reps, a.sweep_reps = 1, 1
    if os.geteuid() != 0:
        sys.exit("needs root (CAP_NET_ADMIN)")

    pools, hs_bytes = build_pools()
    L.setup()
    pid = os.fork()
    if pid == 0:
        receiver_main(); os._exit(0)
    time.sleep(0.8)
    L.enter(L.NS_A)
    link, burners = Link(), Burners()
    out = dict(meta=dict(cycle_s=CYCLE_S, phases={k: dict(bw_mbps=v[0], hold_ms=v[1], busy_procs=v[2]) for k, v in PHASES.items()},
                         schedule=SCHEDULE, reps=a.reps, sweep_reps=a.sweep_reps, nproc=os.cpu_count(),
                         hs_bytes=hs_bytes, queue_ms=L.QUEUE_US / 1000), partA=[], partB=[])
    try:
        names = list(CONFIGS)
        for rep in range(a.reps):
            random.Random(rep).shuffle(names)
            for n in names:
                rows = run_trial(n, pools, hs_bytes, SCHEDULE, burners, link)
                out["partA"].append(dict(config=n, rep=rep, summary=summarize(rows), rows=rows))
                print(f"A rep{rep} {n:16s} viol_stress c={out['partA'][-1]['summary']['viol_clinical_stress']:.3f} "
                      f"r={out['partA'][-1]['summary']['viol_research_stress']:.3f}", flush=True)
        sweep_cfg = ["adaptive", "static_t5", "static_t3"]
        for bw in (5, 2, 1, 0.5):          # constant "severe" RTT/CPU stress, vary the link (as Part B of the emulated eval)
            for rep in range(a.sweep_reps):
                for n in sweep_cfg:
                    rows = run_trial(n, pools, hs_bytes, [("severe", 30)], burners, link, bw_override=bw)
                    s = summarize(rows)
                    out["partB"].append(dict(config=n, bw=bw, rep=rep, summary=s, mean_lat_clinical=float(np.mean([r["lat_clinical"] for r in rows])),
                                             viol=float(np.mean([r["lat_clinical"] > SLA_MS for r in rows]))))
                    print(f"B bw={bw} rep{rep} {n:10s} viol={out['partB'][-1]['viol']:.3f}", flush=True)
    finally:
        burners.set(0); link.close(); os.kill(pid, 9); L.teardown()
        Path(a.out).parent.mkdir(exist_ok=True)
        Path(a.out).write_text(json.dumps(out))
        print("saved", a.out)


if __name__ == "__main__":
    main()
