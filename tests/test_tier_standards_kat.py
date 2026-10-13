"""Tier security suite, part 1: standards conformance and known-answer tests (KATs).

Scope: the three security tiers only (Tier 5 / Tier 3 / Tier 1) and the cryptographic
suite each one selects. Privacy parameters (epsilon, K, L) are deliberately NOT tested.

Standards exercised
-------------------
  FIPS 203   ML-KEM                     NIST ACVP vectors (keyGen, encaps, decaps, key checks)
  FIPS 204   ML-DSA                     NIST ACVP vectors (keyGen, sigGen, sigVer)
  SP 800-38D AES-GCM                    GCM spec Test Case 16 (AES-256, with AAD)
  RFC 8439   ChaCha20-Poly1305          Section 2.8.2 test vector
  RFC 5869   HKDF-SHA256                Test Cases 1 and 3
  RFC 7748   X25519                     Section 6.1 test vector
  RFC 8032   Ed25519                    Section 7.1 TEST 1
  NIST PQC   security categories        Call for Proposals (2016) / FIPS 203 / FIPS 204
  CNSA 2.0   (NSA) ML-KEM-1024 + ML-DSA-87 expectation for Tier 5

Run:   python -m pytest tests/test_tier_standards_kat.py -v
Needs the NIST vector files; they are fetched automatically on first use
(see tests/nist_vectors.py).  Set REQUIRE_NIST_VECTORS=1 to make a missing file a failure.
"""
import dataclasses
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import nist_vectors as nv  # noqa: E402
from agile_hq_pqc.core.tiers import TIERS, TIER_ORDER, MIN_SECURITY_TIER  # noqa: E402
from agile_hq_pqc.crypto.channel import _aead  # noqa: E402
from agile_hq_pqc.crypto.hybrid import DSA, KEM, hkdf  # noqa: E402

TIER_LEVELS = [1, 3, 5]
MAX_PER_GROUP = int(os.environ.get("KAT_MAX_PER_GROUP", "0")) or None   # 0 = all vectors

# FIPS 203 Table 3 / FIPS 204 Table 2 and the NIST security category each set claims.
FIPS203 = {  # name: (ek bytes, ct bytes, shared-secret bytes, NIST category)
    "ML-KEM-512": (800, 768, 32, 1),
    "ML-KEM-768": (1184, 1088, 32, 3),
    "ML-KEM-1024": (1568, 1568, 32, 5),
}
FIPS204 = {  # name: (pk bytes, signature bytes, NIST category)
    "ML-DSA-44": (1312, 2420, 2),
    "ML-DSA-65": (1952, 3309, 3),
    "ML-DSA-87": (2592, 4627, 5),
}


def _vectors(key, **where):
    """Load vector groups; skip (or fail if REQUIRE_NIST_VECTORS=1) when unavailable."""
    try:
        return list(nv.groups(key, **where))
    except nv.VectorsUnavailable as e:
        if os.environ.get("REQUIRE_NIST_VECTORS") == "1":
            pytest.fail(f"NIST vectors required but unavailable: {e}")
        pytest.skip(f"NIST vectors unavailable (run: python tests/nist_vectors.py): {e}")


def _tests(group):
    return group["tests"][:MAX_PER_GROUP] if MAX_PER_GROUP else group["tests"]


