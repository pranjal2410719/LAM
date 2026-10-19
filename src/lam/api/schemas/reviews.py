"""API Schemas for Spaced Retrieval Review endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScheduledReviewItemDTO(BaseModel):
    """Details of a single review item."""

    concept_id: str
    concept_mastery: float
    last_reviewed_at: datetime
    scheduled_for: datetime
    interval_days: float
    retention_estimate: float
    is_due: bool
    priority: str
    reason_code: str
    consecutive_successes: int
    half_life_days: float


class ReviewsDueResponse(BaseModel):
    """Response payload for GET /v1/learners/{student_id}/reviews."""

    student_id: str
    evaluated_at: datetime
    policy_version: str
    total_concepts_evaluated: int
    reviews_due_count: int
    reviews_due: list[ScheduledReviewItemDTO]
    upcoming_reviews: list[ScheduledReviewItemDTO]
    metadata: dict[str, Any] = Field(default_factory=dict)
