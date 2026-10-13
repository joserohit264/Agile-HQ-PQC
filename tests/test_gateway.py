import pytest
from agile_hq_pqc.gateway import HealthGateway, NetworkModel
from agile_hq_pqc.core.probe import StressInjector
import random


@pytest.fixture()
def gw():
    g = HealthGateway(deterministic_probe=True, epoch_len=4)
    yield g
    g.close()


def test_peacetime_is_tier5_and_within_sla(gw):
    for _ in range(5): e = gw.step()
    assert e["active_tier"] == 5 and not e["clinical"]["sla_violation"]


def test_stress_downshifts_after_hysteresis_then_recovers(gw):
    gw.set_stress("severe")
    tiers = [gw.step()["active_tier"] for _ in range(6)]
    assert tiers[:2] == [5, 5] and tiers[-1] == 1           # needs 3 cycles
    gw.set_stress("calm")
    tiers = [gw.step()["active_tier"] for _ in range(6)]
    assert tiers[-1] == 5


def test_clinical_phi_never_below_tier3(gw):
    gw.set_stress("severe")
    for _ in range(10):
        e = gw.step()
        assert e["clinical"]["tier"] >= 3 and e["clinical_tier"] >= 3
    assert e["active_tier"] == 1 and e["research"]["tier"] == 1


def test_privacy_parameters_follow_tier(gw):
    gw.set_stress("severe")
    for _ in range(6): e = gw.step()
    assert (e["privacy"]["epsilon"], e["privacy"]["k"], e["privacy"]["l"]) == (1.0, 2, 2)


def test_tamper_lab_rejects_every_target(gw):
    gw.step()
    for t in ("ciphertext", "tag", "signature", "iv", "header"):
        r = gw.tamper(t, 3)
        assert r["rejected"] and r["control_untampered_ok"]
    assert gw.counters["tamper_rejected"] == 5
    assert gw.audit.verify()["ok"]


def test_ingest_uses_clinical_session(gw):
    gw.step()
    r = gw.ingest({"pid": "x", "vitals": {"hr": 70}})
    assert r["delivered"] and r["tier"] >= 3


def test_bigger_packets_fragment_more():
    s = StressInjector(); s.set(rtt_ms=100, loss_pct=0)
    a = NetworkModel.delay(300, 100, s, random.Random(1)); b = NetworkModel.delay(4800, 100, s, random.Random(1))
    assert a["fragments"] == 1 and b["fragments"] == 4 and b["network_ms"] > a["network_ms"]
