"""Tier security suite, part 3: the tier controller (CADA-AASM) under attack and under stress.

Threat: an attacker who can inflate round-trip time or CPU load (delay injection, flooding) tries
to push the gateway onto a weaker tier, to force constant re-keying, or to make the controller
misbehave with malformed measurements.  Properties checked:

  P1  The clinical floor (>= NIST Category 3) holds for EVERY input, including extremes.
  P2  The active tier is always one of the three defined tiers.
  P3  The controller matches an independent reference model of its specification (differential test).
  P4  Re-key storm bound: at most one tier change per HYSTERESIS_CYCLES cycles, whatever the input.
  P5  Delay-injection attack: downgrade takes exactly 3 sustained cycles, the floor holds, recovery works.
  P6  Monotonicity: more delay/CPU never yields a stronger tier.
  P7  A static (non-adaptive) controller can never be moved.
  P8  Undefined measurements (NaN) must not silently downgrade the tier (fail-safe).
  P9  Bounded memory and determinism.

Run:   python -m pytest tests/test_tier_controller_security.py -v
"""
import math
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agile_hq_pqc.core.cada import CadaController, latency_budget, target_tier_for_budget  # noqa: E402
from agile_hq_pqc.core.tiers import (  # noqa: E402
    BUDGET_HIGH, BUDGET_LOW, HYSTERESIS_CYCLES, MIN_SECURITY_TIER, SLA_MS, TIERS)

# FIPS 203 / FIPS 204 NIST security categories of the algorithms each tier selects
KEM_CAT = {"ML-KEM-512": 1, "ML-KEM-768": 3, "ML-KEM-1024": 5}
DSA_CAT = {"ML-DSA-44": 2, "ML-DSA-65": 3, "ML-DSA-87": 5}

finite = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
probe_st = st.tuples(finite, finite)                      # (rtt_ms, cpu_pct) - deliberately unconstrained
seq_st = st.lists(probe_st, min_size=1, max_size=120)
realistic = st.tuples(st.floats(0, 400), st.floats(0, 100))


def run(seq, **kw):
    c = CadaController(**kw)
    return c, [c.decide(r, u) for r, u in seq]


def reference_model(seq, hysteresis=HYSTERESIS_CYCLES, initial=5):
    """Independent re-statement of the specification (report section 7.2, steps 1-5)."""
    active, pending, count, out = initial, None, 0, []
    for rtt, cpu in seq:
        budget = SLA_MS - rtt - 0.5 * cpu
        raw = 5 if budget > BUDGET_HIGH else 3 if budget > BUDGET_LOW else 1
        if raw == active:
            pending, count = None, 0
        else:
            pending, count = (raw, count + 1) if raw == pending else (raw, 1)
            if count >= hysteresis:
                active, pending, count = raw, None, 0
        out.append(active)
    return out


# ======================================================================================
# P1, P2 - safety invariants
# ======================================================================================
class TestSafetyInvariants:
    @settings(max_examples=300, deadline=None)
    @given(seq=seq_st)
    def test_clinical_floor_holds_for_any_input_sequence(self, seq):
        _, decisions = run(seq)
        for d in decisions:
            assert d.clinical_tier >= MIN_SECURITY_TIER
            assert d.floor_clamped == (d.clinical_tier != d.active_tier)

    @settings(max_examples=300, deadline=None)
    @given(seq=seq_st)
    def test_active_tier_is_always_a_defined_tier(self, seq):
        _, decisions = run(seq)
        assert all(d.active_tier in TIERS and d.clinical_tier in TIERS for d in decisions)

    @settings(max_examples=100, deadline=None)
    @given(seq=st.lists(st.sampled_from([(0, 0), (190, 90), (500, 100), (-50, 0), (1e9, 1e9), (150, 40)]),
                        min_size=1, max_size=80))
    def test_clinical_floor_at_extreme_values(self, seq):
        _, decisions = run(seq)
        assert min(d.clinical_tier for d in decisions) >= MIN_SECURITY_TIER

    def test_clinical_suite_is_nist_category_3_or_better_across_the_whole_rtt_cpu_plane(self):
        """End to end: for every (RTT, CPU) operating point, once the controller has settled, the suite
        protecting raw clinical data uses a Category >= 3 KEM and signature."""
        for rtt in range(0, 401, 10):
            for cpu in range(0, 101, 10):
                c = CadaController()
                for _ in range(HYSTERESIS_CYCLES + 1):
                    d = c.decide(rtt, cpu)
                t = TIERS[d.clinical_tier]
                assert KEM_CAT[t.kem] >= 3 and DSA_CAT[t.dsa] >= 3, (rtt, cpu, t.suite)

    def test_floor_default_is_nist_category_3(self):
        assert MIN_SECURITY_TIER == 3
        assert CadaController().min_clinical_tier == 3

    def test_floor_holds_on_a_non_adaptive_controller_too(self):
        c = CadaController(enabled=False, initial_tier=1)           # misconfigured weak static tier
        assert c.decide(0, 0).clinical_tier == MIN_SECURITY_TIER


