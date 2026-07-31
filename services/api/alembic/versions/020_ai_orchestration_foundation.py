"""020_ai_orchestration_foundation

Revision ID: 020_ai_orchestration_foundation
Revises: 019_comparison_semantics_and_snapshot_integrity
Create Date: 2026-07-31 11:35:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "020_ai_orchestration_foundation"
down_revision = "019_comparison_semantics_and_snapshot_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create analysis_jobs table
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="RECEIVED"),
        sa.Column("request_prompt", sa.Text(), nullable=False),
        sa.Column(
            "normalized_request",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'UNDERSTANDING_REQUEST', 'PLANNING', 'POLICY_CHECK', 'RETRIEVING_INTERNAL_SOURCES', "
            "'VALIDATING_SOURCES', 'EXECUTING_TOOLS', 'RECONCILING_RESULTS', 'GENERATING_STRUCTURED_RESULT', 'QUALITY_GATE', "
            "'COMPLETED', 'NEEDS_CLARIFICATION', 'REJECTED_BY_POLICY', 'FAILED', 'CANCELLED', 'EXPIRED', 'BUDGET_EXCEEDED', "
            "'AWAITING_HUMAN_REVIEW')",
            name="chk_analysis_job_status",
        ),
    )

    # 2. Create analysis_attempts table
    op.create_table(
        "analysis_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
        sa.UniqueConstraint("analysis_job_id", "attempt_number", name="uq_job_attempt_number"),
    )

    # 3. Create analysis_plans table
    op.create_table(
        "analysis_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
    )

    # 4. Create model_invocations table
    op.create_table(
        "model_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_alias", sa.String(length=50), nullable=False),
        sa.Column("model_alias", sa.String(length=50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0.0000"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
    )

    # 5. Create tool_invocations table
    op.create_table(
        "tool_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("arguments_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
    )

    # 6. Create policy_decisions table
    op.create_table(
        "policy_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("policy_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("classification", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
    )

    # 7. Create quality_gate_results table
    op.create_table(
        "quality_gate_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gate_code", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
    )

    # 8. Create final_result_snapshots table
    op.create_table(
        "final_result_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
        sa.UniqueConstraint("analysis_job_id", name="uq_snapshot_analysis_job"),
    )

    # 9. Create analysis_clarifications table
    op.create_table(
        "analysis_clarifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("user_response", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 10. Enable and Force RLS
    for table_name in [
        "analysis_jobs",
        "analysis_attempts",
        "analysis_plans",
        "model_invocations",
        "tool_invocations",
        "policy_decisions",
        "quality_gate_results",
        "final_result_snapshots",
        "analysis_clarifications",
    ]:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation ON {table_name}
            USING (organization_id = (SELECT current_setting('app.current_organization_id', true)::uuid));
            """
        )

    # 11. Role Grants
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT SELECT, INSERT, UPDATE ON analysis_jobs, analysis_clarifications TO db_api_user;
                GRANT SELECT, INSERT ON analysis_attempts, analysis_plans, model_invocations, tool_invocations, policy_decisions, quality_gate_results, final_result_snapshots TO db_api_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "RAISE EXCEPTION 'IRREVERSIBLE MIGRATION: 020_ai_orchestration_foundation cannot be rolled back without audit trail loss.';"
    )
