"""021_ai_runtime_execution_integrity

Revision ID: 021_ai_runtime_execution_integrity
Revises: 020_ai_orchestration_foundation
Create Date: 2026-07-31 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "021_ai_runtime_execution_integrity"
down_revision = "020_ai_orchestration_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add concurrency claim and lease columns to analysis_jobs
    op.add_column("analysis_jobs", sa.Column("locked_by", sa.String(length=100), nullable=True))
    op.add_column("analysis_jobs", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_jobs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))

    op.create_unique_constraint(
        "uq_analysis_jobs_tenant_idempotency",
        "analysis_jobs",
        ["organization_id", "idempotency_key"],
    )

    # 2. Grant UPDATE privileges on analysis_attempts to db_api_user for terminal status updates
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT UPDATE ON analysis_attempts TO db_api_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "RAISE EXCEPTION 'IRREVERSIBLE MIGRATION: 021_ai_runtime_execution_integrity cannot be rolled back without audit trail loss.';"
    )
