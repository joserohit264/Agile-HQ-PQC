/* Data sharing by role: researcher de-identified export, operator IoMT ingestion and inter-hospital exchange. */
import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Card, Table } from "../ui.jsx";

function Export() {
  const [d, setD] = useState(null), [err, setErr] = useState("");
  const preview = useCallback(() => api("/api/export/deid").then((x) => { setD(x); setErr(""); }).catch((e) => setErr(e.message)), []);
  useEffect(() => { preview(); }, [preview]);
  const csv = async () => {
    try {
      const txt = await api("/api/export/deid?format=csv");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([txt], { type: "text/csv" })); a.download = "deid_export.csv"; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (e) { setErr(e.message); }
  };
  return (
    <Card title="De-identified research export" sub="enforces K ≥ 5, L ≥ 3 regardless of tier" className="span2"
      actions={<><button className="btn small" onClick={preview}>Refresh</button>
        <button className="btn primary small" onClick={csv}>⬇ Download CSV</button></>}>
      <p className="muted small">Direct identifiers are removed, quasi-identifiers are generalised by Mondrian, and the release is
        independently re-verified before it is served.</p>
      {err && <p className="err">{err}</p>}
      {d && <p className="small mono soft">K = {d.k} · L = {d.l} · {d.count} rows · {d.classes} classes · info loss {d.info_loss} ·
        verified {d.verified ? "✓" : "✕"}</p>}
      {d && <div style={{ maxHeight: 360, overflowY: "auto" }}><Table rows={d.rows.slice(0, 40)} cols={["age", "zip", "sex", "diagnosis"]} /></div>}
    </Card>
  );
}

const SAMPLE = () => JSON.stringify({ pid: "P00099", device: "ECG-ICU-7", ts: Math.round(Date.now() / 1000),
  vitals: { hr: 78, spo2: 97, sbp: 121, dbp: 79 }, ecg_mv: [0.01, 0.02, 0.05, 0.9, 0.1] }, null, 2);

function Ingest() {
  const [body, setBody] = useState(SAMPLE), [out, setOut] = useState(null), [err, setErr] = useState("");
  const send = async () => {
    let parsed;
    try { parsed = JSON.parse(body); } catch { setErr("Invalid JSON"); return; }
    try { setOut(await api("/api/ingest", { method: "POST", body: parsed })); setErr(""); }
    catch (e) { setOut(null); setErr(e.message); }
  };
  return (
    <Card title="IoMT telemetry ingestion" sub="operator">
      <textarea className="mono" rows={10} value={body} onChange={(e) => setBody(e.target.value)} aria-label="telemetry JSON" />
      <button className="btn primary" onClick={send}>Encrypt &amp; transmit</button>
      {err && <p className="err">{err}</p>}
      {out && <pre className="mono small mt out">{JSON.stringify(out, null, 2)}</pre>}
    </Card>
  );
}

function Exchange() {
  const [ex, setEx] = useState(null), [err, setErr] = useState("");
  const load = useCallback(() => api("/api/exchange").then((d) => { setEx(d); setErr(""); }).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  return (
    <Card title="Inter-hospital exchange" actions={<button className="btn small" onClick={load}>Refresh</button>}>
      {err && <p className="err">{err}</p>}
      {ex && (
        <dl className="kv">
          <dt>Local</dt><dd>{ex.local}</dd>
          <dt>Peer</dt><dd>{ex.peer}</dd>
          <dt>Clinical suite</dt><dd className="mono">{ex.clinical_suite || "—"}</dd>
          <dt>Packets sent</dt><dd className="mono">{ex.packets}</dd>
          <dt>Clinical SLA violations</dt><dd className="mono">{ex.sla_violations}</dd>
        </dl>
      )}
    </Card>
  );
}

export default function SharingTab({ perms }) {
  return (
    <div className="grid g2">
      {perms.has("export_deid") && <Export />}
      {perms.has("ingest") && <Ingest />}
      {perms.has("exchange") && <Exchange />}
    </div>
  );
}
