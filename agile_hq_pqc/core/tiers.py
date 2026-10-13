"""Security tier definitions for Agile-HQ-PQC.

Each tier bundles a transport-crypto suite and a privacy-parameter set.
Tier numbers follow NIST security categories (1, 3, 5).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

SLA_MS = 200.0               # hard clinical end-to-end SLA
MIN_SECURITY_TIER = 3        # HIPAA compliance floor for raw PHI telemetry
HYSTERESIS_CYCLES = 3        # consecutive probes required for a transition

# Budget thresholds (ms of remaining headroom)
BUDGET_HIGH = 80.0           # > 80  -> Tier 5
BUDGET_LOW = 40.0            # <= 40 -> Tier 1, otherwise Tier 3


@dataclass(frozen=True)
class Tier:
    level: int
    name: str
    kem: str
    dsa: str
    aead: str
    epsilon: float
    k: int
    l: int
    kem_pk_bytes: int
    kem_ct_bytes: int
    dsa_pk_bytes: int
    dsa_sig_bytes: int

    @property
    def suite(self) -> str:
        return f"{self.kem} + {self.dsa} + {self.aead}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["suite"] = self.suite
        return d


TIERS = {
    5: Tier(5, "Maximum Security", "ML-KEM-1024", "ML-DSA-87", "AES-256-GCM",
            0.1, 5, 3, 1568, 1568, 2592, 4627),
    3: Tier(3, "Standard Security", "ML-KEM-768", "ML-DSA-65", "AES-256-GCM",
            0.5, 3, 2, 1184, 1088, 1952, 3309),
    1: Tier(1, "Emergency High Throughput", "ML-KEM-512", "ML-DSA-44",
            "ChaCha20-Poly1305", 1.0, 2, 2, 800, 768, 1312, 2420),
}

TIER_ORDER = (1, 3, 5)  # ascending security


def get_tier(level: int) -> Tier:
    return TIERS[level]
