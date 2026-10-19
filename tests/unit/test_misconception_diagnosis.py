"""Unit tests for the deterministic misconception diagnosis engine (Decision D-04 PROPOSED)."""

from datetime import UTC, datetime

import pytest

from lam.domain.diagnosis.engine import DiagnosisEngine
from lam.domain.diagnosis.models import (
    HypothesisStatus,
    MisconceptionCategory,
    MisconceptionHypothesis,
)
from lam.domain.events.models import (
    AssessmentMode,
    EventProvenance,
    EventType,
    LearningEvent,
    VerificationSource,
)


@pytest.fixture
def engine() -> DiagnosisEngine:
    return DiagnosisEngine()


def _make_event(
    event_id: str,
    correctness: bool | None,
    assistance_level: int = 0,
    hints_used: int = 0,
    concept_id: str = "algebra.linear_eq",
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
        event_id=event_id,
        tenant_id="tenant_diag_01",
        student_id="student_diag_1",
        session_id="sess_diag",
        concept_ids=[concept_id],
        item_id=f"item_{event_id}",
        timestamp=datetime.now(UTC),
        event_type=EventType.ATTEMPT,
        correctness=correctness,
        assistance_level=assistance_level,
        hints_used=hints_used,
        assessment_mode=(
            AssessmentMode.INDEPENDENT if assistance_level == 0 else AssessmentMode.ASSISTED
        ),
        provenance=prov,
    )


def test_missing_correctness_bypasses_diagnosis(engine: DiagnosisEngine) -> None:
    event = _make_event(event_id="e_null", correctness=None)
    res = engine.evaluate_observation(
        existing_hypotheses=[],
        event=event,
        concept_id="algebra.linear_eq",
    )
    assert res.evaluated is False
    assert res.reason == "missing_correctness_signal"
    assert len(res.hypotheses_updated) == 0


def test_unverified_provenance_rejected(engine: DiagnosisEngine) -> None:
    event = _make_event(event_id="e_unver", correctness=False, status="provisional")
    res = engine.evaluate_observation(
        existing_hypotheses=[],
        event=event,
        concept_id="algebra.linear_eq",
    )
    assert res.evaluated is False
    assert res.reason == "unverified_or_provisional_provenance_rejected"


def test_missing_provenance_rejected(engine: DiagnosisEngine) -> None:
    event = _make_event(event_id="e_noprov", correctness=False, no_provenance=True)
    res = engine.evaluate_observation(
        existing_hypotheses=[],
        event=event,
        concept_id="algebra.linear_eq",
    )
    assert res.evaluated is False
    assert res.reason == "unverified_or_provisional_provenance_rejected"


def test_single_wrong_answer_opens_hypothesis_without_confirming(
    engine: DiagnosisEngine,
) -> None:
    """Non-negotiable rule: A single incorrect response opens an OPEN candidate hypothesis

    with low confidence (0.35) and must NEVER confirm the hypothesis.
    """
    event = _make_event(event_id="e_err_1", correctness=False)
    res = engine.evaluate_observation(
        existing_hypotheses=[],
        event=event,
        concept_id="algebra.linear_eq",
    )
    assert res.evaluated is True
    assert len(res.hypotheses_updated) == 1
    hypo = res.hypotheses_updated[0]
    assert hypo.status == HypothesisStatus.OPEN
    assert pytest.approx(hypo.confidence, abs=1e-3) == 0.35
    assert len(hypo.supporting_evidence_ids) == 1
    assert len(res.confirmed_hypotheses) == 0


def test_repeated_independent_errors_confirm_hypothesis(engine: DiagnosisEngine) -> None:
    """Repeated unassisted errors accumulate confidence and transition to CONFIRMED."""
    # First error -> OPEN (confidence 0.35)
    e1 = _make_event(event_id="e_err_1", correctness=False)
    res1 = engine.evaluate_observation([], e1, "algebra.linear_eq")
    hypo = res1.hypotheses_updated[0]
    assert hypo.status == HypothesisStatus.OPEN

    # Second error -> confidence 0.65 (still OPEN, threshold 0.75)
    e2 = _make_event(event_id="e_err_2", correctness=False)
    engine.evaluate_observation([hypo], e2, "algebra.linear_eq")
    assert hypo.status == HypothesisStatus.OPEN
    assert pytest.approx(hypo.confidence, abs=1e-3) == 0.65

    # Third error -> confidence 0.95 -> transitions to CONFIRMED
    e3 = _make_event(event_id="e_err_3", correctness=False)
    res3 = engine.evaluate_observation([hypo], e3, "algebra.linear_eq")
    updated_hypo = res3.hypotheses_updated[0]
    assert updated_hypo.status == HypothesisStatus.CONFIRMED
    assert len(res3.confirmed_hypotheses) == 1
    assert res3.confirmed_hypotheses[0].hypothesis_id == hypo.hypothesis_id
    # Verify audit trail records the transition
    assert any(a["to_status"] == HypothesisStatus.CONFIRMED for a in updated_hypo.audit_trail)


