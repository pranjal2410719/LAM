"""Integration tests verifying high-concurrency race safety, transaction rollback,

and optimistic locking against live PostgreSQL 16.
"""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lam.domain.learner_state.models import LearnerConceptState
from lam.infrastructure.repositories.state_repository import (
    StateRepository,
    StateVersionConflictError,
)
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_concurrent_duplicate_event_submissions_race(
    pg_client_concurrent: AsyncClient,
) -> None:
    """Non-negotiable rule: Simultaneous duplicate submissions must never crash with 500

    and must update state exactly ONCE.
    """
    headers = auth_headers(tenant_id="tenant_race_01", client_id="client_race")
    payload = {
        "event_id": "evt_concurrent_dup_100",
        "student_id": "student_race_1",
        "session_id": "sess_race_1",
        "concept_ids": ["algebra.linear_systems"],
        "item_id": "item_sys_1",
        "timestamp": "2026-10-18T13:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }

    # Dispatch 10 identical requests simultaneously
    tasks = [
        pg_client_concurrent.post("/v1/events", json=payload, headers=headers) for _ in range(10)
    ]
    responses = await asyncio.gather(*tasks)

    # Every request must succeed with 200 OK (no 500 internal errors)
    for r in responses:
        assert r.status_code == 200, f"Unexpected status: {r.status_code}, {r.text}"

    statuses = [r.json()["status"] for r in responses]
    assert statuses.count("ingested") == 1
    assert statuses.count("duplicate") == 9

    # Verify database state in PostgreSQL
    state_resp = await pg_client_concurrent.get(
        "/v1/learners/student_race_1/concepts/algebra.linear_systems/state",
        headers=headers,
    )
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert state["total_events_count"] == 1
    assert state["independent_attempts_count"] == 1


@pytest.mark.asyncio
async def test_concurrent_distinct_events_for_same_concept(
    pg_client_concurrent: AsyncClient,
) -> None:
    """Concurrent distinct events for same student must be serialized with row locking."""
    headers = auth_headers(tenant_id="tenant_race_02", client_id="client_race_2")

    def make_payload(idx: int) -> dict[str, object]:
        return {
            "event_id": f"evt_distinct_{idx}",
            "student_id": "student_race_2",
            "session_id": "sess_race_2",
            "concept_ids": ["calculus.limits"],
            "item_id": f"item_lim_{idx}",
            "timestamp": f"2026-10-18T13:0{idx}:00Z",
            "event_type": "attempt",
            "correctness": True,
            "assistance_level": 0,
            "provenance": {
                "judgment_source": "answer_key",
                "status": "verified",
            },
        }

    # Send 5 distinct events concurrently
    tasks = [
        pg_client_concurrent.post("/v1/events", json=make_payload(i), headers=headers)
        for i in range(1, 6)
    ]
    responses = await asyncio.gather(*tasks)

    for r in responses:
        assert r.status_code == 200
        assert r.json()["status"] == "ingested"

    # Verify state reflects all 5 updates
    state_resp = await pg_client_concurrent.get(
        "/v1/learners/student_race_2/concepts/calculus.limits/state",
        headers=headers,
    )
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert state["total_events_count"] == 5
    assert state["independent_attempts_count"] == 5
    assert state["state_version"] >= 5


@pytest.mark.asyncio
async def test_state_version_conflict_optimistic_concurrency(
    clean_pg_session: AsyncSession,
) -> None:
    """Verifies that stale state_version updates raise StateVersionConflictError."""
    session = clean_pg_session
    repo = StateRepository(session)
    initial_state = LearnerConceptState(
        tenant_id="tenant_opt_01",
        student_id="student_opt_1",
        concept_id="physics.kinematics",
        concept_mastery=0.2,
        independent_mastery=0.2,
        assisted_performance=0.0,
        uncertainty=0.8,
        state_version=1,
    )
    saved = await repo.save_concept_state(initial_state)
    await session.commit()
    assert saved.state_version == 1

    # Attempt update with stale version
    stale_update = saved.model_copy()
    stale_update.concept_mastery = 0.5

    with pytest.raises(StateVersionConflictError) as exc_info:
        await repo.save_concept_state(stale_update, expected_version=999)
    assert "Stale state_version" in str(exc_info.value)
    await session.rollback()


@pytest.mark.asyncio
async def test_transaction_atomicity_and_rollback(
    pg_client: AsyncClient, clean_pg_session: AsyncSession
) -> None:
    """Verifies that an error aborts the entire transaction without partial writes."""
    headers = auth_headers(tenant_id="tenant_rollback_01", client_id="client_rb")
    payload = {
        "event_id": "evt_rb_001",
        "student_id": "student_rb_1",
        "session_id": "sess_rb_1",
        "concept_ids": ["test.concept"],
        "item_id": "item_rb_1",
        "timestamp": "2026-10-18T13:30:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }

    # First ingest succeeds
    r1 = await pg_client.post("/v1/events", json=payload, headers=headers)
    assert r1.status_code == 200

    # Conflicting ingest (same event_id, different student_id) must fail with 409
    conflicting_payload = dict(payload)
    conflicting_payload["student_id"] = "different_student"

    r2 = await pg_client.post("/v1/events", json=conflicting_payload, headers=headers)
    assert r2.status_code == 409

    # Verify no state was created for different_student
    res = await clean_pg_session.execute(
        text(
            "SELECT COUNT(*) FROM learner_states WHERE tenant_id='tenant_rollback_01' "
            "AND student_id='different_student'"
        )
    )
    assert res.scalar() == 0
