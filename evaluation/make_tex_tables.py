#!/usr/bin/env python3
"""Generate LaTeX tables for the paper directly from reports/results.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "reports" / "results.json").read_text())
S, T, SW = R["summary"], R["tests"], R["sweep"]
cfgs = [("static_t5", "Static T5"), ("static_t3", "Static T3"), ("adaptive_nohyst", "CADA, no hyst."),
        ("adaptive", "CADA-AASM"), ("static_t5_batch", "T5 + batch"), ("adaptive_batch", "CADA + batch")]
rows = [("viol_clinical_stress", "Clinical viol.\\ (stress)", 100, "\\%"), ("viol_research_stress", "Research viol.\\ (stress)", 100, "\\%"),
        ("p95_clinical", "Clinical p95 (ms)", 1, ""), ("p95_research", "Research p95 (ms)", 1, ""),
        ("mean_wire_clinical", "Mean wire bytes", 1, ""), ("handshakes", "Handshakes/trial", 1, ""),
        ("tier_changes", "Tier changes/trial", 1, "")]

L = ["\\begin{table*}[t]\\centering\\caption{Staged-stress evaluation, " + str(R["trials"]) + " paired trials, mean $\\pm$ 95\\% CI.}\\label{tab:main}\\small",
     "\\begin{tabular}{l" + "r" * len(cfgs) + "}\\toprule", "Metric & " + " & ".join(n for _, n in cfgs) + " \\\\\\midrule"]
for k, name, sc, suf in rows:
    L.append(name + " & " + " & ".join(f"{S[c][k]['mean']*sc:.1f}{suf} $\\pm$ {S[c][k]['ci95']*sc:.1f}" for c, _ in cfgs) + " \\\\")
L += ["\\bottomrule\\end{tabular}\\end{table*}"]

L += ["", "\\begin{table}[t]\\centering\\caption{Paired Wilcoxon tests, CADA-AASM minus baseline (per-packet PQ signatures).}\\label{tab:tests}\\small",
      "\\begin{tabular}{llrr}\\toprule", "Baseline & Metric & mean diff & Wilcoxon $p$ \\\\\\midrule"]
for pair, label in (("adaptive_vs_static_t5", "T5"), ("adaptive_vs_static_t3", "T3"), ("adaptive_vs_adaptive_nohyst", "no hyst.")):
    for m, ml, sc in (("viol_clinical_stress", "clin.\\ viol.\\ (pp)", 100), ("viol_research_stress", "res.\\ viol.\\ (pp)", 100),
                      ("p95_research", "res.\\ p95 (ms)", 1), ("tier_changes", "tier changes", 1)):
        t = T[pair][m]
        L.append(f"{label} & {ml} & {t['mean_diff']*sc:+.2f} & {t['wilcoxon_p']:.1e} \\\\")
L += ["\\bottomrule\\end{tabular}\\end{table}"]

bws, losses, cells = SW["bws"], SW["losses"], SW["cells"]
L += ["", "\\begin{table}[t]\\centering\\caption{Sweep: CADA minus static-T5 SLA-violation rate (percentage points), constant severe RTT/CPU stress.}\\label{tab:sweep}\\small",
      "\\begin{tabular}{l" + "r" * len(bws) + "}\\toprule", "loss $\\backslash$ bw & " + " & ".join(f"{b:g} Mbps" for b in bws) + " \\\\\\midrule"]
for l in losses:
    L.append(f"{l:g}\\% & " + " & ".join(f"{cells[f'{b}|{l}']['delta_pp']:+.1f}" for b in bws) + " \\\\")
L += ["\\bottomrule\\end{tabular}\\end{table}"]
(ROOT / "LaTeX_Sources" / "results_tables.tex").write_text("\n".join(L) + "\n")
print("wrote LaTeX_Sources/results_tables.tex")
