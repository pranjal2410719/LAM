"""Integration tests for atomic event ingestion, idempotency, and state updates."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_successful_event_ingestion(async_client: AsyncClient) -> None:
    headers = {
        "Authorization": "Bearer test_secret_token_12345",
        "X-Tenant-ID": "tenant_school_a",
    }
    payload = {
        "event_id": "evt_100",
        "student_id": "student_alice",
        "session_id": "sess_001",
        "concept_ids": ["fractions.unlike_denominators"],
        "item_id": "item_q1",
        "timestamp": "2026-10-18T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "attempt_number": 1,
        "assistance_level": 0,
    }

    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ingested"
    assert data["event_id"] == "evt_100"
    assert data["student_id"] == "student_alice"

    # Verify state was updated
    state_resp = await async_client.get(
        "/v1/learners/student_alice/concepts/fractions.unlike_denominators/state",
        headers=headers,
    )
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["total_events_count"] == 1
    assert state_data["independent_attempts_count"] == 1
    assert state_data["independent_mastery"] > 0.0
    assert state_data["state_version"] >= 1


@pytest.mark.asyncio
async def test_idempotent_event_deduplication(async_client: AsyncClient) -> None:
    """Non-negotiable rule: Replaying the same event MUST NOT apply duplicate updates."""
    headers = {
        "Authorization": "Bearer test_secret_token_12345",
        "X-Tenant-ID": "tenant_school_a",
    }
    payload = {
        "event_id": "evt_replay_01",
        "student_id": "student_bob",
        "session_id": "sess_001",
        "concept_ids": ["algebra.linear_eq"],
        "item_id": "item_q2",
        "timestamp": "2026-10-18T10:05:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }

    # First submission
    resp1 = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "ingested"

    # Second submission (Replay)
    resp2 = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"

    # Verify state was only updated ONCE
    state_resp = await async_client.get(
        "/v1/learners/student_bob/concepts/algebra.linear_eq/state",
        headers=headers,
    )
    state_data = state_resp.json()
    assert state_data["total_events_count"] == 1


@pytest.mark.asyncio
async def test_assisted_success_does_not_advance_independent_mastery(
    async_client: AsyncClient,
) -> None:
    """Non-negotiable rule: Correct answer after assistance MUST NOT establish

    independent mastery.
    """
    headers = {
        "Authorization": "Bearer test_secret_token_12345",
        "X-Tenant-ID": "tenant_school_a",
    }
    payload = {
        "event_id": "evt_assisted_01",
        "student_id": "student_charlie",
        "session_id": "sess_002",
        "concept_ids": ["geometry.pythagorean"],
        "item_id": "item_q3",
        "timestamp": "2026-10-18T10:10:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 4,  # Strong hint provided
        "hints_used": 1,
    }

    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 200

    state_resp = await async_client.get(
        "/v1/learners/student_charlie/concepts/geometry.pythagorean/state",
        headers=headers,
    )
    state = state_resp.json()
    assert state["assisted_attempts_count"] == 1
    assert state["independent_attempts_count"] == 0
    assert state["assisted_performance"] > 0.0
    assert state["independent_mastery"] == 0.0  # Must remain 0!
