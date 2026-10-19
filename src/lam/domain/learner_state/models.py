"""Domain models and schemas for Learner State."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class LearnerConceptState(BaseModel):
    """Multi-dimensional learner state for a specific concept.

    As required by Section 11 of PRD & Implementation Specification:
    Mastery is never one opaque score, and assisted performance is strictly
    separated from independent mastery.
    """

    tenant_id: str = Field(..., min_length=1, max_length=128)
    student_id: str = Field(..., min_length=1, max_length=128)
    concept_id: str = Field(..., min_length=1, max_length=128)

    # Multi-dimensional estimates (Initial prior P(L_0) = 0.10)
    concept_mastery: float = Field(default=0.10, ge=0.0, le=1.0)
    independent_mastery: float = Field(default=0.10, ge=0.0, le=1.0)
    assisted_performance: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=1.0, ge=0.0, le=1.0)

    # Evidence counts
    total_events_count: int = Field(default=0, ge=0)
    independent_attempts_count: int = Field(default=0, ge=0)
    assisted_attempts_count: int = Field(default=0, ge=0)
    consecutive_independent_successes: int = Field(default=0, ge=0)

    # Readiness & Retention
    prerequisite_readiness: bool | None = None
    retention_strength: float | None = Field(default=None, ge=0.0, le=1.0)
    last_practiced_at: datetime | None = None

    # Versioning & Auditability
    state_version: int = Field(default=1, ge=1)
    last_event_id: str | None = None
    bkt_parameter_version: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"from_attributes": True}
