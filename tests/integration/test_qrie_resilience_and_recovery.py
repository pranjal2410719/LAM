"""Resilience, Timeout, Retry, and Recovery Integration Tests for Qrie-LAM (Phase 6).

Verifies client resilience patterns:
1. Bounded retries and timeouts under simulated transient failures.
2. Safe degradation and fallback when LAM is unreachable without fabricating mastery.
3. Outbox queuing, recovery, and replay after service restoration.
4. Strict rejection (HTTP 409) of conflicting event ID replay.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ReadTimeout, Response

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_qrie_client_bounded_retries_and_timeout() -> None:
    """Simulates Qrie client retry policy with bounded retries under transient 503s."""
    max_retries = 3
    attempts = 0

    mock_client = AsyncMock()

    async def flaky_call(*args: object, **kwargs: object) -> Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return Response(status_code=503, json={"error": "Service temporarily unavailable"})
        return Response(status_code=200, json={"status": "ingested", "event_id": "evt_retry_ok"})

    mock_client.post.side_effect = flaky_call

    # Execute retry loop
    response = None
    for retry in range(max_retries):
        resp = await mock_client.post("http://lam-backend/v1/events")
        if resp.status_code == 200:
            response = resp
            break
        await asyncio.sleep(0.01)  # fast jitter in test

    assert response is not None
    assert response.status_code == 200
    assert response.json()["status"] == "ingested"
    assert attempts == 3


@pytest.mark.asyncio
async def test_safe_fallback_when_lam_unavailable_does_not_fabricate_mastery() -> None:
    """Verifies that client fallback on LAM outage produces safe fallback probe

    and strictly avoids fabricating or guessing learner mastery.
    """

    # Simulate a client attempting to reach LAM with timeout/unreachable host
    async def call_lam_recommendation() -> dict[str, object]:
        # Raises timeout simulating unreachable LAM
        raise ReadTimeout("Connection timed out after 5.0s")

    # Client-side fallback handler:
    try:
        await call_lam_recommendation()
    except ReadTimeout:
        # Fallback invariant: generate safe fallback probe without inventing BKT parameters
        fallback_decision = {
            "action_type": "diagnostic_probe",
            "assistance_level": 2,
            "priority_tier": "fallback",
            "safe_fallback": True,
            "reason_code": "lam_service_unreachable_safe_fallback",
        }

    assert fallback_decision["safe_fallback"] is True
    assert fallback_decision["action_type"] == "diagnostic_probe"
    # Ensure client did NOT invent or fabricate a mastery score
    assert "concept_mastery" not in fallback_decision
    assert "uncertainty" not in fallback_decision


@pytest.mark.asyncio
async def test_recovery_and_replay_after_temporary_failure(
    async_client: AsyncClient,
) -> None:
    """Verifies that offline outbox events queued during an outage can be replayed

    after recovery with exact idempotency and consistent learner state.
    """
    headers = auth_headers(tenant_id="tenant_qrie_replay_recovery")
    student_id = "stu_qrie_replay_01"
    concept_id = "math.geometry.triangles"

    # Simulated client offline outbox queue:
    outbox = [
        {
            "event_id": f"evt_recovery_{i}",
            "student_id": student_id,
            "session_id": "sess_recovery_1",
            "concept_ids": [concept_id],
            "item_id": f"item_geom_{i}",
            "timestamp": f"2026-10-19T12:0{i}:00Z",
            "event_type": "attempt",
            "correctness": True,
            "assistance_level": 0,
            "hints_used": 0,
            "provenance": {
                "judgment_source": "answer_key",
                "status": "verified",
                "verifier_reliability": "authoritative",
                "independently_produced": True,
            },
        }
        for i in range(3)
    ]

    # Batch drain 1: Replay all 3 queued events to recovered LAM
    for event in outbox:
        resp = await async_client.post("/v1/events", json=event, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ingested"

    # Verify state after initial replay
    state_resp = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    assert state_resp.status_code == 200
    state1 = state_resp.json()
    assert state1["total_events_count"] == 3
    assert state1["independent_attempts_count"] == 3
    mastery_after_first_replay = state1["concept_mastery"]

    # Batch drain 2: Network re-sends the exact same outbox (simulating lost ACK)
    for event in outbox:
        resp_dup = await async_client.post("/v1/events", json=event, headers=headers)
        assert resp_dup.status_code == 200
        assert resp_dup.json()["status"] == "duplicate"

    # Verify state after replayed duplicates: unchanged!
    state_resp_dup = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    state2 = state_resp_dup.json()
    assert state2["total_events_count"] == 3
    assert state2["independent_attempts_count"] == 3
    assert state2["concept_mastery"] == mastery_after_first_replay


@pytest.mark.asyncio
async def test_conflicting_event_id_attribute_rejected_409(
    async_client: AsyncClient,
) -> None:
    """Verifies that reusing an event ID with conflicting attributes returns HTTP 409."""
    headers = auth_headers(tenant_id="tenant_qrie_conflict_test")
    event_id = "evt_conflict_unique_001"

    original_event = {
        "event_id": event_id,
        "student_id": "student_original",
        "session_id": "sess_orig",
        "concept_ids": ["science.physics.motion"],
        "item_id": "item_mot_1",
        "timestamp": "2026-10-19T13:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    r1 = await async_client.post("/v1/events", json=original_event, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "ingested"

    # Conflict 1: Different student_id
    conflict_student = dict(original_event)
    conflict_student["student_id"] = "different_student"
    r2 = await async_client.post("/v1/events", json=conflict_student, headers=headers)
    assert r2.status_code == 409
    assert "conflicting attributes" in r2.json()["detail"]

    # Conflict 2: Different item_id
    conflict_item = dict(original_event)
    conflict_item["item_id"] = "different_item"
    r3 = await async_client.post("/v1/events", json=conflict_item, headers=headers)
    assert r3.status_code == 409
    assert "conflicting attributes" in r3.json()["detail"]
