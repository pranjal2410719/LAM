"""Domain models and schemas for learning events."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EventType(StrEnum):
    ATTEMPT = "attempt"
    HINT = "hint"
    EXPLANATION = "explanation"
    ASSESSMENT = "assessment"
    REVIEW = "review"


class AssessmentMode(StrEnum):
    INDEPENDENT = "independent"
    ASSISTED = "assisted"
    DELAYED = "delayed"
    TRANSFER = "transfer"


class VerificationSource(StrEnum):
    SYMBOLIC_MATH_CHECK = "symbolic_math_check"
    CODE_TESTS = "code_tests"
    ANSWER_KEY = "answer_key"
    CURRICULUM_FACT_CHECK = "curriculum_fact_check"
    TEACHER = "teacher"
    MODEL_GRADED = "model_graded"


class EventProvenance(BaseModel):
    judgment_source: VerificationSource
    verifier_version: str = "1.0"
    verifier_reliability: str = "high"  # high, medium, low
    independently_produced: bool = True
    status: str = "verified"  # verified or provisional
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningEvent(BaseModel):
    """Immutable domain representation of a validated learning event.

    Follows the Non-Negotiable Rule:
    Missing, stale, or untrusted signals MUST remain None/unknown and never be
    coerced to zero or false.
    """

    event_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    student_id: str = Field(..., min_length=1, max_length=128)
    session_id: str = Field(..., min_length=1, max_length=128)
    concept_ids: list[str] = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1, max_length=128)
    timestamp: datetime = Field(...)
    event_type: EventType
    correctness: bool | None = None
    attempt_number: int | None = Field(default=None, ge=1)
    assistance_level: int | None = Field(default=None, ge=0, le=8)
    hints_used: int | None = Field(default=None, ge=0)
    response_time_ms: int | None = Field(default=None, ge=0)
    self_reported_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    strategy_id: str | None = None
    intervention_id: str | None = None
    difficulty: float | None = Field(default=None, ge=0.0, le=1.0)
    assessment_mode: AssessmentMode | None = None
    provenance: EventProvenance | None = None
    schema_version: str = Field(default="v1", min_length=1, max_length=32)

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)
