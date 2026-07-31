"""014_calculation_identity_and_evidence_integrity

Revision ID: 014_calculation_identity_evidence
Revises: 013_calc_checksum_lineage
Create Date: 2026-07-30 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014_calc_identity_evidence"
down_revision: str | None = "013_calc_checksum_lineage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create calculation_requests table (tenant-owned)
    op.create_table(
        "calculation_requests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("formula_code", sa.String(length=100), nullable=False),
        sa.Column("formula_version", sa.String(length=50), nullable=False, server_default="1.0.0"),
        sa.Column("institution_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("comparison_period_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("comparison_policy", sa.String(length=50), nullable=False, server_default="PREVIOUS_PERIOD"),
        sa.Column("requested_by_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_calc_requests_org_id", "calculation_requests", ["organization_id", "id"])
    op.create_unique_constraint(
        "uq_calc_requests_org_fingerprint", "calculation_requests", ["organization_id", "request_fingerprint"]
    )
    op.create_foreign_key(
        "fk_calc_requests_organization",
        "calculation_requests",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2. Create calculation_attempts table (tenant-owned)
    op.create_table(
        "calculation_attempts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_request_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("execution_idempotency_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("retry_classification", sa.String(length=50), nullable=False, server_default="NON_RETRIABLE"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("formula_spec_checksum", sa.String(length=64), nullable=True),
        sa.Column("implementation_checksum", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_calc_attempts_org_id", "calculation_attempts", ["organization_id", "id"])
    op.create_unique_constraint(
        "uq_calc_attempts_org_req_num",
        "calculation_attempts",
        ["organization_id", "calculation_request_id", "attempt_number"],
    )
    op.create_foreign_key(
        "fk_calc_attempts_organization",
        "calculation_attempts",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_calc_attempts_request",
        "calculation_attempts",
        "calculation_requests",
        ["organization_id", "calculation_request_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "chk_attempts_status_valid",
        "calculation_attempts",
        "status IN ('PENDING', 'FAILED', 'COMPLETED')",
    )

    # 3. Add lineage columns to candidate_evidence & calculation_evidences
    op.add_column("candidate_evidence", sa.Column("sheet_name", sa.String(length=100), nullable=True))
    op.add_column("candidate_evidence", sa.Column("cell_coordinate", sa.String(length=20), nullable=True))
    op.add_column("candidate_evidence", sa.Column("header_name", sa.String(length=100), nullable=True))
    op.add_column("candidate_evidence", sa.Column("column_index", sa.Integer(), nullable=True))

    op.add_column("calculation_evidences", sa.Column("sheet_name", sa.String(length=100), nullable=True))
    op.add_column("calculation_evidences", sa.Column("cell_coordinate", sa.String(length=20), nullable=True))
    op.add_column("calculation_evidences", sa.Column("header_name", sa.String(length=100), nullable=True))
    op.add_column("calculation_evidences", sa.Column("column_index", sa.Integer(), nullable=True))

    # 4. Add reconciliation columns to calculation_reconciliations
    op.add_column(
        "calculation_reconciliations",
        sa.Column("absolute_difference", sa.Numeric(precision=38, scale=10), nullable=False, server_default="0"),
    )
    op.add_column(
        "calculation_reconciliations",
        sa.Column("relative_difference", sa.Numeric(precision=28, scale=10), nullable=True),
    )

    op.execute("""
    UPDATE calculation_reconciliations
    SET absolute_difference = COALESCE(difference, ABS(COALESCE(derived_unrounded_value, system_derived_value, 0) - COALESCE(source_reported_value, 0)), 0),
        relative_difference = CASE
            WHEN source_reported_value IS NOT NULL AND source_reported_value != 0 THEN ABS((COALESCE(derived_unrounded_value, system_derived_value, 0) - source_reported_value) / source_reported_value)
            ELSE NULL
        END;
    """)

    # 5. Data Migration for existing calculations -> calculation_requests & calculation_attempts
    op.add_column("calculations", sa.Column("calculation_request_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("calculations", sa.Column("calculation_attempt_id", sa.UUID(as_uuid=True), nullable=True))

    # Temporarily drop immutability triggers and disable RLS on calculations for backfill
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_completed_calculation_mutation ON public.calculations;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_terminal_calculation_mutation ON public.calculations;")
    op.execute("ALTER TABLE public.calculations DISABLE ROW LEVEL SECURITY;")

    # Backfill calculations into calculation_requests and calculation_attempts
    op.execute("""
    DO $$
    DECLARE
        calc_row RECORD;
        req_id UUID;
        att_id UUID;
        req_fp VARCHAR(64);
        next_att_num INT;
    BEGIN
        FOR calc_row IN SELECT * FROM public.calculations LOOP
            req_fp := encode(sha256(concat(
                calc_row.organization_id::text,
                calc_row.formula_code,
                calc_row.formula_version,
                calc_row.institution_id::text,
                calc_row.reporting_period_id::text,
                COALESCE(calc_row.comparison_period_id::text, '')
            )::bytea), 'hex');

            SELECT id INTO req_id FROM public.calculation_requests
            WHERE organization_id = calc_row.organization_id AND request_fingerprint = req_fp;

            IF req_id IS NULL THEN
                req_id := gen_random_uuid();
                INSERT INTO public.calculation_requests (
                    id, organization_id, request_fingerprint, formula_code, formula_version,
                    institution_id, reporting_period_id, comparison_period_id, comparison_policy,
                    requested_by_user_id, created_at
                ) VALUES (
                    req_id, calc_row.organization_id, req_fp, calc_row.formula_code, calc_row.formula_version,
                    calc_row.institution_id, calc_row.reporting_period_id, calc_row.comparison_period_id, 'PREVIOUS_PERIOD',
                    calc_row.requested_by_user_id, calc_row.created_at
                );
            END IF;

            SELECT COALESCE(MAX(attempt_number), 0) + 1 INTO next_att_num
            FROM public.calculation_attempts
            WHERE organization_id = calc_row.organization_id AND calculation_request_id = req_id;

            att_id := gen_random_uuid();
            INSERT INTO public.calculation_attempts (
                id, organization_id, calculation_request_id, attempt_number, execution_idempotency_hash,
                status, retry_classification, error_code, formula_spec_checksum, implementation_checksum,
                started_at, completed_at, created_at
            ) VALUES (
                att_id, calc_row.organization_id, req_id, next_att_num,
                CASE WHEN calc_row.status = 'COMPLETED' THEN calc_row.idempotency_hash ELSE NULL END,
                COALESCE(calc_row.status, 'COMPLETED'), 'NON_RETRIABLE',
                CASE WHEN calc_row.status = 'COMPLETED' THEN NULL ELSE COALESCE(calc_row.error_code, 'CALCULATION_INTERNAL_ERROR') END,
                CASE WHEN calc_row.status = 'COMPLETED' THEN calc_row.formula_spec_checksum ELSE NULL END,
                CASE WHEN calc_row.status = 'COMPLETED' THEN calc_row.implementation_checksum ELSE NULL END,
                calc_row.created_at, calc_row.completed_at, calc_row.created_at
            );

            UPDATE public.calculations
            SET calculation_request_id = req_id, calculation_attempt_id = att_id
            WHERE id = calc_row.id;
        END LOOP;
        DELETE FROM public.calculations WHERE status != 'COMPLETED';
    END $$;
    """)

    op.execute(
        "DELETE FROM public.calculations WHERE calculation_request_id IS NULL OR calculation_attempt_id IS NULL;"
    )

    op.execute("ALTER TABLE public.calculations ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.calculations FORCE ROW LEVEL SECURITY;")

    # Enable RLS on calculation_requests and calculation_attempts
    op.execute("ALTER TABLE public.calculation_requests ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.calculation_requests FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY calc_requests_tenant_isolation ON public.calculation_requests
    FOR ALL TO public
    USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
    WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE public.calculation_attempts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.calculation_attempts FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY calc_attempts_tenant_isolation ON public.calculation_attempts
    FOR ALL TO public
    USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
    WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
    """)

    op.execute("GRANT SELECT, INSERT, UPDATE ON public.calculation_requests TO db_api_user;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.calculation_attempts TO db_api_user;")

    # Require calculation_request_id and calculation_attempt_id on calculations
    op.alter_column("calculations", "calculation_request_id", existing_type=sa.UUID(as_uuid=True), nullable=False)
    op.alter_column("calculations", "calculation_attempt_id", existing_type=sa.UUID(as_uuid=True), nullable=False)

    op.create_unique_constraint(
        "uq_calculations_attempt_id", "calculations", ["organization_id", "calculation_attempt_id"]
    )
    op.create_foreign_key(
        "fk_calculations_request",
        "calculations",
        "calculation_requests",
        ["organization_id", "calculation_request_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_calculations_attempt",
        "calculations",
        "calculation_attempts",
        ["organization_id", "calculation_attempt_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )

    # 6. Hardened Security Definer Functions with Fixed Search Path
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_terminal_calculation_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        IF (TG_OP = 'DELETE' AND OLD.status IN ('COMPLETED', 'FAILED')) THEN
            RAISE EXCEPTION 'IMMUTABLE_RECORD: Operation prohibited on terminal calculation.';
        ELSIF (TG_OP = 'UPDATE' AND OLD.status IN ('COMPLETED', 'FAILED')) THEN
            RAISE EXCEPTION 'IMMUTABLE_RECORD: Operation prohibited on terminal calculation.';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog, pg_temp;
    """)
    op.execute("ALTER FUNCTION public.fn_prevent_terminal_calculation_mutation() OWNER TO db_owner;")
    op.execute("REVOKE EXECUTE ON FUNCTION public.fn_prevent_terminal_calculation_mutation() FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION public.fn_prevent_terminal_calculation_mutation() TO db_api_user, db_owner;")
    op.execute("""
    CREATE TRIGGER trg_prevent_terminal_calculation_mutation
    BEFORE UPDATE OR DELETE ON public.calculations
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_terminal_calculation_mutation();
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_terminal_child_lineage_mutation()
    RETURNS TRIGGER AS $$
    DECLARE
        parent_status VARCHAR(50);
    BEGIN
        IF OLD.organization_id IS NOT NULL THEN
            PERFORM set_config('app.current_organization_id', OLD.organization_id::text, true);
        END IF;
        SELECT status INTO parent_status FROM public.calculations WHERE id = OLD.calculation_id AND organization_id = OLD.organization_id;
        IF parent_status IN ('COMPLETED', 'FAILED') THEN
            RAISE EXCEPTION 'IMMUTABLE_LINEAGE: Operation prohibited because parent calculation is terminal.';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog, pg_temp;
    """)
    op.execute("ALTER FUNCTION public.fn_prevent_terminal_child_lineage_mutation() OWNER TO db_owner;")
    op.execute("REVOKE EXECUTE ON FUNCTION public.fn_prevent_terminal_child_lineage_mutation() FROM PUBLIC;")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.fn_prevent_terminal_child_lineage_mutation() TO db_api_user, db_owner;"
    )
    op.execute("""
    CREATE TRIGGER trg_prevent_calculation_inputs_mutation
    BEFORE UPDATE OR DELETE ON public.calculation_inputs
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_terminal_child_lineage_mutation();
    """)
    op.execute("""
    CREATE TRIGGER trg_prevent_calculation_evidence_mutation
    BEFORE UPDATE OR DELETE ON public.calculation_evidences
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_terminal_child_lineage_mutation();
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 014 is prohibited to protect calculation identity lineage and financial audit history."
    )
