"""017_comparison_dataset

Revision ID: 017_comparison_dataset
Revises: 016_traceability_integrity_repair
Create Date: 2026-07-30

Creates comparison_runs and result_datasets tables with RLS, FORCE RLS, composite tenant FKs, append-only immutability triggers, and strict role privileges for comparison engine.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017_comparison_dataset"
down_revision: str | None = "016_traceability_integrity_repair"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create comparison_runs table
    op.execute("""
    CREATE TABLE public.comparison_runs (
        id UUID PRIMARY KEY,
        organization_id UUID NOT NULL REFERENCES public.organizations(id),
        requested_by_user_id UUID NOT NULL,
        comparison_mode VARCHAR(50) NOT NULL,
        value_source_policy VARCHAR(50) NOT NULL,
        query_snapshot JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_comparison_runs_tenant_id UNIQUE (organization_id, id)
    );
    """)

    # 2. Create result_datasets table
    op.execute("""
    CREATE TABLE public.result_datasets (
        id UUID PRIMARY KEY,
        organization_id UUID NOT NULL REFERENCES public.organizations(id),
        comparison_run_id UUID NOT NULL,
        schema_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
        query_snapshot JSONB NOT NULL,
        dimensions_snapshot JSONB NOT NULL,
        measures_snapshot JSONB NOT NULL,
        rows_snapshot JSONB NOT NULL,
        table_spec_snapshot JSONB NOT NULL,
        chart_specs_snapshot JSONB NOT NULL,
        data_quality_summary JSONB NOT NULL,
        warnings_snapshot JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT fk_result_datasets_comparison_run
            FOREIGN KEY (organization_id, comparison_run_id)
            REFERENCES public.comparison_runs (organization_id, id)
            ON DELETE RESTRICT
    );
    """)

    # 3. Indexes
    op.execute("""
    CREATE INDEX idx_comparison_runs_org_created ON public.comparison_runs(organization_id, created_at DESC);
    CREATE INDEX idx_result_datasets_org_run ON public.result_datasets(organization_id, comparison_run_id);
    """)

    # 4. RLS Policies and FORCE RLS Activation
    op.execute("""
    ALTER TABLE public.comparison_runs ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.comparison_runs FORCE ROW LEVEL SECURITY;

    CREATE POLICY owner_comparison_runs_policy ON public.comparison_runs
        FOR ALL TO db_owner USING (true) WITH CHECK (true);

    CREATE POLICY api_user_comparison_runs_policy ON public.comparison_runs
        FOR ALL TO db_api_user
        USING (organization_id = (SELECT NULLIF(current_setting('app.current_organization_id', true), '')::uuid))
        WITH CHECK (organization_id = (SELECT NULLIF(current_setting('app.current_organization_id', true), '')::uuid));

    ALTER TABLE public.result_datasets ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.result_datasets FORCE ROW LEVEL SECURITY;

    CREATE POLICY owner_result_datasets_policy ON public.result_datasets
        FOR ALL TO db_owner USING (true) WITH CHECK (true);

    CREATE POLICY api_user_result_datasets_policy ON public.result_datasets
        FOR ALL TO db_api_user
        USING (organization_id = (SELECT NULLIF(current_setting('app.current_organization_id', true), '')::uuid))
        WITH CHECK (organization_id = (SELECT NULLIF(current_setting('app.current_organization_id', true), '')::uuid));
    """)

    # 5. Role Privileges (db_api_user and db_owner SELECT/INSERT; Worker and Bootstrap denied)
    op.execute("""
    GRANT SELECT, INSERT ON public.comparison_runs, public.result_datasets TO db_api_user, db_owner;
    REVOKE ALL ON public.comparison_runs, public.result_datasets FROM db_ingestion_worker, db_bootstrap, PUBLIC;
    """)

    # 6. Append-Only Immutability Trigger
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_prevent_comparison_dataset_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'IMMUTABLE_DATASET: Comparison runs and result datasets are append-only terminal records.';
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog, pg_temp;

    ALTER FUNCTION public.fn_prevent_comparison_dataset_mutation() OWNER TO db_owner;
    REVOKE EXECUTE ON FUNCTION public.fn_prevent_comparison_dataset_mutation() FROM db_api_user, db_ingestion_worker, db_bootstrap, PUBLIC;

    CREATE TRIGGER trg_prevent_comparison_runs_mutation
    BEFORE UPDATE OR DELETE ON public.comparison_runs
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_comparison_dataset_mutation();

    CREATE TRIGGER trg_prevent_result_datasets_mutation
    BEFORE UPDATE OR DELETE ON public.result_datasets
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_comparison_dataset_mutation();
    """)


def downgrade() -> None:
    raise RuntimeError(
        "IRREVERSIBLE MIGRATION: Downgrading Migration 017 is prohibited to protect comparison dataset lineage and audit history."
    )
