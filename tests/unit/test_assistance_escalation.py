"""Unit tests for the 9-Level Assistance Escalation State Machine (M2-02)."""

from datetime import UTC, datetime

import pytest

from lam.domain.assistance.engine import AssistanceEngine
from lam.domain.assistance.models import (
    AssistanceLevel,
    AssistanceState,
    TransitionAction,
)
from lam.domain.events.models import (
    AssessmentMode,
    EventProvenance,
    EventType,
    LearningEvent,
    VerificationSource,
)


@pytest.fixture
def engine() -> AssistanceEngine:
    return AssistanceEngine()


@pytest.fixture
def initial_state() -> AssistanceState:
    return AssistanceState(
        student_id="student_asst_01",
        concept_id="math.algebra.equations",
        current_level=AssistanceLevel.LEVEL_0_INDEPENDENT,
    )


def _make_event(
    event_id: str,
    correctness: bool | None,
    assistance_level: int = 0,
    hints_used: int = 0,
) -> LearningEvent:
    return LearningEvent(
        event_id=event_id,
        tenant_id="tenant_asst_01",
        student_id="student_asst_01",
        session_id="sess_01",
        concept_ids=["math.algebra.equations"],
        item_id=f"item_{event_id}",
        timestamp=datetime.now(UTC),
        event_type=EventType.ATTEMPT,
        correctness=correctness,
        assistance_level=assistance_level,
        hints_used=hints_used,
        assessment_mode=(
            AssessmentMode.INDEPENDENT
            if assistance_level == 0 and hints_used == 0
            else AssessmentMode.ASSISTED
        ),
        provenance=EventProvenance(
            judgment_source=VerificationSource.ANSWER_KEY,
            status="verified",
            verifier_reliability="authoritative",
            independently_produced=(assistance_level == 0 and hints_used == 0),
        ),
    )


def test_missing_correctness_maintains_level(
    engine: AssistanceEngine, initial_state: AssistanceState
) -> None:
    e = _make_event("e1", correctness=None)
    res = engine.evaluate(initial_state, e)
    assert res.action == TransitionAction.MAINTAIN
    assert res.new_level == AssistanceLevel.LEVEL_0_INDEPENDENT
    assert res.previous_level == AssistanceLevel.LEVEL_0_INDEPENDENT
    assert initial_state.consecutive_failures == 0


def test_escalation_ladder_on_failures(
    engine: AssistanceEngine, initial_state: AssistanceState
) -> None:
    # Failure 1: from Level 0 -> Level 2
    e1 = _make_event("e1", correctness=False)
    r1 = engine.evaluate(initial_state, e1)
    assert r1.action == TransitionAction.ESCALATE
    assert r1.new_level == AssistanceLevel.LEVEL_2_STRATEGY_HINT
    assert initial_state.consecutive_failures == 1

    # Failure 2: from Level 2 -> Level 5 (Worked Example)
    e2 = _make_event("e2", correctness=False)
    r2 = engine.evaluate(initial_state, e2)
    assert r2.action == TransitionAction.ESCALATE
    assert r2.new_level == AssistanceLevel.LEVEL_5_WORKED_EXAMPLE
    assert initial_state.consecutive_failures == 2

    # Failure 3: safety stop -> Level 8 (Teacher Intervention)
    e3 = _make_event("e3", correctness=False)
    r3 = engine.evaluate(initial_state, e3)
    assert r3.action == TransitionAction.SAFETY_STOP
    assert r3.new_level == AssistanceLevel.LEVEL_8_TEACHER_INTERVENTION
    assert initial_state.consecutive_failures == 3

    # Failure 4: remains at Level 8
    e4 = _make_event("e4", correctness=False)
    r4 = engine.evaluate(initial_state, e4)
    assert r4.action == TransitionAction.SAFETY_STOP
    assert r4.new_level == AssistanceLevel.LEVEL_8_TEACHER_INTERVENTION


def test_independent_success_resets_immediately(
    engine: AssistanceEngine, initial_state: AssistanceState
) -> None:
    # Put student at Level 5
    initial_state.current_level = AssistanceLevel.LEVEL_5_WORKED_EXAMPLE
    initial_state.consecutive_failures = 2

    # Unassisted success
    e = _make_event("e_succ", correctness=True, assistance_level=0)
    res = engine.evaluate(initial_state, e)

    assert res.action == TransitionAction.RESET
    assert res.new_level == AssistanceLevel.LEVEL_0_INDEPENDENT
    assert initial_state.consecutive_failures == 0
    assert initial_state.consecutive_independent_successes == 1


def test_assisted_success_fading_ladder(
    engine: AssistanceEngine, initial_state: AssistanceState
) -> None:
    # Start at Level 5
    initial_state.current_level = AssistanceLevel.LEVEL_5_WORKED_EXAMPLE

    # 1. First assisted success: maintains to consolidate
    e1 = _make_event("e_asst_1", correctness=True, assistance_level=5)
    r1 = engine.evaluate(initial_state, e1)
    assert r1.action == TransitionAction.MAINTAIN
    assert r1.new_level == AssistanceLevel.LEVEL_5_WORKED_EXAMPLE
    assert initial_state.consecutive_assisted_successes == 1

    # 2. Second assisted success: fades to Level 3
    e2 = _make_event("e_asst_2", correctness=True, assistance_level=5)
    r2 = engine.evaluate(initial_state, e2)
    assert r2.action == TransitionAction.DE_ESCALATE
    assert r2.new_level == AssistanceLevel.LEVEL_3_SCAFFOLDED_SUBSTEP
    assert initial_state.consecutive_assisted_successes == 2

    # 3. Third assisted success: fades to Level 2
    e3 = _make_event("e_asst_3", correctness=True, assistance_level=3)
    r3 = engine.evaluate(initial_state, e3)
    assert r3.action == TransitionAction.DE_ESCALATE
    assert r3.new_level == AssistanceLevel.LEVEL_2_STRATEGY_HINT


def test_audit_trail_recorded(engine: AssistanceEngine, initial_state: AssistanceState) -> None:
    e1 = _make_event("e1", correctness=False)
    engine.evaluate(initial_state, e1)

    e2 = _make_event("e2", correctness=True, assistance_level=0)
    engine.evaluate(initial_state, e2)

    assert len(initial_state.audit_trail) == 2
    assert initial_state.audit_trail[0].from_level == AssistanceLevel.LEVEL_0_INDEPENDENT
    assert initial_state.audit_trail[0].to_level == AssistanceLevel.LEVEL_2_STRATEGY_HINT
    assert initial_state.audit_trail[1].to_level == AssistanceLevel.LEVEL_0_INDEPENDENT


def test_deterministic_reproducibility(engine: AssistanceEngine) -> None:
    s1 = AssistanceState("stu_1", "concept_1", AssistanceLevel.LEVEL_0_INDEPENDENT)
    s2 = AssistanceState("stu_1", "concept_1", AssistanceLevel.LEVEL_0_INDEPENDENT)

    e = _make_event("e1", correctness=False)
    r1 = engine.evaluate(s1, e)
    r2 = engine.evaluate(s2, e)

    assert r1.new_level == r2.new_level
    assert r1.action == r2.action
    assert r1.reason_code == r2.reason_code
