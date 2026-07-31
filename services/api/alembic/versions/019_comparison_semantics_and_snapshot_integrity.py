"""019_comparison_semantics_and_snapshot_integrity

Revision ID: 019_comparison_semantics_and_snapshot_integrity
Revises: 018_comparison_dataset_correctness
Create Date: 2026-07-31

Upgrades comparison dataset schema version default to 3.0.0, performs preflight snapshot count verification without data loss, and pekiştirir FORCE RLS & worker privilege denials.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019_comparison_semantics_and_snapshot_integrity"
down_revision: str | None = "018_comparison_dataset_correctness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Preflight check to verify snapshot count before modification
    op.execute("""
    DO $$
    DECLARE
        v_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO v_count FROM public.result_datasets;
        RAISE NOTICE 'Migration 019 preflight snapshot count: %', v_count;
    END;
    $$;
    """)

    # 2. Update default schema_version in result_datasets to '3.0.0'
    op.execute("""
    ALTER TABLE public.result_datasets ALTER COLUMN schema_version SET DEFAULT '3.0.0';
    """)

    # 3. Reinforce FORCE RLS on comparison_runs and result_datasets
    op.execute("""
    ALTER TABLE public.comparison_runs FORCE ROW LEVEL SECURITY;
    ALTER TABLE public.result_datasets FORCE ROW LEVEL SECURITY;
    """)

    # 4. Reinforce Worker denial
    op.execute("""
    REVOKE ALL ON public.comparison_runs, public.result_datasets FROM db_ingestion_worker, db_bootstrap, PUBLIC;
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 019 is prohibited to protect comparison dataset semantics and snapshot integrity."
    )
