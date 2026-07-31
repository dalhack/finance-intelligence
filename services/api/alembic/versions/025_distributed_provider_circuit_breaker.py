"""025_distributed_provider_circuit_breaker

Revision ID: 025_distributed_provider_circuit_breaker
Revises: 024_maintenance_scheduler_and_operational_resilience
Create Date: 2026-07-31 20:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "025_distributed_provider_circuit_breaker"
down_revision = "024_maintenance_scheduler_and_operational_resilience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create provider_circuit_states table (Global control-plane table)
    op.create_table(
        "provider_circuit_states",
        sa.Column("provider_key", sa.String(length=100), nullable=False),
        sa.Column("model_alias", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="CLOSED"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("half_open_lease_owner", sa.String(length=100), nullable=True),
        sa.Column("half_open_claim_token", sa.UUID(), nullable=True),
        sa.Column("half_open_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("state IN ('CLOSED', 'OPEN', 'HALF_OPEN')", name="chk_provider_circuit_state_valid"),
        sa.CheckConstraint("consecutive_failures >= 0", name="chk_provider_circuit_failures_non_negative"),
        sa.PrimaryKeyConstraint("provider_key", "model_alias"),
    )

    # 2. Grant least-privilege permissions to runtime roles
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE provider_circuit_states TO db_api_user;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE provider_circuit_states TO db_ingestion_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE provider_circuit_states TO db_maintenance_worker;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE provider_circuit_states TO db_owner;")

    # 3. Create helper CONTROL-PLANE functions for atomic circuit updates
    op.execute("""
    CREATE OR REPLACE FUNCTION record_provider_failure(
        p_provider_key text,
        p_model_alias text,
        p_threshold integer,
        p_open_duration_seconds integer
    )
    RETURNS text
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public, pg_catalog, pg_temp
    AS $$
    DECLARE
        v_state text;
        v_failures integer;
        v_now timestamptz := now();
    BEGIN
        INSERT INTO provider_circuit_states (provider_key, model_alias, state, consecutive_failures, updated_at)
        VALUES (p_provider_key, p_model_alias, 'CLOSED', 1, v_now)
        ON CONFLICT (provider_key, model_alias) DO UPDATE
        SET consecutive_failures = provider_circuit_states.consecutive_failures + 1,
            updated_at = v_now
        RETURNING state, consecutive_failures INTO v_state, v_failures;

        IF v_failures >= p_threshold AND v_state <> 'OPEN' THEN
            UPDATE provider_circuit_states
            SET state = 'OPEN',
                opened_at = v_now,
                retry_after = v_now + (p_open_duration_seconds || ' seconds')::interval,
                half_open_lease_owner = NULL,
                half_open_claim_token = NULL,
                half_open_lease_expires_at = NULL,
                updated_at = v_now
            WHERE provider_key = p_provider_key AND model_alias = p_model_alias;
            RETURN 'OPEN';
        END IF;

        RETURN v_state;
    END;
    $$;
    """)

    op.execute("ALTER FUNCTION record_provider_failure(text, text, integer, integer) OWNER TO db_owner;")
    op.execute("REVOKE EXECUTE ON FUNCTION record_provider_failure(text, text, integer, integer) FROM PUBLIC;")
    op.execute(
        "GRANT EXECUTE ON FUNCTION record_provider_failure(text, text, integer, integer) TO db_api_user, db_ingestion_worker, db_maintenance_worker, db_owner;"
    )

    op.execute("""
    CREATE OR REPLACE FUNCTION record_provider_success(
        p_provider_key text,
        p_model_alias text
    )
    RETURNS text
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public, pg_catalog, pg_temp
    AS $$
    BEGIN
        INSERT INTO provider_circuit_states (provider_key, model_alias, state, consecutive_failures, updated_at)
        VALUES (p_provider_key, p_model_alias, 'CLOSED', 0, now())
        ON CONFLICT (provider_key, model_alias) DO UPDATE
        SET state = 'CLOSED',
            consecutive_failures = 0,
            opened_at = NULL,
            retry_after = NULL,
            half_open_lease_owner = NULL,
            half_open_claim_token = NULL,
            half_open_lease_expires_at = NULL,
            updated_at = now();
        RETURN 'CLOSED';
    END;
    $$;
    """)

    op.execute("ALTER FUNCTION record_provider_success(text, text) OWNER TO db_owner;")
    op.execute("REVOKE EXECUTE ON FUNCTION record_provider_success(text, text) FROM PUBLIC;")
    op.execute(
        "GRANT EXECUTE ON FUNCTION record_provider_success(text, text) TO db_api_user, db_ingestion_worker, db_maintenance_worker, db_owner;"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS record_provider_success(text, text);")
    op.execute("DROP FUNCTION IF EXISTS record_provider_failure(text, text, integer, integer);")
    op.drop_table("provider_circuit_states")
