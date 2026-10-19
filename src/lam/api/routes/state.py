"""Learner State retrieval endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.state import ConceptStateDTO, LearnerStateResponse
from lam.infrastructure.authentication.middleware import (
    SecurityContext,
    get_security_context,
)
from lam.infrastructure.database.session import get_db_session
from lam.infrastructure.repositories.state_repository import StateRepository

router = APIRouter(prefix="/v1/learners", tags=["Learner State"])


@router.get("/{learner_id}/state", response_model=LearnerStateResponse)
async def get_learner_state(
    learner_id: str,
    sec: SecurityContext = Depends(get_security_context),
    session: AsyncSession = Depends(get_db_session),
) -> LearnerStateResponse:
    """Retrieves all concept states for an authorized learner within the tenant."""
    repo = StateRepository(session)
    states = await repo.get_all_student_states(
        tenant_id=sec.tenant_id,
        student_id=learner_id,
    )

    dtos = [
        ConceptStateDTO(
            concept_id=s.concept_id,
            concept_mastery=s.concept_mastery,
            independent_mastery=s.independent_mastery,
            assisted_performance=s.assisted_performance,
            uncertainty=s.uncertainty,
            total_events_count=s.total_events_count,
            independent_attempts_count=s.independent_attempts_count,
            assisted_attempts_count=s.assisted_attempts_count,
            consecutive_independent_successes=s.consecutive_independent_successes,
            prerequisite_readiness=s.prerequisite_readiness,
            retention_strength=s.retention_strength,
            last_practiced_at=s.last_practiced_at,
            state_version=s.state_version,
            last_event_id=s.last_event_id,
            bkt_parameter_version=s.bkt_parameter_version,
            updated_at=s.updated_at,
        )
        for s in states
    ]

    return LearnerStateResponse(
        tenant_id=sec.tenant_id,
        student_id=learner_id,
        concepts=dtos,
    )


@router.get("/{learner_id}/concepts/{concept_id}/state", response_model=ConceptStateDTO)
async def get_learner_concept_state(
    learner_id: str,
    concept_id: str,
    sec: SecurityContext = Depends(get_security_context),
    session: AsyncSession = Depends(get_db_session),
) -> ConceptStateDTO:
    """Retrieves the state for a single concept of an authorized learner."""
    repo = StateRepository(session)
    state = await repo.get_concept_state(
        tenant_id=sec.tenant_id,
        student_id=learner_id,
        concept_id=concept_id,
    )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept state not found for concept '{concept_id}'",
        )

    return ConceptStateDTO(
        concept_id=state.concept_id,
        concept_mastery=state.concept_mastery,
        independent_mastery=state.independent_mastery,
        assisted_performance=state.assisted_performance,
        uncertainty=state.uncertainty,
        total_events_count=state.total_events_count,
        independent_attempts_count=state.independent_attempts_count,
        assisted_attempts_count=state.assisted_attempts_count,
        consecutive_independent_successes=state.consecutive_independent_successes,
        prerequisite_readiness=state.prerequisite_readiness,
        retention_strength=state.retention_strength,
        last_practiced_at=state.last_practiced_at,
        state_version=state.state_version,
        last_event_id=state.last_event_id,
        bkt_parameter_version=state.bkt_parameter_version,
        updated_at=state.updated_at,
    )
