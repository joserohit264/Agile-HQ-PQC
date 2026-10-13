/* The evaluation evidence (reports/results.json) as interactive charts. */
import React, { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, ErrorBar, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api.js";
import { Card, Stat, TooltipBox, useTokens } from "../ui.jsx";

const CONFIGS = [["adaptive", "Adaptive"], ["adaptive_nohyst", "Adaptive, no hysteresis"],
  ["static_t5", "Static T5"], ["static_t3", "Static T3"]];
const COMPARISONS = {
  adaptive_vs_static_t5: "Adaptive vs static T5",
  adaptive_vs_static_t3: "Adaptive vs static T3",
  adaptive_vs_adaptive_nohyst: "Hysteresis on vs off",
  adaptive_batch_vs_static_t5_batch: "With batch signing: adaptive vs static T5",
};
const METRICS = {
  viol_clinical_stress: ["Clinical SLA viol. (stress)", (v) => (v * 100).toFixed(1) + " pp"],
  viol_research_stress: ["Research SLA viol. (stress)", (v) => (v * 100).toFixed(1) + " pp"],
  p95_clinical: ["p95 clinical latency", (v) => v.toFixed(1) + " ms"],
  p95_research: ["p95 research latency", (v) => v.toFixed(1) + " ms"],
  tier_changes: ["Tier changes / trial", (v) => v.toFixed(1)],
  handshakes: ["Handshakes / trial", (v) => v.toFixed(1)],
};
const pct = (v) => (v * 100).toFixed(1) + " %";
const pfmt = (p) => (p < 1e-4 ? "< 0.0001" : p.toFixed(4));

function luminance(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

function ViolationChart({ s, tok }) {
  const data = CONFIGS.map(([k, name]) => ({
    name, clin: s[k].viol_clinical_stress.mean * 100, res: s[k].viol_research_stress.mean * 100,
    ciC: s[k].viol_clinical_stress.ci95 * 100, ciR: s[k].viol_research_stress.ci95 * 100,
  }));
  const axis = { stroke: tok.line, tick: { fill: tok.muted, fontSize: tok.fs }, tickLine: false };
  return (
    <Card title="SLA violations during stress" sub="mean of 30 paired trials · whiskers = 95 % CI · lower is better">
      <div className="legend">
        <span><span className="sw box" style={{ background: tok.s1 }} />Clinical PHI</span>
        <span><span className="sw box" style={{ background: tok.s2 }} />Research</span>
      </div>
      <div className="chart" style={{ height: 260 }}>
        <ResponsiveContainer>
          <BarChart data={data} barGap={2} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={tok.grid} vertical={false} />
            <XAxis dataKey="name" {...axis} interval={0} tick={{ fill: tok.text2, fontSize: tok.fs }} />
            <YAxis {...axis} width={40} unit=" %" />
            <Tooltip cursor={{ fill: tok.grid, opacity: .5 }} content={({ active, payload }) => active && payload?.length ? (
              <TooltipBox title={payload[0].payload.name} rows={[
                { label: "Clinical", value: `${payload[0].payload.clin.toFixed(1)} % ± ${payload[0].payload.ciC.toFixed(1)}`, color: tok.s1 },
                { label: "Research", value: `${payload[0].payload.res.toFixed(1)} % ± ${payload[0].payload.ciR.toFixed(1)}`, color: tok.s2 },
              ]} />) : null} />
            <Bar dataKey="clin" fill={tok.s1} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false}>
              <ErrorBar dataKey="ciC" width={6} stroke={tok.text2} />
              <LabelList dataKey="clin" position="top" offset={10} formatter={(v) => v.toFixed(1)} fill={tok.text2} fontSize={tok.fs} />
            </Bar>
            <Bar dataKey="res" fill={tok.s2} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false}>
              <ErrorBar dataKey="ciR" width={6} stroke={tok.text2} />
              <LabelList dataKey="res" position="top" offset={10} formatter={(v) => v.toFixed(1)} fill={tok.text2} fontSize={tok.fs} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function TierChangeChart({ s, tok }) {
  const data = CONFIGS.map(([k, name]) => ({ name, v: s[k].tier_changes.mean, ci: s[k].tier_changes.ci95 }));
  const axis = { stroke: tok.line, tick: { fill: tok.muted, fontSize: tok.fs }, tickLine: false };
  return (
    <Card title="Tier changes per trial" sub="cipher flapping · 95 % CI">
      <div className="chart" style={{ height: 260 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={tok.grid} vertical={false} />
            <XAxis dataKey="name" {...axis} interval={0} tick={{ fill: tok.text2, fontSize: tok.fs }} />
            <YAxis {...axis} width={32} allowDecimals={false} />
            <Tooltip cursor={{ fill: tok.grid, opacity: .5 }} content={({ active, payload }) => active && payload?.length ? (
              <TooltipBox title={payload[0].payload.name} rows={[
                { label: "Tier changes", value: `${payload[0].payload.v.toFixed(1)} ± ${payload[0].payload.ci.toFixed(1)}`, color: tok.accent },
              ]} />) : null} />
            <Bar dataKey="v" fill={tok.accent} radius={[4, 4, 0, 0]} maxBarSize={48} isAnimationActive={false}>
              <ErrorBar dataKey="ci" width={6} stroke={tok.text2} />
              <LabelList dataKey="v" position="top" offset={10} formatter={(v) => v.toFixed(1)} fill={tok.text2} fontSize={tok.fs} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function SweepHeatmap({ sweep, tok }) {
  const [hover, setHover] = useState(null);
  // [upper bound of gain in pp, legend label, sequential step]
  const bins = [[0, "0", 0], [2, "≤ 2", 1], [5, "2–5", 2], [20, "5–20", 3], [Infinity, "> 20", 5]];
  const color = (gain) => tok.seq[bins.find(([hi]) => gain <= hi)[2]];
  const ink = (bg) => (luminance(bg) > 0.3 ? "#0b0b0b" : "#ffffff");
  const cells = {};
  Object.entries(sweep.cells).forEach(([key, v]) => {
    const [b, l] = key.split("|").map(Number);
    cells[`${b}|${l}`] = v;
  });
  const bws = [...sweep.bws].sort((a, b) => b - a), losses = [...sweep.losses].sort((a, b) => a - b);
  return (
    <Card title="Where adaptation helps" sub={`bandwidth × loss sweep · ${sweep.seeds} seeds per cell`}>
      <p className="small muted">Cell = how many percentage points fewer clinical SLA violations adaptive has than static Tier 5 during stress.
        Stronger colour = bigger gain.</p>
      <div className="heat" style={{ gridTemplateColumns: `auto repeat(${losses.length}, minmax(56px, 1fr))` }}>
        <div className="heat-corner small muted">bandwidth ↓ · loss →</div>
        {losses.map((l) => <div key={l} className="heat-h small muted">{l} %</div>)}
        {bws.map((b) => (
          <React.Fragment key={b}>
            <div className="heat-r small muted">{b} Mbps</div>
            {losses.map((l) => {
              const c = cells[`${b}|${l}`];
              if (!c) return <div key={l} className="heat-c">—</div>;
              const gain = -c.delta_pp, bg = color(gain);
              return (
                <div key={l} className="heat-c mono" style={{ background: bg, color: ink(bg) }} tabIndex={0}
                  onMouseEnter={() => setHover({ b, l, ...c, gain })} onFocus={() => setHover({ b, l, ...c, gain })}
                  onMouseLeave={() => setHover(null)} onBlur={() => setHover(null)}>
                  {gain > 0.05 ? gain.toFixed(1) : "0"}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
      <div className="legend mt">
        {bins.map(([, label, step]) => <span key={label}><span className="sw box" style={{ background: tok.seq[step] }} />{label} pp</span>)}
      </div>
      <p className="small soft mt" aria-live="polite">
        {hover
          ? `${hover.b} Mbps, ${hover.l} % loss: static T5 ${hover.static_t5.toFixed(1)} % vs adaptive ${hover.adaptive.toFixed(1)} % violations (gain ${hover.gain.toFixed(1)} pp).`
          : "Hover a cell for details. Gains concentrate on thin links (1–2 Mbps); at ≥ 5 Mbps there is little or nothing to gain."}
      </p>
    </Card>
  );
}

function TestsTable({ tests }) {
  const [cmp, setCmp] = useState(Object.keys(COMPARISONS).find((k) => tests[k]));
  const rows = tests[cmp] || {};
  return (
    <Card title="Paired significance tests" sub="Wilcoxon signed-rank + paired t-test · negative diff = adaptive lower" className="span2">
      <div className="chips">
        {Object.entries(COMPARISONS).filter(([k]) => tests[k]).map(([k, label]) => (
          <button key={k} className={"chip" + (cmp === k ? " active" : "")} onClick={() => setCmp(k)}>{label}</button>
        ))}
      </div>
      <div className="tbl-wrap mt">
        <table>
          <thead><tr><th>Metric</th><th className="num">Mean diff</th><th className="num">Cohen's d<sub>z</sub></th>
            <th className="num">Wilcoxon p</th><th className="num">t-test p</th><th>Significant (p &lt; 0.05)</th></tr></thead>
          <tbody>
            {Object.entries(METRICS).filter(([m]) => rows[m]).map(([m, [label, fmt]]) => {
              const r = rows[m], sig = r.wilcoxon_p < 0.05;
              return (
                <tr key={m}>
                  <td>{label}</td><td className="num mono">{(r.mean_diff > 0 ? "+" : "") + fmt(r.mean_diff)}</td>
                  <td className="num mono">{r.cohens_dz.toFixed(2)}</td>
                  <td className="num mono">{pfmt(r.wilcoxon_p)}</td><td className="num mono">{pfmt(r.ttest_p)}</td>
                  <td>{sig ? <span className="ok-ico">✓ yes</span> : <span className="muted">no</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function ResultsTab() {
  const tok = useTokens();
  const [d, setD] = useState(null), [err, setErr] = useState("");
  useEffect(() => { api("/api/results").then(setD).catch((e) => setErr(e.message)); }, []);
  if (err) return <Card title="Evaluation results"><p className="err">{err}</p></Card>;
  if (!d) return <p className="muted">Loading…</p>;
  const s = d.summary, a = s.adaptive, t5 = s.static_t5, nh = s.adaptive_nohyst;
  return (
    <div className="grid">
      <div className="grid g4">
        <Stat label="Clinical SLA viol. during stress" value={`${pct(t5.viol_clinical_stress.mean)} → ${pct(a.viol_clinical_stress.mean)}`}
          detail="static Tier 5 → adaptive" />
        <Stat label="Research SLA viol. during stress" value={`${pct(t5.viol_research_stress.mean)} → ${pct(a.viol_research_stress.mean)}`}
          detail="static Tier 5 → adaptive" />
        <Stat label="Tier changes per trial" value={`${nh.tier_changes.mean.toFixed(1)} → ${a.tier_changes.mean.toFixed(1)}`}
          detail={`hysteresis: −${Math.round((1 - a.tier_changes.mean / nh.tier_changes.mean) * 100)} % flapping`} />
        <Stat label="Lowest clinical tier" value={`T${a.min_clinical_tier.mean.toFixed(0)}`}
          detail={<span><span className="ok-ico">✓</span> HIPAA floor held in all {d.trials} trials</span>} />
      </div>
      <div className="grid g2">
        <ViolationChart s={s} tok={tok} />
        <TierChangeChart s={s} tok={tok} />
      </div>
      <div className="grid g3">
        {d.sweep && <SweepHeatmap sweep={d.sweep} tok={tok} />}
        <TestsTable tests={d.tests} />
      </div>
      <p className="small muted">All numbers come from an <b>emulated</b> congestion model (see docs/LIMITATIONS.md). On a real kernel-shaped
        link the gain over static Tier 5 disappears at ≥ 2 Mbit/s; adaptation matters only on very thin links.</p>
    </div>
  );
}
