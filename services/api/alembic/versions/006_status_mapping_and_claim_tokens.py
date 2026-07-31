"""006_status_mapping_and_claim_tokens

Revision ID: 006_claim_tokens
Revises: 005_worker_claim_downgrade
Create Date: 2026-07-29

Adds claim_token column to ingestion_jobs, updates claim_next_ingestion_job SECURITY DEFINER
function with worker validation, claim_token generation, and lease recovery, and sets function owner to db_owner.
"""

from alembic import op

revision = "006_claim_tokens"
down_revision = "005_worker_claim_downgrade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add claim_token UUID column to ingestion_jobs
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'ingestion_jobs' AND column_name = 'claim_token'
            ) THEN
                ALTER TABLE ingestion_jobs ADD COLUMN claim_token UUID NULL;
            END IF;
        END
        $$;
    """)

    # 2. Re-create SECURITY DEFINER control-plane claim function with worker ID validation and claim_token
    op.execute("""
        CREATE OR REPLACE FUNCTION public.claim_next_ingestion_job(
            p_worker_id text,
            p_claim_token uuid
        )
        RETURNS TABLE (
            job_id uuid,
            organization_id uuid,
            document_version_id uuid,
            claim_token uuid
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
            -- Validate worker ID input
            IF p_worker_id IS NULL OR trim(p_worker_id) = '' OR length(p_worker_id) > 255 THEN
                RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Invalid or missing worker ID';
            END IF;

            -- Validate claim token input
            IF p_claim_token IS NULL THEN
                RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Missing claim token';
            END IF;

            -- Atomically claim the oldest QUEUED job or lease-expired stale PARSING job across tenant boundaries
            SELECT ij.id, ij.organization_id, ij.document_version_id
            INTO v_job_id, v_org_id, v_doc_ver_id
            FROM public.ingestion_jobs ij
            WHERE ij.status = 'QUEUED'
               OR (ij.status = 'PARSING' AND ij.locked_at < now() - INTERVAL '15 minutes' AND ij.current_attempt < ij.max_attempts)
            ORDER BY ij.created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1;

            IF v_job_id IS NOT NULL THEN
                UPDATE public.ingestion_jobs
                SET status = 'PARSING',
                    locked_by = p_worker_id,
                    claim_token = p_claim_token,
                    locked_at = now()
                WHERE id = v_job_id;

                RETURN QUERY SELECT v_job_id, v_org_id, v_doc_ver_id, p_claim_token;
            END IF;
        END;
        $$;
    """)

    # 3. Explicitly set function owner to db_owner
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                ALTER FUNCTION public.claim_next_ingestion_job(text, uuid) OWNER TO db_owner;
            END IF;
        END
        $$;
    """)

    # 4. Restrict ACL permissions on claim_next_ingestion_job and grant read access to db_api_user on ingestion_attempts
    op.execute("""
        REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text, uuid) FROM PUBLIC;
        
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT EXECUTE ON FUNCTION public.claim_next_ingestion_job(text, uuid) TO db_ingestion_worker;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT EXECUTE ON FUNCTION public.claim_next_ingestion_job(text, uuid) TO db_owner;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT SELECT ON TABLE public.ingestion_attempts TO db_api_user;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # 1. Drop control-plane claim function
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text, uuid);")

    # 2. Drop claim_token column
    op.execute("ALTER TABLE ingestion_jobs DROP COLUMN IF EXISTS claim_token;")
