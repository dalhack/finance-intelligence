"""009_command_envelope_and_fact_integrity

Revision ID: 009_facts_integrity
Revises: 008_facts_and_envelope
Create Date: 2026-07-30 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_facts_integrity"
down_revision: str | None = "008_facts_and_envelope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop old claim function overloads in public schema
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text);")
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text, uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text, uuid, uuid);")

    # 2. Create new narrow claim_ingestion_job function (job-ID targeted, no queue enumeration, no client org parameter)
    op.execute("""
    CREATE OR REPLACE FUNCTION public.claim_ingestion_job(
        p_job_id uuid,
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
        v_org_id uuid;
        v_doc_ver_id uuid;
    BEGIN
        IF p_job_id IS NULL THEN
            RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Missing job ID';
        END IF;
        IF p_worker_id IS NULL OR trim(p_worker_id) = '' OR length(p_worker_id) > 255 THEN
            RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Invalid or missing worker ID';
        END IF;
        IF p_claim_token IS NULL THEN
            RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Missing claim token';
        END IF;

        -- Lock targeted job record
        SELECT ij.organization_id, ij.document_version_id
        INTO v_org_id, v_doc_ver_id
        FROM public.ingestion_jobs ij
        WHERE ij.id = p_job_id
          AND (
            ij.status = 'QUEUED'
            OR (ij.status = 'PARSING' AND ij.locked_at < now() - INTERVAL '15 minutes' AND ij.current_attempt < ij.max_attempts)
          )
        FOR UPDATE SKIP LOCKED;

        IF v_org_id IS NOT NULL THEN
            UPDATE public.ingestion_jobs
            SET status = 'PARSING',
                locked_by = p_worker_id,
                claim_token = p_claim_token,
                locked_at = now()
            WHERE public.ingestion_jobs.id = p_job_id;

            RETURN QUERY SELECT p_job_id, v_org_id, v_doc_ver_id, p_claim_token;
        END IF;
    END;
    $$;
    """)

    op.execute("ALTER FUNCTION public.claim_ingestion_job(uuid, text, uuid) OWNER TO db_owner;")
    op.execute("REVOKE ALL ON FUNCTION public.claim_ingestion_job(uuid, text, uuid) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION public.claim_ingestion_job(uuid, text, uuid) TO db_ingestion_worker;")
    op.execute("GRANT EXECUTE ON FUNCTION public.claim_ingestion_job(uuid, text, uuid) TO db_owner;")

    # 3. Create persistent Command Replay Log table
    op.create_table(
        "ingestion_command_logs",
        sa.Column("command_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("command_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ingestion_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("command_id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_command_log_idempotency"),
    )

    op.execute("ALTER TABLE public.ingestion_command_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.ingestion_command_logs FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY worker_control_plane_command_logs ON public.ingestion_command_logs
        AS PERMISSIVE
        FOR ALL
        TO db_ingestion_worker, db_owner
        USING (true)
        WITH CHECK (true);

    CREATE POLICY tenant_isolation_command_logs ON public.ingestion_command_logs
        AS RESTRICTIVE
        FOR ALL
        TO db_app_user, db_api_user
        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
    """)

    op.execute("REVOKE ALL ON TABLE public.ingestion_command_logs FROM PUBLIC;")
    op.execute("GRANT SELECT, INSERT ON TABLE public.ingestion_command_logs TO db_ingestion_worker;")
    op.execute("GRANT SELECT, INSERT, DELETE ON TABLE public.ingestion_command_logs TO db_owner;")

    # 4. Add idempotency_hash and value_origin to financial_fact_candidates
    op.add_column("financial_fact_candidates", sa.Column("idempotency_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "financial_fact_candidates",
        sa.Column("value_origin", sa.String(length=32), server_default="SOURCE_REPORTED", nullable=False),
    )
    op.create_unique_constraint(
        "uq_fact_candidate_idempotency", "financial_fact_candidates", ["organization_id", "idempotency_hash"]
    )

    # 5. Add value_origin to financial_facts
    op.add_column(
        "financial_facts",
        sa.Column("value_origin", sa.String(length=32), server_default="SOURCE_REPORTED", nullable=False),
    )

    # 6. Add Database-level Immutability Trigger on financial_facts
    op.execute("""
    CREATE OR REPLACE FUNCTION public.prevent_financial_fact_mutation()
    RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public, pg_catalog, pg_temp
    AS $$
    BEGIN
        IF (OLD.institution_id IS DISTINCT FROM NEW.institution_id OR
            OLD.reporting_period_id IS DISTINCT FROM NEW.reporting_period_id OR
            OLD.metric_definition_id IS DISTINCT FROM NEW.metric_definition_id OR
            OLD.metric_code IS DISTINCT FROM NEW.metric_code OR
            OLD.value IS DISTINCT FROM NEW.value OR
            OLD.normalized_value IS DISTINCT FROM NEW.normalized_value OR
            OLD.currency IS DISTINCT FROM NEW.currency OR
            OLD.unit IS DISTINCT FROM NEW.unit OR
            OLD.scale IS DISTINCT FROM NEW.scale OR
            OLD.reporting_basis IS DISTINCT FROM NEW.reporting_basis OR
            OLD.source_candidate_id IS DISTINCT FROM NEW.source_candidate_id OR
            OLD.source_document_id IS DISTINCT FROM NEW.source_document_id OR
            OLD.value_origin IS DISTINCT FROM NEW.value_origin OR
            OLD.created_at IS DISTINCT FROM NEW.created_at OR
            OLD.organization_id IS DISTINCT FROM NEW.organization_id) THEN
            RAISE EXCEPTION 'CRITICAL_IMMUTABILITY_VIOLATION: Verified FinancialFact core fields are immutable';
        END IF;
        RETURN NEW;
    END;
    $$;

    ALTER FUNCTION public.prevent_financial_fact_mutation() OWNER TO db_owner;

    CREATE TRIGGER trg_prevent_fact_mutation
    BEFORE UPDATE ON public.financial_facts
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_financial_fact_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_fact_mutation ON public.financial_facts;")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_financial_fact_mutation();")

    op.drop_column("financial_facts", "value_origin")
    op.drop_constraint("uq_fact_candidate_idempotency", "financial_fact_candidates", type_="unique")
    op.drop_column("financial_fact_candidates", "value_origin")
    op.drop_column("financial_fact_candidates", "idempotency_hash")

    op.drop_table("ingestion_command_logs")

    op.execute("DROP FUNCTION IF EXISTS public.claim_ingestion_job(uuid, text, uuid);")
