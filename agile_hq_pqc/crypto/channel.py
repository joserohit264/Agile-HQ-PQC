"""Authenticated, signed packet channel on top of a hybrid-handshake secret.

Per packet:  AEAD (AES-256-GCM or ChaCha20-Poly1305) + Ed25519 signature.
Per epoch (every ``epoch_len`` packets): ML-DSA signature over the hash chain
of all packets in the epoch. This amortises the heavy PQ signature while still
binding every packet to a post-quantum signature (batch-signature design).
"""
from __future__ import annotations

import base64
import hashlib
import os
import struct
import time
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305

from ..core.tiers import TIERS, Tier
from .hybrid import DSA, Identity, hkdf, _ms

HEADER = struct.Struct(">B8sQ")     # tier, session_id, seq  (17 bytes)


def derive_keys(master: bytes, aead: str) -> dict:
    # 68 bytes: enc_key (32) | mac_key (32) | iv_prefix (4). The IV prefix is sent in clear in every
    # packet, so it must be its own slice of the HKDF output and never overlap key material.
    okm = hkdf(master, b"agile-hq-pqc traffic keys " + aead.encode(), 68)
    return {"enc_key": okm[:32], "mac_key": okm[32:64], "iv_prefix": okm[64:68]}


def _aead(tier: Tier, key: bytes):
    return AESGCM(key) if tier.aead == "AES-256-GCM" else ChaCha20Poly1305(key)


@dataclass
class Packet:
    tier: int
    session_id: bytes
    seq: int
    iv: bytes
    ciphertext: bytes          # AEAD ciphertext WITHOUT the tag
    tag: bytes                 # 16-byte auth tag
    ed_sig: bytes
    epoch_sig: bytes = b""     # ML-DSA signature (only on epoch-closing packets)

    def header(self) -> bytes:
        return HEADER.pack(self.tier, self.session_id, self.seq)

    def to_wire(self) -> bytes:
        body = (self.header() + self.iv + struct.pack(">I", len(self.ciphertext))
                + self.ciphertext + self.tag + self.ed_sig
                + struct.pack(">H", len(self.epoch_sig)) + self.epoch_sig)
        return body

    def wire_token(self) -> str:
        return base64.urlsafe_b64encode(self.to_wire()).decode()

    @classmethod
    def from_wire(cls, data: bytes) -> "Packet":
        o = 0
        tier, sid, seq = HEADER.unpack_from(data, o); o += HEADER.size
        iv = data[o:o + 12]; o += 12
        (n,) = struct.unpack_from(">I", data, o); o += 4
        ct = data[o:o + n]; o += n
        tag = data[o:o + 16]; o += 16
        ed = data[o:o + 64]; o += 64
        (m,) = struct.unpack_from(">H", data, o); o += 2
        es = data[o:o + m]
        return cls(tier, sid, seq, iv, ct, tag, ed, es)

    @classmethod
    def from_token(cls, token: str) -> "Packet":
        return cls.from_wire(base64.urlsafe_b64decode(token.encode()))

    def wire_size(self) -> int:
        return len(self.to_wire())


class SecureSender:
    def __init__(self, tier: Tier, master: bytes, session_id: bytes,
                 identity: Identity, epoch_len: int = 8):
        self.tier, self.session_id, self.identity = tier, session_id, identity
        self.keys = derive_keys(master, tier.aead)
        self._aead = _aead(tier, self.keys["enc_key"])
        self.seq = 0
        self.epoch_len = epoch_len
        self._chain = hashlib.sha256(b"epoch").digest()

    def send(self, plaintext: bytes, aad: bytes = b"") -> tuple[Packet, dict]:
        T = {}
        self.seq += 1
        iv = self.keys["iv_prefix"] + struct.pack(">Q", self.seq)
        header = HEADER.pack(self.tier.level, self.session_id, self.seq)
        t = time.perf_counter()
        sealed = self._aead.encrypt(iv, plaintext, header + aad)
        ct, tag = sealed[:-16], sealed[-16:]
        T["encrypt"] = _ms(t)

        t = time.perf_counter()
        ed_sig = self.identity.ed_sk.sign(header + iv + sealed)
        T["sign_ed"] = _ms(t)

        self._chain = hashlib.sha256(self._chain + header + iv + sealed + ed_sig).digest()
        epoch_sig = b""
        T["sign_pq"] = 0.0
        if self.seq % self.epoch_len == 0:
            t = time.perf_counter()
            epoch_sig = DSA[self.tier.dsa].sign(self.identity.dsa_sk, self._chain)
            T["sign_pq"] = _ms(t)
        pkt = Packet(self.tier.level, self.session_id, self.seq, iv, ct, tag, ed_sig, epoch_sig)
        return pkt, T


class ReceiveError(Exception):
    pass


class SecureReceiver:
    def __init__(self, tier: Tier, master: bytes, session_id: bytes,
                 ed_pk: bytes, dsa_pk: bytes, epoch_len: int = 8):
        self.tier, self.session_id = tier, session_id
        self.keys = derive_keys(master, tier.aead)
        self._aead = _aead(tier, self.keys["enc_key"])
        self.ed_pk, self.dsa_pk = ed_pk, dsa_pk
        self.epoch_len = epoch_len
        self.expected_seq = 1
        self._chain = hashlib.sha256(b"epoch").digest()

    def check_layers(self, pkt: Packet, aad: bytes = b"") -> dict:
        """Evaluate each defence layer independently (for the tamper lab)."""
        sealed = pkt.ciphertext + pkt.tag
        try:
            Ed25519PublicKey.from_public_bytes(self.ed_pk).verify(
                pkt.ed_sig, pkt.header() + pkt.iv + sealed)
            sig_ok = True
        except Exception:
            sig_ok = False
        try:
            self._aead.decrypt(pkt.iv, sealed, pkt.header() + aad)
            aead_ok = True
        except Exception:
            aead_ok = False
        return dict(ed25519_signature=sig_ok, aead_tag=aead_ok,
                    sequence=pkt.seq == self.expected_seq)

    def receive(self, pkt: Packet, aad: bytes = b"") -> tuple[bytes, dict]:
        T = {}
        if pkt.session_id != self.session_id or pkt.tier != self.tier.level:
            raise ReceiveError("wrong session/tier")
        if pkt.seq != self.expected_seq:
            raise ReceiveError(f"replay/out-of-order seq {pkt.seq} (expected {self.expected_seq})")
        header = pkt.header()
        sealed = pkt.ciphertext + pkt.tag

        t = time.perf_counter()
        try:
            Ed25519PublicKey.from_public_bytes(self.ed_pk).verify(
                pkt.ed_sig, header + pkt.iv + sealed)
        except InvalidSignature:
            raise ReceiveError("Ed25519 signature invalid")
        T["verify_ed"] = _ms(t)

        t = time.perf_counter()
        try:
            plaintext = self._aead.decrypt(pkt.iv, sealed, header + aad)
        except InvalidTag:
            raise ReceiveError("AEAD authentication failed (tampered ciphertext/tag)")
        T["decrypt"] = _ms(t)

        chain = hashlib.sha256(self._chain + header + pkt.iv + sealed + pkt.ed_sig).digest()
        T["verify_pq"] = 0.0
        if pkt.seq % self.epoch_len == 0:
            t = time.perf_counter()
            if not pkt.epoch_sig or not DSA[self.tier.dsa].verify(self.dsa_pk, chain, pkt.epoch_sig):
                raise ReceiveError("ML-DSA epoch signature invalid")
            T["verify_pq"] = _ms(t)
        self._chain = chain
        self.expected_seq += 1
        return plaintext, T
