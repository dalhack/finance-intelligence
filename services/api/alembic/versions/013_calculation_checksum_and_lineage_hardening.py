"""013_calculation_checksum_and_lineage_hardening

Revision ID: 013_calc_checksum_lineage
Revises: 012_calc_correctness
Create Date: 2026-07-30 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013_calc_checksum_lineage"
down_revision: str | None = "012_calc_correctness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Static spec & implementation checksums for backfill (no dynamic python import)
STATIC_FORMULA_CHECKSUMS = {
    "GROWTH_RATE": (
        "de97877f03b71e9430f778611b7cfa380c1064a82a6abeb88d523b99be1efef9",
        "73aa27367c3565a3791edf6f5fae2525a245138c36da403012cada69d83c48da",
    ),
    "LOAN_TO_DEPOSIT_RATIO": (
        "c9a17861eb8160fb9c6bd619fbd3de5c0b8c2c179a2df0102e960767bc50d64f",
        "4f4230dd8c16ff8332e874320b8932647eadcd97778425436cbc8eaee66699ae",
    ),
    "NPL_RATIO": (
        "e04ff017948d5aad2d46491019a26cf47e08d9c5ee0023039b82c67d1f60d7cb",
        "ca34c38f6ae7ddda12772e256f866b2d710cb20c4077e969a45cc512a10818de",
    ),
    "RETURN_ON_ASSETS": (
        "eefcb3f1f091094e9228a378a70346462ce1e3d3b1aa0b8336423258031cf9f3",
        "97129f3bec3eaa3756f432694f1f92594dd5c4885986fcad735ed37e2fe63da3",
    ),
    "RETURN_ON_EQUITY": (
        "30aaed32e7a6cc7c5779245a3894fd6207b0eb7510a69e2cd8c94ce3114b00df",
        "affc3d81a45f766352d02c573a5c49e1b6988ad250ecc2c26e2ac05ba81c4b99",
    ),
}


def upgrade() -> None:
    # 1. Add period_presentation column to reporting_periods with CHECK constraint
    op.add_column(
        "reporting_periods",
        sa.Column("period_presentation", sa.String(length=50), nullable=False, server_default="UNKNOWN"),
    )

    op.create_check_constraint(
        "chk_period_presentation_valid",
        "reporting_periods",
        "period_presentation IN ('DISCRETE_PERIOD', 'YEAR_TO_DATE', 'TRAILING_TWELVE_MONTHS', 'FULL_YEAR', 'DATE_POINT', 'UNKNOWN')",
    )

    # 2. Backfill period_presentation for reporting_periods with unambiguous semantics
    op.execute("UPDATE reporting_periods SET period_presentation = 'FULL_YEAR' WHERE period_type = 'YEAR';")
    op.execute("UPDATE reporting_periods SET period_presentation = 'DATE_POINT' WHERE period_type = 'DATE_POINT';")
    op.execute("UPDATE reporting_periods SET period_presentation = 'TRAILING_TWELVE_MONTHS' WHERE period_type = 'TTM';")

    # 3. Deterministik Checksum Backfill for formula_definitions
    for code, (spec_cs, impl_cs) in STATIC_FORMULA_CHECKSUMS.items():
        op.execute(
            f"UPDATE formula_definitions SET formula_spec_checksum = '{spec_cs}', implementation_checksum = '{impl_cs}' WHERE formula_code = '{code}';"
        )

    # Fail-closed check: verify no formula_definitions exist with null formula_spec_checksum
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM formula_definitions WHERE formula_spec_checksum IS NULL) THEN
            RAISE EXCEPTION 'MIGRATION_FAIL_CLOSED: Unhandled formula_definition without spec checksum found.';
        END IF;
    END $$;
    """)

    # Make formula_spec_checksum NOT NULL and add 64-char lowercase hex CHECK constraints
    op.alter_column("formula_definitions", "formula_spec_checksum", existing_type=sa.String(length=64), nullable=False)

    op.create_check_constraint(
        "chk_formula_spec_checksum_hex",
        "formula_definitions",
        "formula_spec_checksum ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "chk_implementation_checksum_hex",
        "formula_definitions",
        "implementation_checksum ~ '^[0-9a-f]{64}$'",
    )

    # Revoke UPDATE on checksum columns from db_api_user
    op.execute(
        "REVOKE UPDATE (formula_spec_checksum, implementation_checksum) ON formula_definitions FROM db_api_user;"
    )

    # 4. Cleanly drop legacy unconditional triggers from Migration 012
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_calc_inputs_mutation ON calculation_inputs;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_calc_evidences_mutation ON calculation_evidences;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_calc_reconciliations_mutation ON calculation_reconciliations;")

    # 5. Create terminal status-aware immutability functions and triggers
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_terminal_calculation_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        IF (TG_OP = 'DELETE' AND OLD.status IN ('COMPLETED', 'FAILED')) THEN
            RAISE EXCEPTION 'IMMUTABLE_RECORD: Cannot delete a terminal calculation (status = %).', OLD.status;
        ELSIF (TG_OP = 'UPDATE' AND OLD.status IN ('COMPLETED', 'FAILED')) THEN
            RAISE EXCEPTION 'IMMUTABLE_RECORD: Cannot update a terminal calculation (status = %).', OLD.status;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_terminal_calculation_mutation
    BEFORE UPDATE OR DELETE ON calculations
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_terminal_calculation_mutation();
    """)

    # Function preventing lineage mutation if parent calculation is terminal
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_terminal_child_lineage_mutation()
    RETURNS TRIGGER AS $$
    DECLARE
        parent_status VARCHAR(50);
    BEGIN
        SELECT status INTO parent_status FROM public.calculations WHERE id = OLD.calculation_id AND organization_id = OLD.organization_id;
        IF parent_status IN ('COMPLETED', 'FAILED') THEN
            RAISE EXCEPTION 'IMMUTABLE_LINEAGE: Cannot update or delete lineage row because parent calculation % is terminal (status = %).', OLD.calculation_id, parent_status;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_calc_inputs_mutation
    BEFORE UPDATE OR DELETE ON calculation_inputs
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_terminal_child_lineage_mutation();
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_calc_evidences_mutation
    BEFORE UPDATE OR DELETE ON calculation_evidences
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_terminal_child_lineage_mutation();
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_calc_reconciliations_mutation
    BEFORE UPDATE OR DELETE ON calculation_reconciliations
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_terminal_child_lineage_mutation();
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 013 is prohibited to protect calculation lineage and financial audit history."
    )
