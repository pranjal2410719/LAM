"""API router for next-action recommendations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.recommendations import (
    RecommendationRequest,
    RecommendationResponse,
)
from lam.application.services.recommendation_service import RecommendationService
from lam.infrastructure.authentication.middleware import (
    SecurityContext,
    authorize_access,
    get_security_context,
)
from lam.infrastructure.database.session import get_db_session

router = APIRouter(prefix="/v1/recommendations", tags=["Recommendations"])


@router.post("", response_model=RecommendationResponse)
async def request_recommendation(
    request: RecommendationRequest,
    sec: SecurityContext = Depends(get_security_context),
    session: AsyncSession = Depends(get_db_session),
) -> RecommendationResponse:
    """Evaluates learner state and returns a deterministic next-action recommendation.

    Complies with Section 10 of the LAM Implementation Specification.
    Strictly service-only and tenant-isolated: only evaluates data within the authenticated tenant.
    """
    authorize_access(sec, resource="recommendations")
    service = RecommendationService(session)
    return await service.get_recommendation(request=request, sec=sec)
