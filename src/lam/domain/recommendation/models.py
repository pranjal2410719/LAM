"""Domain models and types for the deterministic next-action recommendation engine."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    TEACHER_INTERVENTION = "teacher_intervention"
    PREREQUISITE_REMEDIATION = "prerequisite_remediation"
    DIAGNOSTIC_PROBE = "diagnostic_probe"
    DELAYED_RETRIEVAL_REVIEW = "delayed_retrieval_review"
    MASTERY_VERIFICATION = "mastery_verification"
    ADVANCE_TO_NEXT_CONCEPT = "advance_to_next_concept"
    INDEPENDENT_PRACTICE = "independent_practice"
    SCAFFOLDED_PRACTICE = "scaffolded_practice"
    WORKED_EXAMPLE = "worked_example"


class PriorityTier(StrEnum):
    TIER_1_SAFETY_STOP = "tier_1_safety_stop"
    TIER_2_BLOCKING_PREREQUISITE = "tier_2_blocking_prerequisite"
    TIER_3_CONFIRMED_MISCONCEPTION = "tier_3_confirmed_misconception"
    TIER_4_OVERDUE_RETRIEVAL = "tier_4_overdue_retrieval"
    TIER_5_MASTERY_VERIFICATION = "tier_5_mastery_verification"
    TIER_6_CURRICULUM_PROGRESSION = "tier_6_curriculum_progression"
    TIER_7_DIFFICULTY_FIT_PRACTICE = "tier_7_difficulty_fit_practice"
    FALLBACK = "tier_fallback_insufficient_evidence"


@dataclass(frozen=True)
class RecommendationContext:
    """Inputs required by the deterministic recommendation engine."""

    concept_id: str
    concept_mastery: float
    independent_mastery: float
    assisted_performance: float
    uncertainty: float
    total_events_count: int
    independent_attempts_count: int
    assisted_attempts_count: int
    consecutive_independent_successes: int
    consecutive_failures: int = 0
    prerequisite_readiness: bool | None = None
    retention_strength: float | None = None
    active_misconception_id: str | None = None
    misconception_status: str | None = None  # open, confirmed, revised, retired
    prerequisite_concept_id: str | None = None
    state_version: int | None = None


@dataclass(frozen=True)
class RecommendationDecision:
    """Immutable deterministic decision output."""

    action_type: ActionType
    target_concept_id: str
    assistance_level: int  # 0 to 8
    priority_tier: PriorityTier
    reason_code: str
    suggested_strategy: str
    rationale: str
    policy_version: str
    safe_fallback: bool
    uncertainty: float
    relevant_learner_state_version: int | None
    metadata: dict[str, Any]
