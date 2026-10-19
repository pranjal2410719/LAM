"""API Schemas for Next-Action Recommendation endpoints."""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    """Payload for POST /v1/recommendations."""

    student_id: str = Field(..., min_length=1, max_length=128)
    concept_id: str = Field(..., min_length=1, max_length=128)
    consecutive_failures: int = Field(default=0, ge=0)
    active_misconception_id: str | None = None
    misconception_status: str | None = None
    prerequisite_concept_id: str | None = None
    prerequisite_readiness: bool | None = None
    context_metadata: dict[str, Any] = Field(default_factory=dict)


class RecommendationResponse(BaseModel):
    """Response payload for POST /v1/recommendations."""

    recommendation_id: str = Field(default_factory=lambda: f"rec_{uuid4().hex[:12]}")
    action_type: str
    target_concept_id: str
    assistance_level: int = Field(..., ge=0, le=8)
    priority_tier: str
    reason_code: str
    suggested_strategy: str
    rationale: str
    policy_version: str
    safe_fallback: bool
    uncertainty: float = Field(..., ge=0.0, le=1.0)
    relevant_learner_state_version: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
