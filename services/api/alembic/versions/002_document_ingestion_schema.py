"""002_document_ingestion_schema

Revision ID: 002_document_ingestion_schema
Revises: 001_initial_schema_and_rls
Create Date: 2026-07-29

Phase 2.1 Document Ingestion, Stored Objects, Upload Sessions, Multi-Format Parsing schema with hardened RLS and composite FKs.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_document_ingestion_schema"
down_revision = "001_initial_schema_and_rls"
branch_labels = None
depends_on = None

NEW_TABLES = [
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
]


def upgrade() -> None:
    # 1. stored_objects
    op.create_table(
        "stored_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("opaque_object_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("storage_provider", sa.String(length=50), nullable=False, server_default="local"),
        sa.Column("storage_bucket_alias", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("server_computed_sha256", sa.String(length=64), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=100), nullable=False),
        sa.Column("integrity_status", sa.String(length=50), nullable=False, server_default="VALIDATED"),
        sa.Column("retention_status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("deletion_status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("reference_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("reference_count >= 0", name="chk_stored_objects_ref_count"),
        sa.UniqueConstraint("id", "organization_id", name="uq_stored_objects_id_org"),
        sa.UniqueConstraint("organization_id", "server_computed_sha256", name="uq_stored_object_tenant_hash"),
    )

    # 2. upload_sessions
    op.create_table(
        "upload_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False, server_default="document.bin"),
        sa.Column("sanitized_filename", sa.String(length=255), nullable=False, server_default="document.bin"),
        sa.Column("normalized_extension", sa.String(length=20), nullable=False, server_default=".bin"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("declared_mime_type", sa.String(length=100), nullable=False),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("received_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("server_computed_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING_UPLOAD"),
        sa.Column("temporary_object_key", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("id", "organization_id", name="uq_upload_sessions_id_org"),
    )

    # 3. documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False, server_default="GENERAL"),
        sa.Column("classification", sa.String(length=50), nullable=False, server_default="CONFIDENTIAL"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "organization_id", name="uq_documents_id_org"),
    )

    # 4. document_versions
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stored_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("declared_mime_type", sa.String(length=100), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=100), nullable=False),
        sa.Column("ingestion_status", sa.String(length=50), nullable=False, server_default="PENDING_UPLOAD"),
        sa.Column("extraction_status", sa.String(length=50), nullable=False, server_default="NOT_STARTED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            ondelete="CASCADE",
            name="fk_doc_versions_document_org",
        ),
        sa.ForeignKeyConstraint(
            ["stored_object_id", "organization_id"],
            ["stored_objects.id", "stored_objects.organization_id"],
            ondelete="RESTRICT",
            name="fk_doc_versions_stored_object_org",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_document_versions_id_org"),
        sa.UniqueConstraint("organization_id", "document_id", "version_number", name="uq_doc_version_num"),
    )

    # 5. document_pages
    op.create_table(
        "document_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column("text_layer_present", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("raw_page_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["document_versions.id", "document_versions.organization_id"],
            ondelete="CASCADE",
            name="fk_doc_pages_version_org",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_document_pages_id_org"),
        sa.UniqueConstraint("id", "document_version_id", "organization_id", name="uq_doc_page_composite"),
    )

    # 6. document_chunks
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(length=50), nullable=False, server_default="TEXT"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_lineage", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["document_versions.id", "document_versions.organization_id"],
            ondelete="CASCADE",
            name="fk_doc_chunks_version_org",
        ),
        sa.ForeignKeyConstraint(
            ["document_page_id", "document_version_id", "organization_id"],
            [
                "document_pages.id",
                "document_pages.document_version_id",
                "document_pages.organization_id",
            ],
            ondelete="CASCADE",
            name="fk_doc_chunks_page_composite",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_document_chunks_id_org"),
    )

    # 7. ingestion_jobs
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING_UPLOAD"),
        sa.Column("current_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["document_versions.id", "document_versions.organization_id"],
            ondelete="CASCADE",
            name="fk_ingestion_jobs_version_org",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_ingestion_jobs_id_org"),
    )

    # 8. ingestion_attempts
    op.create_table(
        "ingestion_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id", "organization_id"],
            ["ingestion_jobs.id", "ingestion_jobs.organization_id"],
            ondelete="CASCADE",
            name="fk_ingestion_attempts_job_org",
        ),
    )

    # 9. extraction_results
    op.create_table(
        "extraction_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parser_name", sa.String(length=50), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["document_versions.id", "document_versions.organization_id"],
            ondelete="CASCADE",
            name="fk_extraction_results_version_org",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_extraction_results_id_org"),
    )

    # 10. extraction_warnings
    op.create_table(
        "extraction_warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("extraction_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warning_code", sa.String(length=100), nullable=False),
        sa.Column("warning_message", sa.Text(), nullable=False),
        sa.Column("lineage_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["extraction_result_id", "organization_id"],
            ["extraction_results.id", "extraction_results.organization_id"],
            ondelete="CASCADE",
            name="fk_extraction_warnings_result_org",
        ),
    )

    # Least privilege role grants & RLS policies
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                GRANT SELECT, INSERT, UPDATE ON upload_sessions, documents, document_versions, stored_objects, ingestion_jobs, document_pages, document_chunks, ingestion_attempts, extraction_results, extraction_warnings TO db_app_user;
            END IF;
        END
        $$;
    """)

    for tbl in NEW_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")

        op.execute(f"""
            CREATE POLICY owner_full_access_policy ON {tbl}
                FOR ALL
                TO db_owner
                USING (true)
                WITH CHECK (true);
        """)

        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON {tbl}
                FOR ALL
                TO db_app_user
                USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
        """)


def downgrade() -> None:
    for tbl in reversed(NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS owner_full_access_policy ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(tbl)
