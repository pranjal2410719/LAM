"""Unit tests for the Spaced Retrieval Review Scheduler (M2-03)."""

from datetime import UTC, datetime, timedelta

import pytest

from lam.domain.learner_state.models import LearnerConceptState
from lam.domain.retrieval.models import ReviewDuePriority
from lam.domain.retrieval.scheduler import SpacedRetrievalScheduler


@pytest.fixture
def scheduler() -> SpacedRetrievalScheduler:
    return SpacedRetrievalScheduler()


def _make_state(
    concept_id: str = "math.fractions.addition",
    consecutive_successes: int = 1,
    last_interaction_delta_days: float = 0.0,
    total_events: int = 2,
    assisted_attempts: int = 0,
    independent_attempts: int = 2,
    concept_mastery: float = 0.80,
    reference_now: datetime | None = None,
) -> LearnerConceptState:
    now = reference_now or datetime.now(UTC)
    last_reviewed = now - timedelta(days=last_interaction_delta_days)
    return LearnerConceptState(
        tenant_id="tenant_ret_01",
        student_id="student_ret_01",
        concept_id=concept_id,
        concept_mastery=concept_mastery,
        independent_mastery=concept_mastery,
        assisted_performance=0.0,
        uncertainty=0.10,
        total_events_count=total_events,
        independent_attempts_count=independent_attempts,
        assisted_attempts_count=assisted_attempts,
        consecutive_independent_successes=consecutive_successes,
        retention_strength=1.0,
        last_practiced_at=last_reviewed,
        created_at=last_reviewed,
        state_version=1,
    )


def test_interval_progression(scheduler: SpacedRetrievalScheduler) -> None:
    # 0 consecutive unassisted successes -> 1 day
    assert scheduler.compute_interval_days(0, 0, 0) == 1.0
    # 1 success -> 1 day
    assert scheduler.compute_interval_days(1, 0, 1) == 1.0
    # 2 successes -> 3 days
    assert scheduler.compute_interval_days(2, 0, 2) == 3.0
    # 3 successes -> 7 days
    assert scheduler.compute_interval_days(3, 0, 3) == 7.0
    # 4 successes -> 14 days
    assert scheduler.compute_interval_days(4, 0, 4) == 14.0
    # 5 successes -> 30 days
    assert scheduler.compute_interval_days(5, 0, 5) == 30.0
    # 6+ successes -> 60 days
    assert scheduler.compute_interval_days(6, 0, 6) == 60.0


def test_assisted_attempts_scale_interval_conservatively(
    scheduler: SpacedRetrievalScheduler,
) -> None:
    # 3 successes normally 7 days, but assisted attempts dominate (assisted=5, indep=2)
    # Scaled by 0.70 => 4.9 days
    interval = scheduler.compute_interval_days(
        3, assisted_attempts_count=5, independent_attempts_count=2
    )
    assert pytest.approx(interval, abs=1e-2) == 4.9


def test_retention_exponential_decay(scheduler: SpacedRetrievalScheduler) -> None:
    # At t = 0, retention = 1.0
    assert scheduler.estimate_retention(0.0, 7.0) == 1.0

    # At t = interval (7 days), calibrated retention is ~0.85
    r_interval = scheduler.estimate_retention(7.0, 7.0)
    assert pytest.approx(r_interval, abs=1e-2) == 0.85

    # At t = 2 * interval (14 days), retention decays further (~0.72)
    r_double = scheduler.estimate_retention(14.0, 7.0)
    assert r_double < 0.75

    # At t = 4 * interval (28 days), retention drops into critical overdue (< 0.55)
    r_quad = scheduler.estimate_retention(28.0, 7.0)
    assert r_quad < 0.55


def test_schedule_evaluation_classifies_priorities(
    scheduler: SpacedRetrievalScheduler,
) -> None:
    now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)

    # Concept A: reviewed just now, interval 3 days -> STABLE
    sA = _make_state(
        "math.algebra.monomials",
        consecutive_successes=2,
        last_interaction_delta_days=0.1,
        reference_now=now,
    )

    # Concept B: reviewed 2.5 days ago, interval 3 days -> UPCOMING (within 48h of 3d)
    sB = _make_state(
        "math.algebra.polynomials",
        consecutive_successes=2,
        last_interaction_delta_days=2.5,
        reference_now=now,
    )

    # Concept C: reviewed 3.5 days ago, interval 3 days -> DUE_FOR_REVIEW (elapsed > interval)
    sC = _make_state(
        "math.algebra.quadratics",
        consecutive_successes=2,
        last_interaction_delta_days=3.5,
        reference_now=now,
    )

    # Concept D: reviewed 10 days ago, interval 3 days -> CRITICAL_OVERDUE (elapsed > 2 * interval)
    sD = _make_state(
        "math.algebra.cubics",
        consecutive_successes=2,
        last_interaction_delta_days=10.0,
        reference_now=now,
    )

    result = scheduler.evaluate_schedules(
        student_id="student_ret_01",
        concept_states=[sA, sB, sC, sD],
        reference_time=now,
    )

    assert result.total_concepts_evaluated == 4
    assert result.reviews_due_count == 2  # sC (due) and sD (critical)

    # Check reviews due ordering: critical overdue first
    due = result.reviews_due
    assert due[0].concept_id == "math.algebra.cubics"
    assert due[0].priority == ReviewDuePriority.CRITICAL_OVERDUE
    assert due[0].is_due is True

    assert due[1].concept_id == "math.algebra.quadratics"
    assert due[1].priority == ReviewDuePriority.DUE_FOR_REVIEW
    assert due[1].is_due is True

    # Check upcoming reviews
    upcoming = result.upcoming_reviews
    assert len(upcoming) == 2
    assert upcoming[0].concept_id == "math.algebra.polynomials"
    assert upcoming[0].priority == ReviewDuePriority.UPCOMING

    assert upcoming[1].concept_id == "math.algebra.monomials"
    assert upcoming[1].priority == ReviewDuePriority.STABLE


def test_concepts_with_zero_attempts_excluded_from_reviews(
    scheduler: SpacedRetrievalScheduler,
) -> None:
    now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)
    s_new = _make_state("math.new.concept", total_events=0, reference_now=now)

    result = scheduler.evaluate_schedules(
        student_id="student_ret_01",
        concept_states=[s_new],
        reference_time=now,
    )
    assert result.reviews_due_count == 0
    assert len(result.reviews_due) == 0
    assert len(result.upcoming_reviews) == 0
