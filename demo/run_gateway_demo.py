#!/usr/bin/env python3
"""Headless live demo: peacetime -> stress -> recovery, printed as a table.

    python demo/run_gateway_demo.py            # real host probes, ~25 s
    python demo/run_gateway_demo.py --fast     # no sleeping between cycles
    python demo/run_gateway_demo.py --static   # same scenario, adaptation OFF (baseline)
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agile_hq_pqc.gateway import HealthGateway          # noqa: E402

PHASES = [("PHASE 1  peacetime", "calm", 8), ("PHASE 2a stress: heavy", "heavy", 10),
          ("PHASE 2b stress: severe", "severe", 12), ("PHASE 3  recovery", "calm", 16)]
C = {5: "\033[92m", 3: "\033[93m", 1: "\033[91m"}; R = "\033[0m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true"); ap.add_argument("--static", action="store_true")
    ap.add_argument("--interval", type=float, default=0.5)
    a = ap.parse_args()
    gw = HealthGateway(adaptive=not a.static, static_tier=5, smoothing_alpha=0.5)
    print(f"Agile-HQ-PQC demo - mode: {'STATIC Tier 5 (baseline)' if a.static else 'ADAPTIVE (CADA-AASM)'}\n")
    print(f"{'step':>4} {'budget':>7} {'rtt':>6} {'cpu':>4} {'hyst':>5} {'agile':>6} {'PHI':>4} {'clin ms':>8} {'res ms':>7} {'eps':>4} {'K/L':>4}  event")
    for label, preset, n in PHASES:
        print(f"\n--- {label} ---")
        gw.set_stress(preset)
        for _ in range(n):
            e = gw.step(); d = e["decision"]; t = e["active_tier"]
            ev = []
            if d["changed"]: ev.append(f"TIER CHANGE -> T{t}")
            if e["handshake"]: ev.append(f"re-key {e['handshake']['suite']} ({e['handshake']['timings_ms']['total']:.0f} ms, {e['handshake']['total_bytes']} B)")
            if d["floor_clamped"]: ev.append("HIPAA floor holds PHI at T3")
            if e["clinical"]["sla_violation"] or e["research"]["sla_violation"]: ev.append("SLA!")
            print(f"{e['step']:>4} {e['budget_ms']:>7.1f} {e['probe']['rtt_ms']:>6.1f} {e['probe']['cpu_pct']:>4.0f} "
                  f"{d['hysteresis_count']}/{d['hysteresis_needed']:<3} {C[t]}T{t:<5}{R} T{e['clinical_tier']:<3} "
                  f"{e['clinical']['latency_ms']:>8.1f} {e['research']['latency_ms']:>7.1f} {e['privacy']['epsilon']:>4} "
                  f"{e['privacy']['k']}/{e['privacy']['l']:<2}  {'; '.join(ev)}")
            if not a.fast: time.sleep(a.interval)
    c = gw.counters
    print(f"\npackets={c['packets']} handshakes={c['handshakes']} tier_changes={c['tier_changes']} "
          f"SLA violations clinical/research={c['sla_violations_clinical']}/{c['sla_violations_research']}")
    print("audit chain:", gw.audit.verify())
    gw.close()


if __name__ == "__main__":
    main()
