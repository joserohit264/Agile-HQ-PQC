import React, { useState } from "react";
import { api } from "../../api.js";
import { Card, Stat, Tier } from "../../ui.jsx";
import PipelineFlow from "./PipelineFlow.jsx";
import DemoStepper from "./DemoStepper.jsx";
import Timeline from "./Timeline.jsx";

const RULE = { 5: "budget > 80 ms", 3: "40 – 80 ms", 1: "≤ 40 ms" };

function Kpis({ ev, minClinicalTier }) {
  if (!ev) return null;
  const c = ev.counters, dw = ev.dwell || {}, pct = (n) => c.packets ? ((n / c.packets) * 100).toFixed(1) + " % of packets" : "";
  return (
    <div className="grid g4">
      <Stat label="Clinical SLA violations" value={c.sla_violations_clinical} detail={pct(c.sla_violations_clinical)}
        bad={c.sla_violations_clinical > 0} />
      <Stat label="Research SLA violations" value={c.sla_violations_research} detail={pct(c.sla_violations_research)}
        bad={c.sla_violations_research > 0} />
      <Stat label="Tier changes" value={c.tier_changes} detail={`dwell T5 ${dw[5] ?? 0} · T3 ${dw[3] ?? 0} · T1 ${dw[1] ?? 0} cycles`} />
      <Stat label="Lowest clinical tier" value={`T${minClinicalTier}`}
        detail={minClinicalTier >= 3 ? <span><span className="ok-ico">✓</span> HIPAA floor held (≥ T3)</span>
          : <span><span className="bad-ico">✕</span> floor breached</span>} bad={minClinicalTier < 3} />
    </div>
  );
}

function TierTable({ tiers, active }) {
  if (!tiers) return null;
  return (
    <Card title="Tier ladder" sub="what each tier costs on the wire" className="span2 secondary">
      <div className="tbl-wrap">
        <table>
          <thead><tr>
            <th>Tier</th><th>Selected when</th><th>KEM</th><th>Signature</th><th>AEAD</th>
            <th className="num">KEM pk / ct</th><th className="num">Sig</th><th className="num">ε</th><th className="num">K / L</th>
          </tr></thead>
          <tbody>
            {[5, 3, 1].map((t) => {
              const x = tiers[t];
              return (
                <tr key={t} className={t === active ? "hl" : ""}>
                  <td><Tier t={t}>{`T${t}`}</Tier>{t === active && <span className="small muted"> ◀ active</span>}</td>
                  <td>{RULE[t]}</td><td>{x.kem}</td><td>{x.dsa}</td><td>{x.aead}</td>
                  <td className="num">{x.kem_pk_bytes} / {x.kem_ct_bytes} B</td><td className="num">{x.dsa_sig_bytes} B</td>
                  <td className="num">{x.epsilon}</td><td className="num">{x.k} / {x.l}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="small muted mt">Clinical PHI never goes below Tier 3. Smaller ε and larger K/L mean stronger privacy for the research path.</p>
    </Card>
  );
}

function Controls({ meta, setMeta, addLog }) {
  const [preset, setPreset] = useState(null);
  const stress = (p) => api("/api/stress", { method: "POST", body: { preset: p } })
    .then(() => { setPreset(p); addLog("ev-demo", "stress preset → " + p); }).catch((e) => addLog("ev-sla", e.message));
  const mode = (adaptive) => api("/api/mode", { method: "POST", body: { adaptive, static_tier: 5 } })
    .then(() => { setMeta((m) => ({ ...m, adaptive })); addLog("ev-demo", adaptive ? "mode → adaptive (CADA)" : "mode → static Tier 5 baseline"); })
    .catch((e) => addLog("ev-sla", e.message));
  return (
    <Card title="Manual controls" sub="admin" className="secondary">
      <h4>Stress injection</h4>
      <div className="chips">
        {meta.presets.map((p) => (
          <button key={p} className={"chip" + (preset === p ? " active" : "")} onClick={() => stress(p)}>{p}</button>
        ))}
      </div>
      <h4 className="mt">Control mode</h4>
      <div className="chips">
        <button className={"chip" + (meta.adaptive ? " active" : "")} onClick={() => mode(true)}>Adaptive (CADA)</button>
        <button className={"chip" + (!meta.adaptive ? " active" : "")} onClick={() => mode(false)}>Static Tier 5 baseline</button>
      </div>
      <p className="small muted mt">Stress is emulated on top of real loopback RTT and host CPU probes. Switching mode restarts the gateway counters.</p>
    </Card>
  );
}

function EventLog({ log }) {
  const LABEL = { "ev-tier": "TIER", "ev-rekey": "REKEY", "ev-sla": "SLA", "ev-demo": "INFO" };
  return (
    <Card title="Events" className="secondary">
      <div className="log">
        {log.length === 0 && <span className="muted small">Tier changes, re-keys and SLA violations appear here.</span>}
        {log.map((e) => (
          <div key={e.id} className={e.kind}>
            <span className="k">{LABEL[e.kind]}</span><span className="muted">{e.time.toLocaleTimeString()}</span><span>{e.text}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function LiveTab({ gw, perms }) {
  const { meta, latest } = gw;
  if (!meta) return <p className="muted">Connecting to the gateway…</p>;
  const isAdmin = perms.has("stress");
  return (
    <div className="grid">
      <DemoStepper phases={meta.demo_phases} interval={meta.step_interval} demo={gw.demo} setDemo={gw.setDemo}
        latest={latest} canRun={isAdmin} onError={(m) => gw.addLog("ev-sla", m)} />
      <PipelineFlow ev={latest} />
      <Kpis ev={latest} minClinicalTier={gw.minClinicalTier} />
      <Timeline history={gw.history} sla={meta.sla_ms} />
      <div className="grid g3 secondary">
        <TierTable tiers={meta.tiers} active={latest?.active_tier} />
        {isAdmin ? <Controls meta={meta} setMeta={gw.setMeta} addLog={gw.addLog} /> : <EventLog log={gw.log} />}
      </div>
      {isAdmin && <EventLog log={gw.log} />}
    </div>
  );
}
