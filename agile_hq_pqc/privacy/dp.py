"""Differential privacy for continuous IoMT streams (Laplace mechanism)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class DPResult:
    noisy: np.ndarray
    epsilon: float
    sensitivity: float
    scale: float
    snr_db: float
    rmse: float


def laplace_mechanism(signal: np.ndarray, epsilon: float, sensitivity: float = 0.5,
                      clip: tuple[float, float] | None = None,
                      rng: np.random.Generator | None = None) -> DPResult:
    """Add Laplace(0, sensitivity/epsilon) noise to every sample.

    ``sensitivity`` is the bound on how much one individual's contribution can
    change a single sample (L1). Samples are clipped to ``clip`` first so the
    sensitivity bound is actually enforced.
    Smaller epsilon => stronger privacy => MORE noise.
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")
    rng = rng or np.random.default_rng()
    x = np.asarray(signal, dtype=float)
    if clip is not None:
        x = np.clip(x, clip[0], clip[1])
    scale = sensitivity / epsilon
    noisy = x + rng.laplace(0.0, scale, size=x.shape)
    err = noisy - x
    p_sig = float(np.mean(x ** 2)) or 1e-12
    p_noise = float(np.mean(err ** 2)) or 1e-12
    return DPResult(noisy, epsilon, sensitivity, scale,
                    10 * math.log10(p_sig / p_noise), float(math.sqrt(p_noise)))


class PrivacyAccountant:
    """Sequential-composition privacy-budget tracker (per subject/stream)."""

    def __init__(self, total_epsilon: float = 50.0):
        self.total = total_epsilon
        self.spent = 0.0

    def charge(self, epsilon: float) -> bool:
        if self.spent + epsilon > self.total + 1e-12:
            return False
        self.spent += epsilon
        return True

    @property
    def remaining(self) -> float:
        return max(0.0, self.total - self.spent)
