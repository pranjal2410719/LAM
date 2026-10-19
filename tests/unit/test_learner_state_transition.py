"""Unit tests for domain learner state transitions and initial state semantics."""

from datetime import UTC, datetime

import pytest

from lam.domain.events.models import (
    AssessmentMode,
    EventProvenance,
    EventType,
    LearningEvent,
    VerificationSource,
)
from lam.domain.learner_state.models import LearnerConceptState
from lam.domain.mastery.state_transition import apply_learning_event_transition


def _verified_event(
    correctness: bool | None = True,
    assistance_level: int = 0,
    hints_used: int = 0,
    status: str = "verified",
    source: VerificationSource = VerificationSource.ANSWER_KEY,
    no_provenance: bool = False,
) -> LearningEvent:
    prov = None
    if not no_provenance:
        prov = EventProvenance(
            judgment_source=source,
            status=status,
            independently_produced=(assistance_level == 0 and hints_used == 0),
        )
    return LearningEvent(
        event_id="evt_trans_01",
        tenant_id="tenant_trans",
        student_id="student_trans_1",
        session_id="sess_trans",
        concept_ids=["algebra.quadratics"],
        item_id="item_quad_1",
        timestamp=datetime.now(UTC),
        event_type=EventType.ATTEMPT,
        correctness=correctness,
        assistance_level=assistance_level,
        assessment_mode=(
            AssessmentMode.INDEPENDENT if assistance_level == 0 else AssessmentMode.ASSISTED
        ),
        provenance=prov,
    )


def test_first_event_verified_correct_initializes_and_transitions() -> None:
    event = _verified_event(correctness=True)
    state, eligibility, bkt_res = apply_learning_event_transition(
        current_state=None,
        event=event,
        concept_id="algebra.quadratics",
    )
    assert eligibility.is_eligible_for_bkt is True
    assert bkt_res is not None
    assert bkt_res.transition_applied is True
    # Prior is 0.10, Step 1 posterior is 0.3333, Step 2 transition is ~0.4667
    assert pytest.approx(state.independent_mastery, abs=1e-3) == 0.467
    assert pytest.approx(state.concept_mastery, abs=1e-3) == 0.467
    assert state.total_events_count == 1
    assert state.independent_attempts_count == 1
    assert state.consecutive_independent_successes == 1
    assert state.assisted_attempts_count == 0
    assert state.bkt_parameter_version == "bkt_v1_baseline"
    # Uncertainty with 1 attempt: 1 / sqrt(2) ≈ 0.7071
    assert pytest.approx(state.uncertainty, abs=1e-3) == 0.707


def test_first_event_verified_incorrect_transitions_from_prior() -> None:
    event = _verified_event(correctness=False)
    state, eligibility, bkt_res = apply_learning_event_transition(
        current_state=None,
        event=event,
        concept_id="algebra.quadratics",
    )
    assert eligibility.is_eligible_for_bkt is True
    assert bkt_res is not None
    # Prior 0.10, incorrect observation -> ~0.2110
    assert pytest.approx(state.independent_mastery, abs=1e-3) == 0.211
    assert state.consecutive_independent_successes == 0
    assert state.independent_attempts_count == 1
    assert state.total_events_count == 1
    assert state.bkt_parameter_version == "bkt_v1_baseline"


def test_first_event_assisted_does_not_alter_independent_mastery() -> None:
    event = _verified_event(correctness=True, assistance_level=3, hints_used=1)
    state, eligibility, bkt_res = apply_learning_event_transition(
        current_state=None,
        event=event,
        concept_id="algebra.quadratics",
    )
    assert eligibility.is_assisted is True
    assert eligibility.is_eligible_for_bkt is False
    assert bkt_res is None
    # Must remain at initial prior 0.10, NOT 0.0 or higher
    assert state.independent_mastery == 0.10
    assert state.concept_mastery == 0.10
    assert state.independent_attempts_count == 0
    assert state.consecutive_independent_successes == 0
    assert state.assisted_attempts_count == 1
    assert state.assisted_performance == 0.10
    assert state.total_events_count == 1
    # Uncertainty with 0 independent attempts is 1.0 (maximum uncertainty)
    assert state.uncertainty == 1.0


def test_first_event_missing_correctness_preserves_initial_prior() -> None:
    event = _verified_event(correctness=None)
    state, eligibility, bkt_res = apply_learning_event_transition(
        current_state=None,
        event=event,
        concept_id="algebra.quadratics",
    )
    assert eligibility.is_eligible_for_bkt is False
    assert bkt_res is None
    assert state.independent_mastery == 0.10
    assert state.independent_attempts_count == 0
    assert state.total_events_count == 1
    assert state.uncertainty == 1.0


def test_first_event_provisional_provenance_preserves_initial_prior() -> None:
    event = _verified_event(correctness=True, status="provisional")
    state, eligibility, bkt_res = apply_learning_event_transition(
        current_state=None,
        event=event,
        concept_id="algebra.quadratics",
    )
    assert eligibility.is_eligible_for_bkt is False
    assert state.independent_mastery == 0.10
    assert state.independent_attempts_count == 0
    assert state.total_events_count == 1
    assert state.uncertainty == 1.0


def test_first_event_missing_provenance_preserves_initial_prior() -> None:
    event = _verified_event(correctness=True, no_provenance=True)
    state, eligibility, bkt_res = apply_learning_event_transition(
        current_state=None,
        event=event,
        concept_id="algebra.quadratics",
    )
    assert eligibility.is_eligible_for_bkt is False
    assert state.independent_mastery == 0.10
    assert state.independent_attempts_count == 0
    assert state.total_events_count == 1
    assert state.uncertainty == 1.0


def test_subsequent_assisted_attempt_preserves_previous_independent_mastery() -> None:
    current = LearnerConceptState(
        tenant_id="tenant_trans",
        student_id="student_trans_1",
        concept_id="algebra.quadratics",
        concept_mastery=0.467,
        independent_mastery=0.467,
        assisted_performance=0.0,
        uncertainty=0.707,
        total_events_count=1,
        independent_attempts_count=1,
        assisted_attempts_count=0,
        consecutive_independent_successes=1,
        bkt_parameter_version="bkt_v1_baseline",
    )
    event = _verified_event(correctness=True, assistance_level=2)
    new_state, eligibility, bkt_res = apply_learning_event_transition(
        current_state=current,
        event=event,
        concept_id="algebra.quadratics",
    )
    assert eligibility.is_assisted is True
    assert new_state.independent_mastery == 0.467
    assert new_state.independent_attempts_count == 1
    assert new_state.assisted_attempts_count == 1
    assert new_state.total_events_count == 2
    assert new_state.assisted_performance == 0.10
    assert new_state.state_version == 2
