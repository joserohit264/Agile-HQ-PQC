"""Inter-hospital IoMT gateway: wires probe -> CADA-AASM -> hybrid PQC channel
-> privacy engines, and produces one rich event per control cycle.

Two traffic domains run side by side:
  clinical  raw PHI telemetry, tier floored at MIN_SECURITY_TIER (HIPAA invariant)
  research  de-identified secondary-use stream, full agility (Tier 5 .. Tier 1)
              with DP epsilon and (K, L) scaled by the active tier.

Sessions are re-keyed *make-before-break*: the new hybrid handshake runs on
the control path while data keeps flowing on the old session, so handshake
compute is not charged to the data-path latency (its wire bytes are).
"""
from __future__ import annotations

import copy
import json
import math
import random
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from .core.cada import CadaController
from .core.probe import Prober, StressInjector, STRESS_PRESETS
from .core.tiers import TIERS, SLA_MS, MIN_SECURITY_TIER, Tier
from .crypto.channel import Packet, ReceiveError, SecureReceiver, SecureSender
from .crypto.hybrid import Identity, hybrid_handshake
from .privacy.data import synthetic_ecg, synthetic_ehr, vitals_sample
from .privacy.dp import PrivacyAccountant, laplace_mechanism
from .privacy.mondrian import mondrian_anonymize
from .security.audit import AuditLog

MTU_PAYLOAD = 1400
ECG_CHUNK = 25          # samples per packet (0.1 s @ 250 Hz)


class NetworkModel:
    """Delivery-and-acknowledge latency model for a packet of ``wire_bytes``.

    latency = RTT + serialisation + per-fragment congestion queueing
              + expected loss-recovery (one RTO if any fragment is lost).
    Bigger PQ payloads => more fragments => more exposure to loss/queueing.
    """

    @staticmethod
    def delay(wire_bytes: int, rtt_ms: float, stress: StressInjector, rng: random.Random,
              extra_bytes: int = 0) -> dict:
        frags = max(1, math.ceil(wire_bytes / MTU_PAYLOAD))
        bw_mbps = stress.bw_mbps or 100.0
        ser = (wire_bytes + extra_bytes) * 8 / (bw_mbps * 1e6) * 1000.0
        frag_q = 0.05 + (stress.rtt_ms / 100.0) * 0.8        # ms per extra fragment
        frag_ms = (frags - 1) * frag_q
        p = stress.loss_pct / 100.0
        retx = 0.0
        if p > 0 and rng.random() < 1 - (1 - p) ** frags:
            retx = rtt_ms + 10.0 + MTU_PAYLOAD * 8 / (bw_mbps * 1e6) * 1000.0
        return dict(fragments=frags, serialization_ms=ser, frag_queue_ms=frag_ms,
                    retransmit_ms=retx, network_ms=rtt_ms + ser + frag_ms + retx)


@dataclass
class Session:
    domain: str
    tier: Tier
    tx: SecureSender
    rx: SecureReceiver
    handshake: dict
    master: bytes


