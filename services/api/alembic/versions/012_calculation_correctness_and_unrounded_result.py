"""012_calculation_correctness_and_unrounded_result

Revision ID: 012_calc_correctness
Revises: 011_calculation_engine
Create Date: 2026-07-30 15:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_calc_correctness"
down_revision: str | None = "011_calculation_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update formula_definitions table with spec checksum, revision, and tolerance policy metadata
    op.add_column("formula_definitions", sa.Column("formula_spec_checksum", sa.String(length=64), nullable=True))
    op.add_column(
        "formula_definitions",
        sa.Column("implementation_revision", sa.String(length=50), nullable=False, server_default="1.0.0"),
    )
    op.add_column(
        "formula_definitions",
        sa.Column("tolerance_policy_version", sa.String(length=50), nullable=False, server_default="1.0.0"),
    )
    op.add_column(
        "formula_definitions",
        sa.Column("tolerance_kind", sa.String(length=50), nullable=False, server_default="ABSOLUTE"),
    )
    op.add_column(
        "formula_definitions",
        sa.Column("tolerance_value", sa.Numeric(precision=28, scale=6), nullable=False, server_default="0.05"),
    )
    op.add_column(
        "formula_definitions",
        sa.Column("tolerance_unit", sa.String(length=50), nullable=False, server_default="PERCENTAGE_POINTS"),
    )

    # 2. Update calculations table with unrounded vs display result, annualization, and retry lineage
    op.add_column(
        "calculations", sa.Column("result_value_unrounded", sa.Numeric(precision=38, scale=10), nullable=True)
    )
    op.add_column("calculations", sa.Column("result_value_display", sa.Numeric(precision=28, scale=6), nullable=True))
    op.add_column(
        "calculations", sa.Column("rounding_mode", sa.String(length=50), nullable=False, server_default="ROUND_HALF_UP")
    )
    op.add_column(
        "calculations", sa.Column("display_scale", sa.String(length=50), nullable=False, server_default="ONE")
    )
    op.add_column("calculations", sa.Column("calculation_precision", sa.Integer(), nullable=False, server_default="38"))
    op.add_column(
        "calculations",
        sa.Column("calculation_rounding_policy_version", sa.String(length=50), nullable=False, server_default="1.0.0"),
    )
    op.add_column("calculations", sa.Column("formula_spec_checksum", sa.String(length=64), nullable=True))
    op.add_column("calculations", sa.Column("annualization_factor", sa.Numeric(precision=28, scale=6), nullable=True))
    op.add_column("calculations", sa.Column("annualization_policy_version", sa.String(length=50), nullable=True))
    op.add_column(
        "calculations",
        sa.Column(
            "parent_calculation_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("calculations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("calculations", sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"))

    # Make result_currency nullable for percentage metrics
    op.alter_column("calculations", "result_currency", existing_type=sa.String(length=10), nullable=True)

    # 3. Update calculation_inputs table
    op.add_column(
        "calculation_inputs", sa.Column("annualization_factor", sa.Numeric(precision=28, scale=6), nullable=True)
    )
    op.add_column(
        "calculation_inputs",
        sa.Column("snapshot_schema_version", sa.String(length=50), nullable=False, server_default="1.0.0"),
    )

    # 4. Update calculation_reconciliations table
    op.add_column(
        "calculation_reconciliations",
        sa.Column("derived_unrounded_value", sa.Numeric(precision=38, scale=10), nullable=True),
    )
    op.add_column(
        "calculation_reconciliations", sa.Column("applied_tolerance_kind", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "calculation_reconciliations",
        sa.Column("applied_tolerance_value", sa.Numeric(precision=28, scale=6), nullable=True),
    )
    op.add_column(
        "calculation_reconciliations", sa.Column("applied_tolerance_unit", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "calculation_reconciliations", sa.Column("tolerance_policy_version", sa.String(length=50), nullable=True)
    )

    # 5. Create immutability triggers on calculation_inputs, calculation_evidences, calculation_reconciliations
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_calculation_inputs_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'IMMUTABLE_RECORD: calculation_inputs records cannot be updated or deleted.';
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_calc_inputs_mutation
    BEFORE UPDATE OR DELETE ON calculation_inputs
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_calculation_inputs_mutation();
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_calculation_evidences_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'IMMUTABLE_RECORD: calculation_evidences records cannot be updated or deleted.';
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_calc_evidences_mutation
    BEFORE UPDATE OR DELETE ON calculation_evidences
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_calculation_evidences_mutation();
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_calculation_reconciliations_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'IMMUTABLE_RECORD: calculation_reconciliations records cannot be updated or deleted.';
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_calc_reconciliations_mutation
    BEFORE UPDATE OR DELETE ON calculation_reconciliations
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_calculation_reconciliations_mutation();
    """)

    # 6. Explicit grants and worker denials on calculation tables
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON formula_definitions, calculations, calculation_inputs, calculation_evidences, calculation_reconciliations TO db_api_user;"
    )
    op.execute(
        "REVOKE ALL PRIVILEGES ON formula_definitions, calculations, calculation_inputs, calculation_evidences, calculation_reconciliations FROM db_ingestion_worker;"
    )
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM db_api_user;")
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON document_chunks, extraction_results, ingestion_command_logs FROM db_api_user;"
    )
    op.execute("GRANT SELECT ON extraction_results TO db_api_user;")


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 012 is prohibited to protect calculation lineage and financial audit history."
    )
