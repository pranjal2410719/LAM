import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_successful_event_ingestion(async_client: AsyncClient) -> None:
    headers = auth_headers(tenant_id="tenant_school_a", client_id="client_alice")
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
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
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
    assert state_data["independent_mastery"] > 0.10
    assert state_data["bkt_parameter_version"] == "bkt_v1_baseline"
    assert state_data["state_version"] >= 1


@pytest.mark.asyncio
async def test_idempotent_event_deduplication(async_client: AsyncClient) -> None:
    """Non-negotiable rule: Replaying the same event MUST NOT apply duplicate updates."""
    headers = auth_headers(tenant_id="tenant_school_a", client_id="client_bob")
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
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
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
    headers = auth_headers(tenant_id="tenant_school_a", client_id="client_charlie")
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
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
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
    assert state["independent_mastery"] == 0.10  # Must remain at initial prior 0.10!


@pytest.mark.asyncio
async def test_end_to_end_bkt_trajectory_ingestion(async_client: AsyncClient) -> None:
    """Verifies that ingestion updates learner state matching Decision D-02 BKT vectors."""
    headers = auth_headers(tenant_id="tenant_bkt_e2e", client_id="client_bkt")

    # Step 1: Correct attempt (1) -> expected mastery ≈ 0.4667
    p1 = {
        "event_id": "bkt_evt_1",
        "student_id": "student_bkt_1",
        "session_id": "sess_1",
        "concept_ids": ["math.trig"],
        "item_id": "item_1",
        "timestamp": "2026-10-18T10:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    r1 = await async_client.post("/v1/events", json=p1, headers=headers)
    assert r1.status_code == 200

    s1 = await async_client.get(
        "/v1/learners/student_bkt_1/concepts/math.trig/state",
        headers=headers,
    )
    data1 = s1.json()
    assert pytest.approx(data1["independent_mastery"], abs=1e-3) == 0.467
    assert data1["independent_attempts_count"] == 1
    assert data1["consecutive_independent_successes"] == 1
    assert data1["bkt_parameter_version"] == "bkt_v1_baseline"

    # Step 2: Incorrect attempt (0) -> expected mastery ≈ 0.2789
    p2 = {
        "event_id": "bkt_evt_2",
        "student_id": "student_bkt_1",
        "session_id": "sess_1",
        "concept_ids": ["math.trig"],
        "item_id": "item_2",
        "timestamp": "2026-10-18T10:05:00Z",
        "event_type": "attempt",
        "correctness": False,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    r2 = await async_client.post("/v1/events", json=p2, headers=headers)
    assert r2.status_code == 200

    s2 = await async_client.get(
        "/v1/learners/student_bkt_1/concepts/math.trig/state",
        headers=headers,
    )
    data2 = s2.json()
    assert pytest.approx(data2["independent_mastery"], abs=1e-3) == 0.279
    assert data2["independent_attempts_count"] == 2
    assert data2["consecutive_independent_successes"] == 0

    # Step 3: Correct attempt (1) -> expected mastery ≈ 0.7081
    p3 = {
        "event_id": "bkt_evt_3",
        "student_id": "student_bkt_1",
        "session_id": "sess_1",
        "concept_ids": ["math.trig"],
        "item_id": "item_3",
        "timestamp": "2026-10-18T10:10:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    r3 = await async_client.post("/v1/events", json=p3, headers=headers)
    assert r3.status_code == 200

    s3 = await async_client.get(
        "/v1/learners/student_bkt_1/concepts/math.trig/state",
        headers=headers,
    )
    data3 = s3.json()
    assert pytest.approx(data3["independent_mastery"], abs=1e-3) == 0.708
    assert data3["independent_attempts_count"] == 3
    assert data3["consecutive_independent_successes"] == 1

    # Step 4: Assisted attempt (hint used) -> independent_mastery stays exactly 0.708
    p4 = {
        "event_id": "bkt_evt_4",
        "student_id": "student_bkt_1",
        "session_id": "sess_1",
        "concept_ids": ["math.trig"],
        "item_id": "item_4",
        "timestamp": "2026-10-18T10:15:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 2,
        "hints_used": 1,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "verified",
        },
    }
    r4 = await async_client.post("/v1/events", json=p4, headers=headers)
    assert r4.status_code == 200

    s4 = await async_client.get(
        "/v1/learners/student_bkt_1/concepts/math.trig/state",
        headers=headers,
    )
    data4 = s4.json()
    # Must remain unchanged from step 3!
    assert pytest.approx(data4["independent_mastery"], abs=1e-3) == 0.708
    assert data4["assisted_attempts_count"] == 1
    assert data4["independent_attempts_count"] == 3


@pytest.mark.asyncio
async def test_unverified_provenance_event_ingested_without_advancing_mastery(
    async_client: AsyncClient,
) -> None:
    """Non-negotiable rule: Events with missing, provisional, or model-graded provenance

    must be durably recorded in the ledger, but MUST NOT advance independent BKT mastery.
    """
    headers = auth_headers(tenant_id="tenant_provenance_test", client_id="client_prov")

    # Case A: Missing provenance completely
    payload_no_prov = {
        "event_id": "evt_no_prov_01",
        "student_id": "student_prov_1",
        "session_id": "sess_prov",
        "concept_ids": ["stats.probability"],
        "item_id": "item_prob_1",
        "timestamp": "2026-10-18T11:00:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
    }
    r1 = await async_client.post("/v1/events", json=payload_no_prov, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "ingested"

    s1 = await async_client.get(
        "/v1/learners/student_prov_1/concepts/stats.probability/state",
        headers=headers,
    )
    d1 = s1.json()
    assert d1["total_events_count"] == 1
    assert d1["independent_attempts_count"] == 0  # NOT counted as verified independent attempt
    assert d1["independent_mastery"] == 0.10  # Preserves initial prior, does not advance!
    assert d1["uncertainty"] == 1.0

    # Case B: Provisional status
    payload_provisional = {
        "event_id": "evt_prov_provisional_02",
        "student_id": "student_prov_1",
        "session_id": "sess_prov",
        "concept_ids": ["stats.probability"],
        "item_id": "item_prob_2",
        "timestamp": "2026-10-18T11:05:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "answer_key",
            "status": "provisional",  # Provisional grading
        },
    }
    r2 = await async_client.post("/v1/events", json=payload_provisional, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "ingested"

    s2 = await async_client.get(
        "/v1/learners/student_prov_1/concepts/stats.probability/state",
        headers=headers,
    )
    d2 = s2.json()
    assert d2["total_events_count"] == 2
    assert d2["independent_attempts_count"] == 0  # Still 0
    assert d2["independent_mastery"] == 0.10  # Still 0.10

    # Case C: Model-graded (untrusted without explicit verification)
    payload_model_graded = {
        "event_id": "evt_prov_model_03",
        "student_id": "student_prov_1",
        "session_id": "sess_prov",
        "concept_ids": ["stats.probability"],
        "item_id": "item_prob_3",
        "timestamp": "2026-10-18T11:10:00Z",
        "event_type": "attempt",
        "correctness": True,
        "assistance_level": 0,
        "provenance": {
            "judgment_source": "model_graded",
            "status": "verified",
        },
    }
    r3 = await async_client.post("/v1/events", json=payload_model_graded, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["status"] == "ingested"

    s3 = await async_client.get(
        "/v1/learners/student_prov_1/concepts/stats.probability/state",
        headers=headers,
    )
    d3 = s3.json()
    assert d3["total_events_count"] == 3
    assert d3["independent_attempts_count"] == 0
    assert d3["independent_mastery"] == 0.10
