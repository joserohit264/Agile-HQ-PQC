"""Tier security suite, part 2: hybrid handshake and secure-channel attack tests.

Everything here runs once per tier (Tier 1, 3 and 5) against the real project code:
agile_hq_pqc.crypto.hybrid and agile_hq_pqc.crypto.channel.

Attack classes covered (adversary = active network attacker, plus a harvest-now-decrypt-later
recorder):  bit flips, truncation, replay, reordering, dropping, cross-tier injection,
cross-session splicing, header rewriting, epoch-signature stripping / transplanting,
downgrade of the signed suite, ML-KEM ciphertext tampering, nonce/key hygiene, parser fuzzing,
and cross-implementation interoperability against liboqs (an independent C implementation; opt-in,
set RUN_LIBOQS_TESTS=1).

Run:   python -m pytest tests/test_tier_channel_security.py -v
"""
import copy
import struct
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agile_hq_pqc.core.tiers import TIERS  # noqa: E402
from agile_hq_pqc.crypto.channel import (  # noqa: E402
    HEADER, Packet, ReceiveError, SecureReceiver, SecureSender, derive_keys)
from agile_hq_pqc.crypto.hybrid import (  # noqa: E402
    DSA, KEM, Identity, combine_secrets, hybrid_handshake, verify_dual)

TIER_LEVELS = [1, 3, 5]
EPOCH = 4
AAD = b"clinical"


# ------------------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module", params=TIER_LEVELS, ids=lambda lv: f"tier{lv}")
def tier_ctx(request):
    t = TIERS[request.param]
    ident = Identity.generate("srv", t)
    hs = hybrid_handshake(t, ident)
    assert hs.ok
    return t, ident, hs


def make_pair(ctx, epoch=EPOCH):
    t, ident, hs = ctx
    tx = SecureSender(t, hs.master_secret, hs.session_id, ident, epoch)
    rx = SecureReceiver(t, hs.master_secret, hs.session_id, ident.ed_pk, ident.dsa_pk, epoch)
    return tx, rx


def accepts(rx, pkt, aad=AAD):
    """True only if the receiver returns plaintext. Any exception counts as a rejection."""
    try:
        rx.receive(pkt, aad)
        return True
    except Exception:
        return False


def same_content(a: Packet, b: Packet) -> bool:
    """True if two packets carry identical authenticated content. The wire format has two
    unauthenticated length fields (ciphertext length, epoch-signature length); a flip there that
    parses back to the *same* fields is wire-format malleability, not a forgery."""
    return (a.tier, a.session_id, a.seq, a.iv, a.ciphertext, a.tag, a.ed_sig, a.epoch_sig) == \
           (b.tier, b.session_id, b.seq, b.iv, b.ciphertext, b.tag, b.ed_sig, b.epoch_sig)


def flip_bit(b: bytes, pos: int, bit: int = 0) -> bytes:
    ba = bytearray(b)
    ba[pos] ^= 1 << bit
    return bytes(ba)


