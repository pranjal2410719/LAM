"""Unit tests for pure Python Bayesian Knowledge Tracing (BKT) domain engine."""

import pytest

from lam.domain.mastery.bkt import (
    DEFAULT_BKT_VERSION,
    BKTEngine,
    BKTParameters,
    compute_operational_uncertainty,
)


def test_bkt_default_parameters() -> None:
    """Verifies baseline candidate parameters match Decision D-02."""
    params = BKTParameters()
    assert params.p_l0 == 0.10
    assert params.p_transit == 0.20
    assert params.p_guess == 0.20
    assert params.p_slip == 0.10
    assert params.version == DEFAULT_BKT_VERSION


def test_bkt_parameter_validation_rejects_invalid_values() -> None:
    """Verifies bounds checking and non-degeneracy validation on BKT parameters."""
    # Invalid p_l0
    with pytest.raises(ValueError, match="p_l0 must be in open interval"):
        BKTParameters(p_l0=0.0)
    with pytest.raises(ValueError, match="p_l0 must be in open interval"):
        BKTParameters(p_l0=1.0)

    # Invalid p_transit
    with pytest.raises(ValueError, match="p_transit must be in half-open interval"):
        BKTParameters(p_transit=1.0)
    with pytest.raises(ValueError, match="p_transit must be in half-open interval"):
        BKTParameters(p_transit=-0.1)

    # Broken discrimination: p_guess >= 0.50 or p_slip >= 0.50
    with pytest.raises(ValueError, match="p_guess must be in"):
        BKTParameters(p_guess=0.55)
    with pytest.raises(ValueError, match="p_guess must be in"):
        BKTParameters(p_guess=-0.05)
    with pytest.raises(ValueError, match="p_slip must be in"):
        BKTParameters(p_slip=0.50)
    with pytest.raises(ValueError, match="p_slip must be in"):
        BKTParameters(p_slip=-0.01)


def test_d02_published_deterministic_test_vectors() -> None:
    """Regression test: Verifies the exact 4-step sequence published in Decision Record D-02.

    Sequence:
    - Step 0: Initial state = 0.1000
    - Step 1: Correct (1)   -> Interm: 0.3333, Post: 0.4667
    - Step 2: Incorrect (0) -> Interm: 0.0986, Post: 0.2789
    - Step 3: Correct (1)   -> Interm: 0.6351, Post: 0.7081
    """
    engine = BKTEngine()

    # Step 0: Prior is p_l0 = 0.1000
    step0_prior = engine.params.p_l0
    assert step0_prior == 0.1000

    # Step 1: Observation = Correct (1)
    res1 = engine.update(prior=step0_prior, correctness=True, is_assisted=False)
    assert res1.transition_applied is True
    assert res1.intermediate_posterior is not None
    # 0.10 * 0.90 / (0.10 * 0.90 + 0.90 * 0.20) = 0.09 / 0.27 = 1/3 ≈ 0.333333
    assert pytest.approx(res1.intermediate_posterior, abs=1e-4) == 0.3333
    # 1/3 + (2/3 * 0.20) = 7/15 ≈ 0.466667
    assert pytest.approx(res1.posterior_mastery, abs=1e-4) == 0.4667

    # Step 2: Observation = Incorrect (0)
    res2 = engine.update(prior=res1.posterior_mastery, correctness=False, is_assisted=False)
    assert res2.transition_applied is True
    assert res2.intermediate_posterior is not None
    # (7/15 * 0.10) / [(7/15 * 0.10) + (8/15 * 0.80)] = 0.07 / 0.71 ≈ 0.09859
    assert pytest.approx(res2.intermediate_posterior, abs=1e-4) == 0.0986
    # 0.09859 + (1 - 0.09859) * 0.20 ≈ 0.27887
    assert pytest.approx(res2.posterior_mastery, abs=1e-4) == 0.2789

    # Step 3: Observation = Correct (1)
    res3 = engine.update(prior=res2.posterior_mastery, correctness=True, is_assisted=False)
    assert res3.transition_applied is True
    assert res3.intermediate_posterior is not None
    # ≈ 0.635078
    assert pytest.approx(res3.intermediate_posterior, abs=1e-4) == 0.6351
    # ≈ 0.70806
    assert pytest.approx(res3.posterior_mastery, abs=1e-4) == 0.7081


def test_assisted_attempt_bypasses_bkt_transition() -> None:
    """Non-negotiable rule: Correct or incorrect answers with scaffolding MUST NOT advance

    or update BKT independent mastery.
    """
    engine = BKTEngine()
    prior = 0.4500

    # Assisted correct
    res_assisted_correct = engine.update(prior=prior, correctness=True, is_assisted=True)
    assert res_assisted_correct.transition_applied is False
    assert res_assisted_correct.posterior_mastery == prior
    assert res_assisted_correct.intermediate_posterior is None
    assert res_assisted_correct.reason == "assisted_attempt_excluded"

    # Assisted incorrect
    res_assisted_incorrect = engine.update(prior=prior, correctness=False, is_assisted=True)
    assert res_assisted_incorrect.transition_applied is False
    assert res_assisted_incorrect.posterior_mastery == prior
    assert res_assisted_incorrect.reason == "assisted_attempt_excluded"


def test_missing_correctness_signal_bypasses_bkt() -> None:
    """Non-coercion rule: None correctness (unscored events) leaves BKT mastery unchanged."""
    engine = BKTEngine()
    prior = 0.5500

    res = engine.update(prior=prior, correctness=None, is_assisted=False)
    assert res.transition_applied is False
    assert res.posterior_mastery == prior
    assert res.intermediate_posterior is None
    assert res.reason == "missing_correctness_signal"


def test_boundary_values_and_numerical_stability() -> None:
    """Verifies behavior at mathematical probability boundaries [0.0, 1.0]."""
    engine = BKTEngine()

    # Prior at exactly 0.0
    res_zero = engine.update(prior=0.0, correctness=True, is_assisted=False)
    assert res_zero.transition_applied is True
    assert 0.0 <= res_zero.posterior_mastery <= 1.0

    # Prior at exactly 1.0
    res_one = engine.update(prior=1.0, correctness=True, is_assisted=False)
    assert res_one.transition_applied is True
    assert res_one.intermediate_posterior == 1.0
    assert res_one.posterior_mastery == 1.0

    # Determinism check
    res_a = engine.update(prior=0.35, correctness=True, is_assisted=False)
    res_b = engine.update(prior=0.35, correctness=True, is_assisted=False)
    assert res_a.posterior_mastery == res_b.posterior_mastery


def test_operational_uncertainty_threshold_arithmetic() -> None:
    """Verifies Decision D-01 uncertainty arithmetic:

    U(n) = min(1.0, 1.0 / sqrt(n + 1))
    At n = 43: U ≈ 0.15076 (fails <= 0.15)
    At n = 44: U ≈ 0.14907 (passes <= 0.15)
    """
    assert compute_operational_uncertainty(0) == 1.0
    assert compute_operational_uncertainty(3) == 0.50

    u_43 = compute_operational_uncertainty(43)
    assert u_43 > 0.15
    assert pytest.approx(u_43, abs=1e-5) == 0.15076

    u_44 = compute_operational_uncertainty(44)
    assert u_44 <= 0.15
    assert pytest.approx(u_44, abs=1e-5) == 0.14907
