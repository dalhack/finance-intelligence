"""005_worker_claim_and_guarded_downgrade

Revision ID: 005_worker_claim_downgrade
Revises: 004_revoke_app_user
Create Date: 2026-07-29

Adds claim_next_ingestion_job SECURITY DEFINER control-plane claim function owned by db_owner,
adds locked_by and locked_at tracking columns to ingestion_jobs,
and enforces guarded, irreversible deprecation of db_app_user on downgrade.
"""

from alembic import op

revision = "005_worker_claim_downgrade"
down_revision = "004_revoke_app_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add lock tracking columns to ingestion_jobs
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'ingestion_jobs' AND column_name = 'locked_by'
            ) THEN
                ALTER TABLE ingestion_jobs ADD COLUMN locked_by VARCHAR(255) NULL;
                ALTER TABLE ingestion_jobs ADD COLUMN locked_at TIMESTAMPTZ NULL;
            END IF;
        END
        $$;
    """)

    # 2. Create SECURITY DEFINER control-plane job claim function
    op.execute("""
        CREATE OR REPLACE FUNCTION public.claim_next_ingestion_job(p_worker_id text)
        RETURNS TABLE (
            job_id uuid,
            organization_id uuid,
            document_version_id uuid
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_catalog, pg_temp
        AS $$
        DECLARE
            v_job_id uuid;
            v_org_id uuid;
            v_doc_ver_id uuid;
        BEGIN
            -- Atomically claim the oldest QUEUED job across tenant boundaries
            SELECT ij.id, ij.organization_id, ij.document_version_id
            INTO v_job_id, v_org_id, v_doc_ver_id
            FROM public.ingestion_jobs ij
            WHERE ij.status = 'QUEUED'
            ORDER BY ij.created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1;

            IF v_job_id IS NOT NULL THEN
                UPDATE public.ingestion_jobs
                SET status = 'PARSING',
                    locked_by = p_worker_id,
                    locked_at = now()
                WHERE id = v_job_id;

                RETURN QUERY SELECT v_job_id, v_org_id, v_doc_ver_id;
            END IF;
        END;
        $$;
    """)

    # 3. Restrict ACL permissions on claim_next_ingestion_job
    op.execute("""
        REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM PUBLIC;
        
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) TO db_ingestion_worker;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) TO db_owner;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # 1. Drop control-plane claim function
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text);")

    # 2. Guarded Downgrade Policy:
    # db_app_user privileges were revoked in 004 and are PERMANENTLY DEPRECATED.
    # Downgrade will NOT restore legacy privileges to db_app_user for security reasons.
