"""024_maintenance_scheduler_and_operational_resilience

Revision ID: 024_maintenance_scheduler_and_operational_resilience
Revises: 023_analysis_clarification_workflow
Create Date: 2026-07-31 19:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "024_maintenance_scheduler_and_operational_resilience"
down_revision = "023_analysis_clarification_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Provision db_maintenance_worker role if not exists
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
            CREATE ROLE db_maintenance_worker LOGIN PASSWORD 'dev_maintenance_pass_123' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
        ELSE
            ALTER ROLE db_maintenance_worker LOGIN PASSWORD 'dev_maintenance_pass_123';
        END IF;
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO db_maintenance_worker', current_database());
    END $$;
    """)

    op.execute("GRANT USAGE ON SCHEMA public TO db_maintenance_worker;")

    # 2. Create maintenance_jobs table
    op.create_table(
        "maintenance_jobs",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_code", sa.String(length=100), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("target_entity_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="QUEUED"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token", sa.UUID(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0", name="chk_maintenance_job_attempts"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_maintenance_jobs_org", "maintenance_jobs", ["organization_id"])
    op.create_index("idx_maintenance_jobs_claim", "maintenance_jobs", ["status", "available_at", "job_code"])

    # 3. Create maintenance_attempts table
    op.create_table(
        "maintenance_attempts",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("maintenance_job_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_instance_key", sa.String(length=100), nullable=False),
        sa.Column("claim_token_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["maintenance_job_id"], ["maintenance_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_maintenance_attempts_job", "maintenance_attempts", ["maintenance_job_id"])

    # 4. Create maintenance_worker_heartbeats table (control-plane level, global)
    op.create_table(
        "maintenance_worker_heartbeats",
        sa.Column("worker_instance_key", sa.String(length=100), nullable=False),
        sa.Column("worker_role", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="RUNNING"),
        sa.Column("contract_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.PrimaryKeyConstraint("worker_instance_key"),
    )

    # 5. Enable RLS and FORCE RLS on tenant-owned tables
    op.execute("ALTER TABLE maintenance_jobs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE maintenance_jobs FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY maintenance_jobs_tenant_policy ON maintenance_jobs
        FOR ALL
        TO PUBLIC
        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE maintenance_attempts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE maintenance_attempts FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY maintenance_attempts_tenant_policy ON maintenance_attempts
        FOR ALL
        TO PUBLIC
        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
    """)

    # 6. Grant table permissions to db_maintenance_worker & db_owner
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE maintenance_jobs TO db_maintenance_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE maintenance_attempts TO db_maintenance_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE maintenance_worker_heartbeats TO db_maintenance_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE analysis_jobs TO db_maintenance_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE analysis_clarifications TO db_maintenance_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE analysis_events TO db_maintenance_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE audit_events TO db_maintenance_worker;")

    # 7. Create SECURITY DEFINER control-plane claim function
    op.execute("""
    CREATE OR REPLACE FUNCTION claim_next_maintenance_job(
        p_worker_id text,
        p_claim_token uuid,
        p_allowed_job_codes text[]
    )
    RETURNS TABLE (
        job_id uuid,
        job_code text,
        organization_id uuid,
        target_entity_id text,
        attempt_count integer
    )
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public, pg_catalog, pg_temp
    AS $$
    DECLARE
        v_job_id uuid;
        v_job_code text;
        v_org_id uuid;
        v_target_id text;
        v_attempt_count integer;
    BEGIN
        IF p_worker_id IS NULL OR length(trim(p_worker_id)) = 0 OR length(p_worker_id) > 100 THEN
            RAISE EXCEPTION 'Invalid p_worker_id';
        END IF;
        IF p_claim_token IS NULL THEN
            RAISE EXCEPTION 'Invalid p_claim_token';
        END IF;

        SELECT mj.id, mj.job_code, mj.organization_id, mj.target_entity_id, mj.attempt_count
        INTO v_job_id, v_job_code, v_org_id, v_target_id, v_attempt_count
        FROM maintenance_jobs mj
        WHERE mj.job_code = ANY(p_allowed_job_codes)
          AND (
                mj.status = 'QUEUED'
                OR (mj.status = 'RUNNING' AND mj.lease_expires_at < now())
              )
          AND mj.available_at <= now()
          AND mj.attempt_count < mj.max_attempts
        ORDER BY mj.available_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1;

        IF v_job_id IS NOT NULL THEN
            UPDATE maintenance_jobs
            SET status = 'RUNNING',
                locked_by = p_worker_id,
                locked_at = now(),
                lease_expires_at = now() + INTERVAL '5 minutes',
                claim_token = p_claim_token,
                attempt_count = maintenance_jobs.attempt_count + 1
            WHERE maintenance_jobs.id = v_job_id;

            RETURN QUERY SELECT v_job_id, v_job_code, v_org_id, v_target_id, v_attempt_count + 1;
        END IF;
    END;
    $$;
    """)

    op.execute("ALTER FUNCTION claim_next_maintenance_job(text, uuid, text[]) OWNER TO db_owner;")
    op.execute("REVOKE EXECUTE ON FUNCTION claim_next_maintenance_job(text, uuid, text[]) FROM PUBLIC;")
    op.execute(
        "GRANT EXECUTE ON FUNCTION claim_next_maintenance_job(text, uuid, text[]) TO db_maintenance_worker, db_owner;"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS claim_next_maintenance_job(text, uuid, text[]);")
    op.drop_table("maintenance_worker_heartbeats")
    op.drop_table("maintenance_attempts")
    op.drop_table("maintenance_jobs")
