"""031_analysis_job_claim_authority

Revision ID: 031_analysis_job_claim_authority
Revises: 030_reconcile_application_role_catalog
Create Date: 2026-08-07 12:00:00.000000

"""

from alembic import op

revision = "031_analysis_job_claim_authority"
down_revision = "030_reconcile_application_role_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add claim_token and recovery_count columns with CHECK constraint
    op.execute("""
        ALTER TABLE public.analysis_jobs
        ADD COLUMN claim_token uuid NULL;
    """)

    op.execute("""
        ALTER TABLE public.analysis_jobs
        ADD COLUMN recovery_count integer NOT NULL DEFAULT 0;
    """)

    op.execute("""
        ALTER TABLE public.analysis_jobs
        ADD CONSTRAINT chk_analysis_jobs_recovery_count
        CHECK (recovery_count BETWEEN 0 AND 1);
    """)

    # 2. RLS policies allowing db_owner SECURITY DEFINER claim procedures unscoped table access
    op.execute("""
        CREATE POLICY analysis_jobs_owner_claim_policy
        ON public.analysis_jobs
        FOR ALL
        TO db_owner
        USING (true)
        WITH CHECK (true);
    """)

    op.execute("""
        CREATE POLICY analysis_attempts_owner_claim_policy
        ON public.analysis_attempts
        FOR ALL
        TO db_owner
        USING (true)
        WITH CHECK (true);
    """)

    # 3. Partial indexes for Fresh Claim and Stale Recovery
    op.execute("""
        CREATE INDEX idx_analysis_jobs_fresh
        ON public.analysis_jobs (created_at ASC, id ASC)
        WHERE status = 'RECEIVED' AND claim_token IS NULL;
    """)

    op.execute("""
        CREATE INDEX idx_analysis_jobs_stale
        ON public.analysis_jobs (lease_expires_at ASC, created_at ASC, id ASC)
        WHERE status IN (
          'RECEIVED',
          'UNDERSTANDING_REQUEST',
          'PLANNING',
          'POLICY_CHECK',
          'RETRIEVING_INTERNAL_SOURCES',
          'VALIDATING_SOURCES'
        )
        AND claim_token IS NOT NULL;
    """)

    # 3. Function: claim_next_analysis_job (Fresh Claims Only)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.claim_next_analysis_job(
            p_worker_id text
        )
        RETURNS TABLE (
            job_id uuid,
            organization_id uuid,
            claim_token uuid
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_job_id uuid;
            v_org_id uuid;
            v_new_token uuid;
        BEGIN
            IF p_worker_id IS NULL
               OR pg_catalog.btrim(p_worker_id) = ''
               OR pg_catalog.length(p_worker_id) > 100
               OR p_worker_id OPERATOR(pg_catalog.~) '[[:cntrl:]]' THEN
                RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Invalid or unsafe worker ID';
            END IF;

            SELECT aj.id, aj.organization_id
            INTO v_job_id, v_org_id
            FROM public.analysis_jobs aj
            WHERE aj.status = 'RECEIVED'
              AND aj.claim_token IS NULL
              AND aj.locked_by IS NULL
              AND aj.lease_expires_at IS NULL
            ORDER BY aj.created_at ASC, aj.id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1;

            IF v_job_id IS NOT NULL THEN
                v_new_token := pg_catalog.gen_random_uuid();
                UPDATE public.analysis_jobs
                SET status = 'RECEIVED',
                    locked_by = p_worker_id,
                    claim_token = v_new_token,
                    locked_at = pg_catalog.now(),
                    lease_expires_at = pg_catalog.now() + INTERVAL '15 minutes',
                    updated_at = pg_catalog.now()
                WHERE public.analysis_jobs.id = v_job_id;

                RETURN QUERY SELECT v_job_id, v_org_id, v_new_token;
            END IF;
        END;
        $$;
    """)

    # 4. Function: recover_next_stale_analysis_job (Stale Crash Recovery Only)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.recover_next_stale_analysis_job(
            p_worker_id text
        )
        RETURNS TABLE (
            job_id uuid,
            organization_id uuid,
            claim_token uuid
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_job_id uuid;
            v_org_id uuid;
            v_new_token uuid;
        BEGIN
            IF p_worker_id IS NULL
               OR pg_catalog.btrim(p_worker_id) = ''
               OR pg_catalog.length(p_worker_id) > 100
               OR p_worker_id OPERATOR(pg_catalog.~) '[[:cntrl:]]' THEN
                RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Invalid or unsafe worker ID';
            END IF;

            SELECT aj.id, aj.organization_id
            INTO v_job_id, v_org_id
            FROM public.analysis_jobs aj
            WHERE aj.status IN (
              'RECEIVED',
              'UNDERSTANDING_REQUEST',
              'PLANNING',
              'POLICY_CHECK',
              'RETRIEVING_INTERNAL_SOURCES',
              'VALIDATING_SOURCES'
            )
              AND aj.claim_token IS NOT NULL
              AND aj.lease_expires_at < pg_catalog.now()
              AND aj.recovery_count = 0
            ORDER BY aj.lease_expires_at ASC, aj.created_at ASC, aj.id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1;

            IF v_job_id IS NOT NULL THEN
                UPDATE public.analysis_attempts
                SET status = 'ABANDONED'
                WHERE analysis_job_id = v_job_id
                  AND status = 'RUNNING';

                v_new_token := pg_catalog.gen_random_uuid();
                UPDATE public.analysis_jobs
                SET status = 'RECEIVED',
                    locked_by = p_worker_id,
                    claim_token = v_new_token,
                    locked_at = pg_catalog.now(),
                    lease_expires_at = pg_catalog.now() + INTERVAL '15 minutes',
                    recovery_count = recovery_count + 1,
                    updated_at = pg_catalog.now()
                WHERE public.analysis_jobs.id = v_job_id;

                RETURN QUERY SELECT v_job_id, v_org_id, v_new_token;
            END IF;
        END;
        $$;
    """)

    # 5. Function: renew_analysis_job_lease (Heartbeat)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.renew_analysis_job_lease(
            p_job_id uuid,
            p_claim_token uuid,
            p_worker_id text
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_updated int;
        BEGIN
            IF p_job_id IS NULL OR p_claim_token IS NULL OR p_worker_id IS NULL THEN
                RETURN false;
            END IF;

            IF pg_catalog.btrim(p_worker_id) = ''
               OR pg_catalog.length(p_worker_id) > 100
               OR p_worker_id OPERATOR(pg_catalog.~) '[[:cntrl:]]' THEN
                RETURN false;
            END IF;

            UPDATE public.analysis_jobs
            SET lease_expires_at = pg_catalog.now() + INTERVAL '15 minutes',
                updated_at = pg_catalog.now()
            WHERE id = p_job_id
              AND claim_token = p_claim_token
              AND locked_by = p_worker_id
              AND status IN (
                'RECEIVED',
                'UNDERSTANDING_REQUEST',
                'PLANNING',
                'POLICY_CHECK',
                'RETRIEVING_INTERNAL_SOURCES',
                'VALIDATING_SOURCES',
                'EXECUTING_TOOLS',
                'RECONCILING_RESULTS',
                'GENERATING_STRUCTURED_RESULT',
                'QUALITY_GATE'
              );

            GET DIAGNOSTICS v_updated = ROW_COUNT;
            RETURN v_updated > 0;
        END;
        $$;
    """)

    # 6. Privileges (Least-Privilege)
    op.execute("""
        ALTER FUNCTION public.claim_next_analysis_job(text) OWNER TO db_owner;
        REVOKE ALL ON FUNCTION public.claim_next_analysis_job(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.claim_next_analysis_job(text) TO db_api_user;

        ALTER FUNCTION public.recover_next_stale_analysis_job(text) OWNER TO db_owner;
        REVOKE ALL ON FUNCTION public.recover_next_stale_analysis_job(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.recover_next_stale_analysis_job(text) TO db_api_user;

        ALTER FUNCTION public.renew_analysis_job_lease(uuid, uuid, text) OWNER TO db_owner;
        REVOKE ALL ON FUNCTION public.renew_analysis_job_lease(uuid, uuid, text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.renew_analysis_job_lease(uuid, uuid, text) TO db_api_user;
    """)


def downgrade() -> None:
    # Downgrade in exact reverse order
    op.execute("REVOKE EXECUTE ON FUNCTION public.renew_analysis_job_lease(uuid, uuid, text) FROM db_api_user;")
    op.execute("REVOKE EXECUTE ON FUNCTION public.recover_next_stale_analysis_job(text) FROM db_api_user;")
    op.execute("REVOKE EXECUTE ON FUNCTION public.claim_next_analysis_job(text) FROM db_api_user;")

    op.execute("DROP FUNCTION IF EXISTS public.renew_analysis_job_lease(uuid, uuid, text);")
    op.execute("DROP FUNCTION IF EXISTS public.recover_next_stale_analysis_job(text);")
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_analysis_job(text);")

    op.execute("DROP POLICY IF EXISTS analysis_attempts_owner_claim_policy ON public.analysis_attempts;")
    op.execute("DROP POLICY IF EXISTS analysis_jobs_owner_claim_policy ON public.analysis_jobs;")
    op.execute("DROP INDEX IF EXISTS public.idx_analysis_jobs_stale;")
    op.execute("DROP INDEX IF EXISTS public.idx_analysis_jobs_fresh;")

    op.execute("ALTER TABLE public.analysis_jobs DROP CONSTRAINT IF EXISTS chk_analysis_jobs_recovery_count;")
    op.execute("ALTER TABLE public.analysis_jobs DROP COLUMN IF EXISTS recovery_count;")
    op.execute("ALTER TABLE public.analysis_jobs DROP COLUMN IF EXISTS claim_token;")
