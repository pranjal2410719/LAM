"""Comprehensive Application-Boundary Integration Test Suite for Qrie-LAM Contract (Phase F).

Validates the full application-level adaptive loop:
1. Student answer & trusted verification
2. Qrie event submission with field aliases (duration_ms)
3. LAM append-only ledger, BKT learner state & misconception diagnosis updates
4. Automatic hypothesis lookup & next-action recommendation
5. Assisted response segregation
6. Prerequisite blocking & Tier 1 safety stop
7. Spaced retrieval reviews
8. Multi-tenant isolation and duplicate event idempotency.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_qrie_contract_unauthorized_and_cross_tenant_isolation(
    async_client: AsyncClient,
) -> None:
    """Verifies that missing auth and cross-tenant mismatches are strictly rejected."""
    # 1. Missing Authorization header -> 401
    r_no_auth = await async_client.post(
        "/v1/recommendations",
        json={"student_id": "stu_01", "concept_id": "math.fractions.basic"},
    )
    assert r_no_auth.status_code == 401

    # 2. Cross-tenant mismatch (token tenant != X-Tenant-ID header) -> 403
    mismatched_headers = auth_headers(tenant_id="tenant_alpha")
    mismatched_headers["X-Tenant-ID"] = "tenant_beta"
    r_cross_tenant = await async_client.post(
        "/v1/recommendations",
        json={"student_id": "stu_01", "concept_id": "math.fractions.basic"},
        headers=mismatched_headers,
    )
    assert r_cross_tenant.status_code == 403


@pytest.mark.asyncio
async def test_qrie_contract_alias_payload_and_idempotency(
    async_client: AsyncClient,
) -> None:
    """Verifies duration_ms alias from Qrie and strict duplicate idempotency."""
    headers = auth_headers(tenant_id="tenant_qrie_stage_01")
    event_id = "evt_alias_idemp_001"
    student_id = "stu_qrie_alias_01"
    concept_id = "math.fractions.addition"

    payload = {
        "event_id": event_id,
        "student_id": student_id,
        "session_id": "sess_qrie_01",
        "concept_ids": [concept_id],
        "item_id": "item_frac_01",
        "timestamp": "2026-10-19T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "hints_used": 0,
        "duration_ms": 12500,  # Qrie contract alias for response_time_ms
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
            "verifier_reliability": "authoritative",
            "independently_produced": True,
        },
    }

    # First submission: Ingested
    r1 = await async_client.post("/v1/events", json=payload, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "ingested"

    # Replay of exact same event: Duplicate (no duplicate mutation)
    r2 = await async_client.post("/v1/events", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"

    # Check state has exactly 1 attempt
    state_res = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    assert state_res.status_code == 200
    state_data = state_res.json()
    assert state_data["total_events_count"] == 1
    assert state_data["independent_attempts_count"] == 1


@pytest.mark.asyncio
async def test_qrie_contract_missing_correctness_and_untrusted_provenance(
    async_client: AsyncClient,
) -> None:
    """Verifies non-evaluative and untrusted/provisional events do not alter mastery."""
    headers = auth_headers(tenant_id="tenant_qrie_stage_02")
    student_id = "stu_qrie_uneval_01"
    concept_id = "math.fractions.subtraction"

    # 1. Non-evaluative event (video watch or hint request, correctness is None)
    e1 = {
        "event_id": "evt_uneval_001",
        "student_id": student_id,
        "session_id": "sess_02",
        "concept_ids": [concept_id],
        "item_id": "item_video_01",
        "timestamp": "2026-10-19T10:00:00Z",
        "event_type": "explanation",
        "correctness": None,
        "assistance_level": 1,
    }
    r1 = await async_client.post("/v1/events", json=e1, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "ingested"

    # State initialized with prior 0.10, attempts count remains 0
    s1 = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    assert s1.json()["concept_mastery"] == 0.10
    assert s1.json()["independent_attempts_count"] == 0

    # 2. Model-graded / provisional event (untrusted for independent mastery)
    e2 = {
        "event_id": "evt_uneval_002",
        "student_id": student_id,
        "session_id": "sess_02",
        "concept_ids": [concept_id],
        "item_id": "item_sub_01",
        "timestamp": "2026-10-19T10:05:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "hints_used": 0,
        "provenance": {
            "judgment_source": "model_graded",
            "status": "provisional",
            "verifier_reliability": "medium",
            "independently_produced": True,
        },
    }
    r2 = await async_client.post("/v1/events", json=e2, headers=headers)
    assert r2.status_code == 200

    s2 = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    # Independent mastery strictly preserved at prior 0.10
    assert s2.json()["concept_mastery"] == 0.10
    assert s2.json()["independent_attempts_count"] == 0


@pytest.mark.asyncio
async def test_qrie_contract_full_closed_loop_and_automatic_diagnosis(
    async_client: AsyncClient,
) -> None:
    """Verifies end-to-end adaptive loop:
    1. First error opens candidate hypothesis (no Tier 3 interruption)
    2. Repeated error confirms hypothesis (automatic Tier 3 recommendation without client flag)
    3. Assisted attempt isolates assisted metrics
    4. Independent success retires hypothesis
    5. Progression to next concept
    6. Safety stop at 3 consecutive failures.
    """
    headers = auth_headers(tenant_id="tenant_qrie_closed_loop")
    student_id = "stu_qrie_loop_999"
    concept_id = "math.fractions.division"

    # --- Step 1: First error opens OPEN candidate hypothesis ---
    e1 = {
        "event_id": "evt_cl_001",
        "student_id": student_id,
        "session_id": "sess_cl",
        "concept_ids": [concept_id],
        "item_id": "item_div_01",
        "timestamp": "2026-10-19T11:00:00Z",
        "event_type": "attempt",
        "correctness": False,
        "assistance_level": 0,
        "hints_used": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
            "verifier_reliability": "authoritative",
            "independently_produced": True,
        },
    }
    r1 = await async_client.post("/v1/events", json=e1, headers=headers)
    assert r1.status_code == 200

    # Query recommendation without passing misconception_status:
    # Candidate hypothesis in OPEN status must NOT disrupt student with diagnostic probe
    rec1 = await async_client.post(
        "/v1/recommendations",
        json={"student_id": student_id, "concept_id": concept_id, "consecutive_failures": 1},
        headers=headers,
    )
    assert rec1.status_code == 200
    rec1_data = rec1.json()
    assert rec1_data["priority_tier"] != "tier_3_confirmed_misconceptions"
    assert rec1_data["priority_tier"] == "tier_7_difficulty_fit_practice"

    # --- Step 2: Second error on same concept confirms hypothesis in DB ---
    e2 = {
        "event_id": "evt_cl_002",
        "student_id": student_id,
        "session_id": "sess_cl",
        "concept_ids": [concept_id],
        "item_id": "item_div_02",
        "timestamp": "2026-10-19T11:05:00Z",
        "event_type": "attempt",
        "correctness": False,
        "assistance_level": 0,
        "hints_used": 0,
        "provenance": {
            "judgment_source": "symbolic_math_check",
            "status": "verified",
            "verifier_reliability": "authoritative",
            "independently_produced": True,
        },
    }
    r2 = await async_client.post("/v1/events", json=e2, headers=headers)
    assert r2.status_code == 200

    # Third error on same concept reaches confidence 0.95 (>= 0.75 threshold) -> CONFIRMED
    e3_err = {
        "event_id": "evt_cl_002b",
        "student_id": student_id,
        "session_id": "sess_cl",
        "concept_ids": [concept_id],
        "item_id": "item_div_02b",
        "timestamp": "2026-10-19T11:07:00Z",
        "event_type": "attempt",
        "correctness": False,
        "assistance_level": 0,
        "hints_used": 0,
        "provenance": {
            "judgment_source": "symbolic_math_check",
            "status": "verified",
            "verifier_reliability": "authoritative",
            "independently_produced": True,
        },
    }
    r2b = await async_client.post("/v1/events", json=e3_err, headers=headers)
    assert r2b.status_code == 200

    # Query recommendation without passing misconception_status:
    # Confirmed hypothesis in DB MUST trigger Tier 3 diagnostic probe!
    rec2 = await async_client.post(
        "/v1/recommendations",
        json={"student_id": student_id, "concept_id": concept_id, "consecutive_failures": 2},
        headers=headers,
    )
    assert rec2.status_code == 200
    rec2_data = rec2.json()
    assert rec2_data["priority_tier"] == "tier_3_confirmed_misconception"
    assert rec2_data["action_type"] == "diagnostic_probe"
    assert rec2_data["assistance_level"] == 2

    # --- Step 3: Assisted response (Level 2 hint) ---
    e3 = {
        "event_id": "evt_cl_003",
        "student_id": student_id,
        "session_id": "sess_cl",
        "concept_ids": [concept_id],
        "item_id": "item_div_03",
        "timestamp": "2026-10-19T11:10:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 2,
        "hints_used": 1,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
            "verifier_reliability": "authoritative",
            "independently_produced": False,
        },
    }
    r3 = await async_client.post("/v1/events", json=e3, headers=headers)
    assert r3.status_code == 200

    # Verify assisted attempt updated assisted performance but not independent mastery
    s3 = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state",
        headers=headers,
    )
    s3_data = s3.json()
    assert s3_data["assisted_attempts_count"] == 1
    assert s3_data["assisted_performance"] > 0.0
    assert s3_data["independent_attempts_count"] == 3

    # --- Step 4: Independent Success weakens & retires hypothesis ---
    for i in range(2):
        succ_evt = {
            "event_id": f"evt_cl_succ_{i}",
            "student_id": student_id,
            "session_id": "sess_cl",
            "concept_ids": [concept_id],
            "item_id": f"item_div_succ_{i}",
            "timestamp": f"2026-10-19T11:{15 + i}:00Z",
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
        await async_client.post("/v1/events", json=succ_evt, headers=headers)

    # After independent successes, Tier 3 is cleared (hypothesis retired)
    rec3 = await async_client.post(
        "/v1/recommendations",
        json={"student_id": student_id, "concept_id": concept_id, "consecutive_failures": 0},
        headers=headers,
    )
    assert rec3.json()["priority_tier"] != "tier_3_confirmed_misconception"

    # --- Step 5: Prerequisite Blocking Gap (Tier 2) ---
    rec_blocked = await async_client.post(
        "/v1/recommendations",
        json={
            "student_id": student_id,
            "concept_id": concept_id,
            "prerequisite_readiness": False,
            "prerequisite_concept_id": "math.fractions.multiplication",
        },
        headers=headers,
    )
    assert rec_blocked.json()["priority_tier"] == "tier_2_blocking_prerequisite"
    assert rec_blocked.json()["action_type"] == "prerequisite_remediation"

    # --- Step 6: Tier 1 Safety Stop overrides everything at >= 3 failures ---
    rec_safety = await async_client.post(
        "/v1/recommendations",
        json={
            "student_id": student_id,
            "concept_id": concept_id,
            "consecutive_failures": 3,
            "prerequisite_readiness": False,
        },
        headers=headers,
    )
    assert rec_safety.json()["priority_tier"] == "tier_1_safety_stop"
    assert rec_safety.json()["action_type"] == "teacher_intervention"
    assert rec_safety.json()["assistance_level"] == 8


@pytest.mark.asyncio
async def test_qrie_contract_reviews_and_unknown_learner_fallback(
    async_client: AsyncClient,
) -> None:
    """Verifies unknown learner fallback and reviews schedule endpoint."""
    headers = auth_headers(tenant_id="tenant_qrie_reviews")

    # Unknown learner receives safe fallback
    r_unknown = await async_client.post(
        "/v1/recommendations",
        json={"student_id": "stu_completely_unknown", "concept_id": "math.geometry.angles"},
        headers=headers,
    )
    assert r_unknown.status_code == 200
    assert r_unknown.json()["safe_fallback"] is True
    assert r_unknown.json()["action_type"] == "diagnostic_probe"

    # Reviews schedule endpoint
    r_reviews = await async_client.get(
        "/v1/learners/stu_completely_unknown/reviews",
        headers=headers,
    )
    assert r_reviews.status_code == 200
    assert r_reviews.json()["reviews_due"] == []
    assert r_reviews.json()["upcoming_reviews"] == []
