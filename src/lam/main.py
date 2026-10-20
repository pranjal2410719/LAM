"""Main FastAPI Application Entry Point for LAM."""

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from lam.api.routes import curriculum, events, health, recommendations, reviews, state
from lam.api.schemas.errors import ErrorPayload, ErrorResponse
from lam.infrastructure.config import settings
from lam.infrastructure.database.session import engine, verify_db_connection

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lam.service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup hooks: validate security configuration and verify database connectivity.

    Schema must be managed by Alembic migrations prior to service boot.
    Gracefully disposes database connection pool on shutdown.
    """
    settings.validate_production_security()
    await verify_db_connection()
    yield
    await engine.dispose()


app = FastAPI(
    title="Learning Adaptation Model (LAM)",
    version="0.1.0",
    description=(
        "Independent, versioned service turning learning evidence into learner "
        "state and recommendations."
    ),
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_and_logging_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Attaches request correlation ID and logs structured HTTP metrics."""
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
    request.state.request_id = req_id

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    response.headers["X-Request-ID"] = req_id

    # Do not flood logs with healthy liveness probes
    if request.url.path != "/health/live" or response.status_code >= 400:
        logger.info(
            "%s %s -> %d in %.2fms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            req_id,
        )

    return response


# Global validation error handler formatting to stable error schema
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()
    ]
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    error_payload = ErrorResponse(
        error=ErrorPayload(
            code="INVALID_EVENT_SCHEMA",
            message="The submitted payload does not satisfy the required schema.",
            request_id=req_id,
            details=details,
        )
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_payload.model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Safe fail-closed error response preventing credential or traceback leakage."""
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    logger.exception(
        "Unhandled error processing %s %s [%s]", request.method, request.url.path, req_id
    )
    error_payload = ErrorResponse(
        error=ErrorPayload(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred.",
            request_id=req_id,
            details=[],
        )
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
