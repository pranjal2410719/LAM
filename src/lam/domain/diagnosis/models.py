"""Domain models and types for Misconception Diagnosis (Decision D-04 PROPOSED).

Complies with Section 5.3 & Section 9 of the LAM Implementation Specification.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MisconceptionCategory(StrEnum):
    """Standard taxonomy of student difficulty explanations."""

    CONCEPTUAL_MISUNDERSTANDING = "conceptual_misunderstanding"
    MISSING_PREREQUISITE = "missing_prerequisite"
    PROCEDURAL_ERROR = "procedural_error"
    ARITHMETIC_ERROR = "arithmetic_error"
    MISREADING = "misreading"
    GUESSING = "guessing"
    RETRIEVAL_FAILURE = "retrieval_failure"
    CARELESSNESS = "carelessness"
    FLAWED_REASONING = "flawed_reasoning"


class HypothesisStatus(StrEnum):
    """Lifecycle status of a misconception hypothesis."""

    OPEN = "open"  # Candidate hypothesis formed; unconfirmed
    CONFIRMED = "confirmed"  # Confirmed by repeated independent evidence
    REVISED = "revised"  # Modified due to mixed or refined evidence
    RETIRED = "retired"  # Disconfirmed by subsequent successes


@dataclass(frozen=True)
class HypothesisAuditEntry:
    """Immutable audit entry recording a state change in a hypothesis lifecycle."""

    transition_id: str
    from_status: HypothesisStatus
    to_status: HypothesisStatus
    trigger_event_id: str | None
    reason: str
    confidence_before: float
    confidence_after: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MisconceptionHypothesis:
    """Represents a candidate or confirmed explanation for a student's difficulty.

    Invariants:
    1. A single incorrect response opens a candidate hypothesis with low confidence (OPEN),
       and never confirms it.
    2. Confirmation requires repeated independent supporting observations and high confidence.
    3. Contradictory evidence (independent successes) weakens confidence and
       can retire the hypothesis.
    4. Duplicate event submissions never add duplicate evidence.
    """

    hypothesis_id: str
    tenant_id: str
    student_id: str
    concept_id: str
    category: MisconceptionCategory
    status: HypothesisStatus = HypothesisStatus.OPEN
    confidence: float = 0.20  # Explicit heuristic score in [0.0, 1.0]
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradictory_evidence_ids: list[str] = field(default_factory=list)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    state_version: int = 1
    policy_version: str = "diagnosis_v1_deterministic"
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DiagnosisEvaluationResult:
    """Outcome of evaluating an observation against candidate misconception hypotheses."""

    evaluated: bool
    hypotheses_updated: list[MisconceptionHypothesis]
    confirmed_hypotheses: list[MisconceptionHypothesis]
    reason: str
