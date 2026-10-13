/* Floating autopilot panel: step list, live narration, step progress and transport controls. */
import React, { useEffect, useState } from "react";

function StepProgress({ progress, paused }) {
  const [p, setP] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setP(Math.min(1, progress.current.elapsed / progress.current.est)), 120);
    return () => clearInterval(id);
  }, [progress]);
  return <div className={"rail-bar" + (paused ? " paused" : "")}><div style={{ width: p * 100 + "%" }} /></div>;
}

export default function Autopilot({ ap }) {
  if (!ap.running && !ap.finished) return null;
  const n = ap.steps.length, cur = ap.steps[ap.stepIdx];
  return (
    <aside className="autopilot" role="region" aria-label="Autopilot demo">
      <div className="ap-h">
        <b>{ap.running ? (ap.paused ? "⏸ Autopilot paused" : "▶ Autopilot demo") : "Autopilot demo"}</b>
        <span className="muted small">{ap.running ? `step ${ap.stepIdx + 1} of ${n} · ${cur?.title}` : "finished"}</span>
        <span className="spacer" />
        {ap.running ? (<>
          {ap.paused
            ? <button className="btn small" onClick={ap.resume}>▶ Resume</button>
            : <button className="btn small" onClick={ap.pause}>⏸ Pause</button>}
          <button className="btn small" onClick={ap.skip}>⏭ Skip</button>
          <button className="btn small danger" onClick={ap.stop}>■ Stop</button>
        </>) : (<>
          <button className="btn small primary" onClick={ap.start}>↻ Run again</button>
          <button className="btn small" onClick={ap.close}>Close</button>
        </>)}
      </div>
      <ol className="ap-steps">
        {ap.steps.map((s, i) => (
          <li key={s.id} className={i < ap.stepIdx ? "done" : i === ap.stepIdx ? "now" : "todo"}>
            <span className="stepnum">{i < ap.stepIdx ? "✓" : i + 1}</span>{s.title}
          </li>
        ))}
      </ol>
      <p className="ap-narr" aria-live="polite">{ap.narration}</p>
      {ap.running && <StepProgress progress={ap.progress} paused={ap.paused} />}
      {ap.running && ap.paused && <p className="small muted">The live gateway keeps running while the tour is paused.</p>}
    </aside>
  );
}
