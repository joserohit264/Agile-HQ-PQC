#!/usr/bin/env python3
"""Run the tier security suite and write an evidence report.

    python scripts/run_tier_security.py                 # run everything, write reports/
    python scripts/run_tier_security.py --require-vectors   # missing NIST vectors => FAIL (use for final evidence)
    python scripts/run_tier_security.py --fast          # 3 vectors per ACVP group (quick smoke run)

Outputs (in reports/):
    tier_security_report.md     human-readable table, grouped by standard / attack class
    tier_security_junit.xml     machine-readable results
Exit status is pytest's: 0 only if every executed test passed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

# test class -> (area, standard / source of the check)
AREAS = OrderedDict([
    ("TestTierTableConformance", ("Tier table", "FIPS 203, FIPS 204, NIST PQC security categories, CNSA 2.0")),
    ("TestMLKEM_ACVP", ("ML-KEM known answers", "FIPS 203 - NIST ACVP vectors")),
    ("TestMLDSA_ACVP", ("ML-DSA known answers", "FIPS 204 - NIST ACVP vectors")),
    ("TestPrimitiveVectors", ("Classical / symmetric primitives",
                              "SP 800-38D, RFC 8439, RFC 5869, RFC 7748, RFC 8032")),
    ("TestHybridHandshake", ("Hybrid handshake", "Hybrid KEM combiner (SP 800-56C Rev.2 / SP 800-227 guidance), FIPS 203 implicit rejection")),
    ("TestChannelAttacks", ("Channel attacks", "Active-attacker tests: flips, replay, reorder, splice, downgrade")),
    ("TestKeyAndNonceHygiene", ("Key / nonce hygiene and fuzzing", "SP 800-38D nonce uniqueness, HKDF key separation, property tests")),
    ("TestInteropWithLiboqs", ("Interoperability", "liboqs (independent C implementation of FIPS 203 / 204)")),
    ("TestSafetyInvariants", ("Controller: safety floor", "Clinical floor >= NIST Category 3 for every input")),
    ("TestSpecConformance", ("Controller: spec conformance", "Differential test against a reference model")),
    ("TestRekeyStormBound", ("Controller: re-key storm bound", "<= 1 tier change per 3 cycles")),
    ("TestDelayInjectionAttack", ("Controller: delay-injection attack", "Downgrade timing, floor, recovery")),
    ("TestMonotonicity", ("Controller: monotonicity", "More delay never gives a stronger tier")),
    ("TestStaticBaseline", ("Controller: static baseline", "Static tier can never move")),
    ("TestMalformedMeasurements", ("Controller: malformed measurements", "NaN / inf / negative probes")),
    ("TestRobustness", ("Controller: robustness", "Bounded memory, determinism, smoothing")),
])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-vectors", action="store_true", help="fail (not skip) if NIST vectors are unavailable")
    ap.add_argument("--fast", action="store_true", help="3 vectors per ACVP group")
    ap.add_argument("-k", default=None, help="pytest -k expression")
    args = ap.parse_args()

    REPORTS.mkdir(exist_ok=True)
    junit = REPORTS / "tier_security_junit.xml"
    env = dict(os.environ)
    if args.require_vectors:
        env["REQUIRE_NIST_VECTORS"] = "1"
    if args.fast:
        env["KAT_MAX_PER_GROUP"] = "3"
    cmd = [sys.executable, "-m", "pytest", "tests/test_tier_standards_kat.py",
           "tests/test_tier_channel_security.py", "tests/test_tier_controller_security.py",
           "-q", "-p", "no:cacheprovider", f"--junitxml={junit}", "-W", "ignore::UserWarning"]
    if args.k:
        cmd += ["-k", args.k]
    rc = subprocess.call(cmd, cwd=ROOT, env=env)

    if not junit.exists():
        print("no junit file produced")
        return rc or 1
    stats: "OrderedDict[str, list[int]]" = OrderedDict((k, [0, 0, 0]) for k in AREAS)   # pass, fail, skip
    failures, skipped = [], []
    for case in ET.parse(junit).getroot().iter("testcase"):
        cls = case.get("classname", "").split(".")[-1]
        row = stats.setdefault(cls, [0, 0, 0])
        if case.find("failure") is not None or case.find("error") is not None:
            row[1] += 1
            failures.append(f"{cls}::{case.get('name')}")
        elif case.find("skipped") is not None:
            row[2] += 1
            skipped.append(f"{cls}::{case.get('name')}")
        else:
            row[0] += 1

    tp = sum(r[0] for r in stats.values()); tf = sum(r[1] for r in stats.values()); ts = sum(r[2] for r in stats.values())
    lines = [
        "# Tier security validation report", "",
        f"Generated {dt.datetime.now().isoformat(timespec='seconds')} on {platform.platform()}, Python {platform.python_version()}", "",
        f"**Result: {tp} passed, {tf} failed, {ts} skipped**"
        + ("  - no failures found." if tf == 0 else "  - FAILURES BELOW."), "",
        "| Area | Standard / source | Passed | Failed | Skipped |", "|---|---|---:|---:|---:|",
    ]
    for cls, (a, b, c) in stats.items():
        area, std = AREAS.get(cls, (cls, ""))
        lines.append(f"| {area} | {std} | {a} | {b} | {c} |")
    if failures:
        lines += ["", "## Failures", *[f"- `{f}`" for f in failures]]
    if skipped:
        lines += ["", "## Skipped (evidence NOT obtained for these)", *[f"- `{s}`" for s in sorted(set(skipped))[:40]]]
    lines += ["", "## What a pass does and does not mean", "",
              "- Passing means: the code matched the NIST/RFC known answers, rejected every modelled attack and met the stated properties.",
              "- It does not prove the absence of vulnerabilities. Not covered: constant-time behaviour and side channels",
              "  (kyber-py / dilithium-py are pure Python and not constant-time), hardware attacks, and a formal protocol proof.",
              "- Formal verification (Tamarin / ProVerif) and an independent code audit remain the next evidence tier.", ""]
    out = REPORTS / "tier_security_report.md"
    out.write_text("\n".join(lines))
    print(f"\nreport written to {out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
