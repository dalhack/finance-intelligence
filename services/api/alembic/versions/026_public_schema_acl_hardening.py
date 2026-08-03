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
    # 1. Hardening: Revoke schema privileges from PUBLIC pseudo-role & db_app_user
    op.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC;")

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

    # 2. Hardening: Revoke function EXECUTE privileges from PUBLIC on all existing functions
    op.execute("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;")

    # 3. Hardening: Default privilege owner scope for future function/table/sequence creations
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC;")

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
                ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
                ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                ALTER DEFAULT PRIVILEGES FOR ROLE db_bootstrap IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
                ALTER DEFAULT PRIVILEGES FOR ROLE db_bootstrap IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
                ALTER DEFAULT PRIVILEGES FOR ROLE db_bootstrap IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC;
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
                GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO db_owner;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                GRANT USAGE ON SCHEMA public TO db_bootstrap;
                GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO db_bootstrap;
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

    # 5. Explicit function EXECUTE grants for specific runtime roles & trigger functions
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                IF EXISTS (SELECT FROM pg_proc WHERE proname = 'claim_ingestion_job') THEN
                    GRANT EXECUTE ON FUNCTION claim_ingestion_job(uuid, text, uuid) TO db_ingestion_worker;
                END IF;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                IF EXISTS (SELECT FROM pg_proc WHERE proname = 'claim_next_maintenance_job') THEN
                    GRANT EXECUTE ON FUNCTION claim_next_maintenance_job(text, uuid, text[]) TO db_maintenance_worker;
                END IF;
            END IF;
            IF EXISTS (SELECT FROM pg_proc WHERE proname = 'record_provider_failure') THEN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                    GRANT EXECUTE ON FUNCTION record_provider_failure(text, text, integer, integer) TO db_api_user;
                END IF;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                    GRANT EXECUTE ON FUNCTION record_provider_failure(text, text, integer, integer) TO db_ingestion_worker;
                END IF;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                    GRANT EXECUTE ON FUNCTION record_provider_failure(text, text, integer, integer) TO db_maintenance_worker;
                END IF;
            END IF;
            IF EXISTS (SELECT FROM pg_proc WHERE proname = 'record_provider_success') THEN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                    GRANT EXECUTE ON FUNCTION record_provider_success(text, text) TO db_api_user;
                END IF;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                    GRANT EXECUTE ON FUNCTION record_provider_success(text, text) TO db_ingestion_worker;
                END IF;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                    GRANT EXECUTE ON FUNCTION record_provider_success(text, text) TO db_maintenance_worker;
                END IF;
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
