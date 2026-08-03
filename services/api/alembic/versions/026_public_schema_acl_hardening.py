"""026_public_schema_acl_hardening

Revision ID: 026_public_schema_acl_hardening
Revises: 025_distributed_provider_circuit_breaker
Create Date: 2026-08-03 14:30:00.000000

"""

from alembic import op

revision = "026_public_schema_acl_hardening"
down_revision = "025_distributed_provider_circuit_breaker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Hardening: Revoke default schema privileges from PUBLIC pseudo-role
    op.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC;")

    # 2. Hardening: Revoke default function execution privileges from PUBLIC pseudo-role on public schema
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;")

    # 3. Hardening: Ensure db_app_user has 0 schema and object privileges
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                REVOKE ALL ON SCHEMA public FROM db_app_user;
                REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM db_app_user;
                REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM db_app_user;
                REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM db_app_user;
            END IF;
        END
        $$;
    """)

    # 4. Explicit least-privilege USAGE grants for all authorized canonical runtime roles
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT USAGE ON SCHEMA public TO db_owner;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                GRANT USAGE ON SCHEMA public TO db_bootstrap;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT USAGE ON SCHEMA public TO db_api_user;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_ingestion_worker;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_maintenance_worker;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Fail-Closed / Irreversible Downgrade Policy:
    # Re-granting ALL to PUBLIC is explicitly prohibited to maintain security invariants.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT USAGE ON SCHEMA public TO db_api_user;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_ingestion_worker;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_maintenance_worker;
            END IF;
        END
        $$;
    """)
