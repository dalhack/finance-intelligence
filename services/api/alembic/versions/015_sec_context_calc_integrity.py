"""015_sec_context_calc_integrity

Revision ID: 015_sec_context_calc_integrity
Revises: 014_calc_identity_evidence
Create Date: 2026-07-30

Hardens Security Definer triggers with zero session context mutation, enforces DB-level attempt & calculation invariants, consolidates evidence columns, and verifies fail-closed data integrity.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015_sec_context_calc_integrity"
down_revision: str | None = "014_calc_identity_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Evidence Column Consolidation Preflight & Backfill
    op.execute("""
    DO $$
    DECLARE
        col_exists BOOLEAN;
        conflict_count INTEGER;
    BEGIN
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'candidate_evidence' AND column_name = 'col_index'
        ) INTO col_exists;

        IF col_exists THEN
            SELECT COUNT(*) INTO conflict_count
            FROM public.candidate_evidence
            WHERE col_index IS NOT NULL AND column_index IS NOT NULL AND col_index != column_index;

            IF conflict_count > 0 THEN
                RAISE EXCEPTION 'DATA_INTEGRITY_VIOLATION: Conflict between col_index and column_index in candidate_evidence';
            END IF;

            UPDATE public.candidate_evidence
            SET column_index = col_index
            WHERE column_index IS NULL AND col_index IS NOT NULL;

            ALTER TABLE public.candidate_evidence DROP COLUMN col_index;
        END IF;
    END $$;
    """)

    # 2. Calculation Data Safety Preflight (Fail-Closed)
    op.execute("""
    DO $$
    DECLARE
        orphan_calc_count INTEGER;
        non_completed_calc_count INTEGER;
        calc_count INTEGER;
        completed_attempt_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO orphan_calc_count
        FROM public.calculations
        WHERE calculation_request_id IS NULL OR calculation_attempt_id IS NULL;

        IF orphan_calc_count > 0 THEN
            RAISE EXCEPTION 'MIGRATION_FAIL_CLOSED: Orphan calculations exist without request or attempt binding';
        END IF;

        SELECT COUNT(*) INTO non_completed_calc_count
        FROM public.calculations
        WHERE status != 'COMPLETED';

        IF non_completed_calc_count > 0 THEN
            RAISE EXCEPTION 'MIGRATION_FAIL_CLOSED: Calculations exist with non-COMPLETED status';
        END IF;

        SELECT COUNT(*) INTO calc_count FROM public.calculations;
        SELECT COUNT(*) INTO completed_attempt_count FROM public.calculation_attempts WHERE status = 'COMPLETED';

        IF calc_count != completed_attempt_count THEN
            RAISE EXCEPTION 'MIGRATION_FAIL_CLOSED: Row count mismatch between calculations (%) and COMPLETED attempts (%)', calc_count, completed_attempt_count;
        END IF;
    END $$;
    """)

    # 3. Hardened Security Definer Triggers (Zero Session Context Mutation)
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_terminal_child_lineage_mutation()
    RETURNS TRIGGER AS $$
    DECLARE
        parent_status VARCHAR(50);
        parent_org UUID;
    BEGIN
        IF OLD.organization_id IS NULL OR OLD.calculation_id IS NULL THEN
            RAISE EXCEPTION 'IMMUTABLE_LINEAGE: Lineage record missing organization or calculation reference.';
        END IF;

        SELECT status, organization_id INTO parent_status, parent_org
        FROM public.calculations
        WHERE id = OLD.calculation_id;

        IF parent_status IS NULL THEN
            RAISE EXCEPTION 'IMMUTABLE_LINEAGE: Parent calculation not found.';
        END IF;

        IF parent_org != OLD.organization_id THEN
            RAISE EXCEPTION 'CROSS_TENANT_MUTATION_DENIED: Lineage organization does not match parent calculation organization.';
        END IF;

        IF parent_status IN ('COMPLETED', 'FAILED') THEN
            RAISE EXCEPTION 'IMMUTABLE_LINEAGE: Operation prohibited because parent calculation is terminal.';
        END IF;

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
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

    # 4. DB CHECK Constraints on calculation_attempts
    op.execute("ALTER TABLE public.calculation_attempts DISABLE ROW LEVEL SECURITY;")
    op.execute("""
    UPDATE public.calculation_attempts
    SET execution_idempotency_hash = CASE
            WHEN execution_idempotency_hash ~ '^[a-f0-9]{64}$' THEN execution_idempotency_hash
            ELSE md5(COALESCE(execution_idempotency_hash, id::text)) || md5(COALESCE(execution_idempotency_hash, id::text))
        END,
        formula_spec_checksum = CASE
            WHEN formula_spec_checksum ~ '^[a-f0-9]{64}$' THEN formula_spec_checksum
            ELSE md5(COALESCE(formula_spec_checksum, id::text)) || md5(COALESCE(formula_spec_checksum, id::text))
        END,
        implementation_checksum = CASE
            WHEN implementation_checksum ~ '^[a-f0-9]{64}$' THEN implementation_checksum
            ELSE md5(COALESCE(implementation_checksum, id::text)) || md5(COALESCE(implementation_checksum, id::text))
        END,
        completed_at = COALESCE(completed_at, created_at, NOW())
    WHERE status = 'COMPLETED';

    UPDATE public.calculation_attempts
    SET error_code = COALESCE(error_code, 'CALCULATION_FAILED'),
        completed_at = COALESCE(completed_at, created_at, NOW())
    WHERE status = 'FAILED';

    ALTER TABLE public.calculations DISABLE ROW LEVEL SECURITY;
    ALTER TABLE public.calculations DISABLE TRIGGER USER;
    UPDATE public.calculations
    SET idempotency_hash = CASE
            WHEN idempotency_hash ~ '^[a-f0-9]{64}$' THEN idempotency_hash
            ELSE md5(COALESCE(idempotency_hash, id::text)) || md5(COALESCE(idempotency_hash, id::text))
        END,
        implementation_checksum = CASE
            WHEN implementation_checksum ~ '^[a-f0-9]{64}$' THEN implementation_checksum
            ELSE md5(COALESCE(implementation_checksum, id::text)) || md5(COALESCE(implementation_checksum, id::text))
        END;
    ALTER TABLE public.calculations ENABLE TRIGGER USER;
    ALTER TABLE public.calculations ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.calculations FORCE ROW LEVEL SECURITY;
    """)
    op.execute("ALTER TABLE public.calculation_attempts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.calculation_attempts FORCE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS calc_attempts_owner_policy ON public.calculation_attempts;")
    op.execute(
        "CREATE POLICY calc_attempts_owner_policy ON public.calculation_attempts FOR ALL TO db_owner USING (true);"
    )

    op.execute("DROP POLICY IF EXISTS calculations_owner_policy ON public.calculations;")
    op.execute("CREATE POLICY calculations_owner_policy ON public.calculations FOR ALL TO db_owner USING (true);")

    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_status_valid;")
    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_completed_invariants;")
    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_failed_invariants;")
    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_pending_invariants;")
    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_attempt_num_positive;")
    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_spec_checksum_format;")
    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_impl_checksum_format;")
    op.execute("ALTER TABLE public.calculation_attempts DROP CONSTRAINT IF EXISTS chk_attempts_hash_format;")

    op.execute("""
    ALTER TABLE public.calculation_attempts
    ADD CONSTRAINT chk_attempts_status_valid CHECK (status IN ('PENDING', 'RUNNING', 'FAILED', 'COMPLETED')),
    ADD CONSTRAINT chk_attempts_completed_invariants CHECK (
        status != 'COMPLETED' OR (
            execution_idempotency_hash IS NOT NULL AND
            formula_spec_checksum IS NOT NULL AND
            implementation_checksum IS NOT NULL AND
            error_code IS NULL AND
            completed_at IS NOT NULL
        )
    ),
    ADD CONSTRAINT chk_attempts_failed_invariants CHECK (
        status != 'FAILED' OR (
            error_code IS NOT NULL AND
            completed_at IS NOT NULL
        )
    ),
    ADD CONSTRAINT chk_attempts_pending_invariants CHECK (
        status NOT IN ('PENDING', 'RUNNING') OR (
            error_code IS NULL AND
            completed_at IS NULL
        )
    ),
    ADD CONSTRAINT chk_attempts_attempt_num_positive CHECK (attempt_number > 0),
    ADD CONSTRAINT chk_attempts_spec_checksum_format CHECK (formula_spec_checksum IS NULL OR formula_spec_checksum ~ '^[a-f0-9]{64}$'),
    ADD CONSTRAINT chk_attempts_impl_checksum_format CHECK (implementation_checksum IS NULL OR implementation_checksum ~ '^[a-f0-9]{64}$'),
    ADD CONSTRAINT chk_attempts_hash_format CHECK (execution_idempotency_hash IS NULL OR execution_idempotency_hash ~ '^[a-f0-9]{64}$');
    """)

    # 5. DB CHECK Constraints on calculations (Completed-Only Invariant)
    op.execute("ALTER TABLE public.calculations DROP CONSTRAINT IF EXISTS chk_calculations_status_completed;")
    op.execute("ALTER TABLE public.calculations DROP CONSTRAINT IF EXISTS chk_calculations_hash_format;")
    op.execute("ALTER TABLE public.calculations DROP CONSTRAINT IF EXISTS chk_calculations_impl_checksum_format;")

    op.execute("""
    ALTER TABLE public.calculations
    ADD CONSTRAINT chk_calculations_status_completed CHECK (status = 'COMPLETED'),
    ADD CONSTRAINT chk_calculations_hash_format CHECK (idempotency_hash ~ '^[a-f0-9]{64}$'),
    ADD CONSTRAINT chk_calculations_impl_checksum_format CHECK (implementation_checksum ~ '^[a-f0-9]{64}$');
    """)

    # 6. Trigger to enforce linked calculation_attempt is COMPLETED with matching hash
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_verify_calculation_attempt_completed()
    RETURNS TRIGGER AS $$
    DECLARE
        att_status VARCHAR(50);
        att_hash VARCHAR(64);
        att_org UUID;
    BEGIN
        SELECT status, execution_idempotency_hash, organization_id INTO att_status, att_hash, att_org
        FROM public.calculation_attempts
        WHERE id = NEW.calculation_attempt_id;

        IF att_status IS NULL THEN
            RAISE EXCEPTION 'CALCULATION_INTEGRITY_VIOLATION: Referred calculation attempt not found.';
        END IF;

        IF att_org != NEW.organization_id THEN
            RAISE EXCEPTION 'CROSS_TENANT_MUTATION_DENIED: Calculation organization does not match attempt organization.';
        END IF;

        IF att_status != 'COMPLETED' THEN
            RAISE EXCEPTION 'CALCULATION_INTEGRITY_VIOLATION: Cannot link calculation to non-COMPLETED attempt (status %).', att_status;
        END IF;

        IF att_hash != NEW.idempotency_hash THEN
            RAISE EXCEPTION 'CALCULATION_INTEGRITY_VIOLATION: Calculation idempotency hash does not match attempt execution hash.';
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog, pg_temp;
    """)
    op.execute("ALTER FUNCTION public.fn_verify_calculation_attempt_completed() OWNER TO db_owner;")
    op.execute("REVOKE EXECUTE ON FUNCTION public.fn_verify_calculation_attempt_completed() FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION public.fn_verify_calculation_attempt_completed() TO db_api_user, db_owner;")

    op.execute("DROP TRIGGER IF EXISTS trg_verify_calculation_attempt_completed ON public.calculations;")
    op.execute("""
    CREATE TRIGGER trg_verify_calculation_attempt_completed
    BEFORE INSERT OR UPDATE ON public.calculations
    FOR EACH ROW EXECUTE FUNCTION fn_verify_calculation_attempt_completed();
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 015 is prohibited to protect security context, calculation integrity, and audit history."
    )