# ======================================================================================
# P3 - differential test against the specification
# ======================================================================================
class TestSpecConformance:
    @settings(max_examples=400, deadline=None)
    @given(seq=st.lists(realistic, min_size=1, max_size=150))
    def test_controller_matches_reference_model(self, seq):
        _, decisions = run(seq)
        assert [d.active_tier for d in decisions] == reference_model(seq)

    @settings(max_examples=200, deadline=None)
    @given(seq=seq_st)
    def test_controller_matches_reference_model_on_extreme_inputs(self, seq):
        _, decisions = run(seq)
        assert [d.active_tier for d in decisions] == reference_model(seq)

    @settings(max_examples=200, deadline=None)
    @given(seq=st.lists(realistic, min_size=1, max_size=100))
    def test_a_change_needs_three_consecutive_identical_proposals(self, seq):
        _, decisions = run(seq)
        for i, d in enumerate(decisions):
            if d.changed:
                assert i >= HYSTERESIS_CYCLES - 1
                last = {x.raw_target for x in decisions[i - HYSTERESIS_CYCLES + 1: i + 1]}
                assert len(last) == 1 and last.pop() == d.active_tier

    def test_threshold_edges_are_exact(self):
        assert target_tier_for_budget(BUDGET_HIGH + 1e-9) == 5
        assert target_tier_for_budget(BUDGET_HIGH) == 3
        assert target_tier_for_budget(BUDGET_LOW + 1e-9) == 3
        assert target_tier_for_budget(BUDGET_LOW) == 1

    def test_budget_formula(self):
        assert latency_budget(50, 20) == pytest.approx(200 - 50 - 10)


