"""JWT authentication and role-based access control."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from functools import wraps

import jwt
from flask import g, jsonify, request

ROLES = ("admin", "auditor", "researcher", "operator")

# role -> permissions
PERMISSIONS = {
    "admin": {"monitor", "stress", "policy", "inspect", "tamper", "privacy_view",
              "privacy_raw", "audit_read", "export_deid"},
    "auditor": {"monitor", "audit_read", "inspect_meta"},
    "researcher": {"privacy_view", "export_deid"},
    "operator": {"monitor", "ingest", "exchange", "privacy_view", "privacy_raw"},
}


def _hash(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000).hex()


def _mk(pw: str) -> dict:
    salt = os.urandom(16)
    return {"salt": salt, "hash": _hash(pw, salt)}


# Demo accounts - override with env vars for any real use.
DEMO_USERS = {
    "admin": {"role": "admin", **_mk(os.environ.get("ADMIN_PW", "admin@pqc"))},
    "auditor": {"role": "auditor", **_mk(os.environ.get("AUDITOR_PW", "audit@pqc"))},
    "researcher": {"role": "researcher", **_mk(os.environ.get("RESEARCHER_PW", "research@pqc"))},
    "operator": {"role": "operator", **_mk(os.environ.get("OPERATOR_PW", "operator@pqc"))},
}

SECRET = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-me-" + "x" * 16)
TTL = 8 * 3600


def authenticate(username: str, password: str) -> str | None:
    u = DEMO_USERS.get(username)
    if not u or not hmac.compare_digest(_hash(password, u["salt"]), u["hash"]):
        return None
    now = int(time.time())
    return jwt.encode({"sub": username, "role": u["role"], "iat": now, "exp": now + TTL},
                      SECRET, algorithm="HS256")


def decode(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _token_from_request() -> str | None:
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        return h[7:]
    return request.args.get("token")


def require(permission: str | None):
    """Route guard. ``permission=None`` only requires a valid token (any role)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            claims = decode(_token_from_request() or "")
            if not claims:
                return jsonify(error="authentication required"), 401
            if permission is not None and permission not in PERMISSIONS.get(claims["role"], set()):
                return jsonify(error=f"role '{claims['role']}' lacks '{permission}'"), 403
            g.user, g.role = claims["sub"], claims["role"]
            return fn(*a, **kw)
        return wrapper
    return deco
