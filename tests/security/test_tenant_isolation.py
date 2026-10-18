"""Security tests for multi-tenant isolation, cryptographic JWT verification, and authorization."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from lam.infrastructure.authentication.jwt import create_access_token
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_tenant_data_isolation(async_client: AsyncClient) -> None:
    """Non-negotiable rule: Student data in Tenant A MUST NOT be accessible or

    modified by Tenant B.
    """
    headers_tenant_a = auth_headers(tenant_id="tenant_alpha", client_id="client_a")
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

    # Query learner state from Tenant A (should exist)
    state_a = await async_client.get(
        "/v1/learners/student_shared_id/concepts/calculus.derivatives/state",
        headers=headers_tenant_a,
    )
    assert state_a.status_code == 200

    # Query the same student_id from Tenant B (MUST NOT exist or see Tenant A's state)
    headers_tenant_b = auth_headers(tenant_id="tenant_beta", client_id="client_b")
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

    # Malformed token format
    resp2 = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": "Basic 123", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp2.status_code == 401

    # Raw garbage bearer
    resp3 = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": "Bearer not-a-jwt", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp3.status_code == 401


@pytest.mark.asyncio
async def test_forged_or_tampered_token_rejected(async_client: AsyncClient) -> None:
    """Tokens signed with wrong secret key or tampered signatures must be rejected with 401."""
    # Signed with an attacker secret
    forged_token = create_access_token(
        tenant_id="tenant_alpha",
        client_id="attacker",
        secret_key="attacker-secret-key-that-does-not-match-service-config",
    )
    resp = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": f"Bearer {forged_token}", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp.status_code == 401
    assert "Invalid token" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_expired_token_rejected(async_client: AsyncClient) -> None:
    """Expired tokens must be rejected with 401."""
    expired_token = create_access_token(
        tenant_id="tenant_alpha",
        client_id="student_1",
        expires_delta=timedelta(seconds=-60),
    )
    resp = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": f"Bearer {expired_token}", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp.status_code == 401
    assert "Token expired" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_token_mismatch_rejected(async_client: AsyncClient) -> None:
    """A valid token for Tenant Alpha cannot access Tenant Beta by spoofing X-Tenant-ID."""
    # Token issued specifically for tenant_alpha
    token_alpha = create_access_token(
        tenant_id="tenant_alpha",
        client_id="client_alpha_user",
        roles=["student"],
    )

    # Attempt to target tenant_beta with tenant_alpha's token
    headers_spoofed = {
        "Authorization": f"Bearer {token_alpha}",
        "X-Tenant-ID": "tenant_beta",
    }
    resp = await async_client.get(
        "/v1/learners/student_1/state",
        headers=headers_spoofed,
    )
    assert resp.status_code == 403
    assert "does not match requested tenant" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_prefix_does_not_grant_privilege(async_client: AsyncClient) -> None:
    """P1 Security Fix: Token strings prefixed with 'admin_' without verified admin claims

    MUST NOT grant administrative or cross-tenant access.
    """
    # Token with 'admin_' subject/prefix but ordinary student roles
    unprivileged_token = create_access_token(
        tenant_id="tenant_alpha",
        client_id="admin_fake_attacker",
        roles=["student"],
    )

    # Attempt cross-tenant access
    headers = {
        "Authorization": f"Bearer {unprivileged_token}",
        "X-Tenant-ID": "tenant_beta",
    }
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verified_admin_can_access_cross_tenant(async_client: AsyncClient) -> None:
    """A verified token with explicit 'admin' role claim CAN access requested tenants."""
    admin_token = create_access_token(
        tenant_id="tenant_system",
        client_id="root_admin",
        roles=["admin"],
    )

    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": "tenant_alpha",
    }
    # Should succeed without 401 or 403 (returns 200 with empty list for student_1)
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant_alpha"
