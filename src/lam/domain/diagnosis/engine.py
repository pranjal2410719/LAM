"""Deterministic Misconception Diagnosis Engine.

Implements competing hypothesis tracking, evidentiary confidence scoring,
and full lifecycle transitions (OPEN -> CONFIRMED -> REVISED / RETIRED)
as specified in Section 9 of the LAM Implementation Specification and
Decision Record D-04 (PROPOSED).
"""

from datetime import UTC, datetime
from uuid import uuid4

from lam.domain.diagnosis.models import (
    DiagnosisEvaluationResult,
    HypothesisAuditEntry,
    HypothesisStatus,
    MisconceptionCategory,
    MisconceptionHypothesis,
)
from lam.domain.events.models import LearningEvent
from lam.domain.mastery.eligibility import evaluate_evidence_eligibility

CONFIRMATION_CONFIDENCE_THRESHOLD = 0.75
MIN_INDEPENDENT_SUPPORTING_EVIDENCE = 2
RETIREMENT_CONFIDENCE_THRESHOLD = 0.15
UNASSISTED_SUPPORTING_WEIGHT = 0.30
ASSISTED_SUPPORTING_WEIGHT = 0.15
CONTRADICTORY_SUCCESS_WEIGHT = 0.35
INITIAL_UNASSISTED_CONFIDENCE = 0.35
INITIAL_ASSISTED_CONFIDENCE = 0.20


class DiagnosisEngine:
    """Deterministic evaluator for student misconception hypotheses."""

    def __init__(self, policy_version: str = "diagnosis_v1_deterministic"):
        self.policy_version = policy_version

    def evaluate_observation(
        self,
        existing_hypotheses: list[MisconceptionHypothesis],
        event: LearningEvent,
        concept_id: str,
        candidate_category: MisconceptionCategory | None = None,
        evaluation_time: datetime | None = None,
    ) -> DiagnosisEvaluationResult:
        """Evaluates a validated learning event against student misconception hypotheses.

        Rules:
        1. Non-evaluative events (correctness is None) bypass diagnosis.
        2. Unverified or provisional events cannot open or update hypotheses.
        3. A single incorrect answer creates an OPEN candidate hypothesis with low confidence.
           It NEVER confirms the hypothesis.
        4. Repeated unassisted supporting evidence accumulates confidence toward CONFIRMED.
        5. Independent successes serve as contradictory evidence, weakening confidence
           and retiring the hypothesis upon sufficient disconfirmation.
        6. Duplicate event IDs are ignored to prevent artificial confidence inflation.
        """
        now = evaluation_time or datetime.now(UTC)
        eligibility = evaluate_evidence_eligibility(event)

        # Rule 1: Missing correctness
        if event.correctness is None:
            return DiagnosisEvaluationResult(
                evaluated=False,
                hypotheses_updated=[],
                confirmed_hypotheses=[
                    h for h in existing_hypotheses if h.status == HypothesisStatus.CONFIRMED
                ],
                reason="missing_correctness_signal",
            )

        # Rule 2: Unverified or provisional provenance cannot establish or alter diagnoses
        if not eligibility.is_evaluative or (
            event.provenance is None or event.provenance.status != "verified"
        ):
            return DiagnosisEvaluationResult(
                evaluated=False,
                hypotheses_updated=[],
                confirmed_hypotheses=[
                    h for h in existing_hypotheses if h.status == HypothesisStatus.CONFIRMED
                ],
                reason="unverified_or_provisional_provenance_rejected",
            )

        updated_list: list[MisconceptionHypothesis] = []
        is_assisted = eligibility.is_assisted

        if event.correctness is False:
            # Observation is an ERROR -> Supporting evidence for a misconception
            default_cat = MisconceptionCategory.CONCEPTUAL_MISUNDERSTANDING
            target_category = candidate_category or default_cat

            # Find matching active/open hypothesis for this concept and category
            target_hypothesis: MisconceptionHypothesis | None = None
            for h in existing_hypotheses:
                if (
                    h.concept_id == concept_id
                    and h.category == target_category
                    and h.status != HypothesisStatus.RETIRED
                ):
                    target_hypothesis = h
                    break

            if target_hypothesis is None:
                # Open a new candidate hypothesis (Single error rule: strictly OPEN, not CONFIRMED)
                initial_conf = (
                    INITIAL_ASSISTED_CONFIDENCE if is_assisted else INITIAL_UNASSISTED_CONFIDENCE
                )
                hypo_id = f"hypo_{uuid4().hex[:12]}"
                new_hypo = MisconceptionHypothesis(
                    hypothesis_id=hypo_id,
                    tenant_id=event.tenant_id,
                    student_id=event.student_id,
                    concept_id=concept_id,
                    category=target_category,
                    status=HypothesisStatus.OPEN,
                    confidence=initial_conf,
                    supporting_evidence_ids=[event.event_id],
                    contradictory_evidence_ids=[],
                    audit_trail=[
                        HypothesisAuditEntry(
                            transition_id=f"audit_{uuid4().hex[:8]}",
                            from_status=HypothesisStatus.OPEN,
                            to_status=HypothesisStatus.OPEN,
                            trigger_event_id=event.event_id,
                            reason="initial_candidate_hypothesis_opened",
                            confidence_before=0.0,
                            confidence_after=initial_conf,
                            timestamp=now,
                        ).__dict__
                    ],
                    policy_version=self.policy_version,
                    description=f"Candidate {target_category.value} for concept {concept_id}",
                    created_at=now,
                    updated_at=now,
                )
                updated_list.append(new_hypo)
            else:
                # Existing hypothesis: check for duplicate submission
                if event.event_id in target_hypothesis.supporting_evidence_ids:
                    return DiagnosisEvaluationResult(
                        evaluated=False,
                        hypotheses_updated=[],
                        confirmed_hypotheses=[
                            h for h in existing_hypotheses if h.status == HypothesisStatus.CONFIRMED
                        ],
                        reason="duplicate_event_evidence_ignored",
                    )

                old_conf = target_hypothesis.confidence
                old_status = target_hypothesis.status
                weight = ASSISTED_SUPPORTING_WEIGHT if is_assisted else UNASSISTED_SUPPORTING_WEIGHT
                new_conf = min(1.0, old_conf + weight)

                target_hypothesis.supporting_evidence_ids.append(event.event_id)
                target_hypothesis.confidence = new_conf
                target_hypothesis.updated_at = now

                # Evaluate confirmation rule (Requires multiple unassisted observations)
                supporting_count = len(target_hypothesis.supporting_evidence_ids)
                if (
                    not is_assisted
                    and supporting_count >= MIN_INDEPENDENT_SUPPORTING_EVIDENCE
                    and new_conf >= CONFIRMATION_CONFIDENCE_THRESHOLD
                    and old_status == HypothesisStatus.OPEN
                ):
                    target_hypothesis.status = HypothesisStatus.CONFIRMED
                    target_hypothesis.audit_trail.append(
                        HypothesisAuditEntry(
                            transition_id=f"audit_{uuid4().hex[:8]}",
                            from_status=old_status,
                            to_status=HypothesisStatus.CONFIRMED,
                            trigger_event_id=event.event_id,
                            reason="confirmed_by_repeated_independent_evidence",
                            confidence_before=old_conf,
                            confidence_after=new_conf,
                            timestamp=now,
                        ).__dict__
                    )
                else:
                    target_hypothesis.audit_trail.append(
                        HypothesisAuditEntry(
                            transition_id=f"audit_{uuid4().hex[:8]}",
                            from_status=old_status,
                            to_status=target_hypothesis.status,
                            trigger_event_id=event.event_id,
                            reason="supporting_evidence_accumulated",
                            confidence_before=old_conf,
                            confidence_after=new_conf,
                            timestamp=now,
                        ).__dict__
                    )

                updated_list.append(target_hypothesis)

        else:
            # Observation is CORRECT -> Contradictory evidence against active misconceptions
            for hypo in existing_hypotheses:
                if hypo.concept_id != concept_id or hypo.status == HypothesisStatus.RETIRED:
                    continue

                if event.event_id in hypo.contradictory_evidence_ids:
                    continue

                # Assisted correct answers are weaker disconfirmation than independent success
                if is_assisted:
                    continue

                old_conf = hypo.confidence
                old_status = hypo.status
                new_conf = max(0.0, old_conf - CONTRADICTORY_SUCCESS_WEIGHT)

                hypo.contradictory_evidence_ids.append(event.event_id)
                hypo.confidence = new_conf
                hypo.updated_at = now

                contradictory_count = len(hypo.contradictory_evidence_ids)
                if new_conf <= RETIREMENT_CONFIDENCE_THRESHOLD or contradictory_count >= 2:
                    hypo.status = HypothesisStatus.RETIRED
                    hypo.audit_trail.append(
                        HypothesisAuditEntry(
                            transition_id=f"audit_{uuid4().hex[:8]}",
                            from_status=old_status,
                            to_status=HypothesisStatus.RETIRED,
                            trigger_event_id=event.event_id,
                            reason="disconfirmed_by_independent_success",
                            confidence_before=old_conf,
                            confidence_after=new_conf,
                            timestamp=now,
                        ).__dict__
                    )
                elif old_status == HypothesisStatus.CONFIRMED:
                    hypo.status = HypothesisStatus.REVISED
                    hypo.audit_trail.append(
                        HypothesisAuditEntry(
                            transition_id=f"audit_{uuid4().hex[:8]}",
                            from_status=old_status,
                            to_status=HypothesisStatus.REVISED,
                            trigger_event_id=event.event_id,
                            reason="weakened_by_contradictory_evidence",
                            confidence_before=old_conf,
                            confidence_after=new_conf,
                            timestamp=now,
                        ).__dict__
                    )
                else:
                    hypo.audit_trail.append(
                        HypothesisAuditEntry(
                            transition_id=f"audit_{uuid4().hex[:8]}",
                            from_status=old_status,
                            to_status=hypo.status,
                            trigger_event_id=event.event_id,
                            reason="contradictory_evidence_recorded",
                            confidence_before=old_conf,
                            confidence_after=new_conf,
                            timestamp=now,
                        ).__dict__
                    )

                updated_list.append(hypo)

        all_current = {h.hypothesis_id: h for h in existing_hypotheses}
        for u in updated_list:
            all_current[u.hypothesis_id] = u

        confirmed = [h for h in all_current.values() if h.status == HypothesisStatus.CONFIRMED]

        return DiagnosisEvaluationResult(
            evaluated=True,
            hypotheses_updated=updated_list,
            confirmed_hypotheses=confirmed,
            reason="observation_evaluated_against_hypotheses",
        )
