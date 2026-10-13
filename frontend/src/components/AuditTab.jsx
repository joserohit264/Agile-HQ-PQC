import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { Card } from "../ui.jsx";

export default function AuditTab() {
  const [d, setD] = useState(null), [err, setErr] = useState("");
  const load = () => api("/api/audit?n=200").then((x) => { setD(x); setErr(""); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const v = d?.verify;
  return (
    <Card title="Tamper-evident audit log" sub="HMAC hash chain"
      actions={<>
        {v && <span className={"pill " + (v.ok ? "ok" : "bad")}>{v.ok ? `✓ chain intact · ${v.length} entries` : `✕ chain broken at #${v.broken_at}: ${v.reason}`}</span>}
        <button className="btn small" onClick={load}>Reload</button>
      </>}>
      {err && <p className="err">{err}</p>}
      {d && (
        <div className="tbl-wrap" style={{ maxHeight: 560, overflowY: "auto" }}>
          <table>
            <thead><tr><th>#</th><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th><th>Hash</th></tr></thead>
            <tbody>
              {d.entries.slice().reverse().map((e) => (
                <tr key={e.idx}>
                  <td>{e.idx}</td><td>{new Date(e.ts * 1000).toLocaleTimeString()}</td><td>{e.actor}</td><td>{e.action}</td>
                  <td>{JSON.stringify(e.detail).slice(0, 110)}</td><td className="mono">{e.hash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
