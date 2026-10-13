import pytest
from agile_hq_pqc.web.app import create_app


@pytest.fixture()
def env():
    app, sio, rt = create_app(autostart=False)
    rt.gateway.close(); rt.gateway = type(rt.gateway)(deterministic_probe=True, audit=rt.audit)
    c = app.test_client()
    def tok(u, p):
        return {"Authorization": "Bearer " + c.post("/api/login", json=dict(username=u, password=p)).get_json()["token"]}
    yield app, sio, rt, c, tok
    rt.gateway.close()


def test_login_and_unauthenticated(env):
    app, sio, rt, c, tok = env
    assert c.get("/").status_code == 200
    assert c.post("/api/login", json=dict(username="admin", password="nope")).status_code == 401
    assert c.get("/api/state").status_code == 401


def test_rbac_matrix(env):
    app, sio, rt, c, tok = env
    rt.gateway.step()
    adm, aud, res, op = (tok("admin", "admin@pqc"), tok("auditor", "audit@pqc"),
                         tok("researcher", "research@pqc"), tok("operator", "operator@pqc"))
    assert c.post("/api/stress", headers=adm, json=dict(preset="heavy")).status_code == 200
    for h in (aud, res, op):
        assert c.post("/api/stress", headers=h, json=dict(preset="heavy")).status_code == 403
    assert c.get("/api/trace", headers=adm).status_code == 200
    assert c.get("/api/trace", headers=aud).status_code == 403
    assert c.get("/api/audit", headers=aud).status_code == 200
    assert c.get("/api/audit", headers=op).status_code == 403
    assert c.get("/api/state", headers=res).status_code == 403
    assert c.post("/api/ingest", headers=op, json=dict(pid="p", vitals={})).status_code == 200
    assert c.post("/api/ingest", headers=res, json=dict(pid="p")).status_code == 403


def test_researcher_export_enforces_k5_l3_and_hides_raw(env):
    app, sio, rt, c, tok = env
    res = tok("researcher", "research@pqc")
    d = c.get("/api/export/deid", headers=res).get_json()
    assert d["k"] >= 5 and d["l"] >= 3 and d["verified"]
    assert all("patient_id" not in r for r in d["rows"])
    e = c.get("/api/privacy/ehr?k=2&l=2", headers=res).get_json()
    assert e["raw"] is None
    assert c.get("/api/privacy/ecg", headers=res).get_json()["raw_visible"] is False
    assert c.get("/api/export/deid?format=csv", headers=res).mimetype == "text/csv"


def test_socket_auth(env):
    app, sio, rt, c, tok = env
    from agile_hq_pqc.security import auth
    ok = sio.test_client(app, auth={"token": auth.authenticate("admin", "admin@pqc")})
    bad = sio.test_client(app, auth={"token": auth.authenticate("researcher", "research@pqc")})
    none = sio.test_client(app)
    assert ok.is_connected() and not bad.is_connected() and not none.is_connected()


def test_xss_safe_failed_login_logged_as_data(env):
    app, sio, rt, c, tok = env
    c.post("/api/login", json=dict(username="<script>alert(1)</script>", password="x"))
    a = c.get("/api/audit", headers=tok("auditor", "audit@pqc")).get_json()
    assert a["verify"]["ok"] and any("<script>" in e["actor"] for e in a["entries"])  # stored raw, escaped by UI


def test_react_frontend_only(env):
    app, sio, rt, c, tok = env
    r = c.get("/")
    assert r.status_code == 200 and b"<div id=\"root\">" in r.data
    assert c.get("/legacy").status_code == 404


def test_me_resumes_session_with_server_permissions(env):
    app, sio, rt, c, tok = env
    assert c.get("/api/me").status_code == 401
    d = c.get("/api/me", headers=tok("researcher", "research@pqc")).get_json()
    assert d["user"] == "researcher" and d["role"] == "researcher" and "monitor" not in d["permissions"]


def test_state_exposes_demo_phases(env):
    app, sio, rt, c, tok = env
    rt.gateway.step()
    d = c.get("/api/state", headers=tok("admin", "admin@pqc")).get_json()
    assert [p["preset"] for p in d["demo_phases"]][:2] == ["calm", "heavy"] and d["step_interval"] > 0


def test_privacy_slider_endpoints(env):
    app, sio, rt, c, tok = env
    res = tok("researcher", "research@pqc")
    lo = c.get("/api/privacy/ecg?eps=0.1", headers=res).get_json()
    hi = c.get("/api/privacy/ecg?eps=1.5", headers=res).get_json()
    assert len(lo["dp"]) == len(lo["t"]) and lo["snr_db"] < hi["snr_db"]   # smaller eps -> more noise
    assert c.get("/api/privacy/ecg?eps=abc", headers=res).status_code == 400
    t = c.get("/api/privacy/tradeoff?l=2", headers=res).get_json()
    assert {x["tier"] for x in t["tiers"]} == {1, 3, 5} and t["k_curve"][0]["k"] == 2
    assert t["eps_curve"][0]["snr_db"] < t["eps_curve"][-1]["snr_db"]
    assert c.get("/api/privacy/tradeoff", headers=tok("auditor", "audit@pqc")).status_code == 403


def test_results_endpoint_any_role(env):
    app, sio, rt, c, tok = env
    assert c.get("/api/results").status_code == 401
    d = c.get("/api/results", headers=tok("auditor", "audit@pqc")).get_json()
    assert {"summary", "tests", "sweep"} <= set(d)


def test_guided_demo_can_be_stopped(env):
    import time
    app, sio, rt, c, tok = env
    adm = tok("admin", "admin@pqc")
    assert c.post("/api/demo/stop", headers=tok("auditor", "audit@pqc")).status_code == 403
    assert c.post("/api/demo/start", headers=adm).get_json()["started"] is True
    assert c.post("/api/demo/start", headers=adm).get_json()["started"] is False   # no second run
    assert c.post("/api/demo/stop", headers=adm).get_json()["stopped"] is True
    t0 = time.time()
    while rt.demo["active"] and time.time() - t0 < 3:
        time.sleep(0.05)
    assert not rt.demo["active"] and not rt.gateway.stress.active()
