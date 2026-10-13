import json
from agile_hq_pqc.security.audit import AuditLog
from agile_hq_pqc.security import auth


def test_audit_chain_ok_and_detects_tampering(tmp_path):
    a = AuditLog(tmp_path / "a.jsonl")
    for i in range(5): a.append("u", "act", {"i": i})
    assert a.verify()["ok"]
    a.entries[2]["detail"]["i"] = 99
    v = a.verify(); assert not v["ok"] and v["broken_at"] == 2


def test_audit_detects_deletion_and_persists(tmp_path):
    p = tmp_path / "a.jsonl"; a = AuditLog(p)
    for i in range(4): a.append("u", "act", {"i": i})
    assert AuditLog(p).verify()["ok"]                       # reload from disk
    del a.entries[1]
    assert not a.verify()["ok"]


def test_audit_detects_forged_entry_without_key(tmp_path):
    a = AuditLog(tmp_path / "x.jsonl"); a.append("u", "a"); a.append("u", "b")
    forged = AuditLog(key=b"wrong-key")
    forged.entries = json.loads(json.dumps(a.entries))
    assert not forged.verify()["ok"]


def test_jwt_roles():
    t = auth.authenticate("researcher", "research@pqc"); c = auth.decode(t)
    assert c["role"] == "researcher"
    assert auth.authenticate("researcher", "bad") is None
    assert auth.decode(t + "x") is None
    assert "export_deid" in auth.PERMISSIONS["researcher"] and "stress" not in auth.PERMISSIONS["researcher"]
    assert "privacy_raw" not in auth.PERMISSIONS["researcher"]
