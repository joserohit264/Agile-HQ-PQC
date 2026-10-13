"""CADA-AASM: Context-Aware Dynamic Agility and Adaptive Anonymization
Steering Matrix.

A closed-loop controller that maps live RTT and CPU probes to a joint
(transport-crypto, privacy) tier, damped by a persistence (hysteresis) filter,
with a domain-policy layer that enforces a HIPAA floor on raw PHI.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .tiers import (SLA_MS, MIN_SECURITY_TIER, HYSTERESIS_CYCLES,
                    BUDGET_HIGH, BUDGET_LOW, TIERS, Tier)


def latency_budget(rtt_ms: float, cpu_pct: float, sla_ms: float = SLA_MS) -> float:
    """L_budget = SLA - RTT - 0.5 * CPU  (CPU in percent)."""
    return sla_ms - rtt_ms - 0.5 * cpu_pct


def target_tier_for_budget(budget_ms: float) -> int:
    """Steering matrix: raw (undamped) tier for a given budget."""
    if budget_ms > BUDGET_HIGH:
        return 5
    if budget_ms > BUDGET_LOW:
        return 3
    return 1


@dataclass
class Decision:
    cycle: int
    rtt_ms: float
    cpu_pct: float
    budget_ms: float
    raw_target: int            # undamped steering result
    active_tier: int           # tier in force after hysteresis (agile path)
    clinical_tier: int         # tier for raw PHI after HIPAA floor
    changed: bool              # did the agile tier change this cycle?
    hysteresis_count: int      # consecutive cycles toward pending tier
    hysteresis_needed: int
    pending_tier: Optional[int]
    floor_clamped: bool        # clinical tier held above agile tier by the floor

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class CadaController:
    """Stateful steering controller.

    * ``decide`` is called once per probe cycle.
    * A tier change is committed only after ``hysteresis`` consecutive probes
      agree on the same different target (prevents cipher flapping).
    * ``clinical_tier`` = max(active_tier, MIN_SECURITY_TIER): raw PHI never
      drops below NIST Category 3.
    """

    def __init__(self, hysteresis: int = HYSTERESIS_CYCLES,
                 initial_tier: int = 5, min_clinical_tier: int = MIN_SECURITY_TIER,
                 enabled: bool = True, smoothing_alpha: float = 1.0):
        self.hysteresis = hysteresis
        self.active_tier = initial_tier
        self.min_clinical_tier = min_clinical_tier
        self.enabled = enabled           # False => static baseline
        # EWMA input conditioning: 1.0 = off (spec behaviour); <1.0 damps noisy
        # probes that straddle a threshold and would keep resetting the
        # persistence counter.
        self.alpha = smoothing_alpha
        self._rtt_s: Optional[float] = None
        self._cpu_s: Optional[float] = None
        self._pending: Optional[int] = None
        self._count = 0
        self.cycle = 0
        self.history: list[Decision] = []

    def clinical_tier_for(self, tier: int) -> int:
        return max(tier, self.min_clinical_tier)

    def decide(self, rtt_ms: float, cpu_pct: float) -> Decision:
        self.cycle += 1
        invalid = math.isnan(rtt_ms) or math.isnan(cpu_pct)
        if self.alpha < 1.0 and not invalid:   # never feed NaN into the EWMA state
            a = self.alpha
            self._rtt_s = rtt_ms if self._rtt_s is None else a * rtt_ms + (1 - a) * self._rtt_s
            self._cpu_s = cpu_pct if self._cpu_s is None else a * cpu_pct + (1 - a) * self._cpu_s
            rtt_ms, cpu_pct = self._rtt_s, self._cpu_s
        budget = latency_budget(rtt_ms, cpu_pct)
        # Fail-safe: an undefined measurement (NaN) is "no information", not "budget exhausted".
        # Keep the current tier instead of letting NaN comparisons fall through to Tier 1.
        raw = self.active_tier if math.isnan(budget) else target_tier_for_budget(budget)
        changed = False

        if self.enabled:
            if raw == self.active_tier:
                self._pending, self._count = None, 0
            else:
                if raw == self._pending:
                    self._count += 1
                else:
                    self._pending, self._count = raw, 1
                if self._count >= self.hysteresis:
                    self.active_tier = raw
                    self._pending, self._count = None, 0
                    changed = True

        clinical = self.clinical_tier_for(self.active_tier)
        d = Decision(
            cycle=self.cycle, rtt_ms=round(rtt_ms, 2), cpu_pct=round(cpu_pct, 1),
            budget_ms=round(budget, 2), raw_target=raw,
            active_tier=self.active_tier, clinical_tier=clinical,
            changed=changed, hysteresis_count=self._count,
            hysteresis_needed=self.hysteresis, pending_tier=self._pending,
            floor_clamped=clinical != self.active_tier,
        )
        self.history.append(d)
        if len(self.history) > 5000:
            self.history = self.history[-2500:]
        return d

    def tier(self, level: int) -> Tier:
        return TIERS[level]
