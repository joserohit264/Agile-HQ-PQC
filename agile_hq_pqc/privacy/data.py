"""Synthetic (non-real) clinical data generators: ECG waveform and EHR table."""
from __future__ import annotations

import numpy as np

DIAGNOSES = ["Hypertension", "Diabetes T2", "Arrhythmia", "Asthma", "CKD",
             "Anemia", "Hypothyroidism", "Healthy"]
ZIPS = ["632001", "632002", "632004", "632006", "632009", "632014",
        "600001", "600017", "560001", "560034", "641001", "625001"]


def synthetic_ecg(seconds: float = 4.0, fs: int = 250, hr: float = 72.0,
                  seed: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (t, ecg_mV): sum-of-Gaussians PQRST model."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, seconds, 1 / fs)
    ecg = np.zeros_like(t)
    rr = 60.0 / hr
    for beat in np.arange(0.3, seconds, rr):
        for amp, mu, sd in ((0.12, -0.20, 0.025), (-0.12, -0.04, 0.010),
                            (1.00, 0.00, 0.012), (-0.25, 0.04, 0.010),
                            (0.30, 0.25, 0.045)):
            ecg += amp * np.exp(-0.5 * ((t - beat - mu) / sd) ** 2)
    ecg += rng.normal(0, 0.01, t.shape)
    return t, ecg


def vitals_sample(rng: np.random.Generator) -> dict:
    return {"hr": int(rng.normal(74, 9)), "spo2": int(np.clip(rng.normal(97, 1.5), 85, 100)),
            "sbp": int(rng.normal(122, 12)), "dbp": int(rng.normal(80, 8)),
            "temp_c": round(float(rng.normal(36.8, 0.3)), 1)}


def synthetic_ehr(n: int = 200, seed: int | None = 7) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        rows.append({
            "patient_id": f"P{i:05d}",
            "age": int(np.clip(rng.normal(48, 17), 18, 90)),
            "zip": str(rng.choice(ZIPS)),
            "sex": str(rng.choice(["F", "M"])),
            "diagnosis": str(rng.choice(DIAGNOSES, p=[.17, .16, .10, .12, .08, .10, .09, .18])),
        })
    return rows
