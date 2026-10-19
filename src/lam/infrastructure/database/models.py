"""SQLAlchemy 2.0 database models for LAM."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LearningEventModel(Base):
    """Durable append-only event ledger model.

    Enforces:
    - Event idempotency at database level via UniqueConstraint(tenant_id, event_id).
    - Multi-tenant partitioning and isolation.
    """

    __tablename__ = "learning_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    concept_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Scored / interaction fields (Strict: Nullable for non-coercion)
    correctness: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assistance_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hints_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    self_reported_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    intervention_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    assessment_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", name="uq_tenant_event_id"),
        Index("ix_events_tenant_student_time", "tenant_id", "student_id", "timestamp"),
    )


class LearnerStateModel(Base):
    """Persistent per-student per-concept state model.

    Enforces:
    - Unique state record per (tenant_id, student_id, concept_id).
    - Optimistic concurrency control via monotonic state_version.
    """

    __tablename__ = "learner_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    concept_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    concept_mastery: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    independent_mastery: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    assisted_performance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    total_events_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    independent_attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assisted_attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_independent_successes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    prerequisite_readiness: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    retention_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bkt_parameter_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "concept_id", name="uq_tenant_student_concept"),
    )


class MisconceptionHypothesisModel(Base):
    """Persistent storage for diagnostic misconception hypotheses.

    Tracks active and historical candidate or confirmed misconceptions
    per student per concept.
    """

    __tablename__ = "misconception_hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hypothesis_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    concept_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    category: Mapped[str] = mapped_column(String(64), nullable=False)
    # Lifecycle: open, confirmed, revised, retired
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    contradictory_evidence_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )

    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "hypothesis_id", name="uq_tenant_hypothesis_id"),
        Index("ix_hypo_tenant_student_concept", "tenant_id", "student_id", "concept_id"),
    )


class HypothesisAuditEntryModel(Base):
    """Append-only audit trail recording every state and confidence transition."""

    __tablename__ = "hypothesis_audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence_delta: Mapped[float] = mapped_column(Float, nullable=False)
    new_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(String(512), nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
