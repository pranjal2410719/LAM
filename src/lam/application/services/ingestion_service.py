"""Application service for atomic, idempotent learning event ingestion."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.events import EventIngestRequest, EventIngestResponse
from lam.domain.events.models import LearningEvent
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
        """Processes and records an incoming learning event transactionally.

        Guarantees:
        - Atomic ledger record and learner state update within a single transaction.
        - Full rollback on failure.
        - Strict idempotency against duplicate event submissions.
        - Concurrency safety with row-level locks on state updates.

        Note on Milestone M0/M1 State Updates:
        The current fixed-step (+0.2 / +0.1) increments are interim M0 scaffolding placeholders
        to establish ledger/state mechanics. They MUST NOT be exposed to downstream clients as
        calibrated mastery probabilities until replaced by the validated Bayesian Knowledge
        Tracing (BKT) domain engine in Milestone M1.
        """
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

        try:
            # 1. Idempotency Check & Ledger Persistence (with race-safe savepoint)
            ingest_status, event_model = await self.ledger_repo.ingest_event(domain_event)

            if ingest_status == IngestionStatus.CONFLICT:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Event ID '{request.event_id}' already exists with conflicting attributes"
                    ),
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

            # 2. Update Learner State for each referenced concept atomically with row locks
            for concept_id in domain_event.concept_ids:
                await self.state_repo.record_event_state_transition(
                    tenant_id=tenant_id,
                    student_id=domain_event.student_id,
                    concept_id=concept_id,
                    event=domain_event,
                )

            # Atomic commit of ledger event and learner states
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
        except Exception:
            await self.session.rollback()
            raise
