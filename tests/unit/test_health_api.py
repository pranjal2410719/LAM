"""Unit tests for service health, liveness, readiness, and tracing."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lam.infrastructure.database.session import get_db_session
from lam.main import app
from tests.conftest import scoped_async_client


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


async def _run_failing_database_readiness_probe() -> None:
    """Helper that installs a failing session override and verifies /health/ready returns 503."""

    async def failing_session_override() -> AsyncGenerator[AsyncSession, None]:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = ConnectionRefusedError(
            "Sensitive internal database hostname:5432 refused"
        )
        yield mock_session

    had_override = get_db_session in app.dependency_overrides
    prev_override = app.dependency_overrides.get(get_db_session)
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
        if had_override:
            app.dependency_overrides[get_db_session] = prev_override  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_readiness_probe_failing_database_returns_503() -> None:
    await _run_failing_database_readiness_probe()


@pytest.mark.asyncio
async def test_request_id_tracing_echoes_client_header(async_client: AsyncClient) -> None:
    custom_id = "req_custom_trace_12345"
    resp = await async_client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_readiness_probe_preserves_unrelated_dependency_overrides() -> None:
    """Verifies failing readiness probe cleanup does not wipe unrelated dependency overrides."""

    def unrelated_dep() -> str:
        return "unrelated_value"

    had_unrelated = unrelated_dep in app.dependency_overrides
    prev_unrelated = app.dependency_overrides.get(unrelated_dep)
    had_db = get_db_session in app.dependency_overrides
    prev_db = app.dependency_overrides.get(get_db_session)

    app.dependency_overrides[unrelated_dep] = lambda: "custom_unrelated"
    try:
        await _run_failing_database_readiness_probe()

        # Unrelated override is preserved; get_db_session is restored to original state
        assert unrelated_dep in app.dependency_overrides
        assert app.dependency_overrides[unrelated_dep]() == "custom_unrelated"
        assert (get_db_session in app.dependency_overrides) == had_db
        assert app.dependency_overrides.get(get_db_session) == prev_db
    finally:
        if had_unrelated:
            app.dependency_overrides[unrelated_dep] = prev_unrelated  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(unrelated_dep, None)
        if had_db:
            app.dependency_overrides[get_db_session] = prev_db  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_readiness_probe_restores_preexisting_none_override() -> None:
    """Verifies pre-existing None-valued override is preserved after readiness probe test."""
    had_db = get_db_session in app.dependency_overrides
    prev_db = app.dependency_overrides.get(get_db_session)

    app.dependency_overrides[get_db_session] = None  # type: ignore[assignment]
    try:
        await _run_failing_database_readiness_probe()

        # Key is restored and value is still None
        assert get_db_session in app.dependency_overrides
        assert app.dependency_overrides[get_db_session] is None
    finally:
        if had_db:
            app.dependency_overrides[get_db_session] = prev_db  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_scoped_async_client_preserves_unrelated_overrides() -> None:
    """Verifies scoped_async_client teardown does not wipe unrelated FastAPI overrides."""

    def dummy_dep() -> str:
        return "original"

    def dummy_override() -> str:
        return "overridden"

    had_dummy = dummy_dep in app.dependency_overrides
    prev_dummy = app.dependency_overrides.get(dummy_dep)
    had_db = get_db_session in app.dependency_overrides
    prev_db = app.dependency_overrides.get(get_db_session)

    app.dependency_overrides[dummy_dep] = dummy_override
    try:
        mock_session = AsyncMock(spec=AsyncSession)
        async with scoped_async_client(mock_session):
            assert app.dependency_overrides[dummy_dep] == dummy_override
            assert get_db_session in app.dependency_overrides

        # Unrelated override survived; get_db_session restored to initial state
        assert dummy_dep in app.dependency_overrides
        assert app.dependency_overrides[dummy_dep] == dummy_override
        assert (get_db_session in app.dependency_overrides) == had_db
        assert app.dependency_overrides.get(get_db_session) == prev_db
    finally:
        if had_dummy:
            app.dependency_overrides[dummy_dep] = prev_dummy  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(dummy_dep, None)
        if had_db:
            app.dependency_overrides[get_db_session] = prev_db  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_scoped_async_client_restores_preexisting_override_and_none() -> None:
    """Verifies scoped_async_client restores pre-existing callable and None overrides."""
    had_db = get_db_session in app.dependency_overrides
    prev_db = app.dependency_overrides.get(get_db_session)

    try:
        # Case 1: Pre-existing callable
        def pre_existing() -> str:
            return "pre"

        app.dependency_overrides[get_db_session] = pre_existing
        mock_session = AsyncMock(spec=AsyncSession)

        async with scoped_async_client(mock_session):
            assert app.dependency_overrides[get_db_session] != pre_existing

        assert get_db_session in app.dependency_overrides
        assert app.dependency_overrides[get_db_session] == pre_existing

        # Case 2: Pre-existing None
        app.dependency_overrides[get_db_session] = None  # type: ignore[assignment]

        async with scoped_async_client(mock_session):
            assert app.dependency_overrides[get_db_session] is not None

        assert get_db_session in app.dependency_overrides
        assert app.dependency_overrides[get_db_session] is None
    finally:
        if had_db:
            app.dependency_overrides[get_db_session] = prev_db  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_scoped_async_client_preserves_overrides_on_exception() -> None:
    """Verifies scoped_async_client restores overrides even when an exception is raised in test."""

    def dummy_dep() -> str:
        return "unrelated_err"

    def dummy_func() -> str:
        return "val"

    had_dummy = dummy_dep in app.dependency_overrides
    prev_dummy = app.dependency_overrides.get(dummy_dep)
    had_db = get_db_session in app.dependency_overrides
    prev_db = app.dependency_overrides.get(get_db_session)

    app.dependency_overrides[dummy_dep] = dummy_func
    try:
        mock_session = AsyncMock(spec=AsyncSession)

        with pytest.raises(RuntimeError, match="simulated failure"):
            async with scoped_async_client(mock_session):
                assert app.dependency_overrides[dummy_dep] == dummy_func
                assert get_db_session in app.dependency_overrides
                raise RuntimeError("simulated failure")

        assert dummy_dep in app.dependency_overrides
        assert app.dependency_overrides[dummy_dep] == dummy_func
        assert (get_db_session in app.dependency_overrides) == had_db
        assert app.dependency_overrides.get(get_db_session) == prev_db
    finally:
        if had_dummy:
            app.dependency_overrides[dummy_dep] = prev_dummy  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(dummy_dep, None)
        if had_db:
            app.dependency_overrides[get_db_session] = prev_db  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(get_db_session, None)
