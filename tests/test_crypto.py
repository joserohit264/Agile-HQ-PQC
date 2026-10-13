import pytest
from agile_hq_pqc.core.tiers import TIERS
from agile_hq_pqc.crypto.channel import Packet, ReceiveError, SecureReceiver, SecureSender
from agile_hq_pqc.crypto.hybrid import Identity, combine_secrets, hybrid_handshake


@pytest.fixture(scope="module", params=[1, 3, 5])
def hs(request):
    t = TIERS[request.param]
    ident = Identity.generate("srv", t)
    return t, ident, hybrid_handshake(t, ident)


def test_handshake_ok_and_sizes_match_fips(hs):
    t, ident, r = hs
    assert r.ok and len(r.master_secret) == 32
    assert len(ident.dsa_pk) == t.dsa_pk_bytes
    assert r.bytes_on_wire["client_hello"] == 32 + t.kem_pk_bytes
    assert r.bytes_on_wire["server_hello"] == 32 + t.kem_ct_bytes + 64 + t.dsa_sig_bytes


def _pair(hs, epoch=4):
    t, ident, r = hs
    return (SecureSender(t, r.master_secret, r.session_id, ident, epoch),
            SecureReceiver(t, r.master_secret, r.session_id, ident.ed_pk, ident.dsa_pk, epoch))


def test_roundtrip_and_epoch_signature(hs):
    tx, rx = _pair(hs)
    for i in range(1, 9):
        pkt, _ = tx.send(b"vitals-%d" % i, b"clinical")
        assert bool(pkt.epoch_sig) == (i % 4 == 0)
        pkt = Packet.from_token(pkt.wire_token())          # through the wire format
        assert rx.receive(pkt, b"clinical")[0] == b"vitals-%d" % i


@pytest.mark.parametrize("field", ["ciphertext", "tag", "ed_sig", "iv"])
def test_bitflip_rejected(hs, field):
    tx, rx = _pair(hs)
    pkt, _ = tx.send(b"secret", b"a")
    b = bytearray(getattr(pkt, field)); b[0] ^= 1; setattr(pkt, field, bytes(b))
    with pytest.raises(ReceiveError):
        rx.receive(pkt, b"a")


def test_aad_mismatch_and_replay_rejected(hs):
    tx, rx = _pair(hs)
    p1, _ = tx.send(b"x", b"clinical")
    with pytest.raises(ReceiveError):
        rx.receive(p1, b"research")
    tx2, rx2 = _pair(hs)
    p, _ = tx2.send(b"x", b"c"); rx2.receive(p, b"c")
    with pytest.raises(ReceiveError):
        rx2.receive(p, b"c")                                 # replay


def test_bad_epoch_signature_rejected(hs):
    tx, rx = _pair(hs, epoch=1)
    pkt, _ = tx.send(b"x", b"")
    b = bytearray(pkt.epoch_sig); b[5] ^= 1; pkt.epoch_sig = bytes(b)
    with pytest.raises(ReceiveError):
        rx.receive(pkt, b"")


def test_combiner_depends_on_both_secrets():
    a = combine_secrets(b"A" * 32, b"B" * 32, b"t")
    assert a != combine_secrets(b"X" * 32, b"B" * 32, b"t")
    assert a != combine_secrets(b"A" * 32, b"X" * 32, b"t")
    assert a != combine_secrets(b"A" * 32, b"B" * 32, b"t2")
