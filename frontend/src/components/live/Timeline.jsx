/* Annotated timeline. Shaded background = active tier, dashed verticals = tier
   changes, ringed points = SLA violations. Two synced single-axis charts share one crosshair. */
import React, { useMemo } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card, TIER_COLOR, TooltipBox, useTokens } from "../../ui.jsx";

function segments(rows) {   // contiguous runs of the same active tier
  const out = [];
  rows.forEach((r) => {
    const last = out[out.length - 1];
    if (last && last.tier === r.tier) last.x2 = r.i;
    else out.push({ tier: r.tier, x1: r.i, x2: r.i });
  });
  return out.map((s, k) => ({ ...s, x1: s.x1 - 0.5, x2: s.x2 + 0.5, key: k }));
}

const ViolationDot = (flag, color, surface) => (props) => {
  const { cx, cy, payload, index } = props;
  if (!payload[flag] || cx == null) return <g key={index} />;
  return <circle key={index} cx={cx} cy={cy} r={5} fill={color} stroke={surface} strokeWidth={2} />;
};

export default function Timeline({ history, sla = 200 }) {
  const tok = useTokens();
  const rows = useMemo(() => history.map((ev, i) => ({
    i, step: ev.step, tier: ev.active_tier, clinTier: ev.clinical_tier,
    clin: ev.clinical.latency_ms, res: ev.research.latency_ms, budget: ev.budget_ms, rtt: ev.probe.rtt_ms,
    violC: ev.clinical.sla_violation, violR: ev.research.sla_violation,
  })), [history]);
  const segs = useMemo(() => segments(rows), [rows]);
  const changes = segs.slice(1).map((s, k) => ({ x: s.x1, from: segs[k].tier, to: s.tier }));
  if (!rows.length) return <Card title="Timeline"><p className="muted">No data yet.</p></Card>;

  const domain = [rows[0].i - 0.5, rows[rows.length - 1].i + 0.5];
  const bMin = Math.min(0, Math.floor(Math.min(...rows.map((r) => r.budget)) / 20) * 20);
  const yMax = Math.max(260, ...rows.map((r) => Math.max(r.clin, r.res) * 1.1));
  const axis = { stroke: tok.line, tick: { fill: tok.muted, fontSize: tok.fs }, tickLine: false };
  const bands = segs.map((s) => (
    <ReferenceArea key={"b" + s.key} x1={s.x1} x2={s.x2} fill={TIER_COLOR(tok, s.tier)} fillOpacity={0.1}
      stroke="none" ifOverflow="hidden" />
  ));
  const changeLines = (withLabel) => changes.map((c) => (
    <ReferenceLine key={"c" + c.x} x={c.x} stroke={tok.muted} strokeDasharray="3 3"
      label={withLabel ? { value: `T${c.from}→T${c.to}`, position: "insideTopLeft", fill: tok.text2, fontSize: tok.fs } : undefined} />
  ));
  const tip = (render) => ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    return render(payload[0].payload);
  };

  return (
    <Card title="Timeline" sub={`last ${rows.length} control cycles`}>
      <div className="legend">
        <span><span className="sw" style={{ background: tok.s1 }} />Clinical PHI latency</span>
        <span><span className="sw" style={{ background: tok.s2 }} />Research latency</span>
        <span><span className="sw dash" />SLA {sla} ms</span>
        <span>● SLA violation</span>
        <span className="spacer" />
        <span><span className="sw box" style={{ background: tok.t5, opacity: .5 }} />T5</span>
        <span><span className="sw box" style={{ background: tok.t3, opacity: .5 }} />T3</span>
        <span><span className="sw box" style={{ background: tok.t1, opacity: .5 }} />T1</span>
        <span className="muted">background = active tier · dashed = tier change</span>
      </div>
      <div className="chart" style={{ height: 230 }}>
        <ResponsiveContainer>
          <LineChart data={rows} syncId="timeline" margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
            {bands}
            <CartesianGrid stroke={tok.grid} vertical={false} />
            <XAxis dataKey="i" type="number" domain={domain} hide allowDataOverflow />
            <YAxis {...axis} domain={[0, Math.ceil(yMax / 50) * 50]} width={52} unit=" ms" />
            {changeLines(true)}
            <ReferenceLine y={sla} stroke={tok.muted} strokeDasharray="6 4"
              label={{ value: `SLA ${sla} ms`, position: "insideTopRight", fill: tok.text2, fontSize: tok.fs }} />
            <Tooltip cursor={{ stroke: tok.muted }} content={tip((r) => (
              <TooltipBox title={`step ${r.step} · Tier ${r.tier} (clinical T${r.clinTier})`} rows={[
                { label: "Clinical", value: r.clin.toFixed(1) + " ms" + (r.violC ? " ✕" : ""), color: tok.s1 },
                { label: "Research", value: r.res.toFixed(1) + " ms" + (r.violR ? " ✕" : ""), color: tok.s2 },
              ]} />
            ))} />
            <Line dataKey="clin" stroke={tok.s1} strokeWidth={tok.lw} isAnimationActive={false}
              dot={ViolationDot("violC", tok.s1, tok.surface)} activeDot={{ r: 4 }} />
            <Line dataKey="res" stroke={tok.s2} strokeWidth={tok.lw} isAnimationActive={false}
              dot={ViolationDot("violR", tok.s2, tok.surface)} activeDot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="legend mt"><span><span className="sw" style={{ background: tok.text2 }} />Latency budget L = 200 − RTT − 0.5·CPU (ms)</span>
        <span className="muted">tier thresholds at 80 and 40 ms</span></div>
      <div className="chart" style={{ height: 150 }}>
        <ResponsiveContainer>
          <LineChart data={rows} syncId="timeline" margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            {bands}
            <CartesianGrid stroke={tok.grid} vertical={false} />
            <XAxis dataKey="i" type="number" domain={domain} hide allowDataOverflow />
            <YAxis {...axis} unit=" ms" domain={[bMin, 200]} ticks={[bMin, 40, 80, 120, 160, 200].filter((v, k, a) => a.indexOf(v) === k)} width={52} />
            {changeLines(false)}
            <ReferenceLine y={80} stroke={tok.t5} strokeDasharray="4 4"
              label={{ value: "T5 above 80", position: "insideTopLeft", fill: tok.text2, fontSize: tok.fs }} />
            <ReferenceLine y={40} stroke={tok.t1} strokeDasharray="4 4"
              label={{ value: "T1 at/below 40", position: "insideBottomRight", fill: tok.text2, fontSize: tok.fs }} />
            <Tooltip cursor={{ stroke: tok.muted }} content={tip((r) => (
              <TooltipBox title={`step ${r.step}`} rows={[
                { label: "Budget", value: r.budget.toFixed(1) + " ms", color: tok.text2 },
                { label: "RTT", value: r.rtt.toFixed(1) + " ms" },
              ]} />
            ))} />
            <Line dataKey="budget" stroke={tok.text2} strokeWidth={tok.lw} isAnimationActive={false} dot={false} activeDot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
