"""Integration tests verifying behavior against a live PostgreSQL 16 database."""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from lam.infrastructure.database.session import get_db_session
from lam.main import app

POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_URL",
    "postgresql+asyncpg://lam_user:lam_password@localhost:5432/lam_test_db",
)

pg_engine = create_async_engine(POSTGRES_TEST_URL, poolclass=NullPool, echo=False)
pg_session_factory = async_sessionmaker(
    bind=pg_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_postgres_db() -> AsyncGenerator[None, None]:
    """Cleans tables before and after each test."""
    async with pg_session_factory() as session:
        await session.execute(text("TRUNCATE TABLE learning_events, learner_states CASCADE"))
        await session.commit()
    yield
    async with pg_session_factory() as session:
        await session.execute(text("TRUNCATE TABLE learning_events, learner_states CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    async with pg_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def pg_client() -> AsyncGenerator[AsyncClient, None]:
    """FastAPI async client configured to use PostgreSQL session pool."""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_postgres_connection_and_table_presence(pg_session: AsyncSession) -> None:
    """Verifies that the live PostgreSQL instance is connected and migrations have run."""
    res = await pg_session.execute(text("SELECT 1"))
    assert res.scalar() == 1

    tables = await pg_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    )
    table_names = [row[0] for row in tables.fetchall()]
    assert "learning_events" in table_names
    assert "learner_states" in table_names
    assert "alembic_version" in table_names


@pytest.mark.asyncio
async def test_postgres_event_ingestion_and_state_update(pg_client: AsyncClient) -> None:
    """Tests end-to-end event ingestion against live PostgreSQL."""
    headers = {
        "Authorization": "Bearer token_pg_test_12345",
        "X-Tenant-ID": "tenant_pg_alpha",
    }
    payload = {
        "event_id": "pg_evt_001",
        "student_id": "student_pg_1",
        "session_id": "sess_pg_1",
        "concept_ids": ["math.fractions"],
        "item_id": "item_pg_1",
        "timestamp": "2026-10-18T12:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }

    resp = await pg_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ingested"

    # Query state from PostgreSQL
    state_resp = await pg_client.get(
        "/v1/learners/student_pg_1/concepts/math.fractions/state",
        headers=headers,
    )
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert state["total_events_count"] == 1
    assert state["independent_attempts_count"] == 1
    assert state["state_version"] >= 1


@pytest.mark.asyncio
async def test_postgres_idempotency_deduplication(pg_client: AsyncClient) -> None:
    """Tests that duplicate event replay against PostgreSQL does not re-apply updates."""
    headers = {
        "Authorization": "Bearer token_pg_test_12345",
        "X-Tenant-ID": "tenant_pg_alpha",
    }
    payload = {
        "event_id": "pg_evt_dup_001",
        "student_id": "student_pg_2",
        "session_id": "sess_pg_2",
        "concept_ids": ["math.geometry"],
        "item_id": "item_pg_2",
        "timestamp": "2026-10-18T12:05:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }

    # First attempt: ingested
    r1 = await pg_client.post("/v1/events", json=payload, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "ingested"

    # Second attempt: duplicate returned
    r2 = await pg_client.post("/v1/events", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"

    # Verify event count remains exactly 1 in PostgreSQL
    state_resp = await pg_client.get(
        "/v1/learners/student_pg_2/concepts/math.geometry/state",
        headers=headers,
    )
    assert state_resp.json()["total_events_count"] == 1


@pytest.mark.asyncio
async def test_postgres_tenant_isolation(pg_client: AsyncClient) -> None:
    """Tests cross-tenant isolation enforcement in PostgreSQL."""
    headers_a = {
        "Authorization": "Bearer token_tenant_a_001",
        "X-Tenant-ID": "tenant_pg_alpha",
    }
    payload = {
        "event_id": "pg_evt_iso_100",
        "student_id": "student_shared_pg",
        "session_id": "sess_iso",
        "concept_ids": ["physics.vectors"],
        "item_id": "item_v1",
        "timestamp": "2026-10-18T12:10:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    r = await pg_client.post("/v1/events", json=payload, headers=headers_a)
    assert r.status_code == 200

    # Query from Tenant B (should return 404)
    headers_b = {
        "Authorization": "Bearer token_tenant_b_002",
        "X-Tenant-ID": "tenant_pg_beta",
    }
    r_b = await pg_client.get(
        "/v1/learners/student_shared_pg/concepts/physics.vectors/state",
        headers=headers_b,
    )
    assert r_b.status_code == 404
