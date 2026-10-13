"""Loader for the official NIST ACVP known-answer vectors (FIPS 203 / FIPS 204).

The vectors are published by NIST at https://github.com/usnistgov/ACVP-Server
(directory gen-val/json-files). They are downloaded once into ``tests/vectors/``
and cached, so later runs work offline.

Usage
-----
    python tests/nist_vectors.py          # download / refresh the cache and print SHA-256s

Environment
-----------
    NIST_VECTOR_DIR       cache folder (default: tests/vectors)
    NIST_VECTOR_BASE_URL  override the download base URL (e.g. an internal mirror)
    REQUIRE_NIST_VECTORS  "1" => a missing vector file FAILS the test instead of skipping it
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get(
    "NIST_VECTOR_BASE_URL",
    "https://raw.githubusercontent.com/usnistgov/ACVP-Server/master/gen-val/json-files",
)
CACHE_DIR = Path(os.environ.get("NIST_VECTOR_DIR", Path(__file__).resolve().parent / "vectors"))

# short name -> ACVP directory (the "internalProjection.json" file holds prompts + expected results)
SETS = {
    "mlkem_keygen": "ML-KEM-keyGen-FIPS203",
    "mlkem_encapdecap": "ML-KEM-encapDecap-FIPS203",
    "mldsa_keygen": "ML-DSA-keyGen-FIPS204",
    "mldsa_siggen": "ML-DSA-sigGen-FIPS204",
    "mldsa_sigver": "ML-DSA-sigVer-FIPS204",
}


class VectorsUnavailable(RuntimeError):
    """Raised when a vector file is neither cached nor downloadable."""


def _path(key: str) -> Path:
    return CACHE_DIR / f"{SETS[key]}.internalProjection.json"


def fetch(key: str, force: bool = False) -> Path:
    p = _path(key)
    if p.exists() and not force:
        return p
    url = f"{BASE_URL}/{SETS[key]}/internalProjection.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:  # nosec - fixed https URL
            data = r.read()
    except Exception as e:  # network / TLS / proxy problems
        raise VectorsUnavailable(f"cannot download {url}: {e}") from e
    p.write_bytes(data)
    return p


def load(key: str) -> dict:
    return json.loads(fetch(key).read_text())


def sha256_of(key: str) -> str:
    return hashlib.sha256(fetch(key).read_bytes()).hexdigest()


def groups(key: str, **where):
    """Yield test groups whose metadata matches ``where`` (e.g. parameterSet='ML-KEM-768')."""
    for g in load(key)["testGroups"]:
        if all(g.get(k) == v for k, v in where.items()):
            yield g


def hx(s: str) -> bytes:
    return bytes.fromhex(s)


if __name__ == "__main__":
    ok = True
    for k in SETS:
        try:
            p = fetch(k, force="--force" in sys.argv)
            print(f"{SETS[k]:32s} {p.stat().st_size:>9d} bytes  sha256={sha256_of(k)}")
        except VectorsUnavailable as e:
            ok = False
            print("FAILED:", e)
    sys.exit(0 if ok else 1)
