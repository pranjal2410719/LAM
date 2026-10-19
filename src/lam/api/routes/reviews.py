"""Spaced retrieval review API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.reviews import (
    ReviewsDueResponse,
    ScheduledReviewItemDTO,
)
from lam.domain.retrieval.scheduler import SpacedRetrievalScheduler
from lam.infrastructure.authentication.middleware import (
    SecurityContext,
    get_security_context,
)
from lam.infrastructure.database.session import get_db_session
from lam.infrastructure.repositories.state_repository import StateRepository

router = APIRouter(prefix="/v1/learners", tags=["Spaced Retrieval"])


@router.get("/{learner_id}/reviews", response_model=ReviewsDueResponse)
async def get_learner_reviews(
    learner_id: str,
    sec: SecurityContext = Depends(get_security_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewsDueResponse:
    """Retrieves scheduled and overdue spaced retrieval reviews for an authorized learner."""
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

    return ReviewsDueResponse(
        student_id=learner_id,
        evaluated_at=schedule_result.evaluated_at,
        policy_version=schedule_result.policy_version,
        total_concepts_evaluated=schedule_result.total_concepts_evaluated,
        reviews_due_count=schedule_result.reviews_due_count,
        reviews_due=reviews_due_dto,
        upcoming_reviews=upcoming_dto,
    )
