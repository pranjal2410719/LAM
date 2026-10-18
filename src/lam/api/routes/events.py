"""Learning events ingestion endpoint."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.events import EventIngestRequest, EventIngestResponse
from lam.application.services.ingestion_service import EventIngestionService
from lam.infrastructure.authentication.middleware import (
    SecurityContext,
    get_security_context,
)
from lam.infrastructure.database.session import get_db_session

router = APIRouter(prefix="/v1/events", tags=["Events"])


@router.post("", response_model=EventIngestResponse, status_code=status.HTTP_200_OK)
async def ingest_event(
    request: EventIngestRequest,
    sec: SecurityContext = Depends(get_security_context),
    session: AsyncSession = Depends(get_db_session),
) -> EventIngestResponse:
    """Ingests a structured learning interaction event into the immutable ledger.

    Guarantees:
    - Tenant-scoped authorization verified server-side.
    - Idempotency: duplicate submissions return duplicate status without re-applying state changes.
    - Atomic commit to ledger and learner state.
    """
    service = EventIngestionService(session)
    return await service.ingest_event(request, sec)
