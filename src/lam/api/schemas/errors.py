"""Stable error schemas conforming to Section 6.4 of the Implementation Specification."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    code: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of the error")
    request_id: str | None = Field(default=None, description="Server correlation ID")
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorPayload
