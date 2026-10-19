"""Integration tests for GET /v1/learners/{student_id}/reviews endpoint (M2-03)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_reviews_requires_authentication(async_client: AsyncClient) -> None:
    resp = await async_client.get("/v1/learners/stu_review_01/reviews")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reviews_tenant_isolation(async_client: AsyncClient) -> None:
    # Ingest event for student in tenant_A
    headers_a = auth_headers(tenant_id="tenant_rev_A", client_id="client_rev_A")
    student_id = "student_isolated_01"
    concept_id = "math.fractions.basic"

    event_payload = {
        "event_id": "evt_rev_iso_001",
        "student_id": student_id,
        "session_id": "sess_rev_01",
        "concept_ids": [concept_id],
        "item_id": "item_rev_1",
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    ingest_resp = await async_client.post("/v1/events", json=event_payload, headers=headers_a)
    assert ingest_resp.status_code == 200

    # Query with tenant_B credentials: must see zero concepts
    headers_b = auth_headers(tenant_id="tenant_rev_B", client_id="client_rev_B")
    resp_b = await async_client.get(f"/v1/learners/{student_id}/reviews", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["total_concepts_evaluated"] == 0
    assert data_b["reviews_due_count"] == 0

    # Query with tenant_A credentials: sees concept
    resp_a = await async_client.get(f"/v1/learners/{student_id}/reviews", headers=headers_a)
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["total_concepts_evaluated"] == 1


@pytest.mark.asyncio
async def test_reviews_endpoint_returns_scheduled_concepts(
    async_client: AsyncClient,
) -> None:
    headers = auth_headers(tenant_id="tenant_rev_sched", client_id="client_rev_sched")
    student_id = "student_sched_01"
    concept_id = "science.chemistry.atoms"

    # Ingest event from 5 days ago
    past_time = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    event_payload = {
        "event_id": "evt_rev_sched_001",
        "student_id": student_id,
        "session_id": "sess_rev_02",
        "concept_ids": [concept_id],
        "item_id": "item_chem_1",
        "timestamp": past_time,
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    await async_client.post("/v1/events", json=event_payload, headers=headers)

    # Query reviews
    resp = await async_client.get(f"/v1/learners/{student_id}/reviews", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == student_id
    assert data["policy_version"] == "retrieval_ladder_v1"
    assert data["total_concepts_evaluated"] == 1

    # Since 5 days elapsed with interval 1 day, it should be critical overdue or due
    assert data["reviews_due_count"] == 1
    due_item = data["reviews_due"][0]
    assert due_item["concept_id"] == concept_id
    assert due_item["is_due"] is True
    assert due_item["priority"] in ("due_for_review", "critical_overdue")
