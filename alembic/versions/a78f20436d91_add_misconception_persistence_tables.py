"""add_misconception_persistence_tables

Revision ID: a78f20436d91
Revises: 435e371938d3
Create Date: 2026-10-19 20:27:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a78f20436d91"
down_revision: Union[str, Sequence[str], None] = "435e371938d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add misconception hypotheses and audit trail tables."""
    op.create_table(
        "misconception_hypotheses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hypothesis_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("student_id", sa.String(length=128), nullable=False),
        sa.Column("concept_id", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("contradictory_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "hypothesis_id", name="uq_tenant_hypothesis_id"),
    )
    op.create_index(
        "ix_hypo_tenant_student_concept",
        "misconception_hypotheses",
        ["tenant_id", "student_id", "concept_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_misconception_hypotheses_concept_id"),
        "misconception_hypotheses",
        ["concept_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_misconception_hypotheses_student_id"),
        "misconception_hypotheses",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_misconception_hypotheses_tenant_id"),
        "misconception_hypotheses",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "hypothesis_audit_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=True),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("confidence_delta", sa.Float(), nullable=False),
        sa.Column("new_confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.String(length=512), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hypothesis_audit_entries_hypothesis_id"),
        "hypothesis_audit_entries",
        ["hypothesis_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hypothesis_audit_entries_tenant_id"),
        "hypothesis_audit_entries",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema to drop misconception tables."""
    op.drop_index(
        op.f("ix_hypothesis_audit_entries_tenant_id"),
        table_name="hypothesis_audit_entries",
    )
    op.drop_index(
        op.f("ix_hypothesis_audit_entries_hypothesis_id"),
        table_name="hypothesis_audit_entries",
    )
    op.drop_table("hypothesis_audit_entries")

    op.drop_index(
        op.f("ix_misconception_hypotheses_tenant_id"),
        table_name="misconception_hypotheses",
    )
    op.drop_index(
        op.f("ix_misconception_hypotheses_student_id"),
        table_name="misconception_hypotheses",
    )
    op.drop_index(
        op.f("ix_misconception_hypotheses_concept_id"),
        table_name="misconception_hypotheses",
    )
    op.drop_index(
        "ix_hypo_tenant_student_concept",
        table_name="misconception_hypotheses",
    )
    op.drop_table("misconception_hypotheses")
