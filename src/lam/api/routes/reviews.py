"""Spaced retrieval review API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.reviews import (
    ReviewsDueResponse,
    ScheduledReviewItemDTO,
)
from lam.domain.retrieval.scheduler import SpacedRetrievalScheduler
from lam.infrastructure.authentication.middleware import (
    SecurityContext,
    authorize_access,
    get_security_context,
)
from lam.infrastructure.database.session import get_db_session
from lam.infrastructure.repositories.state_repository import StateRepository

router = APIRouter(prefix="/v1/learners", tags=["Spaced Retrieval"])


@router.get("/{learner_id}/reviews", response_model=ReviewsDueResponse)
async def get_learner_reviews(
    learner_id: str,
    priority: str | None = Query(
        default=None,
        description=(
            "Filter reviews by priority: overdue, critical_overdue, "
            "due_for_review, due_soon, upcoming, stable, maintained"
        ),
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of review items to return (1-200, default 50)",
    ),
    sec: SecurityContext = Depends(get_security_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewsDueResponse:
    """Retrieves scheduled and overdue spaced retrieval reviews for an authorized learner."""
    authorize_access(sec, resource="reviews", target_learner_id=learner_id)
    repo = StateRepository(session)
    states = await repo.get_all_student_states(
        tenant_id=sec.tenant_id,
        student_id=learner_id,
    )

    scheduler = SpacedRetrievalScheduler()
    schedule_result = scheduler.evaluate_schedules(
        student_id=learner_id,
        concept_states=states,
    )

    reviews_due_dto = [
        ScheduledReviewItemDTO(
            concept_id=r.concept_id,
            concept_mastery=r.concept_mastery,
            last_reviewed_at=r.last_reviewed_at,
            scheduled_for=r.scheduled_for,
            interval_days=r.interval_days,
            retention_estimate=r.retention_estimate,
            is_due=r.is_due,
            priority=r.priority.value,
            reason_code=r.reason_code,
            consecutive_successes=r.consecutive_successes,
            half_life_days=r.half_life_days,
        )
        for r in schedule_result.reviews_due
    ]

    upcoming_dto = [
        ScheduledReviewItemDTO(
            concept_id=r.concept_id,
            concept_mastery=r.concept_mastery,
            last_reviewed_at=r.last_reviewed_at,
            scheduled_for=r.scheduled_for,
            interval_days=r.interval_days,
            retention_estimate=r.retention_estimate,
            is_due=r.is_due,
            priority=r.priority.value,
            reason_code=r.reason_code,
            consecutive_successes=r.consecutive_successes,
            half_life_days=r.half_life_days,
        )
        for r in schedule_result.upcoming_reviews
    ]

    # Filter by priority if requested
    if priority:
        target_p = priority.lower().strip()
        priority_map: dict[str, tuple[str, ...]] = {
            "overdue": ("critical_overdue", "due_for_review"),
            "critical_overdue": ("critical_overdue",),
            "due_for_review": ("due_for_review",),
            "due_soon": ("due_for_review",),
            "upcoming": ("upcoming",),
            "stable": ("stable",),
            "maintained": ("stable",),
        }
        allowed = priority_map.get(target_p, (target_p,))
        reviews_due_dto = [r for r in reviews_due_dto if r.priority in allowed]
        upcoming_dto = [r for r in upcoming_dto if r.priority in allowed]

    # Enforce result limit
    if limit:
        reviews_due_dto = reviews_due_dto[:limit]
        upcoming_dto = upcoming_dto[:limit]

    return ReviewsDueResponse(
        student_id=learner_id,
        evaluated_at=schedule_result.evaluated_at,
        policy_version=schedule_result.policy_version,
        total_concepts_evaluated=schedule_result.total_concepts_evaluated,
        reviews_due_count=len(reviews_due_dto),
        reviews_due=reviews_due_dto,
        upcoming_reviews=upcoming_dto,
    )
