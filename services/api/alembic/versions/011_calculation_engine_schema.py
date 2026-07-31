"""011_calculation_engine_schema

Revision ID: 011_calculation_engine
Revises: 010_fact_revision_uniqueness
Create Date: 2026-07-30 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_calculation_engine"
down_revision: str | None = "010_fact_revision_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0. Create composite unique constraints on institutions & reporting_periods for composite FKs
    op.create_unique_constraint("uq_institutions_org_id", "institutions", ["organization_id", "id"])
    op.create_unique_constraint("uq_reporting_periods_org_id", "reporting_periods", ["organization_id", "id"])

    # 1. Create formula_definitions table (global canonical reference table)
    op.create_table(
        "formula_definitions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("formula_code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("formula_version", sa.String(length=50), nullable=False, server_default="1.0.0"),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("calculation_type", sa.String(length=50), nullable=False),
        sa.Column("required_input_roles", sa.JSON(), nullable=False),
        sa.Column("expected_metric_codes", sa.JSON(), nullable=False),
        sa.Column("result_unit", sa.String(length=50), nullable=False, server_default="PERCENT"),
        sa.Column("result_scale", sa.String(length=50), nullable=False, server_default="ONE"),
        sa.Column("rounding_policy", sa.String(length=50), nullable=False, server_default="ROUND_HALF_UP"),
        sa.Column("display_precision", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("effective_from", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("implementation_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_formula_code_version",
        "formula_definitions",
        ["formula_code", "formula_version"],
    )

    # 2. Create calculations table (tenant-owned)
    op.create_table(
        "calculations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("comparison_period_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("formula_code", sa.String(length=100), nullable=False),
        sa.Column("formula_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="COMPLETED"),
        sa.Column("result_value", sa.Numeric(precision=28, scale=6), nullable=True),
        sa.Column("result_unit", sa.String(length=50), nullable=False, server_default="PERCENT"),
        sa.Column("result_scale", sa.String(length=50), nullable=False, server_default="ONE"),
        sa.Column("result_currency", sa.String(length=10), nullable=True),
        sa.Column("value_representation", sa.String(length=50), nullable=False, server_default="PERCENT_DISPLAY"),
        sa.Column("working_precision", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("rounding_policy", sa.String(length=50), nullable=False, server_default="ROUND_HALF_UP"),
        sa.Column("idempotency_hash", sa.String(length=64), nullable=False),
        sa.Column("implementation_checksum", sa.String(length=64), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_calculations_org_id", "calculations", ["organization_id", "id"])
    op.create_foreign_key(
        "fk_calculations_organization",
        "calculations",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_calculations_institution",
        "calculations",
        "institutions",
        ["organization_id", "institution_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_calculations_reporting_period",
        "calculations",
        "reporting_periods",
        ["organization_id", "reporting_period_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )

    # Partial unique index enforcing calculation idempotency per tenant
    op.execute("""
    CREATE UNIQUE INDEX uq_calculations_active_idempotency ON public.calculations (
        organization_id,
        idempotency_hash
    ) WHERE status = 'COMPLETED';
    """)

    # 3. Create calculation_inputs table (tenant-owned)
    op.create_table(
        "calculation_inputs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_fact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("input_role", sa.String(length=100), nullable=False),
        sa.Column("metric_code", sa.String(length=100), nullable=False),
        sa.Column("normalized_value_snapshot", sa.Numeric(precision=28, scale=6), nullable=False),
        sa.Column("currency_snapshot", sa.String(length=10), nullable=False),
        sa.Column("unit_snapshot", sa.String(length=50), nullable=False),
        sa.Column("scale_snapshot", sa.String(length=50), nullable=False),
        sa.Column("reporting_basis_snapshot", sa.String(length=50), nullable=False),
        sa.Column("reporting_period_id_snapshot", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("fact_revision_metadata", sa.JSON(), nullable=False),
        sa.Column("evidence_reference", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_foreign_key(
        "fk_calc_inputs_calculation",
        "calculation_inputs",
        "calculations",
        ["organization_id", "calculation_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_calc_inputs_financial_fact",
        "calculation_inputs",
        "financial_facts",
        ["organization_id", "financial_fact_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )

    # 4. Create calculation_evidences table (tenant-owned)
    op.create_table(
        "calculation_evidences",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_input_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_fact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_evidence_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("source_document_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_version_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
        sa.Column("raw_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_foreign_key(
        "fk_calc_evidences_calculation",
        "calculation_evidences",
        "calculations",
        ["organization_id", "calculation_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )

    # 5. Create calculation_reconciliations table (tenant-owned)
    op.create_table(
        "calculation_reconciliations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reported_fact_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reported_value", sa.Numeric(precision=28, scale=6), nullable=True),
        sa.Column("system_derived_value", sa.Numeric(precision=28, scale=6), nullable=False),
        sa.Column("difference", sa.Numeric(precision=28, scale=6), nullable=True),
        sa.Column("tolerance", sa.Numeric(precision=28, scale=6), nullable=False, server_default="0.05"),
        sa.Column("reconciliation_status", sa.String(length=50), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_foreign_key(
        "fk_calc_reconciliations_calculation",
        "calculation_reconciliations",
        "calculations",
        ["organization_id", "calculation_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )

    # 6. Apply RLS to tenant-owned calculation tables
    tenant_tables = [
        "calculations",
        "calculation_inputs",
        "calculation_evidences",
        "calculation_reconciliations",
    ]

    for tbl in tenant_tables:
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;")

        # Fail-closed policy for db_api_user
        op.execute(f"""
        CREATE POLICY api_user_tenant_policy ON public.{tbl}
            FOR ALL TO db_api_user
            USING (organization_id = (SELECT NULLIF(current_setting('app.current_organization_id', true), '')::uuid))
            WITH CHECK (organization_id = (SELECT NULLIF(current_setting('app.current_organization_id', true), '')::uuid));
        """)

    # 7. Role Grants
    # db_api_user gets access to formula_definitions and tenant calculation tables
    op.execute("GRANT SELECT ON public.formula_definitions TO db_api_user;")
    for tbl in tenant_tables:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{tbl} TO db_api_user;")

    # ZERO calculation table access for db_ingestion_worker (Ingestion/Calculation isolation)

    # 8. Add Immutability Trigger on Completed Calculations
    op.execute("""
    CREATE OR REPLACE FUNCTION public.prevent_completed_calculation_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        IF OLD.status = 'COMPLETED' THEN
            RAISE EXCEPTION 'CRITICAL_CALCULATION_IMMUTABILITY_VIOLATION: Completed calculations are immutable and cannot be updated or deleted.'
                USING ERRCODE = '23505';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_completed_calculation_mutation
        BEFORE UPDATE OR DELETE ON public.calculations
        FOR EACH ROW
        EXECUTE FUNCTION public.prevent_completed_calculation_mutation();
    """)

    # 9. Seed Initial 5 Formula Definitions
    op.execute("""
    INSERT INTO public.formula_definitions (
        id, formula_code, formula_version, display_name, description, calculation_type,
        required_input_roles, expected_metric_codes, result_unit, result_scale,
        rounding_policy, display_precision, status, implementation_checksum
    ) VALUES
        (
            'b0000000-0000-0000-0000-000000000001',
            'GROWTH_RATE',
            '1.0.0',
            'Dönemsel Büyüme Oranı',
            'Mevcut dönem ile karşılaştırma dönemi arasındaki yüzdesel büyüme oranı',
            'GROWTH',
            '["CURRENT_VALUE", "COMPARISON_VALUE"]',
            '[]',
            'PERCENT',
            'ONE',
            'ROUND_HALF_UP',
            2,
            'ACTIVE',
            'e4a217fb9b6a18d193d5a2d10398fb91e01869e96e95aa025a1e2f7b8849b38b'
        ),
        (
            'b0000000-0000-0000-0000-000000000002',
            'LOAN_TO_DEPOSIT_RATIO',
            '1.0.0',
            'Kredi / Mevduat Oranı (KDR)',
            'Toplam Krediler / Toplam Mevduat * 100',
            'RATIO',
            '["NUMERATOR", "DENOMINATOR"]',
            '["TOTAL_LOANS", "TOTAL_DEPOSITS"]',
            'PERCENT',
            'ONE',
            'ROUND_HALF_UP',
            2,
            'ACTIVE',
            'f2d918a7c6b5e4d3a2109876543210fedcba9876543210fedcba9876543210fe'
        ),
        (
            'b0000000-0000-0000-0000-000000000003',
            'NPL_RATIO',
            '1.0.0',
            'Takipteki Kredi Oranı (NPL)',
            'Takipteki Krediler / Toplam Krediler * 100',
            'RATIO',
            '["NUMERATOR", "DENOMINATOR"]',
            '["NON_PERFORMING_LOANS", "TOTAL_LOANS"]',
            'PERCENT',
            'ONE',
            'ROUND_HALF_UP',
            2,
            'ACTIVE',
            'a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0'
        ),
        (
            'b0000000-0000-0000-0000-000000000004',
            'RETURN_ON_ASSETS',
            '1.0.0',
            'Aktif Kârlılığı (ROA)',
            'Net Dönem Kârı / Ortalama Toplam Aktifler * Yıllıklandırma Faktörü * 100',
            'PROFITABILITY',
            '["PERIOD_INCOME", "BEGINNING_BALANCE", "ENDING_BALANCE"]',
            '["NET_INCOME", "TOTAL_ASSETS"]',
            'PERCENT',
            'ONE',
            'ROUND_HALF_UP',
            2,
            'ACTIVE',
            'c8d7e6f5a4b3c2d1e0f9887766554433221100ffeeddccbbaa99887766554433'
        ),
        (
            'b0000000-0000-0000-0000-000000000005',
            'RETURN_ON_EQUITY',
            '1.0.0',
            'Özkaynak Kârlılığı (ROE)',
            'Net Dönem Kârı / Ortalama Toplam Özkaynaklar * Yıllıklandırma Faktörü * 100',
            'PROFITABILITY',
            '["PERIOD_INCOME", "BEGINNING_BALANCE", "ENDING_BALANCE"]',
            '["NET_INCOME", "TOTAL_EQUITY"]',
            'PERCENT',
            'ONE',
            'ROUND_HALF_UP',
            2,
            'ACTIVE',
            'd9e8f7a6b5c4d3e2f1a099887766554433221100ffeeddccbbaa998877665544'
        )
    ON CONFLICT (formula_code) DO NOTHING;
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrade of 011_calculation_engine is guarded to prevent data corruption "
        "and violation of calculation audit integrity."
    )
