"""Repository for persisting Misconception Hypotheses and Audit Trails."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lam.domain.diagnosis.models import (
    HypothesisAuditEntry,
    HypothesisStatus,
    MisconceptionCategory,
    MisconceptionHypothesis,
)
from lam.infrastructure.database.models import (
    HypothesisAuditEntryModel,
    MisconceptionHypothesisModel,
)


class DiagnosisRepository:
    """Manages transactional persistence for misconception hypotheses and audit records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_hypotheses(
        self,
        tenant_id: str,
        student_id: str,
        concept_id: str,
        active_only: bool = True,
        for_update: bool = False,
    ) -> list[MisconceptionHypothesis]:
        """Retrieves persisted hypotheses for a student and concept."""
        stmt = select(MisconceptionHypothesisModel).where(
            MisconceptionHypothesisModel.tenant_id == tenant_id,
            MisconceptionHypothesisModel.student_id == student_id,
            MisconceptionHypothesisModel.concept_id == concept_id,
        )
        if active_only:
            # Active means not RETIRED
            stmt = stmt.where(MisconceptionHypothesisModel.status != HypothesisStatus.RETIRED.value)

        if for_update:
            stmt = stmt.with_for_update()

        res = await self.session.execute(stmt)
        models = res.scalars().all()

        hypotheses: list[MisconceptionHypothesis] = []
        for m in models:
            hypo = MisconceptionHypothesis(
                hypothesis_id=m.hypothesis_id,
                tenant_id=m.tenant_id,
                student_id=m.student_id,
                concept_id=m.concept_id,
                category=MisconceptionCategory(m.category),
                status=HypothesisStatus(m.status),
                confidence=m.confidence,
                supporting_evidence_ids=list(m.supporting_evidence_ids),
                contradictory_evidence_ids=list(m.contradictory_evidence_ids),
                state_version=m.state_version,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            hypotheses.append(hypo)

        return hypotheses

    async def save_hypothesis(
        self,
        tenant_id: str,
        hypothesis: MisconceptionHypothesis,
        new_audit_entry: HypothesisAuditEntry | dict[str, Any] | None = None,
    ) -> None:
        """Upserts a hypothesis record and appends any new audit entry transactionally."""
        stmt = (
            select(MisconceptionHypothesisModel)
            .where(
                MisconceptionHypothesisModel.tenant_id == tenant_id,
                MisconceptionHypothesisModel.hypothesis_id == hypothesis.hypothesis_id,
            )
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()

        if model is None:
            # Insert new hypothesis
            model = MisconceptionHypothesisModel(
                hypothesis_id=hypothesis.hypothesis_id,
                tenant_id=tenant_id,
                student_id=hypothesis.student_id,
                concept_id=hypothesis.concept_id,
                category=hypothesis.category.value,
                status=hypothesis.status.value,
                confidence=hypothesis.confidence,
                supporting_evidence_ids=hypothesis.supporting_evidence_ids,
                contradictory_evidence_ids=hypothesis.contradictory_evidence_ids,
                state_version=hypothesis.state_version,
            )
            self.session.add(model)
        else:
            # Update existing
            model.status = hypothesis.status.value
            model.confidence = hypothesis.confidence
            model.supporting_evidence_ids = hypothesis.supporting_evidence_ids
            model.contradictory_evidence_ids = hypothesis.contradictory_evidence_ids
            model.state_version += 1

        # Append audit entry if provided
        if new_audit_entry is not None:
            if isinstance(new_audit_entry, HypothesisAuditEntry):
                event_id = new_audit_entry.trigger_event_id
                from_status = new_audit_entry.from_status.value
                to_status = new_audit_entry.to_status.value
                delta = new_audit_entry.confidence_after - new_audit_entry.confidence_before
                new_conf = new_audit_entry.confidence_after
                rationale = new_audit_entry.reason
            else:
                event_id = new_audit_entry.get("event_id") or new_audit_entry.get(
                    "trigger_event_id"
                )
                from_status = str(new_audit_entry.get("from_status", hypothesis.status.value))
                to_status = str(new_audit_entry.get("to_status", hypothesis.status.value))
                conf_after = new_audit_entry.get(
                    "new_confidence", new_audit_entry.get("confidence_after")
                )
                conf_before = new_audit_entry.get("confidence_before", 0.0)
                new_conf = float(conf_after if conf_after is not None else hypothesis.confidence)
                delta_val = new_audit_entry.get("delta")
                delta = float(
                    delta_val
                    if delta_val is not None
                    else (new_conf - float(conf_before if conf_before is not None else 0.0))
                )
                rationale = str(
                    new_audit_entry.get("rationale") or new_audit_entry.get("reason") or ""
                )

            audit_model = HypothesisAuditEntryModel(
                tenant_id=tenant_id,
                hypothesis_id=hypothesis.hypothesis_id,
                event_id=event_id,
                from_status=from_status,
                to_status=to_status,
                confidence_delta=delta,
                new_confidence=new_conf,
                rationale=rationale,
            )
            self.session.add(audit_model)

        await self.session.flush()

    async def get_audit_trail(
        self,
        tenant_id: str,
        hypothesis_id: str,
    ) -> list[HypothesisAuditEntryModel]:
        """Retrieves full audit history for a specific hypothesis."""
        stmt = (
            select(HypothesisAuditEntryModel)
            .where(
                HypothesisAuditEntryModel.tenant_id == tenant_id,
                HypothesisAuditEntryModel.hypothesis_id == hypothesis_id,
            )
            .order_by(HypothesisAuditEntryModel.timestamp.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
