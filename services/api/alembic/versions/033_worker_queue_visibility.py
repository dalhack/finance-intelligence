"""033_worker_queue_visibility

Revision ID: 033_worker_queue_visibility
Revises: 032_bootstrap_self_onboarding
Create Date: 2026-08-13 22:10:00.000000

The ingestion worker polls for QUEUED jobs across all tenants, but
worker_tenant_policy RLS scopes db_ingestion_worker to a single org GUC,
so the global poll always saw zero rows. Mirrors the claim_ingestion_job
pattern: a narrow SECURITY DEFINER fetch that exposes only the next
claimable job id, nothing tenant-scoped.
"""

from alembic import op

revision = "033_worker_queue_visibility"
down_revision = "032_bootstrap_self_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION public.fetch_next_queued_ingestion_job(
            p_stale_threshold_minutes integer DEFAULT 15
        )
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT id FROM ingestion_jobs
            WHERE status = 'QUEUED'
               OR (status = 'PARSING'
                   AND locked_at < now() - make_interval(mins => p_stale_threshold_minutes))
            ORDER BY created_at
            LIMIT 1;
        $$;
    """)

    op.execute("""
        REVOKE ALL ON FUNCTION public.fetch_next_queued_ingestion_job(integer) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.fetch_next_queued_ingestion_job(integer) TO db_ingestion_worker;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.fetch_next_queued_ingestion_job(integer);")