def test_contradictory_evidence_weakens_and_retires_hypothesis(
    engine: DiagnosisEngine,
) -> None:
    # Set up a confirmed hypothesis
    hypo = MisconceptionHypothesis(
        hypothesis_id="hypo_test",
        tenant_id="tenant_diag_01",
        student_id="student_diag_1",
        concept_id="algebra.linear_eq",
        category=MisconceptionCategory.CONCEPTUAL_MISUNDERSTANDING,
        status=HypothesisStatus.CONFIRMED,
        confidence=0.80,
        supporting_evidence_ids=["e1", "e2", "e3"],
        contradictory_evidence_ids=[],
    )

    # First independent success -> weakens to REVISED (confidence 0.80 - 0.35 = 0.45)
    e_succ_1 = _make_event(event_id="e_succ_1", correctness=True)
    engine.evaluate_observation([hypo], e_succ_1, "algebra.linear_eq")
    assert hypo.status == HypothesisStatus.REVISED
    assert pytest.approx(hypo.confidence, abs=1e-3) == 0.45

    # Second independent success -> confidence 0.45 - 0.35 = 0.10 <= 0.15 -> RETIRED
    e_succ_2 = _make_event(event_id="e_succ_2", correctness=True)
    res2 = engine.evaluate_observation([hypo], e_succ_2, "algebra.linear_eq")
    retired_hypo = res2.hypotheses_updated[0]
    assert retired_hypo.status == HypothesisStatus.RETIRED
    assert pytest.approx(retired_hypo.confidence, abs=1e-3) == 0.10
    assert len(res2.confirmed_hypotheses) == 0


def test_assisted_errors_have_discounted_weight(engine: DiagnosisEngine) -> None:
    event_assisted = _make_event(
        event_id="e_asst_1",
        correctness=False,
        assistance_level=3,
        hints_used=1,
    )
    res = engine.evaluate_observation([], event_assisted, "algebra.linear_eq")
    hypo = res.hypotheses_updated[0]
    # Assisted error starts at initial confidence 0.20 (lower than unassisted 0.35)
    assert hypo.status == HypothesisStatus.OPEN
    assert pytest.approx(hypo.confidence, abs=1e-3) == 0.20


def test_duplicate_event_does_not_inflate_confidence(engine: DiagnosisEngine) -> None:
    e1 = _make_event(event_id="e_dup_1", correctness=False)
    res1 = engine.evaluate_observation([], e1, "algebra.linear_eq")
    hypo = res1.hypotheses_updated[0]
    conf_before = hypo.confidence

    # Replay same event ID
    res2 = engine.evaluate_observation([hypo], e1, "algebra.linear_eq")
    assert res2.evaluated is False
    assert res2.reason == "duplicate_event_evidence_ignored"
    assert hypo.confidence == conf_before
    assert len(hypo.supporting_evidence_ids) == 1


def test_competing_hypotheses_evaluation(engine: DiagnosisEngine) -> None:
    # Error targeted as procedural error
    e_proc = _make_event(event_id="e_proc_1", correctness=False)
    res1 = engine.evaluate_observation(
        [],
        e_proc,
        "algebra.linear_eq",
        candidate_category=MisconceptionCategory.PROCEDURAL_ERROR,
    )
    h_proc = res1.hypotheses_updated[0]
    assert h_proc.category == MisconceptionCategory.PROCEDURAL_ERROR

    # Another error targeted as arithmetic error on the same concept
    e_arith = _make_event(event_id="e_arith_1", correctness=False)
    res2 = engine.evaluate_observation(
        [h_proc],
        e_arith,
        "algebra.linear_eq",
        candidate_category=MisconceptionCategory.ARITHMETIC_ERROR,
    )
    h_arith = res2.hypotheses_updated[0]
    assert h_arith.category == MisconceptionCategory.ARITHMETIC_ERROR

    # Both competing hypotheses exist for this concept without collision
    assert h_proc.hypothesis_id != h_arith.hypothesis_id


def test_deterministic_reproducibility(engine: DiagnosisEngine) -> None:
    e1 = _make_event(event_id="e_det_1", correctness=False)
    r1 = engine.evaluate_observation([], e1, "math.fractions")
    r2 = engine.evaluate_observation([], e1, "math.fractions")
    assert r1.hypotheses_updated[0].status == r2.hypotheses_updated[0].status
    assert r1.hypotheses_updated[0].confidence == r2.hypotheses_updated[0].confidence
