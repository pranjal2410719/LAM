"""Health check routes."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lam.infrastructure.database.session import get_db_session

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    """Service liveness probe."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness(session: AsyncSession = Depends(get_db_session)) -> JSONResponse:
    """Service readiness probe checking database availability.

    Returns HTTP 200 when database connectivity is verified.
    Returns HTTP 503 without leaking internal credentials or tracebacks on failure.
    """
    try:
        await session.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "connected"},
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "disconnected"},
        )
