"""Unit tests for service health, liveness, readiness, and tracing."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lam.infrastructure.database.session import get_db_session
from lam.main import app


@pytest.mark.asyncio
async def test_liveness_probe_returns_200(async_client: AsyncClient) -> None:
    resp = await async_client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}
    assert "X-Request-ID" in resp.headers


@pytest.mark.asyncio
async def test_readiness_probe_healthy_returns_200(async_client: AsyncClient) -> None:
    resp = await async_client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "connected"}
    assert "X-Request-ID" in resp.headers


@pytest.mark.asyncio
async def test_readiness_probe_failing_database_returns_503() -> None:
    # Override session to simulate database outage
    async def failing_session_override() -> AsyncGenerator[AsyncSession, None]:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = ConnectionRefusedError(
            "Sensitive internal database hostname:5432 refused"
        )
        yield mock_session

    app.dependency_overrides[get_db_session] = failing_session_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/ready")
            assert resp.status_code == 503
            body = resp.json()
            assert body["status"] == "unavailable"
            assert body["database"] == "disconnected"
            # Verify no sensitive DB host or traceback details leaked
            assert "Sensitive internal database" not in resp.text
            assert "5432" not in resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_request_id_tracing_echoes_client_header(async_client: AsyncClient) -> None:
    custom_id = "req_custom_trace_12345"
    resp = await async_client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == custom_id
