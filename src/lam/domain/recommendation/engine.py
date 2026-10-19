"""Deterministic Next-Action Recommendation Engine.

Implements the multi-tier deterministic decision hierarchy defined in Section 10
of the LAM Implementation Specification and Decision Record D-06 (PROPOSED).

Invariants:
- Zero external framework, database, or LLM dependencies.
- Strictly deterministic: identical inputs yield identical outputs.
- Complete reason codes, strategy descriptors, and audit metadata.
- Safe fallbacks when evidence is ambiguous or incomplete.
"""

from typing import Any

from lam.domain.recommendation.models import (
    ActionType,
    PriorityTier,
    RecommendationContext,
    RecommendationDecision,
)

DEFAULT_POLICY_VERSION = "policy_v1_deterministic"
MASTERY_THRESHOLD = 0.85
UNCERTAINTY_THRESHOLD = 0.15
CONSECUTIVE_SUCCESS_THRESHOLD = 3
MAX_CONSECUTIVE_FAILURES = 3
LOW_MASTERY_THRESHOLD = 0.40
RETENTION_THRESHOLD = 0.50


class RecommendationEngine:
    """Deterministic learning action selector."""

    def __init__(self, policy_version: str = DEFAULT_POLICY_VERSION):
        self.policy_version = policy_version

    def evaluate(
        self,
        context: RecommendationContext | None,
        target_concept_id: str,
        custom_metadata: dict[str, Any] | None = None,
    ) -> RecommendationDecision:
        """Evaluates learner state against the deterministic decision priority ladder.

        Priority Order:
        1. Safety and Stop Conditions (persistent failures/frustration -> Teacher Intervention)
        2. Blocking Prerequisite Gaps (prerequisite readiness False -> Prerequisite Remediation)
        3. Confirmed Misconceptions (active misconception -> Diagnostic Probe)
        4. Overdue Retrieval (low retention strength -> Delayed Retrieval Review)
        5. Mastery Verification (high mastery but uncertainty > 0.15 or < 3 consecutive successes)
        6. Curriculum Progression (high mastery + low uncertainty + sufficient evidence -> Advance)
        7. Difficulty Fit / Practice (low mastery -> Worked Example; developing -> Practice)
        Fallback: Insufficient evidence -> Baseline Diagnostic Probe
        """
        meta: dict[str, Any] = custom_metadata.copy() if custom_metadata else {}

        # Fallback: When no learner context exists yet
        if context is None:
            return RecommendationDecision(
                action_type=ActionType.DIAGNOSTIC_PROBE,
                target_concept_id=target_concept_id,
                assistance_level=2,
                priority_tier=PriorityTier.FALLBACK,
                reason_code="no_prior_learner_state",
                suggested_strategy=(
                    "Deliver baseline diagnostic probe to determine initial mastery."
                ),
                rationale="No existing state record found for this learner and concept.",
                policy_version=self.policy_version,
                safe_fallback=True,
                uncertainty=1.0,
                relevant_learner_state_version=None,
                metadata=meta,
            )

        # Tier 1: Safety & Stop Conditions
        if context.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return RecommendationDecision(
                action_type=ActionType.TEACHER_INTERVENTION,
                target_concept_id=target_concept_id,
                assistance_level=8,
                priority_tier=PriorityTier.TIER_1_SAFETY_STOP,
                reason_code="persistent_failure_safety_stop",
                suggested_strategy=(
                    "Pause automated practice and request direct teacher intervention."
                ),
                rationale=(
                    f"Student has experienced {context.consecutive_failures} consecutive "
                    "failures. Safety policy requires pedagogical escalation."
                ),
                policy_version=self.policy_version,
                safe_fallback=False,
                uncertainty=context.uncertainty,
                relevant_learner_state_version=context.state_version,
                metadata=meta,
            )

        # Tier 2: Blocking Prerequisite Gaps
        if context.prerequisite_readiness is False:
            remediation_target = context.prerequisite_concept_id or target_concept_id
            return RecommendationDecision(
                action_type=ActionType.PREREQUISITE_REMEDIATION,
                target_concept_id=remediation_target,
                assistance_level=5,
                priority_tier=PriorityTier.TIER_2_BLOCKING_PREREQUISITE,
                reason_code="blocking_prerequisite_unmet",
                suggested_strategy=(
                    "Deliver worked example and remedial instruction on prerequisite concept."
                ),
                rationale=(
                    f"Prerequisite readiness check failed for target concept '{target_concept_id}'."
                    f" Remediation required on '{remediation_target}' before advancing."
                ),
                policy_version=self.policy_version,
                safe_fallback=False,
                uncertainty=context.uncertainty,
                relevant_learner_state_version=context.state_version,
                metadata=meta,
            )

        # Tier 3: Confirmed Misconceptions
        # Non-negotiable rule: Candidate hypotheses in OPEN or RETIRED state do NOT trigger Tier 3
        if context.active_misconception_id is not None:
            is_confirmed = (
                context.misconception_status is None
                or context.misconception_status.lower() == "confirmed"
            )
            if is_confirmed:
                return RecommendationDecision(
                    action_type=ActionType.DIAGNOSTIC_PROBE,
                    target_concept_id=target_concept_id,
                    assistance_level=2,
                    priority_tier=PriorityTier.TIER_3_CONFIRMED_MISCONCEPTION,
                    reason_code="confirmed_misconception_detected",
                    suggested_strategy=(
                        "Administer targeted conceptual probe to isolate confirmed misconception."
                    ),
                    rationale=(
                        f"Confirmed misconception '{context.active_misconception_id}' flagged. "
                        "Diagnostic probing required to refute or confirm hypothesis."
                    ),
                    policy_version=self.policy_version,
                    safe_fallback=False,
                    uncertainty=context.uncertainty,
                    relevant_learner_state_version=context.state_version,
                    metadata={"misconception_id": context.active_misconception_id, **meta},
                )

        # Tier 4: Overdue Retrieval / Fragile Retention
        if (
            context.retention_strength is not None
            and context.retention_strength < RETENTION_THRESHOLD
        ):
            return RecommendationDecision(
                action_type=ActionType.DELAYED_RETRIEVAL_REVIEW,
                target_concept_id=target_concept_id,
                assistance_level=0,
                priority_tier=PriorityTier.TIER_4_OVERDUE_RETRIEVAL,
                reason_code="fragile_retention_review_due",
                suggested_strategy=(
                    "Present spaced retrieval question to consolidate long-term retention."
                ),
                rationale=(
                    f"Retention strength ({context.retention_strength:.2f}) has decayed below "
                    f"threshold {RETENTION_THRESHOLD:.2f}."
                ),
                policy_version=self.policy_version,
                safe_fallback=False,
                uncertainty=context.uncertainty,
                relevant_learner_state_version=context.state_version,
                metadata=meta,
            )

        # Tier 5: Mastery Verification
        if context.independent_mastery >= MASTERY_THRESHOLD:
            needs_uncertainty_reduction = context.uncertainty > UNCERTAINTY_THRESHOLD
            needs_success_confirmation = (
                context.consecutive_independent_successes < CONSECUTIVE_SUCCESS_THRESHOLD
            )
            if needs_uncertainty_reduction or needs_success_confirmation:
                return RecommendationDecision(
                    action_type=ActionType.MASTERY_VERIFICATION,
                    target_concept_id=target_concept_id,
                    assistance_level=0,
                    priority_tier=PriorityTier.TIER_5_MASTERY_VERIFICATION,
                    reason_code="mastery_verification_required",
                    suggested_strategy="Deliver independent assessment problem without assistance.",
                    rationale=(
                        f"Mastery estimate ({context.independent_mastery:.3f}) exceeds threshold, "
                        f"but evidence uncertainty ({context.uncertainty:.3f} > "
                        f"{UNCERTAINTY_THRESHOLD}) or consecutive successes "
                        f"({context.consecutive_independent_successes} < "
                        f"{CONSECUTIVE_SUCCESS_THRESHOLD}) requires verification."
                    ),
                    policy_version=self.policy_version,
                    safe_fallback=False,
                    uncertainty=context.uncertainty,
                    relevant_learner_state_version=context.state_version,
                    metadata=meta,
                )

        # Tier 6: Curriculum Progression
        if (
            context.independent_mastery >= MASTERY_THRESHOLD
            and context.uncertainty <= UNCERTAINTY_THRESHOLD
            and context.consecutive_independent_successes >= CONSECUTIVE_SUCCESS_THRESHOLD
        ):
            return RecommendationDecision(
                action_type=ActionType.ADVANCE_TO_NEXT_CONCEPT,
                target_concept_id=target_concept_id,
                assistance_level=0,
                priority_tier=PriorityTier.TIER_6_CURRICULUM_PROGRESSION,
                reason_code="durable_mastery_confirmed",
                suggested_strategy=(
                    "Advance student to subsequent concept in the curriculum sequence."
                ),
                rationale=(
                    f"Independent mastery ({context.independent_mastery:.3f}) and evidence "
                    f"certainty (U={context.uncertainty:.3f} <= {UNCERTAINTY_THRESHOLD}) "
                    "confirm durable competency."
                ),
                policy_version=self.policy_version,
                safe_fallback=False,
                uncertainty=context.uncertainty,
                relevant_learner_state_version=context.state_version,
                metadata=meta,
            )

        # Tier 7: Practice and Scaffolding
        if context.independent_mastery < LOW_MASTERY_THRESHOLD:
            return RecommendationDecision(
                action_type=ActionType.WORKED_EXAMPLE,
                target_concept_id=target_concept_id,
                assistance_level=5,
                priority_tier=PriorityTier.TIER_7_DIFFICULTY_FIT_PRACTICE,
                reason_code="low_mastery_scaffolding_needed",
                suggested_strategy=(
                    "Demonstrate step-by-step worked example before further independent attempts."
                ),
                rationale=(
                    f"Independent mastery ({context.independent_mastery:.3f}) is below basic "
                    f"threshold {LOW_MASTERY_THRESHOLD}. Conceptual scaffolding needed."
                ),
                policy_version=self.policy_version,
                safe_fallback=False,
                uncertainty=context.uncertainty,
                relevant_learner_state_version=context.state_version,
                metadata=meta,
            )

        if context.assisted_attempts_count > context.independent_attempts_count:
            return RecommendationDecision(
                action_type=ActionType.SCAFFOLDED_PRACTICE,
                target_concept_id=target_concept_id,
                assistance_level=3,
                priority_tier=PriorityTier.TIER_7_DIFFICULTY_FIT_PRACTICE,
                reason_code="assisted_practice_transition",
                suggested_strategy="Provide practice item with on-demand hint scaffolding.",
                rationale=(
                    "Student demonstrates reliance on scaffolding; gradually fading assistance."
                ),
                policy_version=self.policy_version,
                safe_fallback=False,
                uncertainty=context.uncertainty,
                relevant_learner_state_version=context.state_version,
                metadata=meta,
            )

        return RecommendationDecision(
            action_type=ActionType.INDEPENDENT_PRACTICE,
            target_concept_id=target_concept_id,
            assistance_level=0,
            priority_tier=PriorityTier.TIER_7_DIFFICULTY_FIT_PRACTICE,
            reason_code="standard_independent_practice",
            suggested_strategy=(
                "Deliver standard independent practice item matching current skill level."
            ),
            rationale="Mastery is progressing normally; continuing independent practice cycle.",
            policy_version=self.policy_version,
            safe_fallback=False,
            uncertainty=context.uncertainty,
            relevant_learner_state_version=context.state_version,
            metadata=meta,
        )
