"""Authoritative domain evidence eligibility policy for Bayesian Knowledge Tracing.

Follows Section 8 of the LAM Implementation Specification and Decision Record D-03 (PROPOSED).

Non-Negotiable Rules:
1. Missing, stale, or untrusted signals MUST remain None/unknown and never be coerced.
2. Unassisted, verified, deterministic assessments are the ONLY observations eligible
   to update independent BKT mastery.
3. Assisted attempts (hints, scaffolding, partial solutions) reflect assisted performance,
   NOT independent mastery. They must never advance independent BKT mastery.
4. Provisional or unverified provenance (e.g. unverified AI model grading, missing provenance)
   cannot establish independent mastery.
"""

from dataclasses import dataclass
from enum import StrEnum

from lam.domain.events.models import AssessmentMode, LearningEvent, VerificationSource


class EligibilityReason(StrEnum):
    ELIGIBLE = "eligible_unassisted_verified_observation"
    ASSISTED_ATTEMPT = "assisted_attempt_excluded"
    MISSING_CORRECTNESS = "missing_correctness_signal"
    NON_EVALUATIVE_EVENT = "non_evaluative_event_type"
    MISSING_PROVENANCE = "missing_verification_provenance"
    PROVISIONAL_STATUS = "provisional_provenance_status"
    LOW_RELIABILITY_VERIFIER = "low_reliability_verifier"
    UNTRUSTED_VERIFICATION_SOURCE = "untrusted_verification_source"


# Authoritative sources trusted for independent mastery updates when verified
TRUSTED_VERIFICATION_SOURCES: frozenset[VerificationSource] = frozenset(
    {
        VerificationSource.ANSWER_KEY,
        VerificationSource.SYMBOLIC_MATH_CHECK,
        VerificationSource.CODE_TESTS,
        VerificationSource.CURRICULUM_FACT_CHECK,
        VerificationSource.TEACHER,
    }
)


@dataclass(frozen=True)
class EvidenceEligibilityResult:
    """Evaluation result for an incoming learning event's evidence eligibility."""

    is_eligible_for_bkt: bool
    is_assisted: bool
    reason: EligibilityReason
    is_evaluative: bool


def evaluate_evidence_eligibility(event: LearningEvent) -> EvidenceEligibilityResult:
    """Evaluates whether an event is eligible to update independent BKT mastery.

    Evaluation steps:
    1. Assistance Check:
       Any positive assistance signal (assistance_level > 0, hints_used > 0,
       assessment_mode == ASSISTED, or provenance.independently_produced == False)
       classifies the event as ASSISTED.
    2. Evaluative Check:
       Events without binary correctness or non-evaluative event types
       cannot update mastery.
    3. Provenance & Provenance Trustworthiness Check:
       Verification source must be an approved, non-provisional, verified source.
    """
    # 1. Assistance determination (fail-safe: any assisted signal marks the event as assisted)
    is_assisted = False
    if event.assistance_level is not None and event.assistance_level > 0:
        is_assisted = True
    elif event.hints_used is not None and event.hints_used > 0:
        is_assisted = True
    elif event.assessment_mode == AssessmentMode.ASSISTED:
        is_assisted = True
    elif event.provenance is not None and event.provenance.independently_produced is False:
        is_assisted = True

    # 2. Check for missing correctness
    if event.correctness is None:
        return EvidenceEligibilityResult(
            is_eligible_for_bkt=False,
            is_assisted=is_assisted,
            reason=EligibilityReason.MISSING_CORRECTNESS,
            is_evaluative=False,
        )

    # 3. If assisted, it demonstrates scaffolded performance, not independent mastery
    if is_assisted:
        return EvidenceEligibilityResult(
            is_eligible_for_bkt=False,
            is_assisted=True,
            reason=EligibilityReason.ASSISTED_ATTEMPT,
            is_evaluative=True,
        )

    # 4. Provenance verification checks
    if event.provenance is None:
        return EvidenceEligibilityResult(
            is_eligible_for_bkt=False,
            is_assisted=False,
            reason=EligibilityReason.MISSING_PROVENANCE,
            is_evaluative=True,
        )

    if event.provenance.status != "verified":
        return EvidenceEligibilityResult(
            is_eligible_for_bkt=False,
            is_assisted=False,
            reason=EligibilityReason.PROVISIONAL_STATUS,
            is_evaluative=True,
        )

    if event.provenance.verifier_reliability == "low":
        return EvidenceEligibilityResult(
            is_eligible_for_bkt=False,
            is_assisted=False,
            reason=EligibilityReason.LOW_RELIABILITY_VERIFIER,
            is_evaluative=True,
        )

    if event.provenance.judgment_source not in TRUSTED_VERIFICATION_SOURCES:
        # e.g. MODEL_GRADED or unapproved source
        return EvidenceEligibilityResult(
            is_eligible_for_bkt=False,
            is_assisted=False,
            reason=EligibilityReason.UNTRUSTED_VERIFICATION_SOURCE,
            is_evaluative=True,
        )

    # 5. Fully verified, independent, evaluative observation
    return EvidenceEligibilityResult(
        is_eligible_for_bkt=True,
        is_assisted=False,
        reason=EligibilityReason.ELIGIBLE,
        is_evaluative=True,
    )
