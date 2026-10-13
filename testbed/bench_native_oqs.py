#!/usr/bin/env python3
"""Native (liboqs C library) ML-KEM / ML-DSA timings, to bound what the pure-Python
reference code mis-states. Needs liboqs-python + liboqs (LD_LIBRARY_PATH).
Writes reports/native_pqc_bench.json."""
import json, statistics as st, sys, time
from pathlib import Path
import oqs

N = 300
out = {"liboqs": oqs.oqs_version(), "n": N, "kem": {}, "sig": {}}

def med(f):
    xs = []
    for _ in range(N):
        t = time.perf_counter(); f(); xs.append((time.perf_counter() - t) * 1000)
    xs.sort()
    return dict(median_ms=round(st.median(xs), 4), p95_ms=round(xs[int(.95 * N)], 4))

for k in ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"):
    with oqs.KeyEncapsulation(k) as c, oqs.KeyEncapsulation(k) as s:
        pk = c.generate_keypair(); ct, _ = s.encap_secret(pk)
        out["kem"][k] = dict(pk=c.details["length_public_key"], ct=c.details["length_ciphertext"],
                             keygen=med(lambda: oqs.KeyEncapsulation(k).generate_keypair()),
                             encaps=med(lambda: s.encap_secret(pk)), decaps=med(lambda: c.decap_secret(ct)))
msg = b"x" * 32
for n in ("ML-DSA-44", "ML-DSA-65", "ML-DSA-87"):
    with oqs.Signature(n) as sg, oqs.Signature(n) as vf:
        pk = sg.generate_keypair(); sig = sg.sign(msg)
        out["sig"][n] = dict(pk=sg.details["length_public_key"], sig=sg.details["length_signature"],
                             sign=med(lambda: sg.sign(msg)), verify=med(lambda: vf.verify(msg, sig, pk)))
p = Path(__file__).resolve().parents[1] / "reports" / "native_pqc_bench.json"
p.write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
