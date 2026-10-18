"""Security tests for multi-tenant isolation and authentication enforcement."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_tenant_data_isolation(async_client: AsyncClient) -> None:
    """Non-negotiable rule: Student data in Tenant A MUST NOT be accessible or

    modified by Tenant B.
    """
    # 1. Ingest event in Tenant A
    headers_tenant_a = {
        "Authorization": "Bearer token_for_tenant_a_1234",
        "X-Tenant-ID": "tenant_alpha",
    }
    payload = {
        "event_id": "evt_iso_01",
        "student_id": "student_shared_id",
        "session_id": "sess_iso_1",
        "concept_ids": ["calculus.derivatives"],
        "item_id": "item_iso_1",
        "timestamp": "2026-10-18T10:20:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp_a = await async_client.post("/v1/events", json=payload, headers=headers_tenant_a)
    assert resp_a.status_code == 200

    # 2. Query learner state from Tenant A (should exist)
    state_a = await async_client.get(
        "/v1/learners/student_shared_id/concepts/calculus.derivatives/state",
        headers=headers_tenant_a,
    )
    assert state_a.status_code == 200

    # 3. Query the same student_id from Tenant B (MUST NOT exist or see Tenant A's state)
    headers_tenant_b = {
        "Authorization": "Bearer token_for_tenant_b_5678",
        "X-Tenant-ID": "tenant_beta",
    }
    state_b = await async_client.get(
        "/v1/learners/student_shared_id/concepts/calculus.derivatives/state",
        headers=headers_tenant_b,
    )
    assert state_b.status_code == 404


@pytest.mark.asyncio
async def test_missing_or_invalid_authorization(async_client: AsyncClient) -> None:
    """Missing or invalid auth tokens must be rejected with 401."""
    # Missing auth
    resp1 = await async_client.get("/v1/learners/student_1/state")
    assert resp1.status_code == 401

    # Malformed token
    resp2 = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": "Basic 123", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp2.status_code == 401
