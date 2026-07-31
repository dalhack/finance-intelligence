"""010_fact_revision_and_active_uniqueness

Revision ID: 010_fact_revision_uniqueness
Revises: 009_facts_integrity
Create Date: 2026-07-30 14:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_fact_revision_uniqueness"
down_revision: str | None = "009_facts_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add composite UNIQUE constraint on financial_facts(organization_id, id) for tenant-scoped composite FKs
    op.create_unique_constraint(
        "uq_financial_facts_org_id",
        "financial_facts",
        ["organization_id", "id"],
    )

    # 2. Add conflict tracking columns to financial_fact_candidates
    op.add_column("financial_fact_candidates", sa.Column("conflicting_fact_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "financial_fact_candidates",
        sa.Column("conflict_detected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("financial_fact_candidates", sa.Column("conflict_reason", sa.String(length=50), nullable=True))
    op.add_column("financial_fact_candidates", sa.Column("detected_value_hash", sa.String(length=64), nullable=True))

    # 3. Add composite FK on financial_fact_candidates (organization_id, conflicting_fact_id) referencing financial_facts(organization_id, id)
    op.create_foreign_key(
        "fk_fact_candidates_conflicting_fact",
        "financial_fact_candidates",
        "financial_facts",
        ["organization_id", "conflicting_fact_id"],
        ["organization_id", "id"],
        ondelete="SET NULL",
    )

    # 4. Add composite FK on financial_facts (organization_id, supersedes_fact_id) referencing financial_facts(organization_id, id)
    op.create_foreign_key(
        "fk_financial_facts_supersedes_fact",
        "financial_facts",
        "financial_facts",
        ["organization_id", "supersedes_fact_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )

    # 5. Create partial unique index enforcing EXACTLY ONE active fact per natural key (WHERE valid_to IS NULL)
    op.execute("""
    CREATE UNIQUE INDEX uq_financial_facts_active_natural_key ON public.financial_facts (
        organization_id,
        institution_id,
        reporting_period_id,
        metric_definition_id,
        reporting_basis,
        currency,
        unit
    ) WHERE valid_to IS NULL;
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrade of 010_fact_revision_uniqueness is guarded to prevent data corruption "
        "and violation of active financial fact uniqueness guarantees."
    )
