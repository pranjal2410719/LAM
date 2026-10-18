"""Repository for durable, idempotent event ledger operations."""

from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lam.domain.events.models import LearningEvent
from lam.infrastructure.database.models import LearningEventModel


class IngestionStatus(StrEnum):
    INGESTED = "ingested"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


class LedgerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_event_id(self, tenant_id: str, event_id: str) -> LearningEventModel | None:
        stmt = select(LearningEventModel).where(
            LearningEventModel.tenant_id == tenant_id,
            LearningEventModel.event_id == event_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def ingest_event(
        self, event: LearningEvent
    ) -> tuple[IngestionStatus, LearningEventModel]:
        """Idempotently ingest a validated learning event.

        - If new: persists and returns (INGESTED, model).
        - If duplicate with identical parameters: returns (DUPLICATE, existing_model).
        - If conflict (same event_id, different attributes): returns (CONFLICT, existing_model).
        """
        existing = await self.get_by_event_id(event.tenant_id, event.event_id)
        if existing:
            # Check for conflict: same event_id but different student, session, or item
            if (
                existing.student_id != event.student_id
                or existing.session_id != event.session_id
                or existing.item_id != event.item_id
            ):
                return IngestionStatus.CONFLICT, existing
            return IngestionStatus.DUPLICATE, existing

        provenance_dict: dict[str, Any] | None = None
        if event.provenance:
            provenance_dict = event.provenance.model_dump()

        model = LearningEventModel(
            tenant_id=event.tenant_id,
            event_id=event.event_id,
            student_id=event.student_id,
            session_id=event.session_id,
            concept_ids=event.concept_ids,
            item_id=event.item_id,
            timestamp=event.timestamp,
            event_type=event.event_type.value,
            correctness=event.correctness,
            attempt_number=event.attempt_number,
            assistance_level=event.assistance_level,
            hints_used=event.hints_used,
            response_time_ms=event.response_time_ms,
            self_reported_confidence=event.self_reported_confidence,
            strategy_id=event.strategy_id,
            intervention_id=event.intervention_id,
            difficulty=event.difficulty,
            assessment_mode=event.assessment_mode.value if event.assessment_mode else None,
            provenance=provenance_dict,
            schema_version=event.schema_version,
        )
        self.session.add(model)
        await self.session.flush()
        return IngestionStatus.INGESTED, model
