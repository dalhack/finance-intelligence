"""007_drop_legacy_claim_overload

Revision ID: 007_drop_legacy_overload
Revises: 006_claim_tokens
Create Date: 2026-07-30

Drops the legacy single-parameter claim_next_ingestion_job(text) function overload created in Migration 005,
ensuring only the hardened claim_next_ingestion_job(text, uuid) function exists in the database.
"""

from alembic import op

revision = "007_drop_legacy_overload"
down_revision = "006_claim_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Revoke privileges on legacy single-parameter overload if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT FROM pg_proc p 
                JOIN pg_namespace n ON n.oid = p.pronamespace 
                WHERE n.nspname = 'public' AND p.proname = 'claim_next_ingestion_job' 
                  AND pg_get_function_identity_arguments(p.oid) = 'text'
            ) THEN
                REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM PUBLIC;
                REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM db_ingestion_worker;
                REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM db_owner;
                REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM db_api_user;
                REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM db_bootstrap;
                REVOKE EXECUTE ON FUNCTION public.claim_next_ingestion_job(text) FROM db_app_user;
            END IF;
        END
        $$;
    """)

    # 2. Drop the legacy single-parameter and 2-parameter function overloads so only 1 signature remains
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text);")
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text, uuid);")

    # 3. Create hardened claim_next_ingestion_job with optional p_organization_id for deterministic tenant isolation
    op.execute("""
        CREATE OR REPLACE FUNCTION public.claim_next_ingestion_job(
            p_worker_id text,
            p_claim_token uuid,
            p_organization_id uuid DEFAULT NULL
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

            -- Atomically claim the oldest QUEUED job or lease-expired stale PARSING job (scoped to p_organization_id if provided)
            SELECT ij.id, ij.organization_id, ij.document_version_id
            INTO v_job_id, v_org_id, v_doc_ver_id
            FROM public.ingestion_jobs ij
            WHERE (p_organization_id IS NULL OR ij.organization_id = p_organization_id)
              AND (
                  ij.status = 'QUEUED'
               OR (ij.status = 'PARSING' AND ij.locked_at < now() - INTERVAL '15 minutes' AND ij.current_attempt < ij.max_attempts)
              )
            ORDER BY ij.created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1;

            IF v_job_id IS NOT NULL THEN
                UPDATE public.ingestion_jobs
                SET status = 'PARSING',
                    locked_by = p_worker_id,
                    claim_token = p_claim_token,
                    locked_at = now()
                WHERE public.ingestion_jobs.id = v_job_id;

                RETURN QUERY SELECT v_job_id, v_org_id, v_doc_ver_id, p_claim_token;
            END IF;
        END;
        $$;

        ALTER FUNCTION public.claim_next_ingestion_job(text, uuid, uuid) OWNER TO db_owner;
        REVOKE ALL ON FUNCTION public.claim_next_ingestion_job(text, uuid, uuid) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.claim_next_ingestion_job(text, uuid, uuid) TO db_ingestion_worker;
        GRANT EXECUTE ON FUNCTION public.claim_next_ingestion_job(text, uuid, uuid) TO db_owner;
    """)


def downgrade() -> None:
    # Downgrade explicitly ensures no legacy single-parameter SECURITY DEFINER function is ever re-created
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text);")
