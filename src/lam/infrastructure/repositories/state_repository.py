"""Repository for persistent Learner State operations."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lam.domain.learner_state.models import LearnerConceptState
from lam.infrastructure.database.models import LearnerStateModel


class StateVersionConflictError(Exception):
    """Raised when an update carries a stale state_version (optimistic concurrency failure)."""

    pass


class StateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_concept_state(
        self, tenant_id: str, student_id: str, concept_id: str
    ) -> LearnerConceptState | None:
        stmt = select(LearnerStateModel).where(
            LearnerStateModel.tenant_id == tenant_id,
            LearnerStateModel.student_id == student_id,
            LearnerStateModel.concept_id == concept_id,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None
        return LearnerConceptState.model_validate(model)

    async def get_all_student_states(
        self, tenant_id: str, student_id: str
    ) -> list[LearnerConceptState]:
        stmt = (
            select(LearnerStateModel)
            .where(
                LearnerStateModel.tenant_id == tenant_id,
                LearnerStateModel.student_id == student_id,
            )
            .order_by(LearnerStateModel.concept_id)
        )
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [LearnerConceptState.model_validate(m) for m in models]

    async def save_concept_state(
        self, state: LearnerConceptState, expected_version: int | None = None
    ) -> LearnerConceptState:
        """Persists or updates state with optimistic concurrency check."""
        stmt = select(LearnerStateModel).where(
            LearnerStateModel.tenant_id == state.tenant_id,
            LearnerStateModel.student_id == state.student_id,
            LearnerStateModel.concept_id == state.concept_id,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()

        now = datetime.now(UTC)

        if not model:
            model = LearnerStateModel(
                tenant_id=state.tenant_id,
                student_id=state.student_id,
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
                created_at=now,
                updated_at=now,
            )
            self.session.add(model)
        else:
            if expected_version is not None and model.state_version != expected_version:
                msg = (
                    f"Stale state_version: expected {expected_version}, "
                    f"current {model.state_version}"
                )
                raise StateVersionConflictError(msg)
            model.concept_mastery = state.concept_mastery
            model.independent_mastery = state.independent_mastery
            model.assisted_performance = state.assisted_performance
            model.uncertainty = state.uncertainty
            model.total_events_count = state.total_events_count
            model.independent_attempts_count = state.independent_attempts_count
            model.assisted_attempts_count = state.assisted_attempts_count
            model.consecutive_independent_successes = state.consecutive_independent_successes
            model.prerequisite_readiness = state.prerequisite_readiness
            model.retention_strength = state.retention_strength
            model.last_practiced_at = state.last_practiced_at
            model.state_version = model.state_version + 1
            model.last_event_id = state.last_event_id
            model.updated_at = now

        await self.session.flush()
        return LearnerConceptState.model_validate(model)
