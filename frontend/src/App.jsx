import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken, login, setToken, setUnauthorizedHandler } from "./api.js";
import { useGateway } from "./useGateway.js";
import { Tier } from "./ui.jsx";
import OverviewTab from "./components/OverviewTab.jsx";
import LiveTab from "./components/live/LiveTab.jsx";
import SecurityTab from "./components/SecurityTab.jsx";
import PrivacyTab from "./components/PrivacyTab.jsx";
import SharingTab from "./components/SharingTab.jsx";
import ResultsTab from "./components/ResultsTab.jsx";
import AuditTab from "./components/AuditTab.jsx";
import Autopilot from "./autopilot/Autopilot.jsx";
import { useAutopilot } from "./autopilot/useAutopilot.js";

// [id, label, visible-if(perms)]
const TABS = [
  ["overview", "Overview", () => true],
  ["live", "Live", (p) => p.has("monitor")],
  ["security", "Security Lab", (p) => p.has("inspect")],
  ["privacy", "Privacy", (p) => p.has("privacy_view")],
  ["sharing", "Data Sharing", (p) => p.has("export_deid") || p.has("ingest") || p.has("exchange")],
  ["results", "Results", () => true],
  ["audit", "Audit", (p) => p.has("audit_read")],
];
// The autopilot drives stress, tamper and the privacy view, so it needs all of these.
const AUTOPILOT_PERMS = ["monitor", "stress", "inspect", "tamper", "privacy_view"];

const PERSONAS = [["admin", "admin@pqc", "Admin"], ["auditor", "audit@pqc", "Auditor"],
  ["researcher", "research@pqc", "Researcher"], ["operator", "operator@pqc", "Operator"]];

class TabBoundary extends React.Component {   // a failing tab shows its error instead of blanking the app
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    return this.state.error
      ? <p className="err">This tab failed to render: {String(this.state.error.message || this.state.error)}</p>
      : this.props.children;
  }
}

function Login({ onLogin }) {
  const [u, setU] = useState(""), [p, setP] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { onLogin(await login(u, p)); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="login">
      <form className="card" onSubmit={submit} autoComplete="off">
        <div className="brand"><span className="logo">⬡</span> Agile-HQ-PQC</div>
        <p className="muted small">Adaptive Quantum-Safe Security and Privacy for Healthcare Data · closed-loop SLA steering (CADA-AASM)</p>
        <label>Username<input value={u} onChange={(e) => setU(e.target.value)} required autoFocus /></label>
        <label>Password<input type="password" value={p} onChange={(e) => setP(e.target.value)} required /></label>
        <button className="btn primary" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <div className="err" role="alert">{err}</div>
        <div className="muted small">Demo personas (click to fill)</div>
        <div className="chips">
          {PERSONAS.map(([uu, pp, label]) => (
            <button type="button" key={uu} className="chip" onClick={() => { setU(uu); setP(pp); }}>{label}</button>
          ))}
        </div>
      </form>
    </div>
  );
}

/* Presenter mode: larger type, secondary panels hidden. Toggle with P. */
function usePresenter() {
  const [on, setOn] = useState(() => { try { return localStorage.getItem("pqc_presenter") === "1"; } catch { return false; } });
  useEffect(() => {
    document.documentElement.classList.toggle("presenter", on);
    try { localStorage.setItem("pqc_presenter", on ? "1" : "0"); } catch { /* ignore */ }
  }, [on]);
  useEffect(() => {
    const key = (e) => {
      if (e.target.closest("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "p" || e.key === "P") setOn((x) => !x);
      else if (e.key === "Escape") setOn(false);
    };
    addEventListener("keydown", key);
    return () => removeEventListener("keydown", key);
  }, []);
  return [on, setOn];
}

function ThemeToggle() {
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem("pqc_theme"); } catch { return null; } });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    try { theme ? localStorage.setItem("pqc_theme", theme) : localStorage.removeItem("pqc_theme"); } catch { /* ignore */ }
  }, [theme]);
  const next = { null: "light", light: "dark", dark: null }[String(theme)];
  return (
    <button className="btn small" onClick={() => setTheme(next)} title="Theme: auto → light → dark">
      {theme ? theme[0].toUpperCase() + theme.slice(1) : "Auto"} theme
    </button>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [checking, setChecking] = useState(!!getToken());
  const [tab, setTab] = useState(null);

  const perms = new Set(session?.permissions || []);
  const tabs = TABS.filter(([, , ok]) => ok(perms));
  const active = tab && tabs.some(([id]) => id === tab) ? tab : tabs[0]?.[0];
  const gw = useGateway(!!session && perms.has("monitor"));
  const gwRef = useRef(gw);
  gwRef.current = gw;
  const [presenter, setPresenter] = usePresenter();
  const ap = useAutopilot({ gwRef, setTab, setPresenter, presenter });
  const canAutopilot = AUTOPILOT_PERMS.every((p) => perms.has(p));

  const logout = useCallback(() => { ap.stop(); setToken(null); setSession(null); setTab(null); }, [ap.stop]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setUnauthorizedHandler(logout); }, [logout]);
  useEffect(() => {   // resume a saved session; permissions come from the server, not the client
    if (!getToken()) return;
    api("/api/me").then(setSession).catch(logout).finally(() => setChecking(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (checking) return null;
  if (!session) return <Login onLogin={setSession} />;

  const pickTab = (id) => { if (ap.running) ap.stop(); setTab(id); };   // a manual click takes over from the autopilot
  const latest = gw.latest;
  const viol = latest && (latest.clinical.sla_violation || latest.research.sla_violation);
  return (
    <>
      <header className="top">
        <div className="brand"><span className="logo">⬡</span> Agile-HQ-PQC</div>
        {latest && <Tier t={latest.active_tier}>{`TIER ${latest.active_tier}`}</Tier>}
        {latest && <span className={"pill " + (viol ? "bad" : "ok")}>{viol ? "✕ SLA violation" : "✓ SLA met"}</span>}
        <span className="spacer" />
        {canAutopilot && (
          <button className="btn primary small" disabled={ap.running} onClick={ap.start}
            title="Runs the whole demo hands-free: heavy load, tamper lab, privacy, results">▶ Run demo</button>
        )}
        {perms.has("monitor") && <span className={"pill " + (gw.connected ? "ok" : "off")}>{gw.connected ? "● live" : "○ offline"}</span>}
        <span className="muted small secondary">{session.user} · {session.role}</span>
        <button className={"btn small" + (presenter ? " on" : "")} onClick={() => setPresenter(!presenter)}
          title="Presenter mode: larger text, secondary panels hidden (P)">{presenter ? "Exit presenter" : "Presenter"}</button>
        <ThemeToggle />
        <button className="btn small" onClick={logout}>Sign out</button>
      </header>
      <nav className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={id === active} className={id === active ? "active" : ""}
            onClick={() => pickTab(id)}>{label}</button>
        ))}
      </nav>
      <main className={ap.running || ap.finished ? "with-autopilot" : ""}><TabBoundary key={active}>
        {active === "overview" && <OverviewTab canRunDemo={canAutopilot && !ap.running} onRunDemo={ap.start} />}
        {active === "live" && <LiveTab gw={gw} perms={perms} />}
        {active === "security" && <SecurityTab />}
        {active === "privacy" && <PrivacyTab />}
        {active === "sharing" && <SharingTab perms={perms} />}
        {active === "results" && <ResultsTab />}
        {active === "audit" && <AuditTab />}
      </TabBoundary></main>
      <Autopilot ap={ap} />
    </>
  );
}
