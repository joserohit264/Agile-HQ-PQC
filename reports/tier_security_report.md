# Tier security validation report

Generated 2026-10-13T01:32:34 on Linux-6.8.0-138-generic-x86_64-with-glibc2.35, Python 3.10.12

**Result: 185 passed, 0 failed, 18 skipped**  - no failures found.

| Area | Standard / source | Passed | Failed | Skipped |
|---|---|---:|---:|---:|
| Tier table | FIPS 203, FIPS 204, NIST PQC security categories, CNSA 2.0 | 16 | 0 | 0 |
| ML-KEM known answers | FIPS 203 - NIST ACVP vectors | 15 | 0 | 0 |
| ML-DSA known answers | FIPS 204 - NIST ACVP vectors | 9 | 0 | 0 |
| Classical / symmetric primitives | SP 800-38D, RFC 8439, RFC 5869, RFC 7748, RFC 8032 | 7 | 0 | 0 |
| Hybrid handshake | Hybrid KEM combiner (SP 800-56C Rev.2 / SP 800-227 guidance), FIPS 203 implicit rejection | 23 | 0 | 0 |
| Channel attacks | Active-attacker tests: flips, replay, reorder, splice, downgrade | 57 | 0 | 0 |
| Key / nonce hygiene and fuzzing | SP 800-38D nonce uniqueness, HKDF key separation, property tests | 24 | 0 | 0 |
| Interoperability | liboqs (independent C implementation of FIPS 203 / 204) | 0 | 0 | 18 |
| Controller: safety floor | Clinical floor >= NIST Category 3 for every input | 6 | 0 | 0 |
| Controller: spec conformance | Differential test against a reference model | 5 | 0 | 0 |
| Controller: re-key storm bound | <= 1 tier change per 3 cycles | 4 | 0 | 0 |
| Controller: delay-injection attack | Downgrade timing, floor, recovery | 5 | 0 | 0 |
| Controller: monotonicity | More delay never gives a stronger tier | 2 | 0 | 0 |
| Controller: static baseline | Static tier can never move | 1 | 0 | 0 |
| Controller: malformed measurements | NaN / inf / negative probes | 8 | 0 | 0 |
| Controller: robustness | Bounded memory, determinism, smoothing | 3 | 0 | 0 |

## Skipped (evidence NOT obtained for these)
- `TestInteropWithLiboqs::test_dsa_native_sign_python_verify[1]`
- `TestInteropWithLiboqs::test_dsa_native_sign_python_verify[3]`
- `TestInteropWithLiboqs::test_dsa_native_sign_python_verify[5]`
- `TestInteropWithLiboqs::test_dsa_python_sign_native_verify[1]`
- `TestInteropWithLiboqs::test_dsa_python_sign_native_verify[3]`
- `TestInteropWithLiboqs::test_dsa_python_sign_native_verify[5]`
- `TestInteropWithLiboqs::test_dsa_sizes_agree_with_native[1]`
- `TestInteropWithLiboqs::test_dsa_sizes_agree_with_native[3]`
- `TestInteropWithLiboqs::test_dsa_sizes_agree_with_native[5]`
- `TestInteropWithLiboqs::test_kem_native_encaps_python_decaps[1]`
- `TestInteropWithLiboqs::test_kem_native_encaps_python_decaps[3]`
- `TestInteropWithLiboqs::test_kem_native_encaps_python_decaps[5]`
- `TestInteropWithLiboqs::test_kem_python_encaps_native_decaps[1]`
- `TestInteropWithLiboqs::test_kem_python_encaps_native_decaps[3]`
- `TestInteropWithLiboqs::test_kem_python_encaps_native_decaps[5]`
- `TestInteropWithLiboqs::test_kem_sizes_agree_with_native[1]`
- `TestInteropWithLiboqs::test_kem_sizes_agree_with_native[3]`
- `TestInteropWithLiboqs::test_kem_sizes_agree_with_native[5]`

## What a pass does and does not mean

- Passing means: the code matched the NIST/RFC known answers, rejected every modelled attack and met the stated properties.
- It does not prove the absence of vulnerabilities. Not covered: constant-time behaviour and side channels
  (kyber-py / dilithium-py are pure Python and not constant-time), hardware attacks, and a formal protocol proof.
- Formal verification (Tamarin / ProVerif) and an independent code audit remain the next evidence tier.
