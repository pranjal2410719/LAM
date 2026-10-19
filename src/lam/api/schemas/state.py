"""API Schemas for Learner State retrieval."""

from datetime import datetime

from pydantic import BaseModel, Field


class ConceptStateDTO(BaseModel):
    concept_id: str
    concept_mastery: float = Field(..., ge=0.0, le=1.0)
    independent_mastery: float = Field(..., ge=0.0, le=1.0)
    assisted_performance: float = Field(..., ge=0.0, le=1.0)
    uncertainty: float = Field(..., ge=0.0, le=1.0)
    total_events_count: int = Field(..., ge=0)
    independent_attempts_count: int = Field(..., ge=0)
    assisted_attempts_count: int = Field(..., ge=0)
    consecutive_independent_successes: int = Field(..., ge=0)
    prerequisite_readiness: bool | None = None
    retention_strength: float | None = None
    last_practiced_at: datetime | None = None
    state_version: int = Field(..., ge=1)
    last_event_id: str | None = None
    bkt_parameter_version: str | None = None
    updated_at: datetime


class LearnerStateResponse(BaseModel):
    tenant_id: str
    student_id: str
    concepts: list[ConceptStateDTO]
