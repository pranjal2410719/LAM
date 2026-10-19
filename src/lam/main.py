"""Main FastAPI Application Entry Point for LAM."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from lam.api.routes import curriculum, events, health, recommendations, reviews, state
from lam.api.schemas.errors import ErrorPayload, ErrorResponse
from lam.infrastructure.config import settings
from lam.infrastructure.database.session import verify_db_connection


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup hooks: validate security configuration and verify database connectivity.

    Schema must be managed by Alembic migrations prior to service boot.
    """
    settings.validate_production_security()
    await verify_db_connection()
    yield


app = FastAPI(
    title="Learning Adaptation Model (LAM)",
    version="0.1.0",
    description=(
        "Independent, versioned service turning learning evidence into learner "
        "state and recommendations."
    ),
    lifespan=lifespan,
)


# Global validation error handler formatting to stable error schema
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()
    ]
    error_payload = ErrorResponse(
        error=ErrorPayload(
            code="INVALID_EVENT_SCHEMA",
            message="The submitted payload does not satisfy the required schema.",
            request_id=request.headers.get("X-Request-ID"),
            details=details,
        )
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_payload.model_dump(),
    )


# Mount routers
app.include_router(health.router)
app.include_router(events.router)
app.include_router(state.router)
app.include_router(recommendations.router)
app.include_router(reviews.router)
app.include_router(curriculum.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "LAM", "status": "running", "version": "0.1.0"}
