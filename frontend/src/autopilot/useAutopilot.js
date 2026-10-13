/* Runs the autopilot STEPS with pause / resume / skip / stop. Progress is kept in a ref (read by the
   overlay on its own timer) so the whole app doesn't re-render 20 times a second. */
import { useCallback, useRef, useState } from "react";
import { api } from "../api.js";
import { emit } from "../bus.js";
import { STEPS } from "./script.js";

class Cancelled extends Error {}
const IDLE = { running: false, paused: false, finished: false, stepIdx: -1, narration: "" };

export function useAutopilot({ gwRef, setTab, setPresenter, presenter }) {
  const [st, setSt] = useState(IDLE);
  const ctl = useRef(null);
  const progress = useRef({ elapsed: 0, est: 1 });
  const presenterBefore = useRef(false);

  const start = useCallback(async () => {
    if (ctl.current) return;
    const c = { cancelled: false, paused: false, skip: false };
    ctl.current = c;
    presenterBefore.current = presenter;
    setPresenter(true);

    const wait = (ms) => new Promise((res, rej) => {
      let left = ms, last = performance.now();
      const id = setInterval(() => {
        if (c.cancelled) { clearInterval(id); rej(new Cancelled()); return; }
        const now = performance.now();
        if (!c.paused) { left -= now - last; progress.current.elapsed += now - last; }
        last = now;
        if (c.skip || left <= 0) { clearInterval(id); res(); }
      }, 50);
    });
    const until = async (pred, timeoutMs) => {
      const t0 = performance.now();
      while (!c.skip && !pred() && performance.now() - t0 < timeoutMs) await wait(200);
    };
    const x = {
      wait, until, api, emit,
      gw: () => gwRef.current,
      say: (narration) => setSt((s) => (s.narration === narration ? s : { ...s, narration })),
    };

    setSt({ ...IDLE, running: true, stepIdx: 0 });
    try {
      for (let i = 0; i < STEPS.length; i++) {
        const step = STEPS[i];
        c.skip = false;
        progress.current = { elapsed: 0, est: step.est };
        setTab(step.tab);
        setSt((s) => ({ ...s, stepIdx: i, narration: step.narration }));
        await step.run(x);
      }
      setSt((s) => ({ ...s, running: false, paused: false, finished: true, stepIdx: STEPS.length,
        narration: "✓ Demo complete. Every step ran live against the real gateway." }));
    } catch (e) {
      if (!(e instanceof Cancelled))
        setSt((s) => ({ ...s, running: false, finished: true, narration: "Autopilot stopped: " + e.message }));
    } finally {
      if (ctl.current === c) ctl.current = null;   // stop() may already have released it
      if (!ctl.current) setPresenter(presenterBefore.current);
    }
  }, [gwRef, setTab, setPresenter, presenter]);

  const stop = useCallback(() => {
    const c = ctl.current;
    if (c) c.cancelled = true;
    ctl.current = null;
    if (gwRef.current?.demo.active) api("/api/demo/stop", { method: "POST" }).catch(() => {});
    setSt(IDLE);
  }, [gwRef]);

  const pause = useCallback(() => { if (ctl.current) { ctl.current.paused = true; setSt((s) => ({ ...s, paused: true })); } }, []);
  const resume = useCallback(() => { if (ctl.current) { ctl.current.paused = false; setSt((s) => ({ ...s, paused: false })); } }, []);
  const skip = useCallback(() => { if (ctl.current) { ctl.current.skip = true; ctl.current.paused = false; setSt((s) => ({ ...s, paused: false })); } }, []);
  const close = useCallback(() => setSt(IDLE), []);

  return { ...st, steps: STEPS, progress, start, stop, pause, resume, skip, close };
}