# ======================================================================================
# P4 - re-key storm bound
# ======================================================================================
class TestRekeyStormBound:
    @settings(max_examples=300, deadline=None)
    @given(seq=seq_st)
    def test_at_most_one_tier_change_per_three_cycles_for_any_input(self, seq):
        _, decisions = run(seq)
        changes = sum(d.changed for d in decisions)
        assert changes <= len(seq) // HYSTERESIS_CYCLES

    def test_worst_case_adversary_gets_at_most_one_handshake_per_three_cycles(self):
        """Blocks of three hostile / three calm cycles are the strongest flapping input: the bound
        n // 3 is reached (it is tight) but never exceeded."""
        n = 60
        calm, storm = (5, 5), (190, 90)
        seq = [(storm if (i // HYSTERESIS_CYCLES) % 2 == 0 else calm) for i in range(n)]
        _, damped = run(seq)
        # the first block of three hostile cycles moves 5 -> 1, the next calm block moves 1 -> 5, ...
        assert sum(d.changed for d in damped) == n // HYSTERESIS_CYCLES

    def test_filter_removes_a_cycle_by_cycle_flapping_attack(self):
        """Alternating every cycle would cause a handshake on every cycle without the filter."""
        seq = [(190, 90), (5, 5)] * 30
        _, damped = run(seq)
        _, undamped = run(seq, hysteresis=1)
        assert sum(d.changed for d in damped) == 0
        assert sum(d.changed for d in undamped) >= len(seq) - 1

    def test_period_two_oscillation_causes_no_tier_change_at_all(self):
        seq = [(190, 90), (5, 5)] * 40
        _, decisions = run(seq)
        assert sum(d.changed for d in decisions) == 0


# ======================================================================================
# P5 - delay-injection (downgrade) attack
# ======================================================================================
class TestDelayInjectionAttack:
    def test_sustained_delay_downgrades_research_after_exactly_three_cycles_and_floor_holds(self):
        c = CadaController()
        for _ in range(5):
            c.decide(5, 5)                                       # calm
        tiers, clinical = [], []
        for _ in range(10):
            d = c.decide(190, 80)                                # attacker inflates RTT and CPU
            tiers.append(d.active_tier)
            clinical.append(d.clinical_tier)
        assert tiers[:HYSTERESIS_CYCLES - 1] == [5] * (HYSTERESIS_CYCLES - 1)   # not instant
        assert tiers[HYSTERESIS_CYCLES - 1] == 1                                # exactly 3 cycles
        assert min(clinical) == MIN_SECURITY_TIER                               # raw PHI never below Cat 3

    def test_short_delay_bursts_cannot_downgrade(self):
        c = CadaController()
        for _ in range(20):
            for _ in range(HYSTERESIS_CYCLES - 1):
                c.decide(190, 80)                                # burst one cycle too short
            c.decide(5, 5)
        assert c.active_tier == 5

    def test_recovery_after_the_attack_ends(self):
        c = CadaController()
        for _ in range(6):
            c.decide(190, 80)
        assert c.active_tier == 1
        for _ in range(HYSTERESIS_CYCLES):
            c.decide(5, 5)
        assert c.active_tier == 5

    def test_attacker_cannot_hold_a_weak_tier_without_continuing_the_attack(self):
        c = CadaController()
        for _ in range(6):
            c.decide(190, 80)
        for _ in range(2 * HYSTERESIS_CYCLES):
            d = c.decide(5, 5)
        assert d.active_tier == 5

    def test_cpu_exhaustion_alone_is_enough_but_still_respects_the_floor(self):
        c = CadaController()
        for _ in range(HYSTERESIS_CYCLES):
            d = c.decide(0, 100)                                 # budget = 150 -> still tier 5
        assert d.active_tier == 5
        for _ in range(HYSTERESIS_CYCLES):
            d = c.decide(160, 100)                               # budget = -10
        assert d.active_tier == 1 and d.clinical_tier == MIN_SECURITY_TIER


# ======================================================================================
# P6 - monotonicity
# ======================================================================================
class TestMonotonicity:
    @settings(max_examples=300, deadline=None)
    @given(rtt=st.floats(0, 500), cpu=st.floats(0, 100), d_rtt=st.floats(0, 200), d_cpu=st.floats(0, 100))
    def test_more_delay_or_cpu_never_gives_a_stronger_target_tier(self, rtt, cpu, d_rtt, d_cpu):
        base = target_tier_for_budget(latency_budget(rtt, cpu))
        worse = target_tier_for_budget(latency_budget(rtt + d_rtt, cpu + d_cpu))
        assert worse <= base

    @settings(max_examples=200, deadline=None)
    @given(a=st.floats(-500, 500), b=st.floats(-500, 500))
    def test_target_tier_is_monotone_in_budget(self, a, b):
        lo, hi = sorted((a, b))
        assert target_tier_for_budget(lo) <= target_tier_for_budget(hi)


# ======================================================================================
# P7 - static baseline
# ======================================================================================
class TestStaticBaseline:
    @settings(max_examples=150, deadline=None)
    @given(seq=seq_st, start=st.sampled_from([1, 3, 5]))
    def test_static_controller_never_changes_tier(self, seq, start):
        c, decisions = run(seq, enabled=False, initial_tier=start)
        assert c.active_tier == start and not any(d.changed for d in decisions)


# ======================================================================================
# P8 - malformed / hostile measurements
# ======================================================================================
class TestMalformedMeasurements:
    def test_nan_measurements_do_not_downgrade_the_tier(self):
        """NaN means 'no valid measurement'. A fail-safe controller keeps the last good tier; it must
        not read NaN as 'budget exhausted' and fall to the weakest suite (a one-packet-per-cycle
        downgrade attack for anyone who can corrupt the probe)."""
        for bad in [(math.nan, 10.0), (10.0, math.nan), (math.nan, math.nan)]:
            c = CadaController()
            for _ in range(6 * HYSTERESIS_CYCLES):
                d = c.decide(*bad)
            assert d.active_tier == 5, f"probe {bad} downgraded the tier to {d.active_tier}"

    def test_nan_does_not_corrupt_later_decisions(self):
        c = CadaController()
        for _ in range(6):
            c.decide(math.nan, math.nan)
        for _ in range(HYSTERESIS_CYCLES):
            d = c.decide(190, 80)
        assert d.active_tier == 1                              # real stress is still honoured
        for _ in range(HYSTERESIS_CYCLES):
            d = c.decide(5, 5)
        assert d.active_tier == 5

    def test_nan_does_not_poison_the_smoothing_filter(self):
        """With EWMA smoothing on, one NaN must not stick in the filter state forever."""
        c = CadaController(smoothing_alpha=0.5)
        c.decide(5, 5)
        c.decide(math.nan, math.nan)
        for _ in range(3 * HYSTERESIS_CYCLES):
            d = c.decide(190, 80)
        assert d.active_tier == 1 and not math.isnan(d.budget_ms)

    @pytest.mark.parametrize("bad", [(math.inf, 0), (0, math.inf), (-math.inf, 0), (math.inf, math.inf)])
    def test_infinite_measurements_never_break_the_floor_or_crash(self, bad):
        c = CadaController()
        for _ in range(5):
            d = c.decide(*bad)
        assert d.clinical_tier >= MIN_SECURITY_TIER and d.active_tier in TIERS

    def test_negative_rtt_clock_skew_cannot_lower_security(self):
        c = CadaController()
        for _ in range(10):
            d = c.decide(-1000, 0)
        assert d.active_tier == 5                              # impossible RTT errs toward MORE security


# ======================================================================================
# P9 - bounded memory, determinism, smoothing
# ======================================================================================
class TestRobustness:
    def test_decision_history_is_bounded(self):
        c = CadaController()
        for i in range(6500):
            c.decide(5 + (i % 3), 5)
        assert len(c.history) <= 5000

    @settings(max_examples=100, deadline=None)
    @given(seq=st.lists(realistic, min_size=1, max_size=80))
    def test_decisions_are_deterministic(self, seq):
        _, a = run(seq)
        _, b = run(seq)
        assert [x.active_tier for x in a] == [x.active_tier for x in b]

    def test_smoothing_filters_a_single_extreme_outlier(self):
        c = CadaController(smoothing_alpha=0.3)
        for _ in range(5):
            c.decide(5, 5)
        c.decide(400, 100)                                    # one hostile sample
        for _ in range(HYSTERESIS_CYCLES):
            c.decide(5, 5)
        assert c.active_tier == 5
