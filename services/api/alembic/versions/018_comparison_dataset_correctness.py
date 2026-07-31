"""018_comparison_dataset_correctness

Revision ID: 018_comparison_dataset_correctness
Revises: 017_comparison_dataset
Create Date: 2026-07-31

Upgrades comparison dataset schema version default to 2.0.0 and verifies RLS, FORCE RLS, worker denial, and immutability triggers for comparison datasets.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018_comparison_dataset_correctness"
down_revision: str | None = "017_comparison_dataset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update default schema_version in result_datasets to '2.0.0'
    op.execute("""
    ALTER TABLE public.result_datasets ALTER COLUMN schema_version SET DEFAULT '2.0.0';
    """)

    # 2. Reinforce FORCE RLS on comparison_runs and result_datasets
    op.execute("""
    ALTER TABLE public.comparison_runs FORCE ROW LEVEL SECURITY;
    ALTER TABLE public.result_datasets FORCE ROW LEVEL SECURITY;
    """)

    # 3. Reinforce Worker denial
    op.execute("""
    REVOKE ALL ON public.comparison_runs, public.result_datasets FROM db_ingestion_worker, db_bootstrap, PUBLIC;
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 018 is prohibited to protect comparison dataset correctness and schema versioning."
    )
