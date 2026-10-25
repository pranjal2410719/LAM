"""Pytest configuration and test fixtures."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lam.infrastructure.authentication.jwt import create_access_token
from lam.infrastructure.database.models import Base
from lam.infrastructure.database.session import get_db_session
from lam.main import app


def auth_headers(
    tenant_id: str = "tenant_test",
    client_id: str = "test_client",
    roles: list[str] | None = None,
) -> dict[str, str]:
    """Helper returning cryptographically verified Authorization and X-Tenant-ID headers."""
    token = create_access_token(tenant_id=tenant_id, client_id=client_id, roles=roles)
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


# Isolated SQLite in-memory database for testing
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_async_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Recreate clean database tables for every test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session_factory() as session:
        yield session


@asynccontextmanager
async def scoped_async_client(
    session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Async context manager managing FastAPI dependency overrides for test SQLite sessions.

    Preserves and restores any pre-existing get_db_session dependency override
    without clearing unrelated overrides.
    """

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    had_override = get_db_session in app.dependency_overrides
    prev_override = app.dependency_overrides.get(get_db_session)
    app.dependency_overrides[get_db_session] = override_get_db_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        if had_override:
            app.dependency_overrides[get_db_session] = prev_override  # type: ignore[assignment]
        else:
            app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI async client configured to use the isolated SQLite test session."""
    async with scoped_async_client(db_session) as client:
        yield client
