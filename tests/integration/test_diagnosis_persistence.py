"""Integration tests for Misconception Diagnosis Persistence (M2-Phase G)."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lam.domain.diagnosis.models import (
    HypothesisStatus,
    MisconceptionCategory,
    MisconceptionHypothesis,
)
from lam.infrastructure.repositories.diagnosis_repository import DiagnosisRepository


@pytest.mark.asyncio
async def test_hypothesis_persistence_across_sessions(
    db_session: AsyncSession,
) -> None:
    repo = DiagnosisRepository(db_session)
    tenant_id = "tenant_diag_p01"
    student_id = "student_diag_p01"
    concept_id = "math.fractions.addition"

    hypo = MisconceptionHypothesis(
        hypothesis_id="hypo_persist_01",
        tenant_id=tenant_id,
        student_id=student_id,
        concept_id=concept_id,
        category=MisconceptionCategory.CONCEPTUAL_MISUNDERSTANDING,
        status=HypothesisStatus.OPEN,
        confidence=0.35,
        supporting_evidence_ids=["evt_001"],
        contradictory_evidence_ids=[],
    )

    audit: dict[str, Any] = {
        "event_id": "evt_001",
        "from_status": HypothesisStatus.OPEN.value,
        "to_status": HypothesisStatus.OPEN.value,
        "delta": 0.35,
        "new_confidence": 0.35,
        "rationale": "Initial candidate error opened hypothesis.",
    }

    # Save and commit in session
    await repo.save_hypothesis(tenant_id, hypo, audit)
    await db_session.commit()

    # Query in fresh query
    loaded = await repo.get_hypotheses(tenant_id, student_id, concept_id)
    assert len(loaded) == 1
    assert loaded[0].hypothesis_id == "hypo_persist_01"
    assert loaded[0].status == HypothesisStatus.OPEN
    assert loaded[0].confidence == 0.35
    assert loaded[0].supporting_evidence_ids == ["evt_001"]

    # Verify audit trail persisted
    audit_history = await repo.get_audit_trail(tenant_id, "hypo_persist_01")
    assert len(audit_history) == 1
    assert audit_history[0].event_id == "evt_001"
    assert audit_history[0].confidence_delta == 0.35


@pytest.mark.asyncio
async def test_hypothesis_update_and_audit_accumulation(
    db_session: AsyncSession,
) -> None:
    repo = DiagnosisRepository(db_session)
    tenant_id = "tenant_diag_p02"
    student_id = "student_diag_p02"
    concept_id = "math.algebra.monomials"

    hypo = MisconceptionHypothesis(
        hypothesis_id="hypo_persist_02",
        tenant_id=tenant_id,
        student_id=student_id,
        concept_id=concept_id,
        category=MisconceptionCategory.PROCEDURAL_ERROR,
        status=HypothesisStatus.OPEN,
        confidence=0.35,
        supporting_evidence_ids=["e1"],
        contradictory_evidence_ids=[],
    )
    await repo.save_hypothesis(tenant_id, hypo)
    await db_session.commit()

    # Transition to CONFIRMED
    hypo.status = HypothesisStatus.CONFIRMED
    hypo.confidence = 0.80
    hypo.supporting_evidence_ids.append("e2")
    audit2: dict[str, Any] = {
        "event_id": "e2",
        "from_status": HypothesisStatus.OPEN.value,
        "to_status": HypothesisStatus.CONFIRMED.value,
        "delta": 0.45,
        "new_confidence": 0.80,
        "rationale": "Repeated error confirmed hypothesis.",
    }
    await repo.save_hypothesis(tenant_id, hypo, audit2)
    await db_session.commit()

    # Verify updated state
    loaded = await repo.get_hypotheses(tenant_id, student_id, concept_id)
    assert len(loaded) == 1
    assert loaded[0].status == HypothesisStatus.CONFIRMED
    assert loaded[0].confidence == 0.80
    assert loaded[0].supporting_evidence_ids == ["e1", "e2"]
    assert loaded[0].state_version == 2

    # Verify 1 audit entry
    trail = await repo.get_audit_trail(tenant_id, "hypo_persist_02")
    assert len(trail) == 1
    assert trail[0].to_status == HypothesisStatus.CONFIRMED.value


@pytest.mark.asyncio
async def test_diagnosis_tenant_isolation(
    db_session: AsyncSession,
) -> None:
    repo = DiagnosisRepository(db_session)
    tenant_a = "tenant_iso_A"
    tenant_b = "tenant_iso_B"
    student_id = "student_shared_id"
    concept_id = "math.geometry.angles"

    hypo_a = MisconceptionHypothesis(
        hypothesis_id="hypo_iso_01",
        tenant_id=tenant_a,
        student_id=student_id,
        concept_id=concept_id,
        category=MisconceptionCategory.CONCEPTUAL_MISUNDERSTANDING,
        status=HypothesisStatus.OPEN,
        confidence=0.35,
        supporting_evidence_ids=["ea1"],
        contradictory_evidence_ids=[],
    )
    await repo.save_hypothesis(tenant_a, hypo_a)
    await db_session.commit()

    # Query from tenant B: must return empty list
    results_b = await repo.get_hypotheses(tenant_b, student_id, concept_id)
    assert len(results_b) == 0

    # Query from tenant A: returns hypothesis
    results_a = await repo.get_hypotheses(tenant_a, student_id, concept_id)
    assert len(results_a) == 1
    assert results_a[0].hypothesis_id == "hypo_iso_01"


@pytest.mark.asyncio
async def test_transaction_rollback_preserves_clean_state(
    db_session: AsyncSession,
) -> None:
    repo = DiagnosisRepository(db_session)
    tenant_id = "tenant_diag_rb"
    student_id = "student_diag_rb"
    concept_id = "physics.mechanics.forces"

    hypo = MisconceptionHypothesis(
        hypothesis_id="hypo_rb_01",
        tenant_id=tenant_id,
        student_id=student_id,
        concept_id=concept_id,
        category=MisconceptionCategory.ARITHMETIC_ERROR,
        status=HypothesisStatus.OPEN,
        confidence=0.35,
        supporting_evidence_ids=["e1"],
        contradictory_evidence_ids=[],
    )
    await repo.save_hypothesis(tenant_id, hypo)
    # Rollback transaction instead of committing
    await db_session.rollback()

    loaded = await repo.get_hypotheses(tenant_id, student_id, concept_id)
    assert len(loaded) == 0
