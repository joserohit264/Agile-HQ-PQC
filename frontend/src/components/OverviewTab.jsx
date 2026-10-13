import React from "react";
import { Card, Tier } from "../ui.jsx";

const TIERS = [
  [5, "ML-KEM-1024 + ML-DSA-87", "AES-256-GCM", "0.1", "5 / 3", "plenty of headroom (> 80 ms)"],
  [3, "ML-KEM-768 + ML-DSA-65", "AES-256-GCM", "0.5", "3 / 2", "moderate headroom (40–80 ms)"],
  [1, "ML-KEM-512 + ML-DSA-44", "ChaCha20-Poly1305", "1.0", "2 / 2", "tight budget (≤ 40 ms)"],
];

// yes | no. Groups follow section 5 of docs/REPORT.md; numbers refer to docs/REFERENCES.md.
const RELATED = [
  ["PQC for healthcare [4, 5, 8, 9]", "yes", "no", "no", "no", "no"],
  ["PQC cost on networks [7, 11–16]", "yes", "no", "no", "no", "no"],
  ["Adaptive PQC [6, 10]", "yes", "no", "yes", "no", "no"],
  ["Privacy for medical data [19, 20]", "no", "yes", "no", "no", "no"],
  ["Adaptive privacy [17, 18, 21]", "no", "yes", "yes", "no", "no"],
  ["Agile-HQ-PQC (this work)", "yes", "yes", "yes", "yes", "yes"],
];
const cell = (v, j) => (v === "yes" ? <td key={j} className="yes">✔</td> : <td key={j} className="no">—</td>);

export default function OverviewTab({ onRunDemo, canRunDemo }) {
  return (
    <div className="grid">
      <section className="hero card">
        <h2>Quantum-safe healthcare data, without breaking the 200 ms clock</h2>
        <p>
          Quantum-safe encryption makes every packet bigger, which can break real-time patient monitoring on slow networks.
          Agile-HQ-PQC watches the network and picks the <b>strongest protection it can currently afford</b>, for both
          encryption and patient-data privacy, but <b>never goes below a safe minimum for raw patient data</b>.
        </p>
        {canRunDemo && <button className="btn primary" onClick={onRunDemo}>▶ Run the full demo automatically</button>}
      </section>

      <Card title="How it works in three steps">
        <div className="steps">
          <div className="step"><b>1 · Measure</b>Every cycle: remaining latency budget <span className="mono">L = 200 − RTT − 0.5·CPU</span>.</div>
          <div className="step"><b>2 · Choose</b>Map the budget to Tier 5 / 3 / 1. Three agreeing cycles are needed before switching (no flapping).</div>
          <div className="step"><b>3 · Protect</b>Apply the tier to encryption <i>and</i> privacy noise. Raw patient data is floored at Tier 3; research data uses the full range.</div>
        </div>
      </Card>

      <Card title="The three protection tiers">
        <div className="tbl-wrap"><table>
          <thead><tr><th>Tier</th><th>Key exchange + signature</th><th>Data cipher</th><th className="num">DP ε</th><th className="num">K / L</th><th>Chosen when</th></tr></thead>
          <tbody>{TIERS.map((r) => (
            <tr key={r[0]}><td><Tier t={r[0]} /></td>{r.slice(1).map((c, i) => <td key={i} className={i === 2 || i === 3 ? "num" : ""}>{c}</td>)}</tr>
          ))}</tbody>
        </table></div>
        <p className="muted small">Smaller ε = more noise = stronger privacy. Larger K/L = harder to single out a patient.</p>
      </Card>

      <Card title="Research gap" sub="nobody joins these five properties" className="secondary">
        <div className="tbl-wrap"><table>
          <thead><tr><th>Work</th><th>Post-quantum crypto</th><th>Privacy (DP / anonymity)</th><th>Adapts at runtime</th><th>Crypto + privacy jointly</th><th>Compliance floor</th></tr></thead>
          <tbody>{RELATED.map((r, i) => (
            <tr key={r[0]} className={i === RELATED.length - 1 ? "hl" : ""}><td>{r[0]}</td>{r.slice(1).map(cell)}</tr>
          ))}</tbody>
        </table></div>
        <p className="muted small">Runtime-adaptive PQC already exists [6, 10]; the gap is the joint coupling with privacy under a floor. Adaptive privacy [17, 18] adapts in training and [21] is theory only; [20] sets budgets once per dataset, so it does not adapt at run time. From 18 IEEE Xplore papers (2023–2026), read in full.</p>
      </Card>
    </div>
  );
}
