"""Synthetic End-to-End Learning Loop Integration Test for Qrie-LAM (M2-Phase H).

Simulates the complete closed-loop lifecycle:
Student response
  -> Evidence validation & Provenance Gating
  -> Append-only Event Ledger Ingestion
  -> Pure Domain Learner-State BKT Updates
  -> Misconception Hypothesis Tracking (Candidate -> Confirmed -> Retired)
  -> Deterministic Multi-Tier Recommendation Selection
  -> Next Student Response & Safety-Stop Escalation.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_full_qrie_adaptive_learning_loop(async_client: AsyncClient) -> None:
    headers = auth_headers(tenant_id="tenant_qrie_school_01", client_id="qrie_client_app")
    student_id = "stu_qrie_loop_042"
    concept_id = "math.fractions.addition_unlike"

    # =========================================================================
    # Step 1: Initial Error -> Candidate Misconception Created (OPEN, conf 0.35)
    # =========================================================================
    e1_payload = {
        "event_id": "evt_loop_001",
        "student_id": student_id,
        "session_id": "sess_qrie_101",
        "concept_ids": [concept_id],
        "item_id": "item_frac_unlike_01",
        "timestamp": "2026-10-19T10:00:00Z",
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
    r1 = await async_client.post("/v1/events", json=e1_payload, headers=headers)
    assert r1.status_code == 200
    res1_data = r1.json()
    assert res1_data["status"] == "ingested"

    # =========================================================================
    # Step 2: Qrie Requests Recommendation -> Candidate Hypothesis Must NOT Interrupt
    # =========================================================================
    rec1_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
        "consecutive_failures": 1,
        "active_misconception_id": "misc_add_denominators_directly",
        "misconception_status": "open",
    }
    rec1 = await async_client.post("/v1/recommendations", json=rec1_payload, headers=headers)
    assert rec1.status_code == 200
    rec1_data = rec1.json()

    # Must NOT trigger Tier 3 (DIAGNOSTIC_PROBE); falls through to Tier 7 practice
    assert rec1_data["priority_tier"] == "tier_7_difficulty_fit_practice"
    assert rec1_data["action_type"] in ("worked_example", "independent_practice")

    # =========================================================================
    # Step 3: Repeated Independent Error -> Confirmed Misconception
    # =========================================================================
    e2_payload = {
        "event_id": "evt_loop_002",
        "student_id": student_id,
        "session_id": "sess_qrie_101",
        "concept_ids": [concept_id],
        "item_id": "item_frac_unlike_02",
        "timestamp": "2026-10-19T10:05:00Z",
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
    r2 = await async_client.post("/v1/events", json=e2_payload, headers=headers)
    assert r2.status_code == 200

    # Recommendation with confirmed misconception MUST trigger Tier 3 probe
    rec2_payload = {
        "student_id": student_id,
        "concept_id": concept_id,
        "consecutive_failures": 2,
        "active_misconception_id": "misc_add_denominators_directly",
        "misconception_status": "confirmed",
    }
    rec2 = await async_client.post("/v1/recommendations", json=rec2_payload, headers=headers)
    assert rec2.status_code == 200
    rec2_data = rec2.json()
    assert rec2_data["action_type"] == "diagnostic_probe"
    assert rec2_data["priority_tier"] == "tier_3_confirmed_misconception"
    assert rec2_data["assistance_level"] == 2
    assert rec2_data["metadata"]["misconception_id"] == "misc_add_denominators_directly"

    # =========================================================================
    # Step 4: Assisted Success Does NOT advance independent mastery
    # =========================================================================
    e3_payload = {
        "event_id": "evt_loop_003",
        "student_id": student_id,
        "session_id": "sess_qrie_101",
        "concept_ids": [concept_id],
        "item_id": "item_frac_unlike_03",
        "timestamp": "2026-10-19T10:10:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 3,
        "hints_used": 2,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
            "verifier_reliability": "authoritative",
            "independently_produced": False,
        },
    }
    r3 = await async_client.post("/v1/events", json=e3_payload, headers=headers)
    assert r3.status_code == 200

    # Query state: independent attempts remain 2, assisted attempts is 1
    state_res = await async_client.get(
        f"/v1/learners/{student_id}/concepts/{concept_id}/state", headers=headers
    )
    assert state_res.status_code == 200
    state_data = state_res.json()
    assert state_data["independent_attempts_count"] == 2
    assert state_data["assisted_attempts_count"] == 1

    # =========================================================================
    # Step 5: Consecutive Independent Successes Lead to Mastery
    # =========================================================================
    for idx in range(4, 9):
        e_succ = {
            "event_id": f"evt_loop_00{idx}",
            "student_id": student_id,
            "session_id": "sess_qrie_102",
            "concept_ids": [concept_id],
            "item_id": f"item_frac_unlike_0{idx}",
            "timestamp": f"2026-10-19T10:{15 + idx}:00Z",
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
        await async_client.post("/v1/events", json=e_succ, headers=headers)

    # After 5 consecutive unassisted successes, request recommendation
    rec_adv = await async_client.post(
        "/v1/recommendations",
        json={
            "student_id": student_id,
            "concept_id": concept_id,
            "consecutive_failures": 0,
            "active_misconception_id": None,
        },
        headers=headers,
    )
    assert rec_adv.status_code == 200
    adv_data = rec_adv.json()
    # High mastery + consecutive successes triggers progression (Tier 6)
    assert adv_data["action_type"] in ("advance_to_next_concept", "mastery_verification")

    # =========================================================================
    # Step 6: Safety Stop Escalation on 3 Consecutive Failures
    # =========================================================================
    safety_rec = await async_client.post(
        "/v1/recommendations",
        json={
            "student_id": student_id,
            "concept_id": concept_id,
            "consecutive_failures": 3,
        },
        headers=headers,
    )
    assert safety_rec.status_code == 200
    safety_data = safety_rec.json()
    assert safety_data["priority_tier"] == "tier_1_safety_stop"
    assert safety_data["action_type"] == "teacher_intervention"
    assert safety_data["assistance_level"] == 8
