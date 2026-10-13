/* Guided demo as a progress rail with one line of narration per phase,
   plus a live caption generated from the current control decision. */
import React, { useEffect, useState } from "react";
import { api } from "../../api.js";

// Describes what each phase injects and what the controller is expected to do. The live caption
// below reports what actually happened (host CPU load can push "heavy" straight to Tier 1).
const NARRATION = [
  "Clear network. The budget has close to 200 ms of headroom, so CADA holds Tier 5: ML-KEM-1024, ε = 0.1, K = 5.",
  "+125 ms RTT and +55 % CPU injected. As the budget falls below 80 ms, CADA steps down, but only after 3 consistent cycles.",
  "+150 ms RTT and +75 % CPU. The budget collapses: the research path drops to Tier 1 (ε = 1.0, K = 2), clinical PHI stays at Tier 3.",
  "Stress cleared. The budget recovers; hysteresis waits 3 cycles, then sessions re-key make-before-break back up to Tier 5.",
];

export function caption(ev) {
  if (!ev) return "";
  const d = ev.decision, b = ev.budget_ms.toFixed(0);
  if (d.changed) return `Switched to Tier ${ev.active_tier} - sessions re-keyed make-before-break.`;
  if (d.pending_tier != null)
    return `Budget ${b} ms → CADA wants Tier ${d.pending_tier} (${d.hysteresis_count}/${d.hysteresis_needed} cycles before switching).`;
  return `Budget ${b} ms → holding Tier ${ev.active_tier}` +
    (d.floor_clamped ? "; clinical PHI held at Tier 3 by the HIPAA floor." : ".");
}

const shortLabel = (l) => l.replace(/^Phase\s+\w+\s*-\s*/, "");

export default function DemoStepper({ phases, interval, demo, setDemo, latest, canRun, onError }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!demo.active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, [demo.active]);

  if (!phases) return null;
  const idx = demo.index;                    // null = never run, phases.length = finished
  const done = idx != null && idx >= phases.length;
  const cur = demo.active ? phases[idx] : null;
  const progress = cur && demo.startedAt ? Math.min(1, (now - demo.startedAt) / (cur.steps * interval * 1000)) : 0;
  const total = Math.round(phases.reduce((s, p) => s + p.steps, 0) * interval);

  const run = async () => {
    try { setDemo({ active: true, index: 0, startedAt: Date.now() }); await api("/api/demo/start", { method: "POST" }); }
    catch (e) { setDemo({ active: false, index: null, startedAt: null }); onError(e.message); }
  };

  return (
    <section className="card">
      <div className="card-h">
        <h3>Guided demo · Simulate heavy load</h3>
        <span className="muted small">{demo.active ? `phase ${idx + 1} of ${phases.length}` : done ? "complete - system recovered" : `${phases.length} phases · ≈ ${total} s`}</span>
        <span className="spacer" />
        {canRun
          ? <button className="btn primary small" disabled={demo.active} onClick={run}>{done ? "↻ Run again" : "▶ Simulate Heavy Load"}</button>
          : <span className="muted small">admin starts the demo</span>}
      </div>
      <ol className="rail">
        {phases.map((p, i) => {
          const state = idx == null ? "todo" : i < idx || done ? "done" : i === idx ? "now" : "todo";
          return (
            <li key={i} className={state}>
              <div className="rail-h">
                <span className="stepnum">{state === "done" ? "✓" : i + 1}</span>
                <b>{shortLabel(p.label)}</b>
              </div>
              <div className="rail-bar"><div style={{ width: (state === "done" ? 100 : state === "now" ? progress * 100 : 0) + "%" }} /></div>
              <p className="small soft">{NARRATION[i] || p.label}</p>
            </li>
          );
        })}
      </ol>
      <div className="caption" aria-live="polite"><span className="muted small">now</span> {caption(latest)}</div>
    </section>
  );
}
