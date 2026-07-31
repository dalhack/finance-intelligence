"""003_role_separation

Revision ID: 003_role_separation
Revises: 002_document_ingestion_schema
Create Date: 2026-07-29

Least-privilege role separation migration provisioning schema grants, classification column on upload_sessions, and tenant-isolated RLS policies for db_api_user and db_ingestion_worker.
"""

from alembic import op

revision = "003_role_separation"
down_revision = "002_document_ingestion_schema"
branch_labels = None
depends_on = None

ALL_DOMAIN_TABLES = [
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
    # Add classification column to upload_sessions if not exists
    op.execute(
        "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS classification VARCHAR(50) NOT NULL DEFAULT 'CONFIDENTIAL';"
    )

    op.execute("""
        DO $$
        BEGIN
            -- Grants for db_api_user
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT USAGE ON SCHEMA public TO db_api_user;
                GRANT SELECT ON organizations, users, roles, membership_roles, alembic_version TO db_api_user;
                GRANT SELECT, INSERT, UPDATE ON memberships, upload_sessions, documents, document_versions, stored_objects, ingestion_jobs, audit_events TO db_api_user;
                REVOKE ALL ON document_pages, document_chunks, extraction_results, extraction_warnings FROM db_api_user;
            END IF;

            -- Grants for db_ingestion_worker
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_ingestion_worker;
                GRANT SELECT ON stored_objects, documents, organizations, users, roles, membership_roles, alembic_version TO db_ingestion_worker;
                GRANT SELECT, UPDATE ON ingestion_jobs, document_versions TO db_ingestion_worker;
                GRANT SELECT, INSERT, UPDATE ON ingestion_attempts, document_pages, document_chunks, extraction_results, extraction_warnings, audit_events TO db_ingestion_worker;
                REVOKE INSERT, UPDATE, DELETE ON upload_sessions, documents, stored_objects FROM db_ingestion_worker;
            END IF;
        END
        $$;
    """)

    for tbl in ALL_DOMAIN_TABLES:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                    DROP POLICY IF EXISTS api_user_tenant_policy ON {tbl};
                    CREATE POLICY api_user_tenant_policy ON {tbl}
                        FOR ALL
                        TO db_api_user
                        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
                END IF;

                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                    DROP POLICY IF EXISTS worker_tenant_policy ON {tbl};
                    CREATE POLICY worker_tenant_policy ON {tbl}
                        FOR ALL
                        TO db_ingestion_worker
                        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
                END IF;
            END
            $$;
        """)


def downgrade() -> None:
    for tbl in ALL_DOMAIN_TABLES:
        op.execute(f"DROP POLICY IF EXISTS api_user_tenant_policy ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS worker_tenant_policy ON {tbl};")

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM db_api_user;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM db_ingestion_worker;
            END IF;
        END
        $$;
    """)

    op.execute("ALTER TABLE upload_sessions DROP COLUMN IF EXISTS classification;")