# ======================================================================================
# A. The tier table itself conforms to the standards it claims
# ======================================================================================
class TestTierTableConformance:
    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_kem_sizes_match_fips203(self, lv):
        t = TIERS[lv]
        ek, ct, ss, _ = FIPS203[t.kem]
        assert (t.kem_pk_bytes, t.kem_ct_bytes) == (ek, ct)
        pk, _sk = KEM[t.kem].keygen()
        shared, c = KEM[t.kem].encaps(pk)
        assert (len(pk), len(c), len(shared)) == (ek, ct, ss)

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_dsa_sizes_match_fips204(self, lv):
        t = TIERS[lv]
        pk_len, sig_len, _ = FIPS204[t.dsa]
        assert (t.dsa_pk_bytes, t.dsa_sig_bytes) == (pk_len, sig_len)
        pk, sk = DSA[t.dsa].keygen()
        sig = DSA[t.dsa].sign(sk, b"size check")
        assert (len(pk), len(sig)) == (pk_len, sig_len)

    def test_tier_numbers_are_the_nist_category_of_the_kem(self):
        """Tier N must really provide NIST Category N key establishment."""
        for lv in TIER_LEVELS:
            assert FIPS203[TIERS[lv].kem][3] == lv

    def test_signature_category_never_below_kem_category_except_documented_tier1(self):
        """ML-DSA-44 is NIST Category 2, ML-KEM-512 is Category 1: Tier 1 signatures are
        therefore one category *above* its KEM (never below). Tiers 3 and 5 match exactly."""
        for lv in TIER_LEVELS:
            t = TIERS[lv]
            assert FIPS204[t.dsa][2] >= FIPS203[t.kem][3]
        assert FIPS204[TIERS[3].dsa][2] == FIPS203[TIERS[3].kem][3] == 3
        assert FIPS204[TIERS[5].dsa][2] == FIPS203[TIERS[5].kem][3] == 5

    def test_strength_is_strictly_monotonic_in_tier(self):
        cats = [FIPS203[TIERS[lv].kem][3] for lv in TIER_ORDER]
        assert cats == sorted(cats) and len(set(cats)) == 3
        sizes = [TIERS[lv].kem_ct_bytes + TIERS[lv].dsa_sig_bytes for lv in TIER_ORDER]
        assert sizes == sorted(sizes)            # more security => more bytes (the trade-off)

    def test_clinical_floor_is_nist_category_3_or_higher(self):
        """The floor tier must use a Category >= 3 KEM and signature (SP 800-57 / HIPAA intent)."""
        floor = TIERS[MIN_SECURITY_TIER]
        assert MIN_SECURITY_TIER >= 3
        assert FIPS203[floor.kem][3] >= 3 and FIPS204[floor.dsa][2] >= 3

    def test_tier5_matches_cnsa_2_0_algorithms(self):
        """NSA CNSA 2.0 requires ML-KEM-1024 and ML-DSA-87 for National Security Systems."""
        assert TIERS[5].kem == "ML-KEM-1024" and TIERS[5].dsa == "ML-DSA-87"

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_symmetric_layer_is_256_bit_aead(self, lv):
        """256-bit symmetric keys keep Grover-level security >= 128 bits (NIST SP 800-57)."""
        t = TIERS[lv]
        assert t.aead in {"AES-256-GCM", "ChaCha20-Poly1305"}
        aead = _aead(t, bytes(32))
        assert type(aead).__name__ in {"AESGCM", "ChaCha20Poly1305"}

    def test_tier_table_is_immutable(self):
        """A frozen dataclass: nothing at run time can edit a tier in place."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            TIERS[3].kem = "ML-KEM-512"
        with pytest.raises(dataclasses.FrozenInstanceError):
            TIERS[5].dsa = "ML-DSA-44"

    def test_every_tier_uses_a_nist_standardised_pair_only(self):
        std_kem, std_dsa = set(FIPS203), set(FIPS204)
        for t in TIERS.values():
            assert t.kem in std_kem and t.dsa in std_dsa


# ======================================================================================
# B. NIST ACVP known-answer tests: ML-KEM (FIPS 203)
# ======================================================================================
class TestMLKEM_ACVP:
    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_keygen(self, lv):
        name = TIERS[lv].kem
        n = 0
        for g in _vectors("mlkem_keygen", parameterSet=name):
            for x in _tests(g):
                ek, dk = KEM[name].key_derive(nv.hx(x["d"]) + nv.hx(x["z"]))
                assert ek == nv.hx(x["ek"]), f"{name} keyGen ek mismatch tcId={x['tcId']}"
                assert dk == nv.hx(x["dk"]), f"{name} keyGen dk mismatch tcId={x['tcId']}"
                n += 1
        assert n > 0

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_encapsulation(self, lv):
        name = TIERS[lv].kem
        n = 0
        for g in _vectors("mlkem_encapdecap", parameterSet=name, function="encapsulation"):
            for x in _tests(g):
                k, c = KEM[name]._encaps_internal(nv.hx(x["ek"]), nv.hx(x["m"]))
                assert (k, c) == (nv.hx(x["k"]), nv.hx(x["c"])), f"{name} encaps tcId={x['tcId']}"
                n += 1
        assert n > 0

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_decapsulation_including_implicit_rejection(self, lv):
        """ACVP decapsulation VAL tests include invalid ciphertexts: the correct output is the
        implicit-rejection key (FIPS 203 Alg. 18), not an error."""
        name = TIERS[lv].kem
        n = 0
        for g in _vectors("mlkem_encapdecap", parameterSet=name, function="decapsulation"):
            for x in _tests(g):
                k = KEM[name].decaps(nv.hx(x["dk"]), nv.hx(x["c"]))
                assert k == nv.hx(x["k"]), f"{name} decaps tcId={x['tcId']} ({x.get('reason')})"
                n += 1
        assert n > 0

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_encapsulation_key_check_rejects_malformed_keys(self, lv):
        """FIPS 203 §7.2 input check: out-of-range / wrong-length encapsulation keys are refused."""
        name = TIERS[lv].kem
        n = 0
        for g in _vectors("mlkem_encapdecap", parameterSet=name, function="encapsulationKeyCheck"):
            for x in _tests(g):
                try:
                    KEM[name].encaps(nv.hx(x["ek"]))
                    accepted = True
                except Exception:
                    accepted = False
                assert accepted == x["testPassed"], f"{name} ek check tcId={x['tcId']} ({x.get('reason')})"
                n += 1
        assert n > 0

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_decapsulation_key_check_rejects_malformed_keys(self, lv):
        """FIPS 203 §7.3 input check on the decapsulation key."""
        name = TIERS[lv].kem
        n = 0
        for g in _vectors("mlkem_encapdecap", parameterSet=name, function="decapsulationKeyCheck"):
            for x in _tests(g):
                try:
                    _k, c = KEM[name].encaps(KEM[name].keygen()[0])   # any well-formed ciphertext
                    KEM[name].decaps(nv.hx(x["dk"]), c)
                    accepted = True
                except Exception:
                    accepted = False
                assert accepted == x["testPassed"], f"{name} dk check tcId={x['tcId']} ({x.get('reason')})"
                n += 1
        assert n > 0


# ======================================================================================
# C. NIST ACVP known-answer tests: ML-DSA (FIPS 204)
# ======================================================================================
class TestMLDSA_ACVP:
    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_keygen(self, lv):
        name = TIERS[lv].dsa
        n = 0
        for g in _vectors("mldsa_keygen", parameterSet=name):
            for x in _tests(g):
                pk, sk = DSA[name].key_derive(nv.hx(x["seed"]))
                assert pk == nv.hx(x["pk"]) and sk == nv.hx(x["sk"]), f"{name} keyGen tcId={x['tcId']}"
                n += 1
        assert n > 0

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_signature_generation(self, lv):
        """Deterministic and hedged (explicit rnd), external (pure ML-DSA with context) and
        internal interfaces, with and without externalMu. HashML-DSA (preHash) is not used by
        the channel and is not covered."""
        name = TIERS[lv].dsa
        n = 0
        for g in _vectors("mldsa_siggen", parameterSet=name):
            if g["preHash"] == "preHash":
                continue
            for x in _tests(g):
                rnd = bytes(32) if g["deterministic"] else nv.hx(x["rnd"])
                sk = nv.hx(x["sk"])
                if g["signatureInterface"] == "external":
                    ctx = nv.hx(x["context"])
                    m_prime = bytes([0, len(ctx)]) + ctx + nv.hx(x["message"])
                    sig = DSA[name]._sign_internal(sk, m_prime, rnd)
                elif g["externalMu"]:
                    sig = DSA[name]._sign_internal(sk, nv.hx(x["mu"]), rnd, external_mu=True)
                else:
                    sig = DSA[name]._sign_internal(sk, nv.hx(x["message"]), rnd)
                assert sig == nv.hx(x["signature"]), f"{name} sigGen tcId={x['tcId']} group={g['tgId']}"
                n += 1
        assert n > 0

    @pytest.mark.parametrize("lv", TIER_LEVELS)
    def test_signature_verification_accepts_valid_and_rejects_every_forgery_class(self, lv):
        """ACVP sigVer includes modified message / commitment / hint / z / lengths etc."""
        name = TIERS[lv].dsa
        n = rejected = 0
        for g in _vectors("mldsa_sigver", parameterSet=name):
            if g["preHash"] == "preHash" or g["externalMu"]:
                continue
            for x in _tests(g):
                pk, sig = nv.hx(x["pk"]), nv.hx(x["signature"])
                try:
                    if g["signatureInterface"] == "external":
                        got = DSA[name].verify(pk, nv.hx(x["message"]), sig, ctx=nv.hx(x["context"]))
                    else:
                        got = DSA[name]._verify_internal(pk, nv.hx(x["message"]), sig)
                except Exception:      # a verifier that raises on junk is still a rejection
                    got = False
                assert bool(got) == x["testPassed"], \
                    f"{name} sigVer tcId={x['tcId']} expected {x['testPassed']} ({x.get('reason')})"
                n += 1
                rejected += (not x["testPassed"])
        assert n > 0 and rejected > 0


# ======================================================================================
# D. Classical and symmetric building blocks, through the project's own wrappers
# ======================================================================================
H = bytes.fromhex


class TestPrimitiveVectors:
    def test_hkdf_rfc5869_case1(self):
        okm = hkdf(H("0b" * 22), H("f0f1f2f3f4f5f6f7f8f9"), 42, salt=H("000102030405060708090a0b0c"))
        assert okm.hex() == ("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
                             "34007208d5b887185865")

    def test_hkdf_rfc5869_case3_empty_salt_and_info(self):
        okm = hkdf(H("0b" * 22), b"", 42, salt=None)
        assert okm.hex() == ("8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d"
                             "9d201395faa4b61a96c8")

    def test_x25519_rfc7748(self):
        from cryptography.hazmat.primitives import serialization as s
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        raw = dict(encoding=s.Encoding.Raw, format=s.PublicFormat.Raw)
        a = X25519PrivateKey.from_private_bytes(H("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"))
        b = X25519PrivateKey.from_private_bytes(H("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb"))
        assert a.public_key().public_bytes(**raw).hex() == "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a"
        assert b.public_key().public_bytes(**raw).hex() == "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f"
        k = a.exchange(b.public_key())
        assert k == b.exchange(a.public_key())
        assert k.hex() == "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742"

    def test_ed25519_rfc8032_test1(self):
        from cryptography.hazmat.primitives import serialization as s
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sk = Ed25519PrivateKey.from_private_bytes(H("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"))
        pk = sk.public_key().public_bytes(encoding=s.Encoding.Raw, format=s.PublicFormat.Raw)
        assert pk.hex() == "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
        assert sk.sign(b"").hex() == ("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f"
                                      "b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")

    @pytest.mark.parametrize("lv", [3, 5])
    def test_aes256_gcm_nist_test_case_16_through_tier_cipher(self, lv):
        assert TIERS[lv].aead == "AES-256-GCM"
        g = _aead(TIERS[lv], H("feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308"))
        pt = H("d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
               "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39")
        out = g.encrypt(H("cafebabefacedbaddecaf888"), pt, H("feedfacedeadbeeffeedfacedeadbeefabaddad2"))
        assert out[:-16].hex() == ("522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
                                   "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662")
        assert out[-16:].hex() == "76fc6ece0f4e1768cddf8853bb2d551b"

    def test_chacha20_poly1305_rfc8439_through_tier1_cipher(self):
        assert TIERS[1].aead == "ChaCha20-Poly1305"
        c = _aead(TIERS[1], bytes(range(0x80, 0xA0)))
        pt = (b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip "
              b"for the future, sunscreen would be it.")
        out = c.encrypt(H("070000004041424344454647"), pt, H("50515253c0c1c2c3c4c5c6c7"))
        assert out[:16].hex() == "d31a8d34648e60db7b86afbc53ef7ec2"
        assert out[-16:].hex() == "1ae10b594f09e26a7e902ecbd0600691"
