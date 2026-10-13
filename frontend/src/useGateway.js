/* Live gateway state: initial /api/state, then Socket.IO "tick" and "demo_phase" streams. */
import { useCallback, useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import { api, fmtMs, getToken } from "./api.js";

const MAX_HISTORY = 120, MAX_LOG = 80;
const IDLE_DEMO = { active: false, index: null, startedAt: null };

export function useGateway(enabled) {
  const [meta, setMeta] = useState(null);
  const [history, setHistory] = useState([]);
  const [latest, setLatest] = useState(null);
  const [connected, setConnected] = useState(false);
  const [log, setLog] = useState([]);
  const [demo, setDemo] = useState(IDLE_DEMO);
  const [minClinicalTier, setMinClinicalTier] = useState(5);
  const prev = useRef(null);
  const phases = useRef([]);

  const addLog = useCallback((kind, text) => {
    setLog((l) => [{ id: Math.random(), kind, time: new Date(), text }, ...l].slice(0, MAX_LOG));
  }, []);

  const onTick = useCallback((ev) => {
    const p = prev.current;
    if (p && ev.counters.packets < p.counters.packets) setMinClinicalTier(5);   // mode switch restarted the gateway
    setMinClinicalTier((m) => Math.min(m, ev.clinical_tier));
    setLatest(ev);
    setHistory((h) => [...h, ev].slice(-MAX_HISTORY));
    if (p) {
      if (p.active_tier !== ev.active_tier)
        addLog("ev-tier", `T${p.active_tier} → T${ev.active_tier} at budget ${ev.budget_ms.toFixed(0)} ms`);
      if (ev.handshake)
        addLog("ev-rekey", `re-key ${ev.handshake.suite} (${fmtMs(ev.handshake.timings_ms.total)}, ${ev.handshake.total_bytes} B)`);
      if (ev.counters.sla_violations_clinical > p.counters.sla_violations_clinical)
        addLog("ev-sla", `clinical packet ${ev.clinical.latency_ms.toFixed(0)} ms exceeded the SLA`);
      if (ev.counters.sla_violations_research > p.counters.sla_violations_research)
        addLog("ev-sla", `research packet ${ev.research.latency_ms.toFixed(0)} ms exceeded the SLA`);
    }
    prev.current = ev;
  }, [addLog]);

  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    api("/api/state").then((d) => {
      if (!alive) return;
      phases.current = d.demo_phases || [];
      setMeta({ presets: d.presets, adaptive: d.adaptive, tiers: d.tiers, demo_phases: d.demo_phases,
        step_interval: d.step_interval, sla_ms: d.sla_ms });
      setHistory(d.history);
      if (d.history.length) {
        const last = d.history[d.history.length - 1];
        setLatest(last); prev.current = last;
        setMinClinicalTier(Math.min(5, ...d.history.map((e) => e.clinical_tier)));
      }
      if (d.demo?.active) {
        const i = phases.current.findIndex((p) => p.label === d.demo.phase);
        setDemo({ active: true, index: Math.max(0, i), startedAt: Date.now() });
      }
    }).catch((e) => addLog("ev-sla", e.message));

    const sock = io({ auth: { token: getToken() }, transports: ["websocket", "polling"] });
    sock.on("connect", () => setConnected(true));
    sock.on("disconnect", () => setConnected(false));
    sock.on("tick", onTick);
    sock.on("demo_phase", (p) => {
      if (p.done) {
        setDemo({ active: false, index: phases.current.length, startedAt: null });
        addLog("ev-demo", "guided demo complete - stress cleared");
      } else {
        const i = phases.current.findIndex((x) => x.label === p.label);
        setDemo({ active: true, index: Math.max(0, i), startedAt: Date.now() });
        addLog("ev-demo", p.label);
      }
    });
    return () => { alive = false; sock.disconnect(); };
  }, [enabled, onTick, addLog]);

  return { meta, setMeta, history, latest, connected, log, addLog, demo, setDemo, minClinicalTier };
}
