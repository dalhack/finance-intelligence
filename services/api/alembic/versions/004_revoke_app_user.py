"""004_revoke_app_user

Revision ID: 004_revoke_app_user
Revises: 003_role_separation
Create Date: 2026-07-29

Explicitly revokes all Phase 2 domain table and sequence privileges from legacy db_app_user role, enforcing least-privilege role separation for db_api_user and db_ingestion_worker.
"""

from alembic import op

revision = "004_revoke_app_user"
down_revision = "003_role_separation"
branch_labels = None
depends_on = None

ALL_TABLES = [
    "organizations",
    "users",
    "memberships",
    "membership_roles",
    "stored_objects",
    "upload_sessions",
    "documents",
    "document_versions",
    "document_pages",
    "document_chunks",
    "ingestion_jobs",
    "ingestion_attempts",
    "extraction_results",
    "extraction_warnings",
    "audit_events",
]


def upgrade() -> None:
    # 1. Revoke all privileges from legacy db_app_user
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM db_app_user;
                REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM db_app_user;
                REVOKE USAGE ON SCHEMA public FROM db_app_user;
            END IF;
        END
        $$;
    """)

    # 2. Strict least-privilege grants for db_api_user
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT USAGE ON SCHEMA public TO db_api_user;
                GRANT SELECT ON organizations, users, roles, membership_roles, alembic_version, extraction_results, extraction_warnings TO db_api_user;
                GRANT SELECT, INSERT, UPDATE ON memberships, upload_sessions, documents, document_versions, stored_objects, ingestion_jobs TO db_api_user;
                GRANT SELECT, INSERT ON audit_events TO db_api_user;
                REVOKE UPDATE, DELETE ON audit_events FROM db_api_user;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO db_api_user;
                REVOKE INSERT, UPDATE, DELETE ON document_pages, document_chunks, extraction_results, extraction_warnings FROM db_api_user;
            END IF;

            -- 3. Strict least-privilege grants for db_ingestion_worker
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_ingestion_worker;
                GRANT SELECT ON stored_objects, documents, organizations, users, roles, membership_roles, alembic_version TO db_ingestion_worker;
                GRANT SELECT, UPDATE ON ingestion_jobs, document_versions TO db_ingestion_worker;
                GRANT SELECT, INSERT, UPDATE ON ingestion_attempts, document_pages, document_chunks, extraction_results, extraction_warnings TO db_ingestion_worker;
                GRANT SELECT, INSERT ON audit_events TO db_ingestion_worker;
                REVOKE UPDATE, DELETE ON audit_events FROM db_ingestion_worker;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO db_ingestion_worker;
                REVOKE INSERT, UPDATE, DELETE ON upload_sessions, documents, stored_objects FROM db_ingestion_worker;
            END IF;
        END
        $$;
    """)

    # 4. Create RLS policies for db_api_user & db_ingestion_worker on core tenant tables
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                DROP POLICY IF EXISTS api_user_org_policy ON organizations;
                CREATE POLICY api_user_org_policy ON organizations
                    FOR SELECT TO db_api_user
                    USING (id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);

                DROP POLICY IF EXISTS api_user_users_policy ON users;
                CREATE POLICY api_user_users_policy ON users
                    FOR SELECT TO db_api_user
                    USING (id IN (
                        SELECT user_id FROM memberships
                        WHERE organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
                    ));

                DROP POLICY IF EXISTS api_user_memberships_policy ON memberships;
                CREATE POLICY api_user_memberships_policy ON memberships
                    FOR ALL TO db_api_user
                    USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                    WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);

                DROP POLICY IF EXISTS api_user_mem_roles_policy ON membership_roles;
                CREATE POLICY api_user_mem_roles_policy ON membership_roles
                    FOR SELECT TO db_api_user
                    USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
            END IF;

            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                DROP POLICY IF EXISTS worker_org_policy ON organizations;
                CREATE POLICY worker_org_policy ON organizations
                    FOR SELECT TO db_ingestion_worker
                    USING (id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);

                DROP POLICY IF EXISTS worker_users_policy ON users;
                CREATE POLICY worker_users_policy ON users
                    FOR SELECT TO db_ingestion_worker
                    USING (id IN (
                        SELECT user_id FROM memberships
                        WHERE organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
                    ));

                DROP POLICY IF EXISTS worker_memberships_policy ON memberships;
                CREATE POLICY worker_memberships_policy ON memberships
                    FOR SELECT TO db_ingestion_worker
                    USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
            END IF;
        END
        $$;
    """)

    # 5. Confirm RLS & FORCE RLS policies across all tables
    for tbl in ALL_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    # Deterministic downgrade
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                DROP POLICY IF EXISTS api_user_org_policy ON organizations;
                DROP POLICY IF EXISTS api_user_users_policy ON users;
                DROP POLICY IF EXISTS api_user_memberships_policy ON memberships;
                DROP POLICY IF EXISTS api_user_mem_roles_policy ON membership_roles;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                DROP POLICY IF EXISTS worker_org_policy ON organizations;
                DROP POLICY IF EXISTS worker_users_policy ON users;
                DROP POLICY IF EXISTS worker_memberships_policy ON memberships;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                GRANT USAGE ON SCHEMA public TO db_app_user;
                GRANT SELECT ON organizations, users, memberships, roles, membership_roles, alembic_version TO db_app_user;
            END IF;
        END
        $$;
    """)
