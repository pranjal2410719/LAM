"""Security tests for multi-tenant isolation, cryptographic JWT verification, and authorization.

Exhaustively verifies:
- Part A: Tenant Pinning & Header Mismatch Rejection (SEC-P3-03)
- Part B: Student Learner-Level Object Authorization (SEC-P3-02)
- Part C: Service-Only Write & Algorithmic Restrictions
- Part D: Cross-Tenant Learner References & Side-Effect Prevention
- Part E: Curriculum, Claim Validation, and Backward Compatibility
"""

from datetime import timedelta
from typing import Any

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lam.infrastructure.authentication.jwt import create_access_token
from lam.infrastructure.config import settings
from lam.infrastructure.database.models import (
    HypothesisAuditEntryModel,
    LearnerStateModel,
    LearningEventModel,
    MisconceptionHypothesisModel,
)
from tests.conftest import auth_headers


def _encode_raw_token(payload: dict[str, Any]) -> str:
    """Helper for generating test tokens with arbitrary, non-standard, or malformed claims."""
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def _snapshot_db_state(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """Snapshots every column of every row across ledger, state, hypotheses, and audit trail."""
    events = (
        (await session.execute(select(LearningEventModel).order_by(LearningEventModel.id)))
        .scalars()
        .all()
    )
    states = (
        (await session.execute(select(LearnerStateModel).order_by(LearnerStateModel.id)))
        .scalars()
        .all()
    )
    hypotheses = (
        (
            await session.execute(
                select(MisconceptionHypothesisModel).order_by(MisconceptionHypothesisModel.id)
            )
        )
        .scalars()
        .all()
    )
    audits = (
        (
            await session.execute(
                select(HypothesisAuditEntryModel).order_by(HypothesisAuditEntryModel.id)
            )
        )
        .scalars()
        .all()
    )

    def _model_to_dict(model: Any) -> dict[str, Any]:
        return {c.name: getattr(model, c.name) for c in model.__table__.columns}

    return {
        "events": [_model_to_dict(e) for e in events],
        "states": [_model_to_dict(s) for s in states],
        "hypotheses": [_model_to_dict(h) for h in hypotheses],
        "audits": [_model_to_dict(a) for a in audits],
    }


# =========================================================================
# Part A: Tenant Pinning & Header Mismatch Rejection (SEC-P3-03)
# =========================================================================


@pytest.mark.asyncio
async def test_service_token_can_access_learner_in_authorized_tenant(
    async_client: AsyncClient,
) -> None:
    """Scenario 1: Service token accesses learner resources within its authenticated tenant."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="service_qrie", roles=["service"])
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant_alpha"


@pytest.mark.asyncio
async def test_service_token_cannot_switch_tenant_header(async_client: AsyncClient) -> None:
    """Scenario 2: Service token with mismatched X-Tenant-ID header is rejected."""
    token = create_access_token(
        tenant_id="tenant_alpha", client_id="service_qrie", roles=["service"]
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_beta"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "does not match authenticated token tenant" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_whitespace_only_tenant_header_rejected(async_client: AsyncClient) -> None:
    """Scenario 2b: Whitespace-only X-Tenant-ID header is rejected with 403 (F1 fix)."""
    token = create_access_token(
        tenant_id="tenant_alpha", client_id="service_qrie", roles=["service"]
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "   "}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "does not match authenticated token tenant" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_token_cannot_switch_tenant_header(async_client: AsyncClient) -> None:
    """Scenario 3: Admin token cannot switch tenants via X-Tenant-ID (SEC-P3-03 fix)."""
    admin_token = create_access_token(
        tenant_id="tenant_system",
        client_id="root_admin",
        roles=["admin"],
    )
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": "tenant_alpha",
    }
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "does not match authenticated token tenant" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_system_token_cannot_switch_tenant_header(async_client: AsyncClient) -> None:
    """Scenario 4: System token cannot switch tenants via X-Tenant-ID."""
    sys_token = create_access_token(
        tenant_id="tenant_system",
        client_id="sys_daemon",
        roles=["system"],
    )
    headers = {
        "Authorization": f"Bearer {sys_token}",
        "X-Tenant-ID": "tenant_alpha",
    }
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "does not match authenticated token tenant" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_token_scoped_to_own_tenant_succeeds(async_client: AsyncClient) -> None:
    """Scenario 5: Admin token reading learner state within its own tenant succeeds."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="admin_alpha", roles=["admin"])
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant_alpha"


@pytest.mark.asyncio
async def test_system_token_scoped_to_own_tenant_succeeds(async_client: AsyncClient) -> None:
    """Scenario 6: System token reading learner state within its own tenant succeeds."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="system_alpha", roles=["system"])
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant_alpha"


@pytest.mark.asyncio
async def test_unauthorized_cross_tenant_read_rejected(async_client: AsyncClient) -> None:
    """Scenario 7: Unauthorized cross-tenant read rejected with 403."""
    token_alpha = create_access_token(
        tenant_id="tenant_alpha",
        client_id="student_1",
        roles=["student"],
    )
    headers = {
        "Authorization": f"Bearer {token_alpha}",
        "X-Tenant-ID": "tenant_beta",
    }
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthorized_cross_tenant_event_submission_rejected_no_side_effects(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Scenario 8: Submitting event with mismatched tenant header is rejected

    with zero side effects on ledger and learner state (F3 fix).
    """
    # Snapshot full database state before denied request
    snapshot_before = await _snapshot_db_state(db_session)

    service_token = create_access_token(
        tenant_id="tenant_alpha",
        client_id="service_qrie",
        roles=["service"],
    )
    headers = {
        "Authorization": f"Bearer {service_token}",
        "X-Tenant-ID": "tenant_beta",
    }
    payload = {
        "event_id": "evt_cross_tenant_01",
        "student_id": "student_alpha_1",
        "session_id": "sess_1",
        "concept_ids": ["math.algebra"],
        "item_id": "item_1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 403

    # Direct database assertions verifying zero rows or values changed
    snapshot_after = await _snapshot_db_state(db_session)
    assert snapshot_after == snapshot_before

    # Verify no state or ledger entry was written in tenant_alpha or tenant_beta
    headers_check_a = auth_headers(
        tenant_id="tenant_alpha", client_id="service_qrie", roles=["service"]
    )
    state_a = await async_client.get(
        "/v1/learners/student_alpha_1/concepts/math.algebra/state",
        headers=headers_check_a,
    )
    assert state_a.status_code == 404

    headers_check_b = auth_headers(
        tenant_id="tenant_beta", client_id="service_qrie", roles=["service"]
    )
    state_b = await async_client.get(
        "/v1/learners/student_alpha_1/concepts/math.algebra/state",
        headers=headers_check_b,
    )
    assert state_b.status_code == 404


# =========================================================================
# Part B: Student Learner-Level Object Authorization (SEC-P3-02)
# =========================================================================


@pytest.mark.asyncio
async def test_student_token_can_read_own_state(async_client: AsyncClient) -> None:
    """Scenario 9: Student token can read own learner state."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    resp = await async_client.get("/v1/learners/student_alice/state", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["student_id"] == "student_alice"


@pytest.mark.asyncio
async def test_student_token_cannot_read_other_learner_state(async_client: AsyncClient) -> None:
    """Scenario 10: Student token cannot read other learner's state in same tenant (SEC-P3-02)."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    resp = await async_client.get("/v1/learners/student_bob/state", headers=headers)
    assert resp.status_code == 403
    assert "Students may only access their own learner records" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_student_token_cannot_read_other_learner_concept_state(
    async_client: AsyncClient,
) -> None:
    """Scenario 11: Student token cannot read other learner's concept state."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    resp = await async_client.get(
        "/v1/learners/student_bob/concepts/math.fractions/state",
        headers=headers,
    )
    assert resp.status_code == 403
    assert "Students may only access their own learner records" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_student_token_cannot_read_other_learner_reviews(async_client: AsyncClient) -> None:
    """Scenario 12: Student token cannot read other learner's reviews."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    resp = await async_client.get("/v1/learners/student_bob/reviews", headers=headers)
    assert resp.status_code == 403
    assert "Students may only access their own learner records" in resp.json()["detail"]


# =========================================================================
# Part C: Service-Only Write & Algorithmic Restrictions
# =========================================================================


@pytest.mark.asyncio
async def test_student_cannot_submit_event_even_for_self(async_client: AsyncClient) -> None:
    """Scenario 13: Student cannot submit learning interaction events (service-only)."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    payload = {
        "event_id": "evt_stu_self",
        "student_id": "student_alice",
        "session_id": "sess_1",
        "concept_ids": ["math.algebra"],
        "item_id": "item_1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "not authorized to submit learning interaction events" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_student_cannot_submit_event_for_other_learner(async_client: AsyncClient) -> None:
    """Scenario 14: Student cannot submit learning events for another student."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    payload = {
        "event_id": "evt_stu_other",
        "student_id": "student_bob",
        "session_id": "sess_1",
        "concept_ids": ["math.algebra"],
        "item_id": "item_1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_submit_event(async_client: AsyncClient) -> None:
    """Scenario 15: Admin token cannot submit events (pedagogical integrity)."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="admin_alpha", roles=["admin"])
    payload = {
        "event_id": "evt_admin_01",
        "student_id": "student_alice",
        "session_id": "sess_1",
        "concept_ids": ["math.algebra"],
        "item_id": "item_1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_cannot_submit_event(async_client: AsyncClient) -> None:
    """Scenario 16: System token cannot submit events."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="system_alpha", roles=["system"])
    payload = {
        "event_id": "evt_sys_01",
        "student_id": "student_alice",
        "session_id": "sess_1",
        "concept_ids": ["math.algebra"],
        "item_id": "item_1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_request_recommendations(async_client: AsyncClient) -> None:
    """Scenario 17: Student token cannot request recommendations (service-only)."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    payload = {
        "student_id": "student_alice",
        "concept_id": "math.algebra",
        "available_item_ids": ["item_1", "item_2"],
    }
    resp = await async_client.post("/v1/recommendations", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "not authorized to request recommendations" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_cannot_request_recommendations(async_client: AsyncClient) -> None:
    """Scenario 18: Admin token cannot request recommendations."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="admin_alpha", roles=["admin"])
    payload = {
        "student_id": "student_alice",
        "concept_id": "math.algebra",
        "available_item_ids": ["item_1"],
    }
    resp = await async_client.post("/v1/recommendations", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_cannot_request_recommendations(async_client: AsyncClient) -> None:
    """Scenario 19: System token cannot request recommendations."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="system_alpha", roles=["system"])
    payload = {
        "student_id": "student_alice",
        "concept_id": "math.algebra",
        "available_item_ids": ["item_1"],
    }
    resp = await async_client.post("/v1/recommendations", json=payload, headers=headers)
    assert resp.status_code == 403


# =========================================================================
# Part D: Cross-Tenant Learner References & Side-Effect Prevention
# =========================================================================


@pytest.mark.asyncio
async def test_tenant_partitioned_learner_namespace_isolation(
    async_client: AsyncClient,
) -> None:
    """Scenario 20: Demonstrates that learner state is strictly namespaced by tenant_id:
    when tenant_alpha and tenant_beta ingest events for the same student_id string,
    their ledgers and mastery states remain completely isolated and partitioned,
    preventing cross-tenant leakage or interference.
    """
    # Service in tenant_beta creates state for student_beta
    headers_beta = auth_headers(
        tenant_id="tenant_beta", client_id="service_beta", roles=["service"]
    )
    payload_beta = {
        "event_id": "evt_beta_legit",
        "student_id": "student_beta_only",
        "session_id": "sess_b1",
        "concept_ids": ["math.geometry"],
        "item_id": "item_g1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp_init = await async_client.post("/v1/events", json=payload_beta, headers=headers_beta)
    assert resp_init.status_code == 200

    # Service in tenant_alpha attempts to read student_beta_only's concept state
    headers_alpha = auth_headers(
        tenant_id="tenant_alpha", client_id="service_alpha", roles=["service"]
    )
    resp_read = await async_client.get(
        "/v1/learners/student_beta_only/concepts/math.geometry/state",
        headers=headers_alpha,
    )
    assert resp_read.status_code == 404

    # Service in tenant_alpha attempts to submit an event targeting student_beta_only
    # This must create a record strictly partitioned in tenant_alpha, never altering tenant_beta
    payload_alpha = {
        "event_id": "evt_alpha_cross",
        "student_id": "student_beta_only",
        "session_id": "sess_a1",
        "concept_ids": ["math.geometry"],
        "item_id": "item_g2",
        "timestamp": "2026-10-25T10:05:00Z",
        "event_type": "attempt",
        "correctness": False,
        "assistance_level": 0,
    }
    resp_alpha_post = await async_client.post(
        "/v1/events", json=payload_alpha, headers=headers_alpha
    )
    assert resp_alpha_post.status_code == 200

    # Verify tenant_beta's mastery state for student_beta_only remained intact and unmodified
    state_beta_check = await async_client.get(
        "/v1/learners/student_beta_only/concepts/math.geometry/state",
        headers=headers_beta,
    )
    assert state_beta_check.status_code == 200
    assert state_beta_check.json()["total_events_count"] == 1


@pytest.mark.asyncio
async def test_cross_tenant_recommendation_target_cannot_leak_state(
    async_client: AsyncClient,
) -> None:
    """Scenario 21: Service in tenant_alpha requesting recommendations for student_beta cannot

    observe or use tenant_beta's misconception or mastery state.
    """
    # Create distinct state in tenant_beta
    headers_beta = auth_headers(
        tenant_id="tenant_beta", client_id="service_beta", roles=["service"]
    )
    payload_beta = {
        "event_id": "evt_rec_beta",
        "student_id": "student_beta_rec",
        "session_id": "sess_b2",
        "concept_ids": ["math.algebra"],
        "item_id": "item_a1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": False,
        "assistance_level": 0,
    }
    await async_client.post("/v1/events", json=payload_beta, headers=headers_beta)

    # Service in tenant_alpha requests recommendation for student_beta_rec
    headers_alpha = auth_headers(
        tenant_id="tenant_alpha", client_id="service_alpha", roles=["service"]
    )
    rec_payload = {
        "student_id": "student_beta_rec",
        "concept_id": "math.algebra",
    }
    resp_alpha = await async_client.post(
        "/v1/recommendations", json=rec_payload, headers=headers_alpha
    )
    assert resp_alpha.status_code == 200
    # In tenant_alpha, student_beta_rec has no history, so response reflects default diagnostic
    assert resp_alpha.json()["action_type"] == "diagnostic_probe"


@pytest.mark.asyncio
async def test_cross_tenant_admin_read_fails(async_client: AsyncClient) -> None:
    """Scenario 22: Admin in tenant_alpha cannot read tenant_beta's learner state."""
    headers_beta = auth_headers(
        tenant_id="tenant_beta", client_id="service_beta", roles=["service"]
    )
    payload_beta = {
        "event_id": "evt_adm_cross",
        "student_id": "student_beta_adm",
        "session_id": "sess_b3",
        "concept_ids": ["math.algebra"],
        "item_id": "item_a1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    await async_client.post("/v1/events", json=payload_beta, headers=headers_beta)

    headers_admin_alpha = auth_headers(
        tenant_id="tenant_alpha", client_id="admin_alpha", roles=["admin"]
    )
    resp = await async_client.get(
        "/v1/learners/student_beta_adm/concepts/math.algebra/state",
        headers=headers_admin_alpha,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_system_read_fails(async_client: AsyncClient) -> None:
    """Scenario 23: System in tenant_alpha cannot read tenant_beta's learner state."""
    headers_sys_alpha = auth_headers(
        tenant_id="tenant_alpha", client_id="sys_alpha", roles=["system"]
    )
    resp = await async_client.get(
        "/v1/learners/student_beta_adm/concepts/math.algebra/state",
        headers=headers_sys_alpha,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_service_read_returns_not_found(async_client: AsyncClient) -> None:
    """Scenario 24: Service in tenant_alpha reading nonexistent learner returns 404."""
    headers_service_alpha = auth_headers(
        tenant_id="tenant_alpha", client_id="service_alpha", roles=["service"]
    )
    resp = await async_client.get(
        "/v1/learners/student_beta_adm/concepts/math.algebra/state",
        headers=headers_service_alpha,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_denied_mutation_has_zero_side_effects(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Scenario 25: Denied event submission leaves ledger and learner state completely empty

    (F3 fix).
    """
    # Snapshot full database state before denied request
    snapshot_before = await _snapshot_db_state(db_session)

    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    payload = {
        "event_id": "evt_denied_side_fx",
        "student_id": "student_alice",
        "session_id": "sess_sfx",
        "concept_ids": ["math.calculus"],
        "item_id": "item_c1",
        "timestamp": "2026-10-25T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    resp = await async_client.post("/v1/events", json=payload, headers=headers)
    assert resp.status_code == 403

    # Direct database verification that no rows or values were altered
    snapshot_after = await _snapshot_db_state(db_session)
    assert snapshot_after == snapshot_before

    # Confirm student state does not exist
    resp_check = await async_client.get(
        "/v1/learners/student_alice/concepts/math.calculus/state",
        headers=headers,
    )
    assert resp_check.status_code == 404


# =========================================================================
# Part E: Curriculum, Claim Validation, and Backward Compatibility
# =========================================================================


@pytest.mark.asyncio
async def test_curriculum_allows_service_token(async_client: AsyncClient) -> None:
    """Scenario 26: Curriculum validation allows service token."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="service_qrie", roles=["service"])
    payload = {
        "graph_id": "g_math",
        "version": "1.0",
        "nodes": [
            {"concept_id": "math.arithmetic.addition", "display_name": "Addition", "domain": "math"}
        ],
        "edges": [],
    }
    resp = await async_client.post("/v1/curriculum/validate", json=payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_curriculum_allows_admin_token(async_client: AsyncClient) -> None:
    """Scenario 27: Curriculum validation allows admin token."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="admin_alpha", roles=["admin"])
    payload = {
        "graph_id": "g_math",
        "version": "1.0",
        "nodes": [
            {"concept_id": "math.arithmetic.addition", "display_name": "Addition", "domain": "math"}
        ],
        "edges": [],
    }
    resp = await async_client.post("/v1/curriculum/validate", json=payload, headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_curriculum_allows_system_token(async_client: AsyncClient) -> None:
    """Scenario 28: Curriculum validation allows system token."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="sys_alpha", roles=["system"])
    payload = {
        "graph_id": "g_math",
        "version": "1.0",
        "nodes": [
            {"concept_id": "math.arithmetic.addition", "display_name": "Addition", "domain": "math"}
        ],
        "edges": [],
    }
    resp = await async_client.post("/v1/curriculum/validate", json=payload, headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_curriculum_denies_student_token(async_client: AsyncClient) -> None:
    """Scenario 29: Curriculum validation denies student token."""
    headers = auth_headers(tenant_id="tenant_alpha", client_id="student_alice", roles=["student"])
    payload = {
        "graph_id": "g_math",
        "version": "1.0",
        "nodes": [
            {"concept_id": "math.arithmetic.addition", "display_name": "Addition", "domain": "math"}
        ],
        "edges": [],
    }
    resp = await async_client.post("/v1/curriculum/validate", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "not authorized to perform curriculum operations" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_curriculum_prerequisite_check_allows_service_denies_student(
    async_client: AsyncClient,
) -> None:
    """Scenario 30: Curriculum check-prerequisites allows service and denies student."""
    payload = {
        "graph_id": "g_math",
        "version": "1.0",
        "nodes": [
            {"concept_id": "math.arithmetic.addition", "display_name": "Addition", "domain": "math"}
        ],
        "edges": [],
        "target_concept_id": "math.arithmetic.addition",
        "mastery_map": {"math.arithmetic.addition": 0.9},
    }
    headers_svc = auth_headers(
        tenant_id="tenant_alpha", client_id="service_qrie", roles=["service"]
    )
    resp_svc = await async_client.post(
        "/v1/curriculum/check-prerequisites", json=payload, headers=headers_svc
    )
    assert resp_svc.status_code == 200

    headers_stu = auth_headers(
        tenant_id="tenant_alpha", client_id="student_alice", roles=["student"]
    )
    resp_stu = await async_client.post(
        "/v1/curriculum/check-prerequisites", json=payload, headers=headers_stu
    )
    assert resp_stu.status_code == 403


@pytest.mark.asyncio
async def test_claim_validation_missing_sub_rejected(async_client: AsyncClient) -> None:
    """Scenario 31: Token with missing or empty sub claim is rejected with 401."""
    token = create_access_token(tenant_id="tenant_alpha", client_id="", roles=["service"])
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 401
    assert "missing valid subject claim" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_missing_tid_rejected(async_client: AsyncClient) -> None:
    """Scenario 32: Token with missing or empty tid claim is rejected with 401."""
    token = create_access_token(tenant_id="", client_id="service_1", roles=["service"])
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 401
    assert "missing valid tenant claim" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_empty_roles_rejected(async_client: AsyncClient) -> None:
    """Scenario 33: Token with empty roles array is rejected with 403 (F2 fix)."""
    token = create_access_token(tenant_id="tenant_alpha", client_id="client_1", roles=[])
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "Token must contain exactly one role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_unknown_role_rejected(async_client: AsyncClient) -> None:
    """Scenario 34: Token with unrecognized role string is rejected with 403."""
    token = create_access_token(tenant_id="tenant_alpha", client_id="client_1", roles=["analyst"])
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "unrecognized role 'analyst'" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_multiple_roles_rejected(async_client: AsyncClient) -> None:
    """Scenario 35: Token with multiple roles is rejected with 403 (single-role policy)."""
    token = create_access_token(
        tenant_id="tenant_alpha", client_id="client_1", roles=["service", "student"]
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "Token must contain exactly one role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_whitespace_sub_rejected(async_client: AsyncClient) -> None:
    """Scenario 35b: Token with whitespace-only sub claim is rejected with 401 (F4 fix)."""
    token = _encode_raw_token(
        {
            "sub": "   ",
            "tid": "tenant_alpha",
            "roles": ["service"],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        }
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 401
    assert "missing valid subject claim" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_whitespace_tid_rejected(async_client: AsyncClient) -> None:
    """Scenario 35c: Token with whitespace-only tid claim is rejected with 401 (F4 fix)."""
    token = _encode_raw_token(
        {
            "sub": "service_1",
            "tid": "   ",
            "roles": ["service"],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        }
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 401
    assert "missing valid tenant claim" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_non_list_roles_rejected(async_client: AsyncClient) -> None:
    """Scenario 35d: Token with non-list roles claim is rejected with 403 (F4 fix)."""
    token = _encode_raw_token(
        {
            "sub": "service_1",
            "tid": "tenant_alpha",
            "roles": "service",  # string instead of list
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        }
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "Token must contain exactly one role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_non_string_role_elements_rejected(
    async_client: AsyncClient,
) -> None:
    """Scenario 35e: Token with non-string role elements is rejected with 403 (F4 fix)."""
    token = _encode_raw_token(
        {
            "sub": "service_1",
            "tid": "tenant_alpha",
            "roles": [123],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        }
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 403
    assert "Token contains unrecognized role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_legacy_claims_without_canonical_claims_rejected(
    async_client: AsyncClient,
) -> None:
    """Scenario 35f: Legacy claims without canonical sub and tid are rejected with 401 (F4 fix)."""
    token = _encode_raw_token(
        {
            "client_id": "service_1",
            "tenant_id": "tenant_alpha",
            "roles": ["service"],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        }
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cryptographic_verification_rejections(async_client: AsyncClient) -> None:
    """Scenario 36: Invalid signature, expired token, and wrong key are rejected with 401."""
    # Wrong secret key
    forged = create_access_token(
        tenant_id="tenant_alpha",
        client_id="hacker",
        secret_key="wrong_secret_key_1234567890123456_32bytes",
    )
    headers_forged = {"Authorization": f"Bearer {forged}", "X-Tenant-ID": "tenant_alpha"}
    resp1 = await async_client.get("/v1/learners/student_1/state", headers=headers_forged)
    assert resp1.status_code == 401
    assert "Invalid token" in resp1.json()["detail"]

    # Expired token
    expired = create_access_token(
        tenant_id="tenant_alpha",
        client_id="student_1",
        roles=["student"],
        expires_delta=timedelta(seconds=-60),
    )
    headers_expired = {"Authorization": f"Bearer {expired}", "X-Tenant-ID": "tenant_alpha"}
    resp2 = await async_client.get("/v1/learners/student_1/state", headers=headers_expired)
    assert resp2.status_code == 401
    assert "Token expired" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_tampered_token_signature_rejected(async_client: AsyncClient) -> None:
    """Scenario 36b: Modifying signature segment of a valid token is rejected with 401 (F4 fix)."""
    valid_token = create_access_token(
        tenant_id="tenant_alpha", client_id="service_1", roles=["service"]
    )
    parts = valid_token.split(".")
    tampered_sig = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
    headers = {"Authorization": f"Bearer {tampered_token}", "X-Tenant-ID": "tenant_alpha"}
    resp = await async_client.get("/v1/learners/student_1/state", headers=headers)
    assert resp.status_code == 401
    assert "Invalid token" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_validation_missing_required_claims_rejected(async_client: AsyncClient) -> None:
    """Scenario 36c: Token missing required exp, iss, or aud claim is rejected with 401."""
    # 1. Omit 'exp'
    token_no_exp = _encode_raw_token(
        {
            "sub": "service_1",
            "tid": "tenant_alpha",
            "roles": ["service"],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
    )
    resp_no_exp = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": f"Bearer {token_no_exp}", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp_no_exp.status_code == 401
    assert "Invalid token" in resp_no_exp.json()["detail"]

    # 2. Omit 'iss'
    token_no_iss = _encode_raw_token(
        {
            "sub": "service_1",
            "tid": "tenant_alpha",
            "roles": ["service"],
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        }
    )
    resp_no_iss = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": f"Bearer {token_no_iss}", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp_no_iss.status_code == 401
    assert "Invalid token" in resp_no_iss.json()["detail"]

    # 3. Omit 'aud'
    token_no_aud = _encode_raw_token(
        {
            "sub": "service_1",
            "tid": "tenant_alpha",
            "roles": ["service"],
            "iss": settings.jwt_issuer,
            "exp": 9999999999,
        }
    )
    resp_no_aud = await async_client.get(
        "/v1/learners/student_1/state",
        headers={"Authorization": f"Bearer {token_no_aud}", "X-Tenant-ID": "tenant_alpha"},
    )
    assert resp_no_aud.status_code == 401
    assert "Invalid token" in resp_no_aud.json()["detail"]


@pytest.mark.asyncio
async def test_qrie_service_workflow_remains_fully_compatible(async_client: AsyncClient) -> None:
    """Scenario 37: Legitimate Qrie service workflow operates seamlessly."""
    headers = auth_headers(
        tenant_id="tenant_qrie_school", client_id="qrie_backend", roles=["service"]
    )
    student_id = "student_qrie_101"
    concept_id = "math.fractions.addition"

    # 1. Ingest learning event
    e_payload = {
        "event_id": "evt_qrie_compat_01",
        "student_id": student_id,
        "session_id": "sess_q1",
        "concept_ids": [concept_id],
        "item_id": "item_q1",
        "timestamp": "2026-10-25T11:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "attempt_number": 1,
        "assistance_level": 0,
    }
    resp_ingest = await async_client.post("/v1/events", json=e_payload, headers=headers)
    assert resp_ingest.status_code == 200
    assert resp_ingest.json()["status"] == "ingested"

    # 2. Retrieve learner state
    resp_state = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state", headers=headers
    )
    assert resp_state.status_code == 200
    assert resp_state.json()["concept_id"] == concept_id

    # 3. Request recommendation
    rec_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
    }
    resp_rec = await async_client.post("/v1/recommendations", json=rec_payload, headers=headers)
    assert resp_rec.status_code == 200
    assert resp_rec.json()["action_type"] in [
        "practice_independent",
        "diagnostic_probe",
        "provide_feedback",
        "worked_example",
    ]
