"""016_traceability_integrity_repair

Revision ID: 016_traceability_integrity_repair
Revises: 015_sec_context_calc_integrity
Create Date: 2026-07-30

Repairs calculation traceability, revokes direct EXECUTE privileges on trigger functions from runtime roles, recovers formula spec and implementation checksums against versioned golden registry, and enforces strict fail-closed hash lineage validation without synthetic hash generation.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016_traceability_integrity_repair"
down_revision: str | None = "015_sec_context_calc_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0. Expand alembic_version version_num column to VARCHAR(64) to allow longer revision IDs
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")

    # 1. Dynamically Discover & Revoke Direct EXECUTE Grants on Integrity Trigger Functions from Runtime Roles
    op.execute("""
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN (
            SELECT proname
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public' AND proname IN (
                'fn_prevent_terminal_child_lineage_mutation',
                'fn_verify_calculation_attempt_completed',
                'fn_prevent_terminal_calculation_mutation'
            )
        ) LOOP
            EXECUTE format('REVOKE EXECUTE ON FUNCTION public.%I() FROM db_api_user, db_ingestion_worker, db_bootstrap, PUBLIC;', r.proname);
        END LOOP;
    END $$;
    """)

    # 2. Deterministic Recovery of Formula Checksums via Static Golden Registry
    # LOAN_TO_DEPOSIT_RATIO
    op.execute("""
    UPDATE public.calculation_attempts ca
    SET formula_spec_checksum = 'c9a17861eb8160fb9c6bd619fbd3de5c0b8c2c179a2df0102e960767bc50d64f',
        implementation_checksum = '4f4230dd8c16ff8332e874320b8932647eadcd97778425436cbc8eaee66699ae'
    FROM public.calculation_requests cr
    WHERE ca.calculation_request_id = cr.id
      AND cr.formula_code = 'LOAN_TO_DEPOSIT_RATIO'
      AND COALESCE(cr.formula_version, '1.0.0') = '1.0.0';

    UPDATE public.calculations
    SET formula_spec_checksum = 'c9a17861eb8160fb9c6bd619fbd3de5c0b8c2c179a2df0102e960767bc50d64f',
        implementation_checksum = '4f4230dd8c16ff8332e874320b8932647eadcd97778425436cbc8eaee66699ae'
    WHERE formula_code = 'LOAN_TO_DEPOSIT_RATIO'
      AND COALESCE(formula_version, '1.0.0') = '1.0.0';
    """)

    # NPL_RATIO
    op.execute("""
    UPDATE public.calculation_attempts ca
    SET formula_spec_checksum = 'f1d74d5d89779bfac2ac36064508fc156ec6cbad99231baa6cf991c14c4be4a7',
        implementation_checksum = 'ca34c38f6ae7ddda12772e256f866b2d710cb20c4077e969a45cc512a10818de'
    FROM public.calculation_requests cr
    WHERE ca.calculation_request_id = cr.id
      AND cr.formula_code = 'NPL_RATIO'
      AND COALESCE(cr.formula_version, '1.0.0') = '1.0.0';

    UPDATE public.calculations
    SET formula_spec_checksum = 'f1d74d5d89779bfac2ac36064508fc156ec6cbad99231baa6cf991c14c4be4a7',
        implementation_checksum = 'ca34c38f6ae7ddda12772e256f866b2d710cb20c4077e969a45cc512a10818de'
    WHERE formula_code = 'NPL_RATIO'
      AND COALESCE(formula_version, '1.0.0') = '1.0.0';
    """)

    # GROWTH_RATE
    op.execute("""
    UPDATE public.calculation_attempts ca
    SET formula_spec_checksum = 'de97877f03b71e9430f778611b7cfa380c1064a82a6abeb88d523b99be1efef9',
        implementation_checksum = '73aa27367c3565a3791edf6f5fae2525a245138c36da403012cada69d83c48da'
    FROM public.calculation_requests cr
    WHERE ca.calculation_request_id = cr.id
      AND cr.formula_code = 'GROWTH_RATE'
      AND COALESCE(cr.formula_version, '1.0.0') = '1.0.0';

    UPDATE public.calculations
    SET formula_spec_checksum = 'de97877f03b71e9430f778611b7cfa380c1064a82a6abeb88d523b99be1efef9',
        implementation_checksum = '73aa27367c3565a3791edf6f5fae2525a245138c36da403012cada69d83c48da'
    WHERE formula_code = 'GROWTH_RATE'
      AND COALESCE(formula_version, '1.0.0') = '1.0.0';
    """)

    # RETURN_ON_ASSETS
    op.execute("""
    UPDATE public.calculation_attempts ca
    SET formula_spec_checksum = 'eefcb3f1f091094e9228a378a70346462ce1e3d3b1aa0b8336423258031cf9f3',
        implementation_checksum = '97129f3bec3eaa3756f432694f1f92594dd5c4885986fcad735ed37e2fe63da3'
    FROM public.calculation_requests cr
    WHERE ca.calculation_request_id = cr.id
      AND cr.formula_code = 'RETURN_ON_ASSETS'
      AND COALESCE(cr.formula_version, '1.0.0') = '1.0.0';

    UPDATE public.calculations
    SET formula_spec_checksum = 'eefcb3f1f091094e9228a378a70346462ce1e3d3b1aa0b8336423258031cf9f3',
        implementation_checksum = '97129f3bec3eaa3756f432694f1f92594dd5c4885986fcad735ed37e2fe63da3'
    WHERE formula_code = 'RETURN_ON_ASSETS'
      AND COALESCE(formula_version, '1.0.0') = '1.0.0';
    """)

    # RETURN_ON_EQUITY
    op.execute("""
    UPDATE public.calculation_attempts ca
    SET formula_spec_checksum = '30aaed32e7a6cc7c5779245a3894fd6207b0eb7510a69e2cd8c94ce3114b00df',
        implementation_checksum = 'affc3d81a45f766352d02c573a5c49e1b6988ad250ecc2c26e2ac05ba81c4b99'
    FROM public.calculation_requests cr
    WHERE ca.calculation_request_id = cr.id
      AND cr.formula_code = 'RETURN_ON_EQUITY'
      AND COALESCE(cr.formula_version, '1.0.0') = '1.0.0';

    UPDATE public.calculations
    SET formula_spec_checksum = '30aaed32e7a6cc7c5779245a3894fd6207b0eb7510a69e2cd8c94ce3114b00df',
        implementation_checksum = 'affc3d81a45f766352d02c573a5c49e1b6988ad250ecc2c26e2ac05ba81c4b99'
    WHERE formula_code = 'RETURN_ON_EQUITY'
      AND COALESCE(formula_version, '1.0.0') = '1.0.0';
    """)

    # 3. Fail-Closed Audit (Zero Synthetic Hashes Allowed)
    op.execute("""
    DO $$
    DECLARE
        synth_attempt_count INTEGER;
        synth_calc_count INTEGER;
        unverifiable_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO synth_attempt_count
        FROM public.calculation_attempts
        WHERE status = 'COMPLETED' AND (
            (length(execution_idempotency_hash) = 64 AND substr(execution_idempotency_hash, 1, 32) = substr(execution_idempotency_hash, 33, 32)) OR
            (length(formula_spec_checksum) = 64 AND substr(formula_spec_checksum, 1, 32) = substr(formula_spec_checksum, 33, 32)) OR
            (length(implementation_checksum) = 64 AND substr(implementation_checksum, 1, 32) = substr(implementation_checksum, 33, 32))
        );

        SELECT COUNT(*) INTO synth_calc_count
        FROM public.calculations
        WHERE (length(idempotency_hash) = 64 AND substr(idempotency_hash, 1, 32) = substr(idempotency_hash, 33, 32)) OR
              (length(implementation_checksum) = 64 AND substr(implementation_checksum, 1, 32) = substr(implementation_checksum, 33, 32));

        unverifiable_count := synth_attempt_count + synth_calc_count;

        IF unverifiable_count > 0 THEN
            RAISE EXCEPTION 'MIGRATION_INVALID_CALCULATION_HASH_LINEAGE: Unverifiable synthetic hashes detected in attempts (%) or calculations (%)', synth_attempt_count, synth_calc_count;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 016 is prohibited to protect security context, calculation integrity, and audit history."
    )
