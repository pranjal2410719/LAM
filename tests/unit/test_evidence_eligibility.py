"""Unit tests for evidence eligibility policy (Decision D-03 PROPOSED)."""

from datetime import UTC, datetime

import pytest

from lam.domain.events.models import (
    AssessmentMode,
    EventProvenance,
    EventType,
    LearningEvent,
    VerificationSource,
)
from lam.domain.mastery.eligibility import (
    TRUSTED_VERIFICATION_SOURCES,
    EligibilityReason,
    evaluate_evidence_eligibility,
)


def _make_event(
    correctness: bool | None = True,
    assistance_level: int | None = 0,
    hints_used: int | None = 0,
    assessment_mode: AssessmentMode | None = AssessmentMode.INDEPENDENT,
    provenance: EventProvenance | None = None,
    event_type: EventType = EventType.ATTEMPT,
) -> LearningEvent:
    if provenance is None:
        provenance = EventProvenance(
            judgment_source=VerificationSource.ANSWER_KEY,
            verifier_version="1.0",
            verifier_reliability="high",
            independently_produced=True,
            status="verified",
        )
    return LearningEvent(
        event_id="test_evt_001",
        tenant_id="tenant_test",
        student_id="student_test",
        session_id="sess_test",
        concept_ids=["math.addition"],
        item_id="item_001",
        timestamp=datetime.now(UTC),
        event_type=event_type,
        correctness=correctness,
        assistance_level=assistance_level,
        hints_used=hints_used,
        assessment_mode=assessment_mode,
        provenance=provenance,
    )


def test_eligible_unassisted_verified_event() -> None:
    event = _make_event(correctness=True, assistance_level=0, hints_used=0)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is True
    assert res.is_assisted is False
    assert res.reason == EligibilityReason.ELIGIBLE


@pytest.mark.parametrize("source", list(TRUSTED_VERIFICATION_SOURCES))
def test_all_trusted_verification_sources_eligible(source: VerificationSource) -> None:
    prov = EventProvenance(
        judgment_source=source,
        verifier_reliability="high",
        independently_produced=True,
        status="verified",
    )
    event = _make_event(provenance=prov)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is True
    assert res.is_assisted is False


def test_assisted_by_assistance_level_excluded_from_bkt() -> None:
    event = _make_event(assistance_level=3)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.is_assisted is True
    assert res.reason == EligibilityReason.ASSISTED_ATTEMPT


def test_assisted_by_hints_used_excluded_from_bkt() -> None:
    event = _make_event(assistance_level=0, hints_used=1)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.is_assisted is True
    assert res.reason == EligibilityReason.ASSISTED_ATTEMPT


def test_assisted_by_assessment_mode_excluded_from_bkt() -> None:
    event = _make_event(assessment_mode=AssessmentMode.ASSISTED)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.is_assisted is True
    assert res.reason == EligibilityReason.ASSISTED_ATTEMPT


def test_assisted_by_provenance_independence_flag() -> None:
    prov = EventProvenance(
        judgment_source=VerificationSource.ANSWER_KEY,
        independently_produced=False,
        status="verified",
    )
    event = _make_event(provenance=prov)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.is_assisted is True
    assert res.reason == EligibilityReason.ASSISTED_ATTEMPT


def test_missing_correctness_signal_not_eligible() -> None:
    event = _make_event(correctness=None)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.reason == EligibilityReason.MISSING_CORRECTNESS


def test_missing_provenance_not_eligible() -> None:
    event = _make_event()
    event.provenance = None
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.reason == EligibilityReason.MISSING_PROVENANCE


def test_provisional_status_provenance_not_eligible() -> None:
    prov = EventProvenance(
        judgment_source=VerificationSource.ANSWER_KEY,
        status="provisional",
    )
    event = _make_event(provenance=prov)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.reason == EligibilityReason.PROVISIONAL_STATUS


def test_low_reliability_verifier_not_eligible() -> None:
    prov = EventProvenance(
        judgment_source=VerificationSource.ANSWER_KEY,
        verifier_reliability="low",
        status="verified",
    )
    event = _make_event(provenance=prov)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.reason == EligibilityReason.LOW_RELIABILITY_VERIFIER


def test_model_graded_requires_verification_not_eligible() -> None:
    prov = EventProvenance(
        judgment_source=VerificationSource.MODEL_GRADED,
        verifier_reliability="high",
        status="verified",
    )
    event = _make_event(provenance=prov)
    res = evaluate_evidence_eligibility(event)
    assert res.is_eligible_for_bkt is False
    assert res.reason == EligibilityReason.UNTRUSTED_VERIFICATION_SOURCE