# ======================================================================================
# 1. Hybrid handshake
# ======================================================================================
class TestHybridHandshake:
    def test_two_handshakes_give_independent_secrets_and_session_ids(self, tier_ctx):
        t, ident, _ = tier_ctx
        a, b = hybrid_handshake(t, ident), hybrid_handshake(t, ident)
        assert a.master_secret != b.master_secret          # ephemeral keys: no key reuse
        assert a.session_id != b.session_id

    def test_master_secret_does_not_depend_on_the_long_term_identity(self, tier_ctx):
        """Forward secrecy: leaking the long-term signing key must not reveal past session keys."""
        t, ident, hs = tier_ctx
        other = Identity.generate("other", t)
        # nothing in the derivation takes the identity as input: a handshake under a different
        # identity is just another independent random secret
        assert hybrid_handshake(t, other).master_secret != hs.master_secret
        assert len(hs.master_secret) == 32

    def test_signed_transcript_binds_suite_and_all_handshake_values(self, tier_ctx):
        """Downgrade resistance: the transcript signed by the server contains the negotiated suite
        string, the client's X25519 + ML-KEM keys, and the server's X25519 key + ML-KEM ciphertext."""
        t, ident, _ = tier_ctx
        seen = {}

        class Spy:
            ed_pk, dsa_pk = ident.ed_pk, ident.dsa_pk

            def sign(self, msg):
                seen["msg"] = msg
                return ident.sign(msg)

        assert hybrid_handshake(t, Spy()).ok
        msg = seen["msg"]
        assert msg.endswith(t.suite.encode())
        assert len(msg) == 32 + t.kem_pk_bytes + 32 + t.kem_ct_bytes + len(t.suite.encode())

    def test_suite_downgrade_invalidates_the_server_signature(self, tier_ctx):
        t, ident, _ = tier_ctx
        transcript = b"hello" + t.suite.encode()
        ed, ml = ident.sign(transcript)
        assert verify_dual(ident.ed_pk, ident.dsa_pk, t, transcript, ed, ml)
        for other in TIERS.values():
            if other.level != t.level:
                forged = b"hello" + other.suite.encode()           # attacker swaps in a weaker suite
                assert not verify_dual(ident.ed_pk, ident.dsa_pk, t, forged, ed, ml)

    def test_dual_signature_is_AND_not_OR(self, tier_ctx):
        t, ident, _ = tier_ctx
        msg = b"transcript"
        ed, ml = ident.sign(msg)
        bad_ed = flip_bit(ed, 3)
        bad_ml = flip_bit(ml, 7)
        assert verify_dual(ident.ed_pk, ident.dsa_pk, t, msg, ed, ml)
        assert not verify_dual(ident.ed_pk, ident.dsa_pk, t, msg, bad_ed, ml)     # classical broken
        assert not verify_dual(ident.ed_pk, ident.dsa_pk, t, msg, ed, bad_ml)     # post-quantum broken

    def test_signature_from_another_tier_is_not_accepted(self, tier_ctx):
        t, ident, _ = tier_ctx
        other_t = TIERS[3] if t.level != 3 else TIERS[5]
        other = Identity.generate("o", other_t)
        msg = b"cross tier"
        ed, ml = other.sign(msg)
        try:
            ok = verify_dual(ident.ed_pk, ident.dsa_pk, t, msg, ed, ml)
        except Exception:
            ok = False
        assert not ok

    def test_modified_kem_ciphertext_yields_a_different_key_and_is_detected(self, tier_ctx):
        """FIPS 203 implicit rejection: a tampered ML-KEM ciphertext does not raise, it silently yields
        an unrelated key, so the first AEAD record from the peer fails authentication."""
        t, ident, _ = tier_ctx
        kem = KEM[t.kem]
        ek, dk = kem.keygen()
        ss_server, ct = kem.encaps(ek)
        ss_client_bad = kem.decaps(dk, flip_bit(ct, 5))
        assert ss_client_bad != ss_server and len(ss_client_bad) == 32
        master_s = combine_secrets(b"X" * 32, ss_server, b"transcript")
        master_c = combine_secrets(b"X" * 32, ss_client_bad, b"transcript")
        assert master_s != master_c
        sid = b"\x00" * 8
        tx = SecureSender(t, master_s, sid, ident, EPOCH)
        rx = SecureReceiver(t, master_c, sid, ident.ed_pk, ident.dsa_pk, EPOCH)
        pkt, _ = tx.send(b"first record", AAD)
        assert not accepts(rx, pkt)

    def test_default_combiner_is_not_the_xor_construction(self):
        """XOR of two equal secrets is all-zero, which would make the master secret constant.
        The default (concatenation) combiner must not have that failure mode."""
        a = combine_secrets(b"A" * 32, b"A" * 32, b"t")
        b = combine_secrets(b"B" * 32, b"B" * 32, b"t")
        assert a != b
        assert combine_secrets(b"A" * 32, b"A" * 32, b"t", mode="xor") == \
            combine_secrets(b"B" * 32, b"B" * 32, b"t", mode="xor")      # documents why xor is not default

    def test_combiner_binds_the_transcript(self):
        assert combine_secrets(b"A" * 32, b"B" * 32, b"t1") != combine_secrets(b"A" * 32, b"B" * 32, b"t2")


