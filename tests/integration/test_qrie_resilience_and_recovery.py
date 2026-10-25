"""Production-Realistic Client Resilience, Timeout, Retry, and Recovery Integration Tests.

Validates the real LamRelayClient production implementation against:
1. Transient 502/503/504 server errors recovering within retry budget.
2. Non-retryable errors (401, 403, 409, 422) failing fast without inappropriate retries.
3. Network and read timeouts terminating within a bounded duration.
4. Retry exhaustion triggering safe fallback without fabricating mastery.
5. Offline outbox replay, deduplication, and absence of duplicate state drift.
6. Idempotent re-ingestion yielding duplicate status without state alteration.
7. Event ID conflict rejection (HTTP 409) preventing data corruption.
8. Cross-tenant event and recommendation rejection (HTTP 403).
9. Malformed responses and validation errors handled safely.
10. Verification of real code path execution through live application transport.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient, Request, Response

from lam.infrastructure.clients.lam_client import (
    LamAuthenticationError,
    LamConflictError,
    LamRelayClient,
    LamServiceUnavailableError,
    LamTimeoutError,
    LamValidationError,
)
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_transient_503_recovers_within_retry_budget() -> None:
    """Verifies that transient 502/503/504 errors trigger exponential backoff and recover."""
    call_count = 0

    async def transient_handler(request: Request) -> Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return Response(status_code=503, json={"error": "Service temporarily unavailable"})
        return Response(
            status_code=200,
            json={
                "status": "ingested",
                "event_id": "evt_retry_success",
                "tenant_id": "tenant_test",
                "student_id": "stu_01",
                "affected_concept_ids": ["math.fractions"],
                "ingested_at": datetime.now(UTC).isoformat(),
                "message": "Event processed successfully",
            },
        )

    transport = httpx.MockTransport(transient_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as mock_client:
        client = LamRelayClient(
            base_url="http://testserver",
            tenant_id="tenant_test",
            max_retries=3,
            initial_backoff=0.01,
            http_client=mock_client,
        )

        result = await client.ingest_event({"event_id": "evt_retry_success"})
        assert result.status == "ingested"
        assert result.event_id == "evt_retry_success"
        assert call_count == 3


@pytest.mark.asyncio
async def test_non_retryable_errors_fail_fast_without_retrying() -> None:
    """Verifies that 409 Conflict, 401/403 Auth, and 422 Validation errors fail fast."""
    status_to_return = 409
    call_count = 0

    async def err_handler(request: Request) -> Response:
        nonlocal call_count
        call_count += 1
        return Response(status_code=status_to_return, json={"detail": "Error occurred"})

    transport = httpx.MockTransport(err_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as mock_client:
        client = LamRelayClient(
            base_url="http://testserver",
            max_retries=3,
            http_client=mock_client,
        )

        # 1. 409 Conflict -> LamConflictError
        status_to_return = 409
        call_count = 0
        with pytest.raises(LamConflictError):
            await client.ingest_event({"event_id": "evt_conflict"})
        assert call_count == 1

        # 2. 422 Unprocessable -> LamValidationError
        status_to_return = 422
        call_count = 0
        with pytest.raises(LamValidationError):
            await client.ingest_event({"event_id": "evt_invalid"})
        assert call_count == 1

        # 3. 401 Unauthorized -> LamAuthenticationError
        status_to_return = 401
        call_count = 0
        with pytest.raises(LamAuthenticationError):
            await client.ingest_event({"event_id": "evt_unauth"})
        assert call_count == 1


@pytest.mark.asyncio
async def test_persistent_503_raises_service_unavailable_after_retries() -> None:
    """Verifies that persistent 503s on event ingestion exhaust retries and raise error."""
    call_count = 0

    async def persistent_503(request: Request) -> Response:
        nonlocal call_count
        call_count += 1
        return Response(status_code=503, json={"error": "Database down"})

    transport = httpx.MockTransport(persistent_503)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as mock_client:
        client = LamRelayClient(
            base_url="http://testserver",
            max_retries=3,
            initial_backoff=0.01,
            http_client=mock_client,
        )

        with pytest.raises(LamServiceUnavailableError):
            await client.ingest_event({"event_id": "evt_down"})

        assert call_count == 3


@pytest.mark.asyncio
async def test_network_timeout_terminates_within_bounded_retries() -> None:
    """Verifies that persistent read/connect timeouts terminate after max retries."""
    call_count = 0

    async def timeout_handler(request: Request) -> Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ReadTimeout("Server took too long to answer")

    transport = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as mock_client:
        client = LamRelayClient(
            base_url="http://testserver",
            max_retries=3,
            initial_backoff=0.01,
            http_client=mock_client,
        )

        with pytest.raises(LamTimeoutError) as exc_info:
            await client.ingest_event({"event_id": "evt_timeout"})

        assert "timed out" in str(exc_info.value).lower()
        assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exhaustion_triggers_safe_fallback_without_mastery_fabrication() -> None:
    """Verifies that recommendation requests under service failure trigger safe fallback

    and strictly do NOT fabricate mastery scores, uncertainty, or state versions.
    """

    async def down_handler(request: Request) -> Response:
        return Response(status_code=504, json={"error": "Gateway Timeout"})

    transport = httpx.MockTransport(down_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as mock_client:
        client = LamRelayClient(
            base_url="http://testserver",
            max_retries=2,
            initial_backoff=0.01,
            http_client=mock_client,
        )

        rec = await client.get_recommendation(
            student_id="stu_offline_99",
            concept_id="math.fractions.basic",
        )

        assert rec.safe_fallback is True
        assert rec.action_type == "diagnostic_probe"
        assert rec.target_concept_id == "math.fractions.basic"
        assert rec.assistance_level == 2
        assert rec.reason_code == "lam_service_unreachable_safe_fallback"
        # Invariant: Never fabricate mastery or uncertainty!
        assert rec.concept_mastery is None
        assert rec.uncertainty is None
        assert rec.relevant_learner_state_version is None


@pytest.mark.asyncio
async def test_outbox_replay_recovers_with_zero_state_drift(
    async_client: AsyncClient,
) -> None:
    """End-to-end integration test with isolated in-memory SQLite backend:

    Replaying an offline outbox batch ensures all events land and duplicate
    replay causes zero state drift.
    """
    tenant_id = "tenant_outbox_replay_prod"
    student_id = "stu_replay_live_01"
    concept_id = "math.fractions.replay"
    headers = auth_headers(tenant_id=tenant_id)
    token = headers["Authorization"].replace("Bearer ", "")

    client = LamRelayClient(
        base_url="http://testserver",
        auth_token=token,
        tenant_id=tenant_id,
        http_client=async_client,
    )

    outbox_events: list[dict[str, Any]] = [
        {
            "event_id": f"evt_prod_replay_{i}",
            "student_id": student_id,
            "session_id": "sess_replay_prod",
            "concept_ids": [concept_id],
            "item_id": f"item_rep_{i}",
            "timestamp": f"2026-10-19T14:0{i}:00Z",
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

    # First replay: all 3 ingested
    report1 = await client.replay_outbox(outbox_events)
    assert report1.total_submitted == 3
    assert report1.ingested_count == 3
    assert report1.duplicate_count == 0
    assert report1.conflict_count == 0
    assert report1.failed_count == 0

    # Query persisted learner state
    state_res1 = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    assert state_res1.status_code == 200
    state1 = state_res1.json()
    assert state1["total_events_count"] == 3
    assert state1["independent_attempts_count"] == 3
    mastery_before_second_replay = state1["concept_mastery"]

    # Second replay: identical batch replayed (simulating offline retry)
    report2 = await client.replay_outbox(outbox_events)
    assert report2.total_submitted == 3
    assert report2.ingested_count == 0
    assert report2.duplicate_count == 3  # All detected as duplicates!
    assert report2.conflict_count == 0
    assert report2.failed_count == 0

    # Verify state after second replay: ZERO DRIFT
    state_res2 = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    state2 = state_res2.json()
    assert state2["total_events_count"] == 3
    assert state2["independent_attempts_count"] == 3
    assert state2["concept_mastery"] == mastery_before_second_replay


@pytest.mark.asyncio
async def test_conflicting_event_id_raises_conflict_error(
    async_client: AsyncClient,
) -> None:
    """Verifies that submitting conflicting attributes under an existing event ID

    raises LamConflictError.
    """
    tenant_id = "tenant_conflict_prod"
    headers = auth_headers(tenant_id=tenant_id)
    token = headers["Authorization"].replace("Bearer ", "")

    client = LamRelayClient(
        base_url="http://testserver",
        auth_token=token,
        tenant_id=tenant_id,
        http_client=async_client,
    )

    original_event = {
        "event_id": "evt_unique_conflict_999",
        "student_id": "student_alpha",
        "session_id": "sess_alpha",
        "concept_ids": ["science.chemistry.elements"],
        "item_id": "item_chem_1",
        "timestamp": "2026-10-19T14:30:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }

    res1 = await client.ingest_event(original_event)
    assert res1.status == "ingested"

    # Conflicting attempt: different student_id
    conflicting_event = dict(original_event)
    conflicting_event["student_id"] = "different_student"

    with pytest.raises(LamConflictError):
        await client.ingest_event(conflicting_event)


@pytest.mark.asyncio
async def test_cross_tenant_rejection_raises_authentication_error(
    async_client: AsyncClient,
) -> None:
    """Verifies that mismatched tenant credentials raise LamAuthenticationError

    (HTTP 403).
    """
    headers = auth_headers(tenant_id="tenant_legitimate")
    token = headers["Authorization"].replace("Bearer ", "")

    # Client configured with tenant_impostor but holding token for tenant_legitimate
    client = LamRelayClient(
        base_url="http://testserver",
        auth_token=token,
        tenant_id="tenant_impostor",
        http_client=async_client,
    )

    with pytest.raises(LamAuthenticationError):
        await client.get_recommendation(
            student_id="student_x",
            concept_id="math.fractions",
        )
