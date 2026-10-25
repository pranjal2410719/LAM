"""Centralized PostgreSQL test fixtures with verified non-cascading cleanup.

Enforces:
- Static URL and opt-in validation before engine binding.
- Runtime active catalog and role privilege inspection.
- Explicit, non-cascading cleanup of all 4 application tables in dependency order.
- Guaranteed teardown with try/finally, preserving any test failure if teardown fails.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from lam.infrastructure.database.session import get_db_session
from lam.main import app
from tests.integration.db_guard import (
    validate_test_connection_string,
    verify_role_isolation_and_privileges,
)

# Verified application tables to clean (without CASCADE, in reverse dependency order)
APPLICATION_TABLES = [
    "hypothesis_audit_entries",
    "misconception_hypotheses",
    "learning_events",
    "learner_states",
]


@pytest.fixture(scope="session")
def postgres_test_url() -> str:
    """Validates and returns the test connection URL."""
    url = os.getenv("POSTGRES_TEST_URL")
    validate_test_connection_string(url)
    return url  # type: ignore[return-value]


@pytest_asyncio.fixture(scope="session")
async def pg_engine(postgres_test_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """Provides a guarded AsyncEngine with runtime privilege and boundary inspection."""
    parsed_url = make_url(postgres_test_url)
    engine = create_async_engine(postgres_test_url, poolclass=NullPool, echo=False)

    # Probe runtime catalog and role privileges on first connection
    async with engine.connect() as conn:
        await verify_role_isolation_and_privileges(conn, parsed_url.database or "")

    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def pg_session_factory(pg_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session maker bound to guarded NullPool engine."""
    return async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def clean_pg_session(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated database session with guaranteed pre- and post-test cleanup.

    Guarantees teardown runs via try...finally without swallowing original test failures.
    """
    clean_query = text(f"TRUNCATE TABLE {', '.join(APPLICATION_TABLES)};")

    # 1. Setup cleanup
    async with pg_session_factory() as setup_session:
        await setup_session.execute(clean_query)
        await setup_session.commit()

    test_session = pg_session_factory()
    teardown_error: Exception | None = None
    try:
        yield test_session
    finally:
        # Guarantee session is closed before teardown DDL to avoid lock contention
        try:
            await test_session.close()
        except Exception as e:
            teardown_error = e

        # 2. Teardown cleanup: always executes
        try:
            async with pg_session_factory() as teardown_session:
                await teardown_session.execute(clean_query)
                await teardown_session.commit()
        except Exception as e:
            if teardown_error is None:
                teardown_error = e

        if teardown_error is not None:
            # Re-raise so teardown failures are not masked
            raise teardown_error


@asynccontextmanager
async def scoped_pg_client(
    clean_pg_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Async context manager managing FastAPI dependency overrides for test PostgreSQL sessions.

    Preserves and restores any pre-existing get_db_session dependency override
    without clearing unrelated overrides.
    """

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield clean_pg_session

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
async def pg_client(clean_pg_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI async client configured to use the cleaned PostgreSQL session."""
    async with scoped_pg_client(clean_pg_session) as client:
        yield client


@pytest_asyncio.fixture
async def pg_client_concurrent(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI async client for concurrency tests.

    Unlike pg_client, each request receives its own independent session from
    the pool so concurrent asyncio.gather calls do not share a single session.
    Pre- and post-test cleanup truncates all application tables.
    """
    clean_query = text(f"TRUNCATE TABLE {', '.join(APPLICATION_TABLES)};")

    async with pg_session_factory() as setup_session:
        await setup_session.execute(clean_query)
        await setup_session.commit()

    had_override = get_db_session in app.dependency_overrides
    prev_override = app.dependency_overrides.get(get_db_session)

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_factory() as session:
            yield session

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

        async with pg_session_factory() as teardown_session:
            await teardown_session.execute(clean_query)
            await teardown_session.commit()
