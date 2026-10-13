/* Shared UI primitives + chart tokens read from CSS custom properties (so charts follow the theme). */
import React, { useEffect, useState } from "react";

export const LEVEL = { 5: "High", 3: "Medium", 1: "Low" };

export function Card({ title, sub, actions, className = "", children }) {
  return (
    <section className={"card " + className}>
      {(title || actions) && (
        <div className="card-h">
          {title && <h3>{title}</h3>}
          {sub && <span className="muted small">{sub}</span>}
          {actions && <><span className="spacer" />{actions}</>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, detail, bad }) {
  return (
    <div className={"card stat" + (bad ? " bad" : "")}>
      <div className="muted small">{label}</div>
      <div className="stat-v mono">{value}</div>
      {detail && <div className="small soft">{detail}</div>}
    </div>
  );
}

export function Tier({ t, lg, children }) {
  return <span className={"tier t" + t + (lg ? " lg" : "")}>{children || `Tier ${t} · ${LEVEL[t]}`}</span>;
}

export function Table({ rows, cols }) {
  if (!rows || !rows.length) return <p className="muted small">Restricted for your role.</p>;
  return (
    <div className="tbl-wrap">
      <table>
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c}>{String(r[c] ?? "")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export function TooltipBox({ title, rows }) {
  return (
    <div className="tip">
      <div className="tip-h">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="tip-r">
          {r.color && <span className="sw" style={{ background: r.color }} />}
          <span className="muted">{r.label}</span><b className="mono">{r.value}</b>
        </div>
      ))}
    </div>
  );
}

export const TIER_COLOR = (tok, t) => ({ 5: tok.t5, 3: tok.t3, 1: tok.t1 }[t] || tok.muted);

// chart token key -> CSS custom property (see the palette at the top of styles.css)
const NAMES = { text: "text", text2: "text-2", muted: "muted", line: "line", grid: "grid", surface: "surface",
  accent: "accent", s1: "series-1", s2: "series-2", critical: "critical", t5: "t5", t3: "t3", t1: "t1" };

function readTokens() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue("--" + n).trim();
  const tok = Object.fromEntries(Object.entries(NAMES).map(([k, n]) => [k, v(n)]));
  tok.seq = [0, 1, 2, 3, 4, 5].map((i) => v("seq-" + i));
  tok.fs = document.documentElement.classList.contains("presenter") ? 14 : 12;
  tok.lw = 2;
  return tok;
}

/** Chart colours from the active theme; re-reads when the theme or presenter mode changes. */
export function useTokens() {
  const [tok, setTok] = useState(readTokens);
  useEffect(() => {
    const refresh = () => setTok(readTokens());
    const mo = new MutationObserver(refresh);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", refresh);
    return () => { mo.disconnect(); mq.removeEventListener("change", refresh); };
  }, []);
  return tok;
}
