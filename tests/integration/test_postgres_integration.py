"""Integration tests verifying behavior against a live PostgreSQL 16 database."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_postgres_connection_and_table_presence(clean_pg_session: AsyncSession) -> None:
    """Verifies that the live PostgreSQL instance is connected and migrations have run."""
    res = await clean_pg_session.execute(text("SELECT 1"))
    assert res.scalar() == 1

    tables = await clean_pg_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    )
    table_names = [row[0] for row in tables.fetchall()]
    assert "learning_events" in table_names
    assert "learner_states" in table_names
    assert "alembic_version" in table_names


@pytest.mark.asyncio
async def test_postgres_event_ingestion_and_state_update(pg_client: AsyncClient) -> None:
    """Tests end-to-end event ingestion against live PostgreSQL."""
    headers = auth_headers(tenant_id="tenant_pg_alpha", client_id="pg_client_1")
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
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
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
    assert state["bkt_parameter_version"] == "bkt_v1_baseline"
    assert state["state_version"] >= 1


@pytest.mark.asyncio
async def test_postgres_idempotency_deduplication(pg_client: AsyncClient) -> None:
    """Tests that duplicate event replay against PostgreSQL does not re-apply updates."""
    headers = auth_headers(tenant_id="tenant_pg_alpha", client_id="pg_client_2")
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
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
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
    headers_a = auth_headers(tenant_id="tenant_pg_alpha", client_id="pg_client_alpha")
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
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    r = await pg_client.post("/v1/events", json=payload, headers=headers_a)
    assert r.status_code == 200

    # Query from Tenant B (should return 404)
    headers_b = auth_headers(tenant_id="tenant_pg_beta", client_id="pg_client_beta")
    r_b = await pg_client.get(
        "/v1/learners/student_shared_pg/concepts/physics.vectors/state",
        headers=headers_b,
    )
    assert r_b.status_code == 404