class HealthGateway:
    def __init__(self, adaptive: bool = True, static_tier: int = 5, seed: int = 42,
                 audit: AuditLog | None = None, min_clinical_tier: int = MIN_SECURITY_TIER,
                 epoch_len: int = 8, anon_every: int = 5,
                 deterministic_probe: bool = False, smoothing_alpha: float = 1.0):
        self.rng = random.Random(seed)
        self.nrng = np.random.default_rng(seed)
        self.stress = StressInjector()
        self.prober = Prober(self.stress, deterministic=deterministic_probe)
        self.controller = CadaController(enabled=adaptive, initial_tier=static_tier,
                                         min_clinical_tier=min_clinical_tier,
                                         smoothing_alpha=smoothing_alpha)
        self.adaptive = adaptive
        self.audit = audit or AuditLog()
        self.epoch_len = epoch_len
        self.anon_every = anon_every
        self.lock = threading.RLock()
        self.identities = {lv: Identity.generate(f"gw-{lv}", t) for lv, t in TIERS.items()}
        self.sessions: dict[str, Session] = {}
        self.accountant = PrivacyAccountant(total_epsilon=1e6)
        _, self._ecg = synthetic_ecg(seconds=60, seed=seed)
        self._ecg_pos = 0
        self._ehr_pool = synthetic_ehr(400, seed=seed)
        self.ehr_last_anon: dict | None = None
        self.step_no = 0
        self.history: deque = deque(maxlen=600)
        self.last_trace: dict | None = None
        self._rx_snapshot: SecureReceiver | None = None
        self._last_clinical_pkt: Packet | None = None
        self._pending_handshake_bytes = {"clinical": 0, "research": 0}
        self.counters = dict(packets=0, sla_violations_clinical=0, sla_violations_research=0,
                             handshakes=0, tier_changes=0, tamper_rejected=0, tamper_total=0)
        self.dwell = {1: 0, 3: 0, 5: 0}

    # ------------------------------------------------------------------ sessions
    def _new_session(self, domain: str, level: int) -> Session:
        tier = TIERS[level]
        ident = self.identities[level]
        hs = hybrid_handshake(tier, ident)
        assert hs.ok
        tx = SecureSender(tier, hs.master_secret, hs.session_id, ident, self.epoch_len)
        rx = SecureReceiver(tier, hs.master_secret, hs.session_id, ident.ed_pk,
                            ident.dsa_pk, self.epoch_len)
        sess = Session(domain, tier, tx, rx, dict(
            tier=level, suite=tier.suite, timings_ms=hs.timings_ms,
            bytes=hs.bytes_on_wire, total_bytes=hs.total_bytes,
            session_id=hs.session_id.hex()), hs.master_secret)
        self.counters["handshakes"] += 1
        self._pending_handshake_bytes[domain] += hs.total_bytes
        self.audit.append("gateway", "handshake", dict(
            domain=domain, tier=level, suite=tier.suite, ms=round(hs.timings_ms["total"], 1),
            bytes=hs.total_bytes, session=hs.session_id.hex()))
        return sess

    def _ensure_session(self, domain: str, level: int) -> tuple[Session, bool]:
        cur = self.sessions.get(domain)
        if cur is None or cur.tier.level != level:
            self.sessions[domain] = self._new_session(domain, level)
            return self.sessions[domain], True
        return cur, False

    # ------------------------------------------------------------------- stress
    def set_stress(self, preset: str | dict):
        with self.lock:
            cfg = STRESS_PRESETS[preset] if isinstance(preset, str) else preset
            self.stress.set(**cfg)
            self.audit.append("system", "stress_set",
                              dict(preset=preset if isinstance(preset, str) else "custom", **cfg))

    # --------------------------------------------------------------- telemetry
    def _next_ecg(self) -> np.ndarray:
        n = len(self._ecg)
        idx = (np.arange(ECG_CHUNK) + self._ecg_pos) % n
        self._ecg_pos = (self._ecg_pos + ECG_CHUNK) % n
        return self._ecg[idx]

    def _send(self, sess: Session, payload: bytes, domain: str) -> dict:
        slow = 1.0 / max(0.1, 1.0 - 0.9 * self.stress.cpu_pct / 100.0)   # CPU contention
        pkt, tx = sess.tx.send(payload, aad=domain.encode())
        snapshot = copy.copy(sess.rx)
        plain, rxt = sess.rx.receive(pkt, aad=domain.encode())
        assert plain == payload
        crypto_ms = (tx["encrypt"] + tx["sign_ed"] + rxt["verify_ed"] + rxt["decrypt"]) * slow
        return dict(pkt=pkt, tx=tx, rx=rxt, crypto_ms=crypto_ms, snapshot=snapshot, slow=slow)

    # -------------------------------------------------------------------- step
    def step(self) -> dict:
        with self.lock:
            self.step_no += 1
            t_step = time.perf_counter()
            probe = self.prober.probe(self.rng)
            dec = self.controller.decide(probe["rtt_ms"], probe["cpu_pct"])
            if dec.changed:
                self.counters["tier_changes"] += 1
                self.audit.append("cada", "tier_change", dict(
                    to=dec.active_tier, budget=dec.budget_ms, rtt=dec.rtt_ms, cpu=dec.cpu_pct,
                    clinical_tier=dec.clinical_tier, floor_clamped=dec.floor_clamped))

            clin_sess, clin_rekey = self._ensure_session("clinical", dec.clinical_tier)
            res_sess, res_rekey = self._ensure_session("research", dec.active_tier)

            # --- payloads
            ecg = self._next_ecg()
            vit = vitals_sample(self.nrng)
            raw = dict(pid="P00042", ts=round(time.time(), 3), vitals=vit,
                       ecg_mv=[round(float(x), 4) for x in ecg])
            raw_bytes = json.dumps(raw, separators=(",", ":")).encode()

            tier_a = TIERS[dec.active_tier]
            dp = laplace_mechanism(ecg, tier_a.epsilon, sensitivity=0.5, rng=self.nrng)
            self.accountant.charge(tier_a.epsilon)
            dp_vit = {k: (round(float(v) + self.nrng.laplace(0, 0.5 / tier_a.epsilon), 1))
                      for k, v in vit.items()}
            deid = dict(subject="anon", ts=raw["ts"], vitals=dp_vit,
                        ecg_mv=[round(float(x), 4) for x in dp.noisy], epsilon=tier_a.epsilon)
            deid_bytes = json.dumps(deid, separators=(",", ":")).encode()

            # --- transmit
            out = {}
            for dom, sess, pay in (("clinical", clin_sess, raw_bytes), ("research", res_sess, deid_bytes)):
                s = self._send(sess, pay, dom)
                extra = self._pending_handshake_bytes[dom]
                self._pending_handshake_bytes[dom] = 0
                net = NetworkModel.delay(s["pkt"].wire_size(), probe["rtt_ms"], self.stress,
                                         self.rng, extra_bytes=extra)
                latency = net["network_ms"] + s["crypto_ms"]
                viol = latency > SLA_MS
                self.counters[f"sla_violations_{dom}"] += int(viol)
                out[dom] = dict(
                    tier=sess.tier.level, suite=sess.tier.suite, wire_bytes=s["pkt"].wire_size(),
                    payload_bytes=len(pay), crypto_ms=round(s["crypto_ms"], 3),
                    pq_sign_async_ms=round(s["tx"]["sign_pq"], 2),
                    pq_verify_async_ms=round(s["rx"]["verify_pq"], 2),
                    latency_ms=round(latency, 2), sla_violation=viol,
                    epoch_packet=bool(s["pkt"].epoch_sig), **{k: round(v, 3) if isinstance(v, float) else v
                                                              for k, v in net.items()},
                    micro=dict(encrypt=round(s["tx"]["encrypt"], 4), decrypt=round(s["rx"]["decrypt"], 4),
                               sign_ed=round(s["tx"]["sign_ed"], 4), verify_ed=round(s["rx"]["verify_ed"], 4)))
                if dom == "clinical":
                    self._last_clinical_pkt = s["pkt"]
                    self._rx_snapshot = s["snapshot"]
                    keys = sess.tx.keys
                    self.last_trace = dict(
                        tier=sess.tier.level, suite=sess.tier.suite,
                        stage1_master_secret=sess.master.hex(),
                        stage2_enc_key=keys["enc_key"].hex(), stage2_mac_key=keys["mac_key"].hex(),
                        stage3_plaintext=raw_bytes.decode()[:400] + ("..." if len(raw_bytes) > 400 else ""),
                        stage4_iv=s["pkt"].iv.hex(), stage4_ciphertext=s["pkt"].ciphertext.hex()[:240],
                        stage4_tag=s["pkt"].tag.hex(), stage4_ed25519_sig=s["pkt"].ed_sig.hex(),
                        stage5_wire_token=s["pkt"].wire_token(), seq=s["pkt"].seq,
                        wire_bytes=s["pkt"].wire_size())

            # --- tabular path: periodic Mondrian (K, L) on a rolling EHR window
            if self.step_no % self.anon_every == 1:
                t = time.perf_counter()
                win = self._ehr_pool[: 150]
                an = mondrian_anonymize(win, tier_a.k, tier_a.l)
                ms = (time.perf_counter() - t) * 1000
                self.ehr_last_anon = dict(k=tier_a.k, l=tier_a.l, classes=an.classes,
                                          info_loss=round(an.info_loss, 4), ms=round(ms, 2),
                                          satisfied=an.satisfied, avg_class=round(an.avg_class_size, 1))

            self.counters["packets"] += 1
            self.dwell[dec.active_tier] += 1
            ev = dict(
                step=self.step_no, ts=round(time.time(), 3), probe=probe,
                decision=dec.to_dict(), budget_ms=dec.budget_ms,
                active_tier=dec.active_tier, clinical_tier=dec.clinical_tier,
                tier_info=tier_a.to_dict(), clinical=out["clinical"], research=out["research"],
                rekey=dict(clinical=clin_rekey, research=res_rekey),
                handshake=(res_sess.handshake if res_rekey else (clin_sess.handshake if clin_rekey else None)),
                privacy=dict(epsilon=tier_a.epsilon, k=tier_a.k, l=tier_a.l,
                             dp_snr_db=round(dp.snr_db, 2), dp_scale=round(dp.scale, 3),
                             ehr=self.ehr_last_anon, eps_spent=round(self.accountant.spent, 2)),
                stress=self.stress.to_dict(), adaptive=self.adaptive,
                counters=dict(self.counters), dwell=dict(self.dwell),
                step_ms=round((time.perf_counter() - t_step) * 1000, 1))
            self.history.append(ev)
            return ev

    # ---------------------------------------------------------- operator ingest
    def ingest(self, record: dict) -> dict:
        """Send an operator-supplied telemetry record over the clinical session."""
        with self.lock:
            level = self.controller.clinical_tier_for(self.controller.active_tier)
            sess, _ = self._ensure_session("clinical", level)
            payload = json.dumps(record, separators=(",", ":")).encode()
            if len(payload) > 16384:
                raise ValueError("record too large (max 16 KiB)")
            s = self._send(sess, payload, "clinical")
            last = self.history[-1]["probe"]["rtt_ms"] if self.history else 0.0
            net = NetworkModel.delay(s["pkt"].wire_size(), last, self.stress, self.rng)
            latency = net["network_ms"] + s["crypto_ms"]
            self.audit.append("operator", "ingest", dict(
                bytes=len(payload), tier=sess.tier.level, latency_ms=round(latency, 2)))
            return dict(delivered=True, tier=sess.tier.level, suite=sess.tier.suite,
                        wire_bytes=s["pkt"].wire_size(), latency_ms=round(latency, 2),
                        sla_violation=latency > SLA_MS, seq=s["pkt"].seq)

    # ------------------------------------------------------------- tamper lab
    def tamper(self, target: str = "ciphertext", bit: int = 0) -> dict:
        """Flip one bit of the last clinical packet and try to deliver it."""
        with self.lock:
            if self._last_clinical_pkt is None or self._rx_snapshot is None:
                return dict(error="no packet yet - run at least one step")
            pkt = copy.deepcopy(self._last_clinical_pkt)

            def flip(b: bytes) -> bytes:
                ba = bytearray(b)
                ba[(bit // 8) % len(ba)] ^= 1 << (bit % 8)
                return bytes(ba)

            if target == "ciphertext":
                pkt.ciphertext = flip(pkt.ciphertext)
            elif target == "tag":
                pkt.tag = flip(pkt.tag)
            elif target == "signature":
                pkt.ed_sig = flip(pkt.ed_sig)
            elif target == "iv":
                pkt.iv = flip(pkt.iv)
            elif target == "header":
                pkt.seq ^= 1 << (bit % 8)
            else:
                return dict(error="unknown target")
            self.counters["tamper_total"] += 1
            rx = copy.copy(self._rx_snapshot)
            try:
                rx.receive(pkt, aad=b"clinical")
                accepted, err = True, None
            except ReceiveError as e:
                accepted, err = False, str(e)
            except Exception as e:  # malformed
                accepted, err = False, f"{type(e).__name__}: {e}"
            layers = copy.copy(self._rx_snapshot).check_layers(pkt, aad=b"clinical")
            if not accepted:
                self.counters["tamper_rejected"] += 1
            self.audit.append("admin", "tamper_test", dict(target=target, bit=bit,
                                                           accepted=accepted, error=err))
            # control: untampered packet verifies
            ctrl = copy.copy(self._rx_snapshot)
            try:
                ctrl.receive(self._last_clinical_pkt, aad=b"clinical"); control_ok = True
            except Exception:
                control_ok = False
            return dict(target=target, bit=bit, accepted=accepted, rejected=not accepted,
                        error=err, layers=layers, control_untampered_ok=control_ok)

    def close(self):
        self.prober.close()
