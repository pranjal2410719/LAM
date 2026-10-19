"""API Schemas for Event Ingestion."""

from datetime import UTC, datetime

from pydantic import AliasChoices, BaseModel, Field, field_validator

from lam.domain.events.models import AssessmentMode, EventProvenance, EventType


class EventIngestRequest(BaseModel):
    """Payload submitted to POST /v1/events."""

    event_id: str = Field(..., min_length=1, max_length=128)
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
    response_time_ms: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("response_time_ms", "duration_ms", "ms"),
    )
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


class EventIngestResponse(BaseModel):
    status: str = Field(..., description="ingested or duplicate")
    event_id: str
    tenant_id: str
    student_id: str
    affected_concept_ids: list[str]
    ingested_at: datetime
    message: str | None = None
