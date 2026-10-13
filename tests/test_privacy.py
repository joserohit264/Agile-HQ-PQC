import numpy as np
from agile_hq_pqc.privacy.data import synthetic_ecg, synthetic_ehr
from agile_hq_pqc.privacy.dp import PrivacyAccountant, laplace_mechanism
from agile_hq_pqc.privacy.mondrian import mondrian_anonymize, verify_k_l


def test_dp_noise_scales_inversely_with_epsilon():
    _, x = synthetic_ecg(seed=1)
    rng = np.random.default_rng(0)
    lo = laplace_mechanism(x, 0.1, rng=rng).rmse
    hi = laplace_mechanism(x, 1.0, rng=rng).rmse
    assert lo > 5 * hi                      # ~10x in expectation


def test_dp_rejects_bad_epsilon():
    import pytest
    with pytest.raises(ValueError):
        laplace_mechanism(np.zeros(3), 0)


def test_accountant():
    a = PrivacyAccountant(1.0)
    assert a.charge(0.6) and not a.charge(0.6) and abs(a.remaining - 0.4) < 1e-9


def test_mondrian_satisfies_k_l_for_all_tiers():
    data = synthetic_ehr(300, seed=3)
    for k, l in ((2, 2), (3, 2), (5, 3)):
        r = mondrian_anonymize(data, k, l)
        assert r.satisfied and r.min_class_size >= k and len(r.rows) == len(data)
        assert verify_k_l(r.rows, k, l, ("age", "zip", "sex"), "diagnosis")


def test_stronger_k_loses_more_information():
    data = synthetic_ehr(300, seed=3)
    assert mondrian_anonymize(data, 10, 3).info_loss > mondrian_anonymize(data, 2, 2).info_loss


def test_no_direct_identifiers_and_generalisation_shape():
    r = mondrian_anonymize(synthetic_ehr(200, seed=5), 3, 2)
    assert all("patient_id" not in row for row in r.rows)
    assert any("-" in row["age"] for row in r.rows) and any("*" in row["zip"] for row in r.rows)


def test_too_small_table_is_suppressed_not_leaked():
    r = mondrian_anonymize(synthetic_ehr(4, seed=1), 5, 3)
    assert not r.satisfied and r.rows == []
