"""022_model_provider_and_analysis_events

Revision ID: 022_model_provider_and_analysis_events
Revises: 021_ai_runtime_execution_integrity
Create Date: 2026-07-31 13:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "022_model_provider_and_analysis_events"
down_revision = "021_ai_runtime_execution_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create analysis_events table
    op.create_table(
        "analysis_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_attempts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("sequence > 0", name="ck_sequence_positive"),
        sa.UniqueConstraint("organization_id", "analysis_job_id", "sequence", name="uq_analysis_events_org_job_seq"),
    )

    # 2. Enable & Force RLS
    op.execute("ALTER TABLE analysis_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE analysis_events FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY analysis_events_tenant_isolation ON analysis_events
        USING (organization_id = (SELECT current_setting('app.current_organization_id', true)::uuid));
        """
    )

    # 3. Role Grants
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT SELECT, INSERT ON analysis_events TO db_api_user;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                REVOKE ALL ON analysis_events FROM db_ingestion_worker;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "RAISE EXCEPTION 'IRREVERSIBLE MIGRATION: 022_model_provider_and_analysis_events cannot be rolled back.';"
    )
