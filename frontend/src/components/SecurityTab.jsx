/* Cryptographic Inspector (5 packet stages) + Tamper Lab (per-layer verdicts with an untampered control). */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { on } from "../bus.js";
import { Card, Tier } from "../ui.jsx";

const TARGETS = [["ciphertext", "Ciphertext"], ["tag", "Auth tag"], ["signature", "Ed25519 signature"],
  ["iv", "IV / nonce"], ["header", "Header (sequence)"]];

function Stage({ title, text }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 900); };
  return (
    <div className="stage">
      <div className="stage-h"><h4>{title}</h4><button className="btn small" onClick={copy}>{copied ? "Copied" : "Copy"}</button></div>
      <pre className="mono">{text}</pre>
    </div>
  );
}

const Layer = ({ name, ok }) => (
  <div className={"layer " + (ok ? "good" : "bad")}><span>{name}</span><b>{ok ? "PASS" : "FAIL"}</b></div>
);

function Inspector() {
  const [t, setT] = useState(null), [err, setErr] = useState("");
  const load = useCallback(() => api("/api/trace").then((x) => { setT(x); setErr(""); }).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  const stages = t && t.stage1_master_secret ? [
    ["01 · Master secret (hybrid PQC)", `${t.suite}\n${t.stage1_master_secret}`],
    ["02 · HKDF-SHA256 derived keys", `enc_key: ${t.stage2_enc_key}\nmac_key: ${t.stage2_mac_key}`],
    ["03 · Plaintext IoMT telemetry", t.stage3_plaintext],
    ["04 · AEAD envelope", `IV (12 B): ${t.stage4_iv}\nCiphertext: ${t.stage4_ciphertext}…\nTag (16 B): ${t.stage4_tag}\nEd25519: ${t.stage4_ed25519_sig}`],
    ["05 · Wire token (base64url)", t.stage5_wire_token]] : null;
  return (
    <Card title="Cryptographic Inspector" sub="latest clinical packet"
      actions={<button className="btn small" onClick={load}>Refresh</button>}>
      {err && <p className="err">{err}</p>}
      {!stages && !err && <p className="muted">Waiting for first packet…</p>}
      {stages && stages.map(([h, x]) => <Stage key={h} title={h} text={x} />)}
      {stages && <div className="muted small mt">seq {t.seq} · <Tier t={t.tier}>{`T${t.tier}`}</Tier> · {t.wire_bytes} B on wire
        (teaching view - keys are shown for evaluators only)</div>}
    </Card>
  );
}

function TamperLab() {
  const [target, setTarget] = useState("ciphertext"), [bit, setBit] = useState(0);
  const [res, setRes] = useState(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]);
  const verdictRef = useRef(null);

  const tamper = useCallback(async (tg, b) => {
    setErr(""); setBusy(true);
    try {
      const r = await api("/api/tamper", { method: "POST", body: { target: tg, bit: Number(b) || 0 } });
      setRes({ ...r, target: tg, at: Date.now() });
      setHistory((h) => [{ target: tg, bit: Number(b) || 0, rejected: r.rejected, id: Math.random() }, ...h].slice(0, 8));
    } catch (e) { setRes(null); setErr(e.message); } finally { setBusy(false); }
  }, []);

  useEffect(() => on("security:tamper", ({ target: tg, bit: b = 0 }) => { setTarget(tg); setBit(b); tamper(tg, b); }), [tamper]);

  return (
    <Card title="Tamper Lab" sub="flip one bit, watch every defence layer react">
      <p className="muted small">Flips one bit of the latest clinical packet. The untampered packet is re-verified as a control.</p>
      <div className="row wrap">
        <label>Target
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {TARGETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select></label>
        <label>Bit index<input type="number" value={bit} min={0} max={2047} onChange={(e) => setBit(e.target.value)} /></label>
        <button className="btn danger" disabled={busy} onClick={() => tamper(target, bit)}>⚡ Inject bit-flip</button>
      </div>
      {err && <p className="err">{err}</p>}
      {res && (
        <div className="tam-out" key={res.at}>
          <Layer name="Ed25519 packet signature" ok={res.layers.ed25519_signature} />
          <Layer name="AEAD authentication tag" ok={res.layers.aead_tag} />
          <Layer name="Sequence / anti-replay" ok={res.layers.sequence} />
          <div ref={verdictRef} className={"verdict flash " + (res.rejected ? "rej" : "acc")}>
            {res.rejected ? "✔ Gateway REJECTED the forged packet — " + res.error : "✘ FORGED PACKET ACCEPTED"}
          </div>
          <div className="muted small mt">Control (untampered) packet verifies: {res.control_untampered_ok ? "✓ yes" : "✕ NO"}</div>
        </div>
      )}
      {history.length > 0 && (
        <>
          <h4 className="mt">Recent attempts</h4>
          <div className="chips">
            {history.map((h) => (
              <span key={h.id} className={"chip " + (h.rejected ? "ok-chip" : "bad-chip")}>
                {h.target} bit {h.bit} · {h.rejected ? "rejected" : "ACCEPTED"}
              </span>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

export default function SecurityTab() {
  return <div className="grid g2"><Inspector /><TamperLab /></div>;
}
