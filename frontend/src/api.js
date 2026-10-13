/* Thin fetch wrapper around the Flask API. */
let token = null;
try { token = sessionStorage.getItem("pqc_token"); } catch { /* storage blocked */ }
let onUnauthorized = () => {};

export const getToken = () => token;
export function setToken(t) {
  token = t;
  try {
    if (t) sessionStorage.setItem("pqc_token", t);
    else sessionStorage.removeItem("pqc_token");
  } catch { /* storage blocked */ }
}
export function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

export async function api(path, { method = "GET", body } = {}) {
  const r = await fetch(path, {
    method,
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 401) { onUnauthorized(); throw new Error("session expired"); }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.error) || r.statusText);
  return data;
}

export async function login(username, password) {
  const r = await fetch("/api/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "login failed");
  setToken(d.token);
  return { user: d.user, role: d.role, permissions: d.permissions };
}

export const fmtMs = (ms) =>
  ms == null ? "—" : ms < 1 ? (ms * 1000).toFixed(0) + " µs" : ms.toFixed(ms < 10 ? 2 : 1) + " ms";
