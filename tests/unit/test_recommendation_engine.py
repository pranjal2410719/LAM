"""Unit test suite for deterministic next-action recommendation engine (Decision D-06 PROPOSED)."""

import pytest

from lam.domain.recommendation.engine import RecommendationEngine
from lam.domain.recommendation.models import (
    ActionType,
    PriorityTier,
    RecommendationContext,
)


@pytest.fixture
def engine() -> RecommendationEngine:
    return RecommendationEngine()


def _make_context(
    concept_id: str = "math.fractions",
    independent_mastery: float = 0.50,
    uncertainty: float = 0.50,
    consecutive_successes: int = 1,
    consecutive_failures: int = 0,
    prerequisite_readiness: bool | None = None,
    retention_strength: float | None = None,
    active_misconception: str | None = None,
    misconception_status: str | None = None,
    prerequisite_concept_id: str | None = None,
    assisted_attempts: int = 0,
    independent_attempts: int = 2,
) -> RecommendationContext:
    return RecommendationContext(
        concept_id=concept_id,
        concept_mastery=independent_mastery,
        independent_mastery=independent_mastery,
        assisted_performance=0.0,
        uncertainty=uncertainty,
        total_events_count=independent_attempts + assisted_attempts,
        independent_attempts_count=independent_attempts,
        assisted_attempts_count=assisted_attempts,
        consecutive_independent_successes=consecutive_successes,
        consecutive_failures=consecutive_failures,
        prerequisite_readiness=prerequisite_readiness,
        retention_strength=retention_strength,
        active_misconception_id=active_misconception,
        misconception_status=misconception_status,
        prerequisite_concept_id=prerequisite_concept_id,
        state_version=1,
    )


def test_fallback_when_context_is_none(engine: RecommendationEngine) -> None:
    decision = engine.evaluate(context=None, target_concept_id="math.geometry")
    assert decision.action_type == ActionType.DIAGNOSTIC_PROBE
    assert decision.priority_tier == PriorityTier.FALLBACK
    assert decision.safe_fallback is True
    assert decision.assistance_level == 2
    assert decision.reason_code == "no_prior_learner_state"


def test_tier_1_safety_stop_on_repeated_failures(engine: RecommendationEngine) -> None:
    ctx = _make_context(consecutive_failures=3, independent_mastery=0.2)
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.TEACHER_INTERVENTION
    assert decision.priority_tier == PriorityTier.TIER_1_SAFETY_STOP
    assert decision.assistance_level == 8
    assert decision.reason_code == "persistent_failure_safety_stop"


def test_tier_1_safety_overrides_tier_2_prerequisite_gap(engine: RecommendationEngine) -> None:
    # Conflicting priorities: failures = 3 AND prerequisite_readiness is False
    ctx = _make_context(consecutive_failures=3, prerequisite_readiness=False)
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    # Tier 1 must win over Tier 2!
    assert decision.action_type == ActionType.TEACHER_INTERVENTION
    assert decision.priority_tier == PriorityTier.TIER_1_SAFETY_STOP


