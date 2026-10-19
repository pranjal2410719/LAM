"""Repository for persistent Learner State operations with concurrency safety."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lam.domain.events.models import LearningEvent
from lam.domain.learner_state.models import LearnerConceptState
from lam.domain.mastery.bkt import BKTEngine
from lam.domain.mastery.state_transition import apply_learning_event_transition
from lam.infrastructure.database.models import LearnerStateModel


class StateVersionConflictError(Exception):
    """Raised when an update carries a stale state_version (optimistic concurrency failure)."""

    pass


class StateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_concept_state(
        self,
        tenant_id: str,
        student_id: str,
        concept_id: str,
        for_update: bool = False,
    ) -> LearnerConceptState | None:
        """Retrieves learner concept state, optionally acquiring a row lock for update."""
        stmt = select(LearnerStateModel).where(
            LearnerStateModel.tenant_id == tenant_id,
            LearnerStateModel.student_id == student_id,
            LearnerStateModel.concept_id == concept_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
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

    async def record_event_state_transition(
        self,
        tenant_id: str,
        student_id: str,
        concept_id: str,
        event: LearningEvent,
        bkt_engine: BKTEngine | None = None,
    ) -> LearnerConceptState:
        """Atomically applies a learning event to the learner concept state.

        Uses PostgreSQL row-level locks (with_for_update) and savepoint retries to ensure
        strictly serializable, race-safe state updates under high concurrency.
        Delegates cognitive mastery and evidence rules to the domain layer.
        """
        stmt = (
            select(LearnerStateModel)
            .where(
                LearnerStateModel.tenant_id == tenant_id,
                LearnerStateModel.student_id == student_id,
                LearnerStateModel.concept_id == concept_id,
            )
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()

        now = datetime.now(UTC)
        current_state = LearnerConceptState.model_validate(model) if model else None

        updated_state, _, _ = apply_learning_event_transition(
            current_state=current_state,
            event=event,
            concept_id=concept_id,
            bkt_engine=bkt_engine,
            transition_time=now,
        )

        if not model:
            model = LearnerStateModel(
                tenant_id=tenant_id,
                student_id=student_id,
                concept_id=concept_id,
                concept_mastery=updated_state.concept_mastery,
                independent_mastery=updated_state.independent_mastery,
                assisted_performance=updated_state.assisted_performance,
                uncertainty=updated_state.uncertainty,
                total_events_count=updated_state.total_events_count,
                independent_attempts_count=updated_state.independent_attempts_count,
                assisted_attempts_count=updated_state.assisted_attempts_count,
                consecutive_independent_successes=updated_state.consecutive_independent_successes,
                prerequisite_readiness=updated_state.prerequisite_readiness,
                retention_strength=updated_state.retention_strength,
                last_practiced_at=updated_state.last_practiced_at,
                state_version=updated_state.state_version,
                last_event_id=updated_state.last_event_id,
                bkt_parameter_version=updated_state.bkt_parameter_version,
                created_at=now,
                updated_at=now,
            )
            try:
                async with self.session.begin_nested():
                    self.session.add(model)
                    await self.session.flush()
                return LearnerConceptState.model_validate(model)
            except IntegrityError:
                # Concurrent race created the row first: re-fetch with row lock
                res = await self.session.execute(stmt)
                model = res.scalar_one()
                current_state = LearnerConceptState.model_validate(model)
                updated_state, _, _ = apply_learning_event_transition(
                    current_state=current_state,
                    event=event,
                    concept_id=concept_id,
                    bkt_engine=bkt_engine,
                    transition_time=now,
                )

        # Apply domain state transition to existing/locked model
        model.concept_mastery = updated_state.concept_mastery
        model.independent_mastery = updated_state.independent_mastery
        model.assisted_performance = updated_state.assisted_performance
        model.uncertainty = updated_state.uncertainty
        model.total_events_count = updated_state.total_events_count
        model.independent_attempts_count = updated_state.independent_attempts_count
        model.assisted_attempts_count = updated_state.assisted_attempts_count
        model.consecutive_independent_successes = updated_state.consecutive_independent_successes
        model.prerequisite_readiness = updated_state.prerequisite_readiness
        model.retention_strength = updated_state.retention_strength
        model.last_practiced_at = updated_state.last_practiced_at
        model.last_event_id = updated_state.last_event_id
        model.bkt_parameter_version = updated_state.bkt_parameter_version
        model.state_version = updated_state.state_version
        model.updated_at = now

        await self.session.flush()
        return LearnerConceptState.model_validate(model)

    async def save_concept_state(
        self, state: LearnerConceptState, expected_version: int | None = None
    ) -> LearnerConceptState:
        """Persists or updates state with row locking and optimistic concurrency checks."""
        stmt = (
            select(LearnerStateModel)
            .where(
                LearnerStateModel.tenant_id == state.tenant_id,
                LearnerStateModel.student_id == state.student_id,
                LearnerStateModel.concept_id == state.concept_id,
            )
            .with_for_update()
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
                bkt_parameter_version=state.bkt_parameter_version,
                created_at=now,
                updated_at=now,
            )
            try:
                async with self.session.begin_nested():
                    self.session.add(model)
                    await self.session.flush()
                return LearnerConceptState.model_validate(model)
            except IntegrityError:
                res = await self.session.execute(stmt)
                model = res.scalar_one()

        if expected_version is not None and model.state_version != expected_version:
            msg = f"Stale state_version: expected {expected_version}, current {model.state_version}"
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
        model.bkt_parameter_version = state.bkt_parameter_version
        model.state_version = model.state_version + 1
        model.last_event_id = state.last_event_id
        model.updated_at = now

        await self.session.flush()
        return LearnerConceptState.model_validate(model)