# ======================================================================================
# 2. Packet-level attacks on the secure channel
# ======================================================================================
class TestChannelAttacks:
    def test_normal_traffic_across_epochs_is_accepted(self, tier_ctx):
        tx, rx = make_pair(tier_ctx)
        for i in range(1, 2 * EPOCH + 2):
            pkt, _ = tx.send(b"vitals-%d" % i, AAD)
            assert bool(pkt.epoch_sig) == (i % EPOCH == 0)
            assert rx.receive(Packet.from_wire(pkt.to_wire()), AAD)[0] == b"vitals-%d" % i

    def test_every_single_bit_flip_in_every_byte_of_a_packet_is_rejected(self, tier_ctx):
        """Flip bit 0 and bit 7 of every byte of an ordinary packet's wire encoding."""
        tx, rx = make_pair(tier_ctx)
        pkt, _ = tx.send(b"secret clinical record", AAD)
        wire = pkt.to_wire()
        for pos in range(len(wire)):
            for bit in (0, 7):
                try:
                    forged = Packet.from_wire(flip_bit(wire, pos, bit))
                except Exception:
                    continue                                    # unparsable = rejected
                if same_content(forged, pkt):
                    continue                                    # harmless length-field malleability
                assert not accepts(rx, forged), f"bit flip accepted at byte {pos} bit {bit}"
        assert accepts(rx, pkt)                                 # control: untouched packet still verifies

    def test_bit_flips_in_the_epoch_signature_are_rejected(self, tier_ctx):
        t, _, _ = tier_ctx
        tx, rx = make_pair(tier_ctx, epoch=1)                   # every packet closes an epoch
        pkt, _ = tx.send(b"x", AAD)
        n = len(pkt.epoch_sig)
        assert n == t.dsa_sig_bytes
        for pos in sorted({0, 1, 31, 32, n // 3, n // 2, n - 33, n - 2, n - 1}):
            forged = copy.deepcopy(pkt)
            forged.epoch_sig = flip_bit(pkt.epoch_sig, pos, pos % 8)
            assert not accepts(rx, forged), f"epoch signature flip accepted at byte {pos}"
        assert accepts(rx, pkt)

    @pytest.mark.parametrize("field", ["ciphertext", "tag", "iv", "ed_sig"])
    def test_replacing_any_field_with_zeros_or_random_is_rejected(self, tier_ctx, field):
        tx, rx = make_pair(tier_ctx)
        pkt, _ = tx.send(b"payload payload", AAD)
        for repl in (bytes(len(getattr(pkt, field))), bytes(range(len(getattr(pkt, field))))):
            forged = copy.deepcopy(pkt)
            setattr(forged, field, repl)
            assert not accepts(rx, forged)

    def test_truncation_at_every_length_is_never_accepted(self, tier_ctx):
        tx, rx = make_pair(tier_ctx)
        pkt, _ = tx.send(b"truncate me", AAD)
        wire = pkt.to_wire()
        for n in range(0, len(wire)):
            try:
                forged = Packet.from_wire(wire[:n])
            except Exception:
                continue
            if same_content(forged, pkt):
                continue
            assert not accepts(rx, forged), f"truncated packet ({n} of {len(wire)} bytes) accepted"

    def test_replay_of_an_accepted_packet_is_rejected(self, tier_ctx):
        tx, rx = make_pair(tier_ctx)
        p1, _ = tx.send(b"one", AAD)
        p2, _ = tx.send(b"two", AAD)
        assert accepts(rx, p1) and accepts(rx, p2)
        assert not accepts(rx, p1) and not accepts(rx, p2)

    def test_reordering_and_dropping_are_detected_and_do_not_corrupt_state(self, tier_ctx):
        tx, rx = make_pair(tier_ctx)
        p1, _ = tx.send(b"one", AAD)
        p2, _ = tx.send(b"two", AAD)
        p3, _ = tx.send(b"three", AAD)
        assert not accepts(rx, p2)                              # arrived before p1 (reordered)
        assert not accepts(rx, p3)                              # p1, p2 dropped
        assert accepts(rx, p1) and accepts(rx, p2) and accepts(rx, p3)   # state intact, order restored

    def test_forged_packet_cannot_block_the_legitimate_stream(self, tier_ctx):
        """A rejected packet must not advance receiver state (no remote desynchronisation)."""
        tx, rx = make_pair(tier_ctx)
        p1, _ = tx.send(b"one", AAD)
        junk = copy.deepcopy(p1)
        junk.ciphertext = flip_bit(junk.ciphertext, 0)
        for _ in range(20):
            assert not accepts(rx, junk)
        assert accepts(rx, p1)

    def test_cross_tier_injection_is_rejected(self, tier_ctx):
        """A packet from a session at another tier cannot be injected here, even with the header
        rewritten to look like it belongs to this tier."""
        t, ident, hs = tier_ctx
        tx, rx = make_pair(tier_ctx)
        other_t = TIERS[3] if t.level != 3 else TIERS[5]
        other_ident = Identity.generate("o", other_t)
        other_hs = hybrid_handshake(other_t, other_ident)
        otx = SecureSender(other_t, other_hs.master_secret, other_hs.session_id, other_ident, EPOCH)
        opkt, _ = otx.send(b"evil", AAD)
        assert not accepts(rx, opkt)
        rewritten = copy.deepcopy(opkt)
        rewritten.tier, rewritten.session_id = t.level, hs.session_id
        assert not accepts(rx, rewritten)

    def test_header_rewrite_attacks_are_rejected(self, tier_ctx):
        """Tier byte, session id and sequence number are all covered by the signature and the AEAD AAD."""
        t, _, _ = tier_ctx
        tx, rx = make_pair(tier_ctx)
        pkt, _ = tx.send(b"hdr", AAD)
        for name, val in (("tier", (t.level + 2) % 6), ("session_id", b"\xff" * 8), ("seq", pkt.seq + 1)):
            forged = copy.deepcopy(pkt)
            setattr(forged, name, val)
            assert not accepts(rx, forged), f"header field {name} rewrite accepted"

    def test_cross_session_splice_is_rejected(self, tier_ctx):
        """A valid packet from another session of the same tier, header patched to this session."""
        t, ident, hs = tier_ctx
        tx, rx = make_pair(tier_ctx)
        hs2 = hybrid_handshake(t, ident)
        tx2 = SecureSender(t, hs2.master_secret, hs2.session_id, ident, EPOCH)
        p, _ = tx2.send(b"from another session", AAD)
        assert not accepts(rx, p)
        p.session_id = hs.session_id
        assert not accepts(rx, p)

    def test_aad_domain_separation_between_clinical_and_research(self, tier_ctx):
        tx, rx = make_pair(tier_ctx)
        pkt, _ = tx.send(b"phi", b"clinical")
        assert not accepts(rx, pkt, aad=b"research")
        assert accepts(rx, pkt, aad=b"clinical")

    def test_epoch_signature_stripped_is_rejected(self, tier_ctx):
        tx, rx = make_pair(tier_ctx, epoch=1)
        pkt, _ = tx.send(b"x", AAD)
        pkt.epoch_sig = b""
        assert not accepts(rx, pkt)

    def test_epoch_signature_transplanted_from_an_earlier_epoch_is_rejected(self, tier_ctx):
        tx, rx = make_pair(tier_ctx, epoch=2)
        p1, _ = tx.send(b"1", AAD)
        p2, _ = tx.send(b"2", AAD)                              # closes epoch 1
        p3, _ = tx.send(b"3", AAD)
        p4, _ = tx.send(b"4", AAD)                              # closes epoch 2
        for p in (p1, p2, p3):
            assert accepts(rx, p)
        stale = copy.deepcopy(p4)
        stale.epoch_sig = p2.epoch_sig                          # valid ML-DSA signature, wrong chain
        assert not accepts(rx, stale)
        assert accepts(rx, p4)

    def test_attacker_holding_the_ed25519_key_still_cannot_forge_an_epoch_boundary(self, tier_ctx):
        """Classical-break model: the attacker can produce valid Ed25519 signatures, so only the
        ML-DSA epoch signature stands between them and a forged epoch-closing packet."""
        t, ident, _ = tier_ctx
        tx, rx = make_pair(tier_ctx, epoch=1)
        pkt, _ = tx.send(b"genuine", AAD)
        forged = copy.deepcopy(pkt)
        forged.epoch_sig = bytes(len(pkt.epoch_sig))            # attacker cannot sign with ML-DSA
        sealed = forged.ciphertext + forged.tag
        forged.ed_sig = ident.ed_sk.sign(forged.header() + forged.iv + sealed)  # valid classical sig
        assert not accepts(rx, forged)

    def test_make_before_break_rekey_keeps_old_session_usable_and_isolated(self, tier_ctx):
        t, ident, hs = tier_ctx
        old_tx, old_rx = make_pair(tier_ctx)
        p1, _ = old_tx.send(b"before rekey", AAD)
        assert accepts(old_rx, p1)
        hs_new = hybrid_handshake(t, ident)                     # new session established on the side
        new_tx = SecureSender(t, hs_new.master_secret, hs_new.session_id, ident, EPOCH)
        new_rx = SecureReceiver(t, hs_new.master_secret, hs_new.session_id, ident.ed_pk, ident.dsa_pk, EPOCH)
        p2, _ = old_tx.send(b"old session still flowing", AAD)  # old path unaffected
        assert accepts(old_rx, p2)
        q1, _ = new_tx.send(b"new session", AAD)
        assert accepts(new_rx, q1)
        assert not accepts(new_rx, p2) and not accepts(old_rx, q1)


# ======================================================================================
# 3. Key, nonce and parser hygiene
# ======================================================================================
class TestKeyAndNonceHygiene:
    def test_nonces_are_unique_and_strictly_increasing(self, tier_ctx):
        tx, _ = make_pair(tier_ctx, epoch=10 ** 9)              # no ML-DSA signing: fast
        seen, last = set(), 0
        for _ in range(3000):
            pkt, _ = tx.send(b"n", AAD)
            assert pkt.iv not in seen
            seen.add(pkt.iv)
            seq = struct.unpack(">Q", pkt.iv[4:])[0]
            assert seq > last
            last = seq

    def test_iv_prefix_is_independent_of_the_encryption_key(self, tier_ctx):
        """The IV travels in clear in every packet, so none of it may be derived from (or equal to)
        key material. Reusing okm[:4] as both enc_key[:4] and iv_prefix would leak 32 key bits."""
        t, _, hs = tier_ctx
        k = derive_keys(hs.master_secret, t.aead)
        assert k["iv_prefix"] != k["enc_key"][:4]
        assert k["iv_prefix"] not in k["enc_key"]
        assert k["iv_prefix"] not in k["mac_key"]

    def test_wire_iv_reveals_no_bytes_of_the_session_key(self, tier_ctx):
        tx, _ = make_pair(tier_ctx)
        pkt, _ = tx.send(b"x", AAD)
        key = tx.keys["enc_key"]
        assert not any(pkt.iv[i:i + 4] == key[j:j + 4] for i in range(len(pkt.iv) - 3)
                       for j in range(len(key) - 3))

    def test_derived_keys_are_distinct_full_length_and_master_dependent(self, tier_ctx):
        t, _, hs = tier_ctx
        k = derive_keys(hs.master_secret, t.aead)
        assert len(k["enc_key"]) == 32 and k["enc_key"] != k["mac_key"]
        assert k["enc_key"] != bytes(32)
        assert derive_keys(hs.master_secret, t.aead) == k                       # deterministic
        assert derive_keys(b"\x01" * 32, t.aead)["enc_key"] != k["enc_key"]     # master dependent
        other = "ChaCha20-Poly1305" if t.aead == "AES-256-GCM" else "AES-256-GCM"
        assert derive_keys(hs.master_secret, other)["enc_key"] != k["enc_key"]  # cipher-label separation

    def test_ml_dsa_signatures_are_hedged_not_deterministic(self, tier_ctx):
        t, ident, _ = tier_ctx
        assert ident.sign(b"m")[1] != ident.sign(b"m")[1]

    @settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(blob=st.binary(min_size=0, max_size=400))
    def test_parser_fuzz_random_bytes_never_accepted(self, tier_ctx, blob):
        _, rx = make_pair(tier_ctx)
        try:
            pkt = Packet.from_wire(blob)
        except (struct.error, ValueError, IndexError):
            return
        assert not accepts(rx, pkt)

    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(pos=st.integers(min_value=0, max_value=10 ** 6), bit=st.integers(0, 7),
           payload=st.binary(min_size=0, max_size=300))
    def test_property_any_single_bit_flip_is_rejected(self, tier_ctx, pos, bit, payload):
        _, rx = make_pair(tier_ctx)
        tx, _ = make_pair(tier_ctx)
        pkt, _ = tx.send(payload, AAD)
        wire = pkt.to_wire()
        try:
            forged = Packet.from_wire(flip_bit(wire, pos % len(wire), bit))
        except Exception:
            return
        if same_content(forged, pkt):
            return
        assert not accepts(rx, forged)

    @settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(payload=st.binary(min_size=0, max_size=2000))
    def test_property_roundtrip_for_any_payload(self, tier_ctx, payload):
        tx, rx = make_pair(tier_ctx, epoch=10 ** 9)
        pkt, _ = tx.send(payload, AAD)
        assert rx.receive(Packet.from_wire(pkt.to_wire()), AAD)[0] == payload


# ======================================================================================
# 4. Cross-implementation interoperability (opt-in: RUN_LIBOQS_TESTS=1, needs liboqs + liboqs-python)
# ======================================================================================
@pytest.fixture(scope="module")
def oqs():
    """liboqs-python tries to download and BUILD the liboqs C library on first import when it cannot
    find one, which can take many minutes. So these tests only run when explicitly requested:
        RUN_LIBOQS_TESTS=1 python -m pytest tests/test_tier_channel_security.py -k Liboqs
    (set OQS_INSTALL_PATH / LD_LIBRARY_PATH first if liboqs is installed in a non-standard place)."""
    import os
    if os.environ.get("RUN_LIBOQS_TESTS") != "1":
        pytest.skip("liboqs interop tests are opt-in: set RUN_LIBOQS_TESTS=1 (see docstring)")
    try:
        import oqs as _oqs
    except Exception as e:                                  # not installed / library not found
        pytest.skip(f"liboqs-python unavailable: {type(e).__name__}: {e}")
    return _oqs


class TestInteropWithLiboqs:
    """liboqs is an independent C implementation of FIPS 203 / FIPS 204. Agreement between it and
    the pure-Python reference code the project uses is strong evidence both are correct."""

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_kem_python_encaps_native_decaps(self, oqs, lv):
        name = TIERS[lv].kem
        ek, dk = KEM[name].keygen()
        ss, ct = KEM[name].encaps(ek)
        with oqs.KeyEncapsulation(name, secret_key=dk) as native:
            assert native.decap_secret(ct) == ss

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_kem_native_encaps_python_decaps(self, oqs, lv):
        name = TIERS[lv].kem
        ek, dk = KEM[name].keygen()
        with oqs.KeyEncapsulation(name) as native:
            ct, ss = native.encap_secret(ek)
        assert KEM[name].decaps(dk, ct) == ss

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_kem_sizes_agree_with_native(self, oqs, lv):
        t = TIERS[lv]
        with oqs.KeyEncapsulation(t.kem) as native:
            d = native.details
            assert (d["length_public_key"], d["length_ciphertext"], d["length_shared_secret"]) == \
                (t.kem_pk_bytes, t.kem_ct_bytes, 32)

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_dsa_python_sign_native_verify(self, oqs, lv):
        name = TIERS[lv].dsa
        pk, sk = DSA[name].keygen()
        msg = b"interop message " * 8
        sig = DSA[name].sign(sk, msg)
        with oqs.Signature(name) as native:
            assert native.verify(msg, sig, pk)
            assert not native.verify(msg + b"!", sig, pk)

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_dsa_native_sign_python_verify(self, oqs, lv):
        name = TIERS[lv].dsa
        with oqs.Signature(name) as native:
            pk = native.generate_keypair()
            msg = b"interop message " * 8
            sig = native.sign(msg)
        assert DSA[name].verify(pk, msg, sig)
        assert not DSA[name].verify(pk, msg + b"!", sig)

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_dsa_sizes_agree_with_native(self, oqs, lv):
        t = TIERS[lv]
        with oqs.Signature(t.dsa) as native:
            d = native.details
            assert (d["length_public_key"], d["length_signature"]) == (t.dsa_pk_bytes, t.dsa_sig_bytes)
