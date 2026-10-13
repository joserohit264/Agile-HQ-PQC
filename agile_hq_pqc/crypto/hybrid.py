"""Hybrid post-quantum primitives: X25519+ML-KEM key establishment and
Ed25519+ML-DSA dual signatures, with per-phase timing.

Uses the pure-Python reference implementations ``kyber-py`` (FIPS 203) and
``dilithium-py`` (FIPS 204). They are correct but slow and NOT constant-time:
fine for research/benchmarking, not for production deployment (swap in liboqs
via the same interface for that - see docs/ARCHITECTURE.md).
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidSignature
from dilithium_py.ml_dsa import ML_DSA_44, ML_DSA_65, ML_DSA_87
from kyber_py.ml_kem import ML_KEM_512, ML_KEM_768, ML_KEM_1024

from ..core.tiers import TIERS, Tier

KEM = {"ML-KEM-512": ML_KEM_512, "ML-KEM-768": ML_KEM_768, "ML-KEM-1024": ML_KEM_1024}
DSA = {"ML-DSA-44": ML_DSA_44, "ML-DSA-65": ML_DSA_65, "ML-DSA-87": ML_DSA_87}

_RAW = dict(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def _ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def hkdf(ikm: bytes, info: bytes, length: int = 32, salt: bytes | None = None) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def combine_secrets(ss_classical: bytes, ss_pq: bytes, transcript: bytes,
                    mode: str = "concat") -> bytes:
    """Bind the classical and PQ shared secrets into one master secret.

    ``concat`` (default): HKDF(ss_c || ss_pq, salt=H(transcript)) - the combiner
    recommended by current hybrid-KEM drafts (secure if either input is).
    ``xor``: HKDF(ss_c XOR ss_pq) as in the original project description
    (requires equal lengths; kept for comparison).
    """
    salt = hashlib.sha256(transcript).digest()
    if mode == "xor":
        ikm = bytes(a ^ b for a, b in zip(ss_classical, ss_pq))
    else:
        ikm = ss_classical + ss_pq
    return hkdf(ikm, b"agile-hq-pqc master v1", 32, salt)


@dataclass
class Identity:
    """Long-term signing identity of a gateway for one tier's DSA."""
    name: str
    tier: Tier
    ed_sk: Ed25519PrivateKey
    dsa_pk: bytes
    dsa_sk: bytes

    @property
    def ed_pk(self) -> bytes:
        return self.ed_sk.public_key().public_bytes(**_RAW)

    @classmethod
    def generate(cls, name: str, tier: Tier) -> "Identity":
        pk, sk = DSA[tier.dsa].keygen()
        return cls(name, tier, Ed25519PrivateKey.generate(), pk, sk)

    def sign(self, msg: bytes) -> tuple[bytes, bytes]:
        """Dual signature: (ed25519_sig, ml_dsa_sig)."""
        return self.ed_sk.sign(msg), DSA[self.tier.dsa].sign(self.dsa_sk, msg)


def verify_dual(ed_pk: bytes, dsa_pk: bytes, tier: Tier, msg: bytes,
                ed_sig: bytes, dsa_sig: bytes) -> bool:
    """Both signatures must verify (AND, not OR)."""
    try:
        Ed25519PublicKey.from_public_bytes(ed_pk).verify(ed_sig, msg)
    except InvalidSignature:
        return False
    return bool(DSA[tier.dsa].verify(dsa_pk, msg, dsa_sig))


@dataclass
class HandshakeResult:
    tier: int
    suite: str
    master_secret: bytes
    session_id: bytes
    timings_ms: dict
    bytes_on_wire: dict
    total_bytes: int
    ok: bool = True


def hybrid_handshake(tier: Tier, server_id: Identity, mode: str = "concat") -> HandshakeResult:
    """Run a full client<->server hybrid handshake in-process.

    Messages (sizes are computed from real serialized objects):
      C->S  ClientHello: x25519_pk || mlkem_ek
      S->C  ServerHello: x25519_pk || mlkem_ct || ed25519_sig || mldsa_sig
    The server signs the transcript with BOTH signature schemes; the client
    verifies both before accepting the key.
    """
    T: dict[str, float] = {}
    kem = KEM[tier.kem]

    # --- client: ephemeral keys
    t = time.perf_counter()
    c_x = X25519PrivateKey.generate()
    c_x_pk = c_x.public_key().public_bytes(**_RAW)
    ek, dk = kem.keygen()
    T["keygen"] = _ms(t)
    client_hello = c_x_pk + ek

    # --- server: encapsulate + sign
    t = time.perf_counter()
    s_x = X25519PrivateKey.generate()
    s_x_pk = s_x.public_key().public_bytes(**_RAW)
    ss_pq_s, ct = kem.encaps(ek)
    ss_c_s = s_x.exchange(X25519PublicKey.from_public_bytes(c_x_pk))
    T["encaps"] = _ms(t)

    transcript = client_hello + s_x_pk + ct + tier.suite.encode()
    t = time.perf_counter()
    master_s = combine_secrets(ss_c_s, ss_pq_s, transcript, mode)
    T["hkdf"] = _ms(t)

    t = time.perf_counter()
    ed_sig, dsa_sig = server_id.sign(transcript)
    T["sign"] = _ms(t)
    server_hello = s_x_pk + ct + ed_sig + dsa_sig

    # --- client: verify + decapsulate
    t = time.perf_counter()
    ok = verify_dual(server_id.ed_pk, server_id.dsa_pk, tier, transcript, ed_sig, dsa_sig)
    T["verify"] = _ms(t)
    if not ok:
        return HandshakeResult(tier.level, tier.suite, b"", b"", T, {}, 0, False)

    t = time.perf_counter()
    ss_pq_c = kem.decaps(dk, ct)
    ss_c_c = c_x.exchange(X25519PublicKey.from_public_bytes(s_x_pk))
    T["decaps"] = _ms(t)
    t = time.perf_counter()
    master_c = combine_secrets(ss_c_c, ss_pq_c, transcript, mode)
    T["hkdf"] += _ms(t)
    assert master_c == master_s, "hybrid KEM mismatch"

    T["total"] = sum(T.values())
    sizes = dict(client_hello=len(client_hello), server_hello=len(server_hello),
                 server_identity=len(server_id.ed_pk) + len(server_id.dsa_pk))
    return HandshakeResult(
        tier=tier.level, suite=tier.suite, master_secret=master_s,
        session_id=hashlib.sha256(transcript).digest()[:8], timings_ms=T,
        bytes_on_wire=sizes, total_bytes=sizes["client_hello"] + sizes["server_hello"],
    )
