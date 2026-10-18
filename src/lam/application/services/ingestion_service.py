"""Application service for atomic, idempotent learning event ingestion."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.events import EventIngestRequest, EventIngestResponse
from lam.domain.events.models import LearningEvent
from lam.domain.learner_state.models import LearnerConceptState
from lam.infrastructure.authentication.middleware import SecurityContext
from lam.infrastructure.repositories.ledger_repository import (
    IngestionStatus,
    LedgerRepository,
)
from lam.infrastructure.repositories.state_repository import StateRepository


class EventIngestionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ledger_repo = LedgerRepository(session)
        self.state_repo = StateRepository(session)

    async def ingest_event(
        self, request: EventIngestRequest, sec: SecurityContext
    ) -> EventIngestResponse:
        """Processes and records an incoming learning event transactionally."""
        # Enforce server-side tenant scoping
        tenant_id = sec.tenant_id

        domain_event = LearningEvent(
            tenant_id=tenant_id,
            event_id=request.event_id,
            student_id=request.student_id,
            session_id=request.session_id,
            concept_ids=request.concept_ids,
            item_id=request.item_id,
            timestamp=request.timestamp,
            event_type=request.event_type,
            correctness=request.correctness,
            attempt_number=request.attempt_number,
            assistance_level=request.assistance_level,
            hints_used=request.hints_used,
            response_time_ms=request.response_time_ms,
            self_reported_confidence=request.self_reported_confidence,
            strategy_id=request.strategy_id,
            intervention_id=request.intervention_id,
            difficulty=request.difficulty,
            assessment_mode=request.assessment_mode,
            provenance=request.provenance,
            schema_version=request.schema_version,
        )

        # 1. Idempotency Check & Ledger Persistence
        ingest_status, event_model = await self.ledger_repo.ingest_event(domain_event)

        if ingest_status == IngestionStatus.CONFLICT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Event ID '{request.event_id}' already exists with conflicting attributes",
            )

        if ingest_status == IngestionStatus.DUPLICATE:
            return EventIngestResponse(
                status="duplicate",
                event_id=event_model.event_id,
                tenant_id=event_model.tenant_id,
                student_id=event_model.student_id,
                affected_concept_ids=event_model.concept_ids,
                ingested_at=event_model.ingested_at,
                message="Event already ingested; no state changes applied.",
            )

        # 2. Update Learner State for each referenced concept
        now = datetime.now(UTC)
        for concept_id in domain_event.concept_ids:
            current_state = await self.state_repo.get_concept_state(
                tenant_id=tenant_id,
                student_id=domain_event.student_id,
                concept_id=concept_id,
            )
            if not current_state:
                current_state = LearnerConceptState(
                    tenant_id=tenant_id,
                    student_id=domain_event.student_id,
                    concept_id=concept_id,
                    concept_mastery=0.0,
                    independent_mastery=0.0,
                    assisted_performance=0.0,
                    uncertainty=1.0,
                    total_events_count=1,
                    state_version=1,
                    last_event_id=domain_event.event_id,
                    last_practiced_at=now,
                )
            else:
                current_state.total_events_count += 1
                current_state.last_practiced_at = now
                current_state.last_event_id = domain_event.event_id

            # Track assisted vs unassisted metrics
            is_assisted = (
                domain_event.assistance_level is not None and domain_event.assistance_level > 0
            ) or (domain_event.hints_used is not None and domain_event.hints_used > 0)

            if is_assisted:
                current_state.assisted_attempts_count += 1
                if domain_event.correctness is True:
                    # Assisted success increases assisted performance, NOT independent mastery!
                    current_state.assisted_performance = min(
                        1.0, current_state.assisted_performance + 0.1
                    )
            else:
                current_state.independent_attempts_count += 1
                if domain_event.correctness is True:
                    current_state.consecutive_independent_successes += 1
                    current_state.independent_mastery = min(
                        1.0, current_state.independent_mastery + 0.2
                    )
                    current_state.uncertainty = max(0.1, current_state.uncertainty - 0.15)
                elif domain_event.correctness is False:
                    current_state.consecutive_independent_successes = 0
                    current_state.uncertainty = max(0.1, current_state.uncertainty - 0.05)

            await self.state_repo.save_concept_state(current_state)

        # Commit transaction atomically
        await self.session.commit()

        return EventIngestResponse(
            status="ingested",
            event_id=event_model.event_id,
            tenant_id=event_model.tenant_id,
            student_id=event_model.student_id,
            affected_concept_ids=domain_event.concept_ids,
            ingested_at=event_model.ingested_at,
            message="Event successfully validated, stored, and learner state updated.",
        )
