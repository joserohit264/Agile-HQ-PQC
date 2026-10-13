#!/usr/bin/env python3
"""Empirical evaluation of CADA-AASM against static baselines.

Part A  30 paired trials on a staged-stress schedule (calm -> moderate -> heavy
        -> severe -> recovery).
Part B  sensitivity sweep over link bandwidth x packet loss, to find WHERE
        adaptive steering helps and where it does not.

Configurations
  adaptive          CADA-AASM, 3-cycle hysteresis, PQ signature on every packet
  adaptive_nohyst   ablation: no hysteresis
  static_t5/_t3     fixed tier, PQ signature on every packet (the baseline the
                    project premise describes)
  adaptive_batch    CADA + batch ML-DSA signing every 8 packets (design improvement)
  static_t5_batch   fixed Tier 5 + batch signing

Probing is deterministic (fixed 0.2 ms / 5 % host baselines) so workers running
in parallel do not contaminate the controller's inputs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCHEDULE = [("calm", 12), ("moderate", 10), ("heavy", 10), ("severe", 12), ("calm", 16)]
CONFIGS = {
    "adaptive":        dict(adaptive=True, epoch_len=1),
    "adaptive_nohyst": dict(adaptive=True, epoch_len=1, hysteresis=1),
    "static_t5":       dict(adaptive=False, static_tier=5, epoch_len=1),
    "static_t3":       dict(adaptive=False, static_tier=3, epoch_len=1),
    "adaptive_batch":  dict(adaptive=True, epoch_len=8),
    "static_t5_batch": dict(adaptive=False, static_tier=5, epoch_len=8),
}
LABEL = {"adaptive": "CADA-AASM", "adaptive_nohyst": "CADA no-hyst", "static_t5": "Static T5",
         "static_t3": "Static T3", "adaptive_batch": "CADA + batch-sign", "static_t5_batch": "Static T5 + batch-sign"}


def run_trial(args) -> dict:
    cname, seed, schedule, custom = args
    from agile_hq_pqc.gateway import HealthGateway
    from agile_hq_pqc.security.audit import AuditLog
    cfg = CONFIGS[cname]
    gw = HealthGateway(adaptive=cfg["adaptive"], static_tier=cfg.get("static_tier", 5), seed=seed,
                       audit=AuditLog(), epoch_len=cfg["epoch_len"], deterministic_probe=True)
    if "hysteresis" in cfg:
        gw.controller.hysteresis = cfg["hysteresis"]
    evs = []
    for preset, n in schedule:
        gw.set_stress(custom if (custom and preset != "calm") else preset)
        for _ in range(n):
            evs.append(gw.step())
    gw.close()
    cl = np.array([e["clinical"]["latency_ms"] for e in evs])
    rs = np.array([e["research"]["latency_ms"] for e in evs])
    si = [i for i, e in enumerate(evs) if e["stress"]["rtt_ms"] > 0]
    tiers = [e["active_tier"] for e in evs]
    return dict(
        config=cname, seed=seed,
        viol_clinical_stress=float(np.mean(cl[si] > 200)), viol_research_stress=float(np.mean(rs[si] > 200)),
        p95_clinical=float(np.percentile(cl, 95)), p95_research=float(np.percentile(rs, 95)),
        p99_clinical=float(np.percentile(cl, 99)), mean_clinical=float(cl.mean()),
        mean_wire_clinical=float(np.mean([e["clinical"]["wire_bytes"] for e in evs])),
        handshakes=gw.counters["handshakes"], tier_changes=sum(1 for a, b in zip(tiers, tiers[1:]) if a != b),
        dwell={str(k): v for k, v in gw.dwell.items()},
        mean_privacy_eps=float(np.mean([e["privacy"]["epsilon"] for e in evs])),
        mean_k=float(np.mean([e["privacy"]["k"] for e in evs])),
        min_clinical_tier=int(min(e["clinical_tier"] for e in evs)),
        lat_research=rs.tolist(), lat_clinical=cl.tolist(), tiers=tiers)


def stats(v):
    a = np.asarray(v, float); n = len(a)
    return dict(mean=float(a.mean()), std=float(a.std(ddof=1)) if n > 1 else 0.0,
                ci95=float(1.96 * a.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0)


def paired(a, b):
    from scipy import stats as st
    d = np.asarray(a, float) - np.asarray(b, float)
    out = dict(mean_diff=float(d.mean()))
    sd = d.std(ddof=1)
    out["cohens_dz"] = float(d.mean() / sd) if sd > 0 else 0.0
    if np.any(d != 0):
        out["wilcoxon_p"] = float(st.wilcoxon(a, b).pvalue)
        out["ttest_p"] = float(st.ttest_rel(a, b).pvalue)
    else:
        out["wilcoxon_p"] = out["ttest_p"] = 1.0
    return out


def verdict(t, lower_is_better=True):
    if t["wilcoxon_p"] >= 0.05:
        return "no significant difference"
    better = (t["mean_diff"] < 0) == lower_is_better
    return "significantly better" if better else "significantly worse"


# --------------------------------------------------------------------------- plots
def plots(R, sweep, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 140, "axes.grid": True, "grid.alpha": .25, "font.size": 9})
    col = {"adaptive": "#1b9e77", "adaptive_nohyst": "#7570b3", "static_t5": "#d95f02", "static_t3": "#e6ab02",
           "adaptive_batch": "#66a61e", "static_t5_batch": "#a6761d"}
    n = len(R["adaptive"][0]["lat_research"]); bounds = np.r_[0, np.cumsum([k for _, k in SCHEDULE])[:-1]]

    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for c in ("static_t5", "adaptive"):
        M = np.array([t["lat_research"] for t in R[c]])
        ax.plot(np.median(M, 0), color=col[c], label=LABEL[c], lw=1.6)
        ax.fill_between(range(n), np.percentile(M, 25, 0), np.percentile(M, 75, 0), color=col[c], alpha=.18)
    ax.axhline(200, color="k", ls="--", lw=1, label="200 ms SLA")
    for b, (p, _) in zip(bounds, SCHEDULE):
        ax.axvline(b, color="#999", lw=.5); ax.text(b + .4, ax.get_ylim()[1] * .98, p, fontsize=7, va="top", color="#555")
    ax.set(xlabel="control cycle", ylabel="delivery latency (ms)", title="Research-path latency, staged stress (median + IQR)")
    ax.legend(fontsize=7, loc="lower left"); fig.tight_layout(); fig.savefig(out / "fig1.png"); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.2), sharey=True)
    names = ["static_t5", "static_t3", "adaptive_nohyst", "adaptive", "static_t5_batch", "adaptive_batch"]
    for ax, path in zip(axs, ("clinical", "research")):
        m = [np.mean([t[f"viol_{path}_stress"] for t in R[c]]) * 100 for c in names]
        e = [stats([t[f"viol_{path}_stress"] * 100 for t in R[c]])["ci95"] for c in names]
        ax.bar(range(len(names)), m, yerr=e, color=[col[c] for c in names], capsize=3)
        ax.set_xticks(range(len(names))); ax.set_xticklabels(["T5", "T3", "CADA\nno-hyst", "CADA", "T5\nbatch", "CADA\nbatch"], fontsize=7)
        ax.set_title(f"{path.capitalize()} path")
    axs[0].set_ylabel("SLA violations during stress (%) ±95% CI"); fig.tight_layout(); fig.savefig(out / "fig2.png"); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"width_ratios": [2, 1]})
    for c in ("adaptive", "adaptive_nohyst"):
        axs[0].step(range(n), R[c][0]["tiers"], where="post", color=col[c], label=LABEL[c], lw=1.4)
    axs[0].set(yticks=[1, 3, 5], xlabel="control cycle", ylabel="active tier", title="Tier trajectory (seed 1)"); axs[0].legend(fontsize=7)
    axs[1].boxplot([[t["tier_changes"] for t in R[c]] for c in ("adaptive_nohyst", "adaptive")])
    axs[1].set_xticks([1, 2]); axs[1].set_xticklabels(["no hyst", "3-cycle"]); axs[1].set(ylabel="tier changes / trial", title="Flapping")
    fig.tight_layout(); fig.savefig(out / "fig3.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for i, c in enumerate(("static_t5", "static_t3", "adaptive")):
        d = {k: np.mean([t["dwell"][k] for t in R[c]]) for k in ("5", "3", "1")}; tot = sum(d.values()); bot = 0
        for k, cc in (("5", "#2fd18b"), ("3", "#f2b84b"), ("1", "#ff6b6b")):
            ax.bar(i, d[k] / tot * 100, bottom=bot, color=cc, label=f"Tier {k}" if i == 0 else None); bot += d[k] / tot * 100
    ax.set_xticks(range(3)); ax.set_xticklabels(["Static T5", "Static T3", "CADA"]); ax.set(ylabel="% of cycles", title="Tier dwell (agile path)")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(out / "fig4.png"); plt.close(fig)

    if sweep:
        bws, losses = sweep["bws"], sweep["losses"]
        Z = np.array([[sweep["cells"][f"{b}|{l}"]["delta_pp"] for b in bws] for l in losses])
        fig, ax = plt.subplots(figsize=(5.4, 3.3))
        vm = max(1.0, float(np.abs(Z).max()))
        im = ax.imshow(Z, cmap="RdYlGn_r", aspect="auto", origin="lower", vmin=-vm, vmax=vm)
        ax.set_xticks(range(len(bws))); ax.set_xticklabels([f"{b:g}" for b in bws]); ax.set_yticks(range(len(losses))); ax.set_yticklabels([f"{l:g}" for l in losses])
        for i in range(len(losses)):
            for j in range(len(bws)):
                ax.text(j, i, f"{Z[i, j]:+.1f}", ha="center", va="center", fontsize=8)
        ax.set(xlabel="link bandwidth (Mbps)", ylabel="packet loss (%)", title="Δ SLA violations: CADA − static T5 (pp, stress phase)")
        fig.colorbar(im, ax=ax); fig.tight_layout(); fig.savefig(out / "fig5.png"); plt.close(fig)


# ---------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--sweep-seeds", type=int, default=4)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    jobs = [(c, s, SCHEDULE, None) for s in range(1, a.trials + 1) for c in CONFIGS]
    R = {c: [] for c in CONFIGS}
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(run_trial, jobs, chunksize=1), 1):
            R[r["config"]].append(r)
            if i % len(CONFIGS) == 0:
                print(f"[A] trial {i // len(CONFIGS)}/{a.trials} ({time.time() - t0:.0f}s)", flush=True)
    for c in R:
        R[c].sort(key=lambda t: t["seed"])

    # ---- Part B: bandwidth x loss sweep (constant severe RTT/CPU, vary link)
    bws, losses = [20.0, 5.0, 2.0, 1.0], [0.0, 0.5, 1.0, 2.0]
    sched = [("calm", 6), ("severe", 24)]
    cells = {}
    sj = [(c, s, sched, dict(rtt_ms=150, cpu_pct=75, jitter_ms=15, loss_pct=l, bw_mbps=b))
          for b in bws for l in losses for c in ("adaptive", "static_t5") for s in range(1, a.sweep_seeds + 1)]
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(run_trial, sj, chunksize=1))
    k = 0
    for b in bws:
        for l in losses:
            vals = {"adaptive": [], "static_t5": []}
            for c in ("adaptive", "static_t5"):
                for s in range(a.sweep_seeds):
                    r = res[k]; k += 1
                    vals[c].append(0.5 * (r["viol_clinical_stress"] + r["viol_research_stress"]) * 100)
            cells[f"{b}|{l}"] = dict(adaptive=float(np.mean(vals["adaptive"])), static_t5=float(np.mean(vals["static_t5"])),
                                     delta_pp=float(np.mean(vals["adaptive"]) - np.mean(vals["static_t5"])))
    sweep = dict(bws=bws, losses=losses, cells=cells, seeds=a.sweep_seeds)
    print(f"[B] sweep done ({time.time() - t0:.0f}s)", flush=True)

    plots(R, sweep, out)
    metrics = ["viol_clinical_stress", "viol_research_stress", "p95_clinical", "p95_research", "p99_clinical",
               "mean_wire_clinical", "handshakes", "tier_changes", "mean_privacy_eps", "mean_k", "min_clinical_tier"]
    summary = {c: {m: stats([t[m] for t in R[c]]) for m in metrics} for c in R}
    pairs = [("adaptive", "static_t5"), ("adaptive", "static_t3"), ("adaptive", "adaptive_nohyst"),
             ("adaptive_batch", "static_t5_batch")]
    tm = ("viol_clinical_stress", "viol_research_stress", "p95_clinical", "p95_research", "tier_changes", "handshakes")
    tests = {f"{x}_vs_{y}": {m: paired([t[m] for t in R[x]], [t[m] for t in R[y]]) for m in tm} for x, y in pairs}
    slim = {c: [{k2: v for k2, v in t.items() if not k2.startswith("lat_") and k2 != "tiers"} for t in R[c]] for c in R}
    (out / "results.json").write_text(json.dumps(dict(schedule=SCHEDULE, trials=a.trials, summary=summary,
                                                      tests=tests, sweep=sweep, per_trial=slim), indent=1))

    L = ["# Module 7 - Empirical Evaluation Report (Agile-HQ-PQC / CADA-AASM)\n",
         f"*{a.trials} paired trials (seeds 1..{a.trials}); each trial = {sum(n for _, n in SCHEDULE)} control cycles: "
         f"{' -> '.join(f'{p}({n})' for p, n in SCHEDULE)}. Reproduce with `python evaluation/run_eval.py`.*\n",
         "## 1. What is measured vs. modelled\n",
         "- **Real**: hybrid handshakes, AEAD, Ed25519 and ML-KEM/ML-DSA operations (pure-Python reference libraries), wire sizes, controller logic, anonymisation.\n"
         "- **Emulated (assumptions, not testbed data)**: congestion via `StressInjector` (extra RTT / CPU / loss / bandwidth) and the "
         "delivery-latency model `NetworkModel` = RTT + serialisation + per-extra-fragment queueing + one RTO if any fragment is lost.\n"
         "- Host RTT/CPU probes are fixed baselines (0.2 ms, 5 %) during evaluation so parallel workers do not perturb the controller.\n"
         "- ML-DSA compute and handshake compute are **not charged** to per-packet latency (re-key is make-before-break; the pure-Python "
         "implementations are not representative of native speed). Only their **bytes on the wire** are. This isolates the size/fragmentation "
         "mechanism the project is about, and means compute-bound effects are out of scope.\n"
         "- Latency is delivery-and-acknowledge time, consistent with L = 200 - RTT - 0.5*CPU.\n",
         "## 2. Part A - staged stress, mean ± 95% CI\n",
         "| Metric | " + " | ".join(LABEL[c] for c in CONFIGS) + " |", "|---|" + "---|" * len(CONFIGS)]
    pretty = {"viol_clinical_stress": "Clinical SLA violations in stress (frac.)", "viol_research_stress": "Research SLA violations in stress (frac.)",
              "p95_clinical": "Clinical p95 (ms)", "p95_research": "Research p95 (ms)", "p99_clinical": "Clinical p99 (ms)",
              "mean_wire_clinical": "Mean clinical wire bytes", "handshakes": "Handshakes / trial", "tier_changes": "Tier changes / trial",
              "mean_privacy_eps": "Mean ε (agile path)", "mean_k": "Mean K (agile path)", "min_clinical_tier": "Min clinical tier"}
    for m, nm in pretty.items():
        L.append(f"| {nm} | " + " | ".join(f"{summary[c][m]['mean']:.3f} ± {summary[c][m]['ci95']:.3f}" for c in CONFIGS) + " |")
    L += ["\n## 3. Paired tests (first config minus second; Wilcoxon signed-rank p, paired-t p)\n",
          "| Comparison | Metric | mean diff | Wilcoxon p | t p | d_z | Reading |", "|---|---|---|---|---|---|---|"]
    for k2, v in tests.items():
        for m, r in v.items():
            L.append(f"| {k2} | {m} | {r['mean_diff']:+.4f} | {r['wilcoxon_p']:.2e} | {r['ttest_p']:.2e} | {r['cohens_dz']:.2f} | {verdict(r)} |")
    L += ["\n## 4. Part B - where does steering help? (bandwidth × loss sweep)\n",
          f"Constant severe RTT/CPU stress, {sweep['seeds']} seeds per cell, per-packet PQ signatures. Cell = CADA minus static-T5 SLA-violation rate (percentage points; negative = CADA better).\n",
          "| loss \\ bandwidth | " + " | ".join(f"{b:g} Mbps" for b in bws) + " |", "|---|" + "---|" * len(bws)]
    for l in losses:
        L.append(f"| {l:g} % | " + " | ".join(f"{cells[f'{b}|{l}']['delta_pp']:+.1f} (T5 {cells[f'{b}|{l}']['static_t5']:.1f}%)" for b in bws) + " |")
    L += ["\n![fig1](fig1.png)\n\n![fig2](fig2.png)\n\n![fig3](fig3.png)\n\n![fig4](fig4.png)\n\n![fig5](fig5.png)\n",
          "## 5. Invariants\n",
          f"- HIPAA floor: minimum clinical tier over all adaptive trials = **{min(t['min_clinical_tier'] for t in R['adaptive'])}** (required >= 3).\n"
          f"- Anti-flapping: tier changes / trial {summary['adaptive']['tier_changes']['mean']:.1f} (3-cycle hysteresis) vs "
          f"{summary['adaptive_nohyst']['tier_changes']['mean']:.1f} (none).\n"]
    (out / "module7_evaluation_report.md").write_text("\n".join(L))
    print("\n".join(L), flush=True)
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