def test_tier_2_blocking_prerequisite_gap(engine: RecommendationEngine) -> None:
    ctx = _make_context(
        prerequisite_readiness=False,
        prerequisite_concept_id="math.basic_division",
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.PREREQUISITE_REMEDIATION
    assert decision.target_concept_id == "math.basic_division"
    assert decision.priority_tier == PriorityTier.TIER_2_BLOCKING_PREREQUISITE
    assert decision.assistance_level == 5


def test_tier_2_prerequisite_overrides_tier_3_misconception(engine: RecommendationEngine) -> None:
    ctx = _make_context(
        prerequisite_readiness=False,
        active_misconception="misc_inverted_fraction",
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.PREREQUISITE_REMEDIATION


def test_tier_3_confirmed_misconception(engine: RecommendationEngine) -> None:
    ctx = _make_context(
        active_misconception="misc_add_denominators",
        misconception_status="confirmed",
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.DIAGNOSTIC_PROBE
    assert decision.priority_tier == PriorityTier.TIER_3_CONFIRMED_MISCONCEPTION
    assert decision.assistance_level == 2
    assert decision.metadata["misconception_id"] == "misc_add_denominators"


def test_tier_3_not_triggered_for_open_candidate_hypothesis(engine: RecommendationEngine) -> None:
    # A single error or unconfirmed hypothesis in 'open' status must NOT disrupt learning flow
    ctx = _make_context(
        independent_mastery=0.65,
        active_misconception="misc_add_denominators",
        misconception_status="open",
        independent_attempts=5,
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    # Must bypass Tier 3 and fall through to standard practice (Tier 7)
    assert decision.action_type == ActionType.INDEPENDENT_PRACTICE
    assert decision.priority_tier == PriorityTier.TIER_7_DIFFICULTY_FIT_PRACTICE


def test_tier_3_not_triggered_for_retired_hypothesis(engine: RecommendationEngine) -> None:
    ctx = _make_context(
        independent_mastery=0.65,
        active_misconception="misc_add_denominators",
        misconception_status="retired",
        independent_attempts=5,
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.INDEPENDENT_PRACTICE
    assert decision.priority_tier == PriorityTier.TIER_7_DIFFICULTY_FIT_PRACTICE


def test_tier_4_overdue_retrieval(engine: RecommendationEngine) -> None:
    ctx = _make_context(retention_strength=0.35)
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.DELAYED_RETRIEVAL_REVIEW
    assert decision.priority_tier == PriorityTier.TIER_4_OVERDUE_RETRIEVAL
    assert decision.assistance_level == 0


def test_tier_5_mastery_verification_due_to_high_uncertainty(engine: RecommendationEngine) -> None:
    # High mastery (0.88), but uncertainty is 0.25 (> 0.15)
    ctx = _make_context(
        independent_mastery=0.88,
        uncertainty=0.25,
        consecutive_successes=4,
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.MASTERY_VERIFICATION
    assert decision.priority_tier == PriorityTier.TIER_5_MASTERY_VERIFICATION
    assert decision.assistance_level == 0


def test_tier_5_mastery_verification_due_to_low_consecutive_successes(
    engine: RecommendationEngine,
) -> None:
    # High mastery (0.90), low uncertainty (0.12), but only 1 consecutive success (< 3)
    ctx = _make_context(
        independent_mastery=0.90,
        uncertainty=0.12,
        consecutive_successes=1,
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.MASTERY_VERIFICATION


def test_tier_6_curriculum_progression_when_all_conditions_met(
    engine: RecommendationEngine,
) -> None:
    # High mastery (0.91), low uncertainty (0.14 <= 0.15), consecutive successes = 3
    ctx = _make_context(
        independent_mastery=0.91,
        uncertainty=0.14,
        consecutive_successes=3,
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.ADVANCE_TO_NEXT_CONCEPT
    assert decision.priority_tier == PriorityTier.TIER_6_CURRICULUM_PROGRESSION
    assert decision.reason_code == "durable_mastery_confirmed"


def test_tier_7_low_mastery_triggers_worked_example(engine: RecommendationEngine) -> None:
    ctx = _make_context(independent_mastery=0.25)
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.WORKED_EXAMPLE
    assert decision.assistance_level == 5
    assert decision.priority_tier == PriorityTier.TIER_7_DIFFICULTY_FIT_PRACTICE


def test_tier_7_scaffolded_practice_when_assisted_attempts_dominate(
    engine: RecommendationEngine,
) -> None:
    ctx = _make_context(
        independent_mastery=0.60,
        assisted_attempts=4,
        independent_attempts=2,
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.SCAFFOLDED_PRACTICE
    assert decision.assistance_level == 3


def test_tier_7_standard_independent_practice(engine: RecommendationEngine) -> None:
    ctx = _make_context(
        independent_mastery=0.65,
        assisted_attempts=1,
        independent_attempts=5,
    )
    decision = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert decision.action_type == ActionType.INDEPENDENT_PRACTICE
    assert decision.assistance_level == 0


def test_deterministic_reproducibility(engine: RecommendationEngine) -> None:
    ctx = _make_context(independent_mastery=0.65)
    d1 = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    d2 = engine.evaluate(context=ctx, target_concept_id="math.fractions")
    assert d1.action_type == d2.action_type
    assert d1.assistance_level == d2.assistance_level
    assert d1.priority_tier == d2.priority_tier
    assert d1.reason_code == d2.reason_code
    assert d1.uncertainty == d2.uncertainty
