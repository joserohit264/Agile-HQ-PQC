"""Tamper-evident audit log: SHA-256 hash chain + HMAC per entry."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path

GENESIS = "0" * 64


class AuditLog:
    def __init__(self, path: str | Path | None = None, key: bytes | None = None):
        self.key = key or os.environ.get("AUDIT_HMAC_KEY", "dev-audit-key-change-me").encode()
        self.path = Path(path) if path else None
        self.entries: list[dict] = []
        self._lock = threading.Lock()
        if self.path and self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    self.entries.append(json.loads(line))

    def _mac(self, body: dict) -> str:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(self.key, raw, hashlib.sha256).hexdigest()

    def append(self, actor: str, action: str, detail: dict | None = None) -> dict:
        with self._lock:
            prev = self.entries[-1]["hash"] if self.entries else GENESIS
            body = {"idx": len(self.entries), "ts": round(time.time(), 3), "actor": actor,
                    "action": action, "detail": detail or {}, "prev": prev}
            body["hash"] = hashlib.sha256(
                (prev + json.dumps(body, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()
            body["mac"] = self._mac({k: v for k, v in body.items() if k != "mac"})
            self.entries.append(body)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a") as f:
                    f.write(json.dumps(body) + "\n")
            return body

    def verify(self) -> dict:
        prev = GENESIS
        for i, e in enumerate(self.entries):
            core = {k: e[k] for k in ("idx", "ts", "actor", "action", "detail", "prev")}
            if e["prev"] != prev:
                return {"ok": False, "broken_at": i, "reason": "prev-hash mismatch"}
            h = hashlib.sha256((prev + json.dumps(core, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()
            if h != e["hash"]:
                return {"ok": False, "broken_at": i, "reason": "entry content altered"}
            if not hmac.compare_digest(self._mac({**core, "hash": e["hash"]}), e["mac"]):
                return {"ok": False, "broken_at": i, "reason": "HMAC invalid"}
            prev = e["hash"]
        return {"ok": True, "length": len(self.entries), "head": prev}

    def tail(self, n: int = 100) -> list[dict]:
        return self.entries[-n:]
