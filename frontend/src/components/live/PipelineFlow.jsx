/* The control loop as a live diagram:
   Probe → Budget → CADA (hysteresis) → Active tier → Clinical PHI | Research. */
import React from "react";
import { Tier } from "../../ui.jsx";

const BUDGET_MAX = 200, LOW = 40, HIGH = 80;

function BudgetBar({ value }) {
  const pct = (v) => Math.max(0, Math.min(100, (v / BUDGET_MAX) * 100));
  return (
    <div className="bbar" aria-hidden="true">
      <div className="z t1" style={{ width: pct(LOW) + "%" }} />
      <div className="z t3" style={{ width: pct(HIGH) - pct(LOW) + "%" }} />
      <div className="z t5" style={{ flex: 1 }} />
      <div className="bmark" style={{ left: pct(value) + "%" }} />
    </div>
  );
}

const Arrow = ({ pulse }) => <div className="flow-arrow" key={pulse}><span className="dot" /></div>;

export default function PipelineFlow({ ev }) {
  if (!ev) return <section className="card flow-empty muted">Waiting for the first control cycle…</section>;
  const d = ev.decision, st = ev.stress, t = ev.active_tier;
  const injected = st.rtt_ms || st.cpu_pct;
  const pending = d.pending_tier != null;
  const pulse = ev.step;

  return (
    <section className="card">
      <div className="card-h">
        <h3>Control loop</h3>
        <span className="muted small">one cycle every tick · step {ev.step}</span>
      </div>
      <div className="flow">
        <div className="node">
          <h4>1 · Probe</h4>
          <div className="nv mono">{ev.probe.rtt_ms.toFixed(1)} ms</div>
          <div className="soft small">RTT · CPU <b className="mono">{ev.probe.cpu_pct.toFixed(0)} %</b></div>
          <div className={"small " + (injected ? "warn-t" : "muted")}>
            {injected ? `stress: +${st.rtt_ms} ms, +${st.cpu_pct} % CPU` : "no stress injected"}
          </div>
        </div>
        <Arrow pulse={pulse} />
        <div className="node">
          <h4>2 · Latency budget</h4>
          <div className="nv mono">{ev.budget_ms.toFixed(1)} ms</div>
          <div className="muted small mono">200 − RTT − 0.5·CPU</div>
          <BudgetBar value={ev.budget_ms} />
          <div className="bbar-lbl muted mono"><span>T1 ≤ 40</span><span>T3</span><span>T5 &gt; 80</span></div>
        </div>
        <Arrow pulse={pulse} />
        <div className={"node" + (pending ? " pending" : "")}>
          <h4>3 · CADA controller</h4>
          <div className="row" style={{ gap: 6 }}>
            <span className="soft small">target</span> <Tier t={d.raw_target} />
          </div>
          <div className="pips" aria-label={`hysteresis ${d.hysteresis_count} of ${d.hysteresis_needed}`}>
            {Array.from({ length: d.hysteresis_needed }, (_, i) => (
              <span key={i} className={"pip" + (i < d.hysteresis_count ? " on" : "")} />
            ))}
          </div>
          <div className="small soft">
            {pending ? `${d.hysteresis_count}/${d.hysteresis_needed} cycles toward Tier ${d.pending_tier}` : "stable · no pending switch"}
          </div>
        </div>
        <Arrow pulse={pulse} />
        <div className={"node" + (d.changed ? " flash" : "")} key={"tier" + t}>
          <h4>4 · Active tier</h4>
          <Tier t={t} lg />
          <div className="small soft mt-s">{ev.tier_info.kem} + {ev.tier_info.dsa}</div>
          <div className="small muted">{ev.tier_info.aead}</div>
        </div>
        <div className="flow-split" key={"split" + pulse}><span className="dot a" /><span className="dot b" /></div>
        <div className="domains">
          <div className="node dom clin">
            <h4><span className="sw-dot s1" />Clinical PHI</h4>
            <div className="row" style={{ gap: 6 }}>
              <Tier t={ev.clinical_tier} />
              {d.floor_clamped
                ? <span className="small shield">🛡 Safety floor holding</span>
                : <span className="small muted">floor ≥ T3</span>}
            </div>
            <div className="small mono soft mt-s">{ev.clinical.latency_ms.toFixed(1)} ms · {ev.clinical.wire_bytes} B</div>
          </div>
          <div className="node dom res">
            <h4><span className="sw-dot s2" />Research (de-identified)</h4>
            <div className="row" style={{ gap: 6 }}>
              <Tier t={t} />
              <span className="small mono soft">ε {ev.privacy.epsilon} · K {ev.privacy.k} · L {ev.privacy.l}</span>
            </div>
            <div className="small mono soft mt-s">{ev.research.latency_ms.toFixed(1)} ms · {ev.research.wire_bytes} B</div>
          </div>
        </div>
      </div>
    </section>
  );
}
