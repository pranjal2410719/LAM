"""Integration tests for POST /v1/recommendations endpoint."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_recommendation_requires_authentication(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/v1/recommendations",
        json={"student_id": "stu_01", "concept_id": "math.fractions"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recommendation_fallback_for_unknown_student(async_client: AsyncClient) -> None:
    headers = auth_headers(tenant_id="tenant_rec_01", client_id="client_rec")
    payload = {
        "student_id": "stu_unknown_01",
        "concept_id": "physics.mechanics",
    }
    resp = await async_client.post("/v1/recommendations", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_type"] == "diagnostic_probe"
    assert data["priority_tier"] == "tier_fallback_insufficient_evidence"
    assert data["safe_fallback"] is True
    assert data["assistance_level"] == 2
    assert data["uncertainty"] == 1.0


@pytest.mark.asyncio
async def test_end_to_end_event_to_recommendation_flow(async_client: AsyncClient) -> None:
    headers = auth_headers(tenant_id="tenant_rec_e2e", client_id="client_rec_e2e")
    student_id = "student_rec_e2e"
    concept_id = "algebra.polynomials"

    # 1. Ingest an initial verified correct attempt
    event_payload = {
        "event_id": "evt_rec_001",
        "student_id": student_id,
        "session_id": "sess_rec_01",
        "concept_ids": [concept_id],
        "item_id": "item_poly_1",
        "timestamp": "2026-10-18T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    ingest_resp = await async_client.post("/v1/events", json=event_payload, headers=headers)
    assert ingest_resp.status_code == 200

    # 2. Request recommendation for this student
    rec_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
    }
    rec_resp = await async_client.post("/v1/recommendations", json=rec_payload, headers=headers)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()

    # After 1 correct attempt: mastery ≈ 0.467 (between 0.40 and 0.85)
    # Triggers standard independent practice
    assert rec_data["action_type"] == "independent_practice"
    assert rec_data["priority_tier"] == "tier_7_difficulty_fit_practice"
    assert rec_data["assistance_level"] == 0
    assert rec_data["safe_fallback"] is False
    assert rec_data["relevant_learner_state_version"] >= 1


@pytest.mark.asyncio
async def test_recommendation_prerequisite_blocking(async_client: AsyncClient) -> None:
    headers = auth_headers(tenant_id="tenant_rec_e2e", client_id="client_rec_e2e")
    student_id = "student_rec_blocked"
    concept_id = "algebra.logarithms"

    # Ingest event to create state
    event_payload = {
        "event_id": "evt_rec_prereq_001",
        "student_id": student_id,
        "session_id": "sess_rec_02",
        "concept_ids": [concept_id],
        "item_id": "item_log_1",
        "timestamp": "2026-10-18T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    await async_client.post("/v1/events", json=event_payload, headers=headers)

    # Request recommendation indicating prerequisite readiness is False
    rec_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
        "prerequisite_readiness": False,
        "prerequisite_concept_id": "algebra.exponents",
    }
    rec_resp = await async_client.post("/v1/recommendations", json=rec_payload, headers=headers)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["action_type"] == "prerequisite_remediation"
    assert rec_data["target_concept_id"] == "algebra.exponents"
    assert rec_data["priority_tier"] == "tier_2_blocking_prerequisite"
    assert rec_data["assistance_level"] == 5


@pytest.mark.asyncio
async def test_recommendation_safety_stop_on_failures(async_client: AsyncClient) -> None:
    headers = auth_headers(tenant_id="tenant_rec_e2e", client_id="client_rec_e2e")
    student_id = "student_rec_safety"
    concept_id = "calculus.derivatives"

    # Ingest event to create state
    event_payload = {
        "event_id": "evt_rec_fail_001",
        "student_id": student_id,
        "session_id": "sess_rec_03",
        "concept_ids": [concept_id],
        "item_id": "item_deriv_1",
        "timestamp": "2026-10-18T10:00:00Z",
        "event_type": "attempt",
        "correctness": False,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    await async_client.post("/v1/events", json=event_payload, headers=headers)

    # Request with 3 consecutive failures
    rec_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
        "consecutive_failures": 3,
    }
    rec_resp = await async_client.post("/v1/recommendations", json=rec_payload, headers=headers)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["action_type"] == "teacher_intervention"
    assert rec_data["priority_tier"] == "tier_1_safety_stop"
    assert rec_data["assistance_level"] == 8


@pytest.mark.asyncio
async def test_recommendation_confirmed_vs_open_misconception(
    async_client: AsyncClient,
) -> None:
    headers = auth_headers(tenant_id="tenant_rec_e2e", client_id="client_rec_e2e")
    student_id = "student_rec_misc"
    concept_id = "algebra.quadratics"

    # Ingest event
    event_payload = {
        "event_id": "evt_rec_misc_001",
        "student_id": student_id,
        "session_id": "sess_rec_04",
        "concept_ids": [concept_id],
        "item_id": "item_quad_1",
        "timestamp": "2026-10-18T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    await async_client.post("/v1/events", json=event_payload, headers=headers)

    # 1. Request with OPEN candidate misconception: must NOT trigger Tier 3
    open_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
        "active_misconception_id": "misc_sign_error",
        "misconception_status": "open",
    }
    resp_open = await async_client.post("/v1/recommendations", json=open_payload, headers=headers)
    assert resp_open.status_code == 200
    data_open = resp_open.json()
    assert data_open["action_type"] == "independent_practice"
    assert data_open["priority_tier"] == "tier_7_difficulty_fit_practice"

    # 2. Request with CONFIRMED misconception: MUST trigger Tier 3 diagnostic probe
    conf_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
        "active_misconception_id": "misc_sign_error",
        "misconception_status": "confirmed",
    }
    resp_conf = await async_client.post("/v1/recommendations", json=conf_payload, headers=headers)
    assert resp_conf.status_code == 200
    data_conf = resp_conf.json()
    assert data_conf["action_type"] == "diagnostic_probe"
    assert data_conf["priority_tier"] == "tier_3_confirmed_misconception"
    assert data_conf["assistance_level"] == 2
    assert data_conf["metadata"]["misconception_id"] == "misc_sign_error"
