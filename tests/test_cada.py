from agile_hq_pqc.core.cada import CadaController, latency_budget, target_tier_for_budget
from agile_hq_pqc.core.tiers import TIERS, MIN_SECURITY_TIER


def test_budget_formula():
    assert latency_budget(50, 20) == 200 - 50 - 10


def test_steering_thresholds():
    assert target_tier_for_budget(80.01) == 5
    assert target_tier_for_budget(80.0) == 3
    assert target_tier_for_budget(40.01) == 3
    assert target_tier_for_budget(40.0) == 1


def test_tier_parameters_match_spec():
    assert (TIERS[5].epsilon, TIERS[5].k, TIERS[5].l) == (0.1, 5, 3)
    assert (TIERS[3].epsilon, TIERS[3].k, TIERS[3].l) == (0.5, 3, 2)
    assert (TIERS[1].epsilon, TIERS[1].k, TIERS[1].l) == (1.0, 2, 2)
    assert TIERS[1].aead == "ChaCha20-Poly1305" and TIERS[5].aead == "AES-256-GCM"


def test_hysteresis_requires_three_consecutive_probes():
    c = CadaController()
    d1 = c.decide(150, 40); d2 = c.decide(150, 40)
    assert d1.active_tier == d2.active_tier == 5 and (d1.hysteresis_count, d2.hysteresis_count) == (1, 2)
    d3 = c.decide(150, 40)
    assert d3.active_tier == 1 and d3.changed


def test_single_spike_does_not_flap():
    c = CadaController()
    c.decide(180, 50)            # spike
    c.decide(10, 5); c.decide(10, 5)
    assert c.active_tier == 5 and c.decide(10, 5).hysteresis_count == 0


def test_interrupted_streak_resets():
    c = CadaController()
    c.decide(150, 40); c.decide(150, 40); c.decide(10, 5); c.decide(150, 40)
    assert c.active_tier == 5


def test_clinical_floor_never_below_tier3():
    c = CadaController()
    for _ in range(5):
        d = c.decide(190, 90)
        assert d.clinical_tier >= MIN_SECURITY_TIER
    assert c.active_tier == 1 and d.clinical_tier == 3 and d.floor_clamped


def test_recovery_reescalates():
    c = CadaController()
    for _ in range(4): c.decide(190, 90)
    for _ in range(4): d = c.decide(5, 2)
    assert d.active_tier == 5


def test_static_baseline_never_moves():
    c = CadaController(enabled=False, initial_tier=5)
    for _ in range(10): c.decide(190, 90)
    assert c.active_tier == 5


def test_noisy_probes_straddling_threshold_stall_without_smoothing_but_not_with():
    seq = [(130, 100), (130, 55)] * 8            # budget alternates 20 / 42.5 ms
    raw = CadaController()
    for r, c in seq: raw.decide(r, c)
    assert raw.active_tier == 5                  # persistence counter keeps resetting
    smooth = CadaController(smoothing_alpha=0.5)
    for r, c in seq: smooth.decide(r, c)
    assert smooth.active_tier == 1               # smoothed budget stays below 40 ms


def test_default_is_unsmoothed_spec_behaviour():
    c = CadaController()
    d = c.decide(150, 40)
    assert d.rtt_ms == 150 and d.cpu_pct == 40
