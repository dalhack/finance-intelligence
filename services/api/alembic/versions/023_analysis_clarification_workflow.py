"""023_analysis_clarification_workflow

Revision ID: 023_analysis_clarification_workflow
Revises: 022_model_provider_and_analysis_events
Create Date: 2026-07-31 18:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "023_analysis_clarification_workflow"
down_revision = "022_model_provider_and_analysis_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns to analysis_clarifications
    op.add_column(
        "analysis_clarifications",
        sa.Column("clarification_code", sa.String(length=100), nullable=False, server_default="INSTITUTION_REQUIRED"),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column(
            "prompt_key",
            sa.String(length=100),
            nullable=False,
            server_default="clarification.select_institution",
        ),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column(
            "allowed_response_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="AWAITING_CLARIFICATION"),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column("response_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "analysis_clarifications",
        sa.Column("created_by_system", sa.String(length=100), nullable=False, server_default="SYSTEM"),
    )

    # 2. Add Check Constraints
    op.create_check_constraint(
        "ck_clarification_status",
        "analysis_clarifications",
        "status IN ('AWAITING_CLARIFICATION', 'CLARIFICATION_RECEIVED', 'CLARIFICATION_EXPIRED', 'CLARIFICATION_CANCELLED')",
    )
    op.create_check_constraint(
        "ck_clarification_attempt_positive",
        "analysis_clarifications",
        "attempt_number > 0",
    )
    op.create_check_constraint(
        "ck_clarification_code_allowlist",
        "analysis_clarifications",
        "clarification_code IN ('INSTITUTION_REQUIRED', 'REPORTING_PERIOD_REQUIRED', 'REPORTING_BASIS_REQUIRED', 'MEASURE_REQUIRED', 'DOCUMENT_SCOPE_REQUIRED', 'COMPARISON_SCOPE_AMBIGUOUS', 'UNSUPPORTED_REQUEST_SCOPE')",
    )

    # 3. Partial Unique Index for Single Active Clarification per Job
    op.create_index(
        "uq_active_clarification_per_job",
        "analysis_clarifications",
        ["organization_id", "analysis_job_id"],
        unique=True,
        postgresql_where=sa.text("status = 'AWAITING_CLARIFICATION'"),
    )

    # 4. Create Trigger Function for Terminal Immutability
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_analysis_clarifications_immutability()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_catalog, pg_temp
        AS $$
        BEGIN
            IF OLD.status IN ('CLARIFICATION_RECEIVED', 'CLARIFICATION_EXPIRED', 'CLARIFICATION_CANCELLED') THEN
                IF NEW.clarification_code <> OLD.clarification_code OR
                   NEW.prompt_key <> OLD.prompt_key OR
                   NEW.analysis_job_id <> OLD.analysis_job_id OR
                   NEW.organization_id <> OLD.organization_id OR
                   NEW.status <> OLD.status THEN
                    RAISE EXCEPTION 'TERMINAL_CLARIFICATION_IMMUTABLE: Terminal clarification records cannot be modified.';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER check_analysis_clarifications_immutability
        BEFORE UPDATE ON analysis_clarifications
        FOR EACH ROW
        EXECUTE FUNCTION trg_analysis_clarifications_immutability();
        """
    )

    # 5. Role Grants & Least Privilege
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT SELECT, INSERT, UPDATE ON analysis_clarifications TO db_api_user;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                REVOKE ALL ON analysis_clarifications FROM db_ingestion_worker;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("RAISE EXCEPTION 'IRREVERSIBLE MIGRATION: 023_analysis_clarification_workflow cannot be rolled back.';")
