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

    # 2. Partial indexes for Fresh Claim and Stale Recovery
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

    # 3. Dedicated NOLOGIN function-owner role provision
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_analysis_claim_owner') THEN
                CREATE ROLE db_analysis_claim_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
            END IF;
            EXECUTE format('GRANT db_analysis_claim_owner TO %I', CURRENT_USER);
        END $$;
    """)

    op.execute("GRANT USAGE, CREATE ON SCHEMA public TO db_analysis_claim_owner;")

    # Minimal Column-Level Grants for db_analysis_claim_owner
    op.execute("""
        GRANT SELECT (id, organization_id, status, claim_token, locked_by, lease_expires_at, recovery_count, created_at)
        ON public.analysis_jobs TO db_analysis_claim_owner;

        GRANT UPDATE (status, locked_by, claim_token, locked_at, lease_expires_at, recovery_count, updated_at)
        ON public.analysis_jobs TO db_analysis_claim_owner;

        GRANT SELECT (id, analysis_job_id, organization_id, status, attempt_number, created_at)
        ON public.analysis_attempts TO db_analysis_claim_owner;

        GRANT UPDATE (status)
        ON public.analysis_attempts TO db_analysis_claim_owner;
    """)

    # 4. Narrow RLS Policies ONLY for db_analysis_claim_owner role
    op.execute("""
        CREATE POLICY analysis_jobs_claim_owner_select_policy
        ON public.analysis_jobs
        FOR SELECT
        TO db_analysis_claim_owner
        USING (
          (status = 'RECEIVED' AND claim_token IS NULL)
          OR (
            status IN (
              'RECEIVED',
              'UNDERSTANDING_REQUEST',
              'PLANNING',
              'POLICY_CHECK',
              'RETRIEVING_INTERNAL_SOURCES',
              'VALIDATING_SOURCES'
            )
            AND claim_token IS NOT NULL
            AND lease_expires_at IS NOT NULL
            AND lease_expires_at < pg_catalog.now()
            AND recovery_count = 0
          )
          OR (
            status IN (
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
            )
            AND claim_token IS NOT NULL
          )
        );
    """)

    op.execute("""
        CREATE POLICY analysis_jobs_claim_owner_update_policy
        ON public.analysis_jobs
        FOR UPDATE
        TO db_analysis_claim_owner
        USING (
          (status = 'RECEIVED' AND claim_token IS NULL)
          OR (
            status IN (
              'RECEIVED',
              'UNDERSTANDING_REQUEST',
              'PLANNING',
              'POLICY_CHECK',
              'RETRIEVING_INTERNAL_SOURCES',
              'VALIDATING_SOURCES'
            )
            AND claim_token IS NOT NULL
            AND lease_expires_at IS NOT NULL
            AND lease_expires_at < pg_catalog.now()
            AND recovery_count = 0
          )
          OR (
            status IN (
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
            )
            AND claim_token IS NOT NULL
          )
        )
        WITH CHECK (
          status IN (
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
          )
          AND claim_token IS NOT NULL
          AND recovery_count BETWEEN 0 AND 1
        );
    """)

    op.execute("""
        CREATE POLICY analysis_attempts_claim_owner_select_policy
        ON public.analysis_attempts
        FOR SELECT
        TO db_analysis_claim_owner
        USING (
            status IN ('RUNNING', 'ABANDONED')
            AND EXISTS (
                SELECT 1 FROM public.analysis_jobs aj
                WHERE aj.id = analysis_attempts.analysis_job_id
                  AND aj.claim_token IS NOT NULL
                  AND aj.lease_expires_at IS NOT NULL
                  AND aj.lease_expires_at < pg_catalog.now()
                  AND aj.recovery_count = 0
                  AND aj.status IN (
                    'RECEIVED',
                    'UNDERSTANDING_REQUEST',
                    'PLANNING',
                    'POLICY_CHECK',
                    'RETRIEVING_INTERNAL_SOURCES',
                    'VALIDATING_SOURCES'
                  )
            )
        );

        CREATE POLICY analysis_attempts_claim_owner_update_policy
        ON public.analysis_attempts
        FOR UPDATE
        TO db_analysis_claim_owner
        USING (
            status = 'RUNNING'
            AND EXISTS (
                SELECT 1 FROM public.analysis_jobs aj
                WHERE aj.id = analysis_attempts.analysis_job_id
                  AND aj.claim_token IS NOT NULL
                  AND aj.lease_expires_at IS NOT NULL
                  AND aj.lease_expires_at < pg_catalog.now()
                  AND aj.recovery_count = 0
                  AND aj.status IN (
                    'RECEIVED',
                    'UNDERSTANDING_REQUEST',
                    'PLANNING',
                    'POLICY_CHECK',
                    'RETRIEVING_INTERNAL_SOURCES',
                    'VALIDATING_SOURCES'
                  )
            )
        )
        WITH CHECK (status = 'ABANDONED');
    """)

    # 5. Functions Creation & Ownership Assignment to db_analysis_claim_owner
    op.execute("""
        DO $$
        BEGIN
            EXECUTE format('GRANT db_analysis_claim_owner TO %I', CURRENT_USER);
        END $$;

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

        ALTER FUNCTION public.claim_next_analysis_job(text) OWNER TO db_analysis_claim_owner;
        ALTER FUNCTION public.recover_next_stale_analysis_job(text) OWNER TO db_analysis_claim_owner;
        ALTER FUNCTION public.renew_analysis_job_lease(uuid, uuid, text) OWNER TO db_analysis_claim_owner;

        REVOKE EXECUTE ON FUNCTION public.claim_next_analysis_job(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.claim_next_analysis_job(text) TO db_api_user;

        REVOKE EXECUTE ON FUNCTION public.recover_next_stale_analysis_job(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.recover_next_stale_analysis_job(text) TO db_api_user;

        REVOKE EXECUTE ON FUNCTION public.renew_analysis_job_lease(uuid, uuid, text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.renew_analysis_job_lease(uuid, uuid, text) TO db_api_user;

        DO $$
        BEGIN
            EXECUTE format('REVOKE db_analysis_claim_owner FROM %I', CURRENT_USER);
        END $$;
    """)


def downgrade() -> None:
    # Downgrade in exact reverse order
    op.execute("DROP FUNCTION IF EXISTS public.renew_analysis_job_lease(uuid, uuid, text);")
    op.execute("DROP FUNCTION IF EXISTS public.recover_next_stale_analysis_job(text);")
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_analysis_job(text);")

    op.execute("DROP POLICY IF EXISTS analysis_attempts_claim_owner_update_policy ON public.analysis_attempts;")
    op.execute("DROP POLICY IF EXISTS analysis_attempts_claim_owner_select_policy ON public.analysis_attempts;")
    op.execute("DROP POLICY IF EXISTS analysis_jobs_claim_owner_update_policy ON public.analysis_jobs;")
    op.execute("DROP POLICY IF EXISTS analysis_jobs_claim_owner_select_policy ON public.analysis_jobs;")

    op.execute("DROP INDEX IF EXISTS public.idx_analysis_jobs_stale;")
    op.execute("DROP INDEX IF EXISTS public.idx_analysis_jobs_fresh;")

    op.execute("ALTER TABLE public.analysis_jobs DROP CONSTRAINT IF EXISTS chk_analysis_jobs_recovery_count;")
    op.execute("ALTER TABLE public.analysis_jobs DROP COLUMN IF EXISTS recovery_count;")
    op.execute("ALTER TABLE public.analysis_jobs DROP COLUMN IF EXISTS claim_token;")

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_analysis_claim_owner') THEN
                EXECUTE format('GRANT db_analysis_claim_owner TO %I', CURRENT_USER);
                DROP OWNED BY db_analysis_claim_owner CASCADE;
                EXECUTE format('REVOKE db_analysis_claim_owner FROM %I', CURRENT_USER);
                BEGIN
                    DROP ROLE db_analysis_claim_owner;
                EXCEPTION WHEN dependent_objects_still_exist THEN
                    NULL;
                END;
            END IF;
        END $$;
    """)
