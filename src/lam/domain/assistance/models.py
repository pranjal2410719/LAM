"""Domain models for 9-Level Assistance Escalation State Machine (M2-02)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum


class AssistanceLevel(IntEnum):
    """Authoritative 9-Level Scaffolding Hierarchy (Levels 0 through 8)."""

    LEVEL_0_INDEPENDENT = 0  # Independent attempt, unassisted
    LEVEL_1_METACOGNITIVE_PROMPT = 1  # Pause, reflect, check work prompt
    LEVEL_2_STRATEGY_HINT = 2  # High-level directional hint / diagnostic probe
    LEVEL_3_SCAFFOLDED_SUBSTEP = 3  # Decompose into structured sub-steps
    LEVEL_4_CONCEPTUAL_BREAKDOWN = 4  # Detailed conceptual formula/property reminder
    LEVEL_5_WORKED_EXAMPLE = 5  # Step-by-step solved parallel example
    LEVEL_6_GUIDED_WALKTHROUGH = 6  # Interactive step-by-step guided execution
    LEVEL_7_DIRECT_INSTRUCTION = 7  # Re-teach concept with explicit exposition
    LEVEL_8_TEACHER_INTERVENTION = 8  # Human tutor escalation / safety stop


class TransitionAction(StrEnum):
    """Categorization of assistance level transitions."""

    MAINTAIN = "maintain"
    ESCALATE = "escalate"
    DE_ESCALATE = "de_escalate"
    RESET = "reset"
    SAFETY_STOP = "safety_stop"


@dataclass(frozen=True)
class AssistanceAuditEntry:
    """Immutable audit record of an assistance state transition."""

    event_id: str | None
    from_level: AssistanceLevel
    to_level: AssistanceLevel
    action: TransitionAction
    reason_code: str
    rationale: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AssistanceState:
    """State tracking for a student on a specific concept."""

    student_id: str
    concept_id: str
    current_level: AssistanceLevel = AssistanceLevel.LEVEL_0_INDEPENDENT
    consecutive_failures: int = 0
    consecutive_assisted_successes: int = 0
    consecutive_independent_successes: int = 0
    total_assisted_attempts: int = 0
    total_independent_attempts: int = 0
    audit_trail: list[AssistanceAuditEntry] = field(default_factory=list)
    state_version: int = 1


@dataclass(frozen=True)
class AssistanceTransitionResult:
    """Result of evaluating an observation through the assistance state machine."""

    previous_level: AssistanceLevel
    new_level: AssistanceLevel
    action: TransitionAction
    consecutive_failures: int
    reason_code: str
    rationale: str
    policy_version: str
    audit_entry: AssistanceAuditEntry
