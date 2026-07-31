"""008_financial_facts_and_command_envelope

Revision ID: 008_facts_and_envelope
Revises: 007_drop_legacy_overload
Create Date: 2026-07-30

Provisions Phase 3A Financial Fact Engine schema:
- institutions, reporting_periods, metric_definitions, metric_aliases
- financial_fact_candidates, candidate_evidence, financial_facts, fact_review_decisions
- PostgreSQL RLS policies & role permissions for db_api_user and db_ingestion_worker
- Refactors claim_next_ingestion_job to 2-parameter signature (p_worker_id text, p_claim_token uuid), dropping legacy 3-parameter overload
- Seeds 11 MVP canonical metric definitions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008_facts_and_envelope"
down_revision = "007_drop_legacy_overload"
branch_labels = None
depends_on = None

NEW_TENANT_TABLES = [
    "institutions",
    "reporting_periods",
    "metric_aliases",
    "financial_fact_candidates",
    "candidate_evidence",
    "financial_facts",
    "fact_review_decisions",
]


def upgrade() -> None:
    # 1. Create Institutions table (Tenant-owned for MVP)
    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("institution_type", sa.String(length=50), nullable=False, server_default="BANK"),
        sa.Column("country_code", sa.String(length=2), nullable=False, server_default="TR"),
        sa.Column("regulatory_identifier", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("external_registry_type", sa.String(length=50), nullable=True),
        sa.Column("external_registry_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "canonical_name", name="uq_institution_org_canonical_name"),
    )

    # 2. Create Reporting Periods table (Tenant-owned)
    op.create_table(
        "reporting_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_type", sa.String(length=50), nullable=False),  # YEAR, QUARTER, MONTH, DATE_POINT, TTM
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("comparison_key", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("start_date <= end_date", name="ck_period_dates_valid"),
        sa.UniqueConstraint(
            "organization_id", "period_type", "fiscal_year", "comparison_key", name="uq_reporting_period_org_key"
        ),
    )

    # 3. Create Metric Definitions table (Global Catalog)
    op.create_table(
        "metric_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("metric_code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "value_type", sa.String(length=50), nullable=False, server_default="CURRENCY"
        ),  # CURRENCY, PERCENT, RATIO, COUNT
        sa.Column("default_currency_behavior", sa.String(length=50), nullable=False, server_default="SAME_AS_SOURCE"),
        sa.Column("default_unit", sa.String(length=50), nullable=False, server_default="TRY"),
        sa.Column("normal_balance", sa.String(length=50), nullable=False, server_default="NOT_APPLICABLE"),
        sa.Column("aggregation_behavior", sa.String(length=50), nullable=False, server_default="POINT_IN_TIME"),
        sa.Column("formula_type", sa.String(length=50), nullable=False, server_default="SOURCE_REPORTED"),
        sa.Column("formula_version", sa.String(length=50), nullable=False, server_default="1.0.0"),
        sa.Column("numerator_metric_code", sa.String(length=100), nullable=True),
        sa.Column("denominator_metric_code", sa.String(length=100), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 4. Create Metric Aliases table (Tenant-owned mapping)
    op.create_table(
        "metric_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metric_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_pattern", sa.String(length=255), nullable=False),
        sa.Column("match_type", sa.String(length=50), nullable=False, server_default="EXACT_NORMALIZED"),
        sa.Column("locale", sa.String(length=10), nullable=False, server_default="tr_TR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "organization_id", "metric_definition_id", "alias_pattern", name="uq_metric_alias_org_def_pattern"
        ),
    )

    # 5. Create Financial Fact Candidates table (Tenant-owned)
    op.create_table(
        "financial_fact_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reporting_period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reporting_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metric_definitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("suggested_metric_code", sa.String(length=100), nullable=True),
        sa.Column("raw_label", sa.String(length=255), nullable=False),
        sa.Column("raw_value", sa.String(length=255), nullable=False),
        sa.Column("parsed_decimal_value", sa.Numeric(precision=28, scale=6), nullable=True),
        sa.Column("raw_currency", sa.String(length=10), nullable=False, server_default="TRY"),
        sa.Column("raw_unit", sa.String(length=50), nullable=False, server_default="CURRENCY"),
        sa.Column("raw_scale", sa.String(length=50), nullable=False, server_default="ONE"),
        sa.Column("normalized_currency", sa.String(length=10), nullable=False, server_default="TRY"),
        sa.Column("normalized_unit", sa.String(length=50), nullable=False, server_default="CURRENCY"),
        sa.Column("normalized_scale", sa.String(length=50), nullable=False, server_default="ONE"),
        sa.Column("normalized_value", sa.Numeric(precision=28, scale=6), nullable=True),
        sa.Column(
            "detected_reporting_basis", sa.String(length=50), nullable=False, server_default="UNKNOWN"
        ),  # SOLO, CONSOLIDATED, UNKNOWN
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_location", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("extraction_method", sa.String(length=50), nullable=False, server_default="PARSER_TABLE"),
        sa.Column("mapping_rule_id", sa.String(length=100), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=4, scale=3), nullable=False, server_default="0.500"),
        sa.Column(
            "validation_status", sa.String(length=50), nullable=False, server_default="EXTRACTED"
        ),  # EXTRACTED, NORMALIZED, NEEDS_REVIEW, APPROVED, REJECTED, CONFLICTED, INVALID
        sa.Column(
            "review_status", sa.String(length=50), nullable=False, server_default="PENDING"
        ),  # PENDING, APPROVED, REJECTED
        sa.Column("warning_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 6. Create Candidate Evidence table (Tenant-owned lineage)
    op.create_table(
        "candidate_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_fact_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("table_index", sa.Integer(), nullable=True),
        sa.Column("row_index", sa.Integer(), nullable=True),
        sa.Column("col_index", sa.Integer(), nullable=True),
        sa.Column("bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("raw_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 7. Create Verified Financial Facts table (Tenant-owned & Immutable)
    op.create_table(
        "financial_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reporting_period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reporting_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metric_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_code", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Numeric(precision=28, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="TRY"),
        sa.Column("unit", sa.String(length=50), nullable=False, server_default="CURRENCY"),
        sa.Column("scale", sa.String(length=50), nullable=False, server_default="ONE"),
        sa.Column("normalized_value", sa.Numeric(precision=28, scale=6), nullable=False),
        sa.Column("reporting_basis", sa.String(length=50), nullable=False, server_default="SOLO"),
        sa.Column(
            "source_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_fact_candidates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_location", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("extraction_method", sa.String(length=50), nullable=False, server_default="PARSER_TABLE"),
        sa.Column("confidence_score", sa.Numeric(precision=4, scale=3), nullable=False, server_default="1.000"),
        sa.Column("review_status", sa.String(length=50), nullable=False, server_default="HUMAN_VERIFIED"),
        sa.Column(
            "verified_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "supersedes_fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_facts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 8. Create Fact Review Decisions table (Tenant-owned Audit Trail)
    op.create_table(
        "fact_review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_fact_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=50), nullable=False),  # APPROVED, REJECTED
        sa.Column("rejection_reason_code", sa.String(length=100), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_facts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 9. Role Grants & RLS Policies for New Domain Tables
    op.execute("""
        DO $$
        BEGIN
            -- Grants for db_api_user
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT SELECT ON metric_definitions TO db_api_user;
                GRANT SELECT, INSERT, UPDATE ON institutions, reporting_periods, metric_aliases, financial_fact_candidates, candidate_evidence, financial_facts, fact_review_decisions TO db_api_user;
            END IF;

            -- Grants for db_ingestion_worker
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT SELECT ON metric_definitions, institutions, reporting_periods, metric_aliases TO db_ingestion_worker;
                GRANT SELECT, INSERT, UPDATE ON financial_fact_candidates, candidate_evidence TO db_ingestion_worker;
                REVOKE INSERT, UPDATE, DELETE ON financial_facts, fact_review_decisions FROM db_ingestion_worker;
            END IF;
        END
        $$;
    """)

    for tbl in NEW_TENANT_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                    DROP POLICY IF EXISTS api_user_tenant_policy ON {tbl};
                    CREATE POLICY api_user_tenant_policy ON {tbl}
                        FOR ALL TO db_api_user
                        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
                END IF;

                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                    DROP POLICY IF EXISTS worker_tenant_policy ON {tbl};
                    CREATE POLICY worker_tenant_policy ON {tbl}
                        FOR ALL TO db_ingestion_worker
                        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
                END IF;
            END
            $$;
        """)

    # 10. Refactor claim_next_ingestion_job to 2-parameter production signature (p_worker_id text, p_claim_token uuid)
    # Drop legacy 3-parameter overload explicitly
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text, uuid, uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text, uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.claim_next_ingestion_job(text);")

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
            IF p_worker_id IS NULL OR trim(p_worker_id) = '' OR length(p_worker_id) > 255 THEN
                RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Invalid or missing worker ID';
            END IF;

            IF p_claim_token IS NULL THEN
                RAISE EXCEPTION 'CRITICAL_SECURITY_VIOLATION: Missing claim token';
            END IF;

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

    # 11. Seed 11 MVP Canonical Metric Definitions
    op.execute("""
        INSERT INTO metric_definitions (id, metric_code, canonical_name, description, value_type, default_currency_behavior, default_unit, normal_balance, aggregation_behavior, formula_type, formula_version, status)
        VALUES
            ('a0000000-0000-0000-0000-000000000001', 'TOTAL_ASSETS', 'Toplam Aktifler', 'Toplam Varlıklar / Bilanço Aktif Toplamı', 'CURRENCY', 'SAME_AS_SOURCE', 'TRY', 'DEBIT', 'POINT_IN_TIME', 'SOURCE_REPORTED', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000002', 'TOTAL_LOANS', 'Toplam Krediler', 'Banka Toplam Nakdi Krediler', 'CURRENCY', 'SAME_AS_SOURCE', 'TRY', 'DEBIT', 'POINT_IN_TIME', 'SOURCE_REPORTED', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000003', 'TOTAL_DEPOSITS', 'Toplam Mevduat', 'Toplanan Müşteri Mevduatları', 'CURRENCY', 'SAME_AS_SOURCE', 'TRY', 'CREDIT', 'POINT_IN_TIME', 'SOURCE_REPORTED', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000004', 'TOTAL_EQUITY', 'Toplam Özkaynaklar', 'Bilanço Özvarlık Toplamı', 'CURRENCY', 'SAME_AS_SOURCE', 'TRY', 'CREDIT', 'POINT_IN_TIME', 'SOURCE_REPORTED', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000005', 'NET_INCOME', 'Net Dönem Kârı', 'Gelir Tablosu Net Kâr / Zarar', 'CURRENCY', 'SAME_AS_SOURCE', 'TRY', 'CREDIT', 'SUM', 'SOURCE_REPORTED', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000006', 'NON_PERFORMING_LOANS', 'Takipteki Krediler', 'Takipteki Alacaklar (NPL Tutar)', 'CURRENCY', 'SAME_AS_SOURCE', 'TRY', 'DEBIT', 'POINT_IN_TIME', 'SOURCE_REPORTED', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000007', 'CAPITAL_ADEQUACY_RATIO', 'Sermaye Yeterlilik Oranı', 'Sermaye Yeterliliği Standart Rasyosu (SYR/CAR)', 'PERCENT', 'SAME_AS_SOURCE', 'PERCENT', 'NOT_APPLICABLE', 'POINT_IN_TIME', 'DERIVED_CALCULATION', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000008', 'RETURN_ON_ASSETS', 'Aktif Kârlılığı', 'Aktif Kârlılık Oranı (ROA)', 'PERCENT', 'SAME_AS_SOURCE', 'PERCENT', 'NOT_APPLICABLE', 'POINT_IN_TIME', 'DERIVED_CALCULATION', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000009', 'RETURN_ON_EQUITY', 'Özkaynak Kârlılığı', 'Özkaynak Kârlılık Oranı (ROE)', 'PERCENT', 'SAME_AS_SOURCE', 'PERCENT', 'NOT_APPLICABLE', 'POINT_IN_TIME', 'DERIVED_CALCULATION', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000010', 'NET_INTEREST_MARGIN', 'Net Faiz Marjı', 'Net Faiz Marjı Oranı (NIM)', 'PERCENT', 'SAME_AS_SOURCE', 'PERCENT', 'NOT_APPLICABLE', 'POINT_IN_TIME', 'DERIVED_CALCULATION', '1.0.0', 'ACTIVE'),
            ('a0000000-0000-0000-0000-000000000011', 'LOAN_TO_DEPOSIT_RATIO', 'Kredi / Mevduat Oranı', 'Kredi / Mevduat Rasyosu (KDR)', 'PERCENT', 'SAME_AS_SOURCE', 'PERCENT', 'NOT_APPLICABLE', 'POINT_IN_TIME', 'DERIVED_CALCULATION', '1.0.0', 'ACTIVE')
        ON CONFLICT (metric_code) DO NOTHING;
    """)


def downgrade() -> None:
    # Downgrade drops new domain tables and restores 2-parameter claim function
    for tbl in reversed(NEW_TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS api_user_tenant_policy ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS worker_tenant_policy ON {tbl};")
        op.drop_table(tbl)

    op.drop_table("metric_definitions")
