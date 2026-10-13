/* Privacy sliders: ε (log scale) drives the ECG noise live, K/L drive Mondrian, and each
   sits on its privacy/utility curve with the three tier settings marked. */
import React, { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api.js";
import { on } from "../bus.js";
import { Card, Table, Tier, TIER_COLOR, TooltipBox, useTokens } from "../ui.jsx";

const EPS_MIN = 0.05, EPS_MAX = 2;
const toEps = (s) => +(EPS_MIN * (EPS_MAX / EPS_MIN) ** s).toFixed(3);          // slider 0..1 -> ε
const toSlider = (e) => Math.log(e / EPS_MIN) / Math.log(EPS_MAX / EPS_MIN);

function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}

function TierMarks({ tiers, tok }) {
  return tiers.map((t) => (
    <ReferenceDot key={t.tier} x={t.x} y={t.y} r={5} fill={TIER_COLOR(tok, t.tier)} stroke={tok.surface} strokeWidth={2}
      label={{ value: `T${t.tier}`, position: "top", fill: tok.text2, fontSize: tok.fs }} ifOverflow="extendDomain" />
  ));
}

function TradeoffChart({ data, xKey, yKey, xLabel, yLabel, current, tiers, tok, logX, fmtY, height = 170 }) {
  const axis = { stroke: tok.line, tick: { fill: tok.muted, fontSize: tok.fs }, tickLine: false };
  const nearest = (x) => data.reduce((a, b) => (Math.abs(b[xKey] - x) < Math.abs(a[xKey] - x) ? b : a))[yKey];
  return (
    <div className="chart" style={{ height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 18, right: 14, bottom: 14, left: 0 }}>
          <CartesianGrid stroke={tok.grid} vertical={false} />
          <XAxis dataKey={xKey} type="number" scale={logX ? "log" : "auto"} domain={["dataMin", "dataMax"]} {...axis}
            ticks={logX ? [0.05, 0.1, 0.2, 0.5, 1, 2] : undefined} allowDecimals={false}
            label={{ value: xLabel, position: "insideBottom", offset: -8, fill: tok.muted, fontSize: tok.fs }} />
          <YAxis {...axis} width={48} tickFormatter={fmtY} />
          <Tooltip cursor={{ stroke: tok.muted }} content={({ active, payload }) => active && payload?.length ? (
            <TooltipBox title={`${xLabel} ${payload[0].payload[xKey]}`} rows={[{ label: yLabel, value: fmtY(payload[0].payload[yKey]), color: tok.accent }]} />
          ) : null} />
          <Line dataKey={yKey} stroke={tok.accent} strokeWidth={tok.lw} dot={false} isAnimationActive={false} />
          <TierMarks tiers={tiers.map((t) => ({ tier: t.tier, x: t.x, y: nearest(t.x) }))} tok={tok} />
          <ReferenceDot x={current} y={nearest(current)} r={7} fill="none" stroke={tok.text} strokeWidth={2} ifOverflow="extendDomain" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Ecg({ curve, tiers }) {
  const tok = useTokens();
  const [eps, setEps] = useState(0.5), [d, setD] = useState(null), [err, setErr] = useState("");
  const q = useDebounced(eps, 80);
  useEffect(() => on("privacy:eps", setEps), []);
  useEffect(() => { api(`/api/privacy/ecg?eps=${q}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(e.message)); }, [q]);
  const rows = d ? d.t.map((t, i) => ({ t, raw: d.series.raw?.[i], dp: d.dp[i] })) : [];
  const axis = { stroke: tok.line, tick: { fill: tok.muted, fontSize: tok.fs }, tickLine: false };
  const tierAt = tiers.find((t) => Math.abs(t.epsilon - eps) < 1e-9);
  return (
    <Card title="Differential privacy · ECG" sub="Laplace mechanism, Δ = 0.5 mV">
      <div className="slider-row">
        <label className="grow"><span>ε = <b className="mono" data-testid="eps">{eps}</b> {tierAt && <Tier t={tierAt.tier}>{`T${tierAt.tier}`}</Tier>}</span>
          <input type="range" min="0" max="1" step="0.005" value={toSlider(eps)} onChange={(e) => setEps(toEps(+e.target.value))}
            aria-label="epsilon" />
          <span className="range-ends"><span>0.05 · most private</span><span>2 · least noise</span></span>
        </label>
        <div className="chips">{tiers.map((t) => (
          <button key={t.tier} className={"chip" + (tierAt?.tier === t.tier ? " active" : "")} onClick={() => setEps(t.epsilon)}>
            T{t.tier} · ε {t.epsilon}</button>))}</div>
      </div>
      {err && <p className="err">{err}</p>}
      {d && (<>
        <div className="legend mt">
          {d.raw_visible && <span><span className="sw" style={{ background: tok.s1 }} />Raw ECG</span>}
          <span><span className="sw" style={{ background: tok.s2 }} />DP-perturbed</span>
          <span className="spacer" /><span className="mono">SNR {d.snr_db} dB · noise scale b = {d.scale} mV</span>
        </div>
        <div className="chart" style={{ height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={tok.grid} vertical={false} />
              <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} {...axis} unit=" s" tickCount={5} />
              <YAxis {...axis} width={44} domain={[-4, 4]} allowDataOverflow />
              <Tooltip content={({ active, payload }) => active && payload?.length ? (
                <TooltipBox title={`t = ${payload[0].payload.t} s`} rows={[
                  ...(d.raw_visible ? [{ label: "Raw", value: payload[0].payload.raw.toFixed(3) + " mV", color: tok.s1 }] : []),
                  { label: "DP", value: payload[0].payload.dp.toFixed(3) + " mV", color: tok.s2 },
                ]} />) : null} />
              <Line dataKey="dp" stroke={tok.s2} strokeWidth={1.2} dot={false} isAnimationActive={false} />
              {d.raw_visible && <Line dataKey="raw" stroke={tok.s1} strokeWidth={tok.lw} dot={false} isAnimationActive={false} />}
            </LineChart>
          </ResponsiveContainer>
        </div>
        {!d.raw_visible && <p className="small muted">Raw signal hidden for your role.</p>}
      </>)}
      {curve && (<>
        <h4 className="mt">Privacy ↔ utility: ε vs signal-to-noise <span className="muted">· ring = your ε · dots = tier settings</span></h4>
        <TradeoffChart data={curve} xKey="epsilon" yKey="snr_db" xLabel="ε" yLabel="SNR dB" current={eps} logX tok={tok}
          tiers={tiers.map((t) => ({ tier: t.tier, x: t.epsilon }))} fmtY={(v) => Math.round(v) + " dB"} />
      </>)}
      <p className="small muted">Smaller ε means stronger privacy and more noise. The research path uses the tier's ε automatically.</p>
    </Card>
  );
}

function Ehr({ tiers }) {
  const tok = useTokens();
  const [k, setK] = useState(3), [l, setL] = useState(2);
  const [d, setD] = useState(null), [curve, setCurve] = useState(null), [err, setErr] = useState("");
  const qk = useDebounced(k, 120), ql = useDebounced(l, 120);
  useEffect(() => on("privacy:kl", ({ k: nk, l: nl }) => { setK(nk); setL(Math.min(nl, nk)); }), []);
  useEffect(() => { api(`/api/privacy/ehr?k=${qk}&l=${ql}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(e.message)); }, [qk, ql]);
  useEffect(() => { api(`/api/privacy/tradeoff?l=${ql}`).then((x) => setCurve(x.k_curve)).catch(() => {}); }, [ql]);
  const tierAt = tiers.find((t) => t.k === k && t.l === l);
  return (
    <Card title="(K, L)-anonymity · EHR" sub="Mondrian generalisation">
      <div className="slider-row">
        <label className="grow"><span>K = <b className="mono" data-testid="k">{k}</b> <span className="muted">· ≥ K patients per class</span></span>
          <input type="range" min="2" max="10" value={k} onChange={(e) => { const v = +e.target.value; setK(v); if (l > v) setL(v); }} aria-label="K" /></label>
        <label className="grow"><span>L = <b className="mono">{l}</b> <span className="muted">· ≥ L diagnoses per class</span></span>
          <input type="range" min="1" max={Math.min(5, k)} value={l} onChange={(e) => setL(+e.target.value)} aria-label="L" /></label>
        <div className="chips">{tiers.map((t) => (
          <button key={t.tier} className={"chip" + (tierAt?.tier === t.tier ? " active" : "")} onClick={() => { setK(t.k); setL(t.l); }}>
            T{t.tier} · K {t.k} L {t.l}</button>))}</div>
      </div>
      {err && <p className="err">{err}</p>}
      {d && <p className="small mono soft mt">{d.classes} equivalence classes · min {d.min_class} · avg {d.avg_class} ·
        info loss {d.info_loss} · independently verified {d.verified ? "✓" : "✕"}</p>}
      {curve && (<>
        <h4 className="mt">Privacy ↔ utility: K vs information loss (L = {ql}) <span className="muted">· lower is more useful</span></h4>
        <TradeoffChart data={curve} xKey="k" yKey="info_loss" xLabel="K" yLabel="info loss" current={k} tok={tok}
          tiers={tiers.filter((t) => t.l === ql).map((t) => ({ tier: t.tier, x: t.k }))} fmtY={(v) => v.toFixed(2)} />
        {ql !== 3 && <p className="small muted">T5 uses L = 3; set L to 3 to see it on this curve.</p>}
      </>)}
      {d && (
        <div className="grid g2 mt">
          <div><h4>Raw (restricted)</h4><Table rows={d.raw} cols={["patient_id", "age", "zip", "sex", "diagnosis"]} /></div>
          <div><h4>Anonymised</h4><Table rows={d.anonymized} cols={["age", "zip", "sex", "diagnosis"]} /></div>
        </div>
      )}
    </Card>
  );
}

export default function PrivacyTab() {
  const [t, setT] = useState(null);
  useEffect(() => { api("/api/privacy/tradeoff").then(setT).catch(() => setT({ eps_curve: null, tiers: [] })); }, []);
  if (!t) return <p className="muted">Loading…</p>;
  const tiers = [...t.tiers].sort((a, b) => b.tier - a.tier);
  return <div className="grid g2"><Ecg curve={t.eps_curve} tiers={tiers} /><Ehr tiers={tiers} /></div>;
}
