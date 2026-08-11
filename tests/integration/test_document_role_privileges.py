import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import pytest
from app.db.session import ApiSessionLocal, WorkerSessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
from app.models.extraction_result import ExtractionResult
from app.models.stored_object import StoredObject
from app.models.upload_session import UploadSession
from sqlalchemy import text

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_BOOTSTRAP_URL = os.environ.get("TEST_BOOTSTRAP_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")
RAW_WORKER_URL = os.environ.get("TEST_WORKER_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
BOOTSTRAP_URL = RAW_BOOTSTRAP_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_BOOTSTRAP_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None
WORKER_URL = RAW_WORKER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_WORKER_URL else None


@pytest.mark.asyncio
async def test_least_privilege_bootstrap_cannot_insert_documents():
    conn_bootstrap = await asyncpg.connect(BOOTSTRAP_URL)
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await conn_bootstrap.execute(
            "INSERT INTO documents (id, organization_id, uploaded_by_user_id, display_name) VALUES ($1, $2, $3, $4);",
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            "illegal_insert.pdf",
        )
    await conn_bootstrap.close()


@pytest.mark.asyncio
async def test_api_role_privilege_boundary_and_tenant_isolation():
    org_id = uuid4()
    org_b = uuid4()
    user_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_id), f"Org {org_id}", f"org-{org_id}"
    )
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_b), f"Org {org_b}", f"org-{org_b}"
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    doc_id = uuid4()
    doc_ver_id = uuid4()
    obj_id = uuid4()
    await conn_owner.execute(
        "INSERT INTO stored_objects (id, organization_id, opaque_object_key, server_computed_sha256, byte_size, detected_mime_type, storage_provider) VALUES ($1, $2, $3, $4, $5, $6, $7);",
        obj_id,
        org_id,
        f"obj-{obj_id}.pdf",
        "sha256",
        100,
        "application/pdf",
        "LOCAL",
    )
    await conn_owner.execute(
        "INSERT INTO documents (id, organization_id, uploaded_by_user_id, display_name) VALUES ($1, $2, $3, $4);",
        doc_id,
        org_id,
        user_id,
        "doc.pdf",
    )
    await conn_owner.execute(
        "INSERT INTO document_versions (id, organization_id, document_id, version_number, stored_object_id, content_hash_sha256, file_size_bytes, declared_mime_type, detected_mime_type) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);",
        doc_ver_id,
        org_id,
        doc_id,
        1,
        obj_id,
        "sha256",
        100,
        "application/pdf",
        "application/pdf",
    )
    await conn_owner.close()

    async with ApiSessionLocal() as session:
        # Verify exact role username
        res_user = await session.execute(text("SELECT current_user;"))
        assert res_user.scalar() == "db_api_user"

        # Set Tenant A context
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )

        # 1. API user CAN create UploadSession and Document
        sess_id = uuid4()
        upload_sess = UploadSession(
            id=sess_id,
            organization_id=org_id,
            created_by_user_id=user_id,
            declared_mime_type="text/csv",
            expected_size_bytes=100,
            status="PENDING_UPLOAD",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(upload_sess)
        await session.commit()

        # Re-set session context
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )

        # 2. API user CANNOT write to document_chunks or extraction_results
        illegal_chunk = DocumentChunk(
            id=uuid4(),
            organization_id=org_id,
            document_version_id=doc_ver_id,
            chunk_index=0,
            chunk_type="CELL",
            content="illegal_api_chunk",
        )
        session.add(illegal_chunk)
        with pytest.raises(Exception) as exc_info:
            await session.commit()
        assert (
            "permission denied" in str(exc_info.value).lower() or "insufficientprivilege" in str(exc_info.value).lower()
        )

        await session.rollback()

    # 3. Tenant context isolation fail-closed check without tenant context set
    async with ApiSessionLocal() as session_no_ctx:
        await session_no_ctx.execute(text("SELECT set_config('app.current_organization_id', '', true);"))

        res = await session_no_ctx.execute(__import__("sqlalchemy").select(UploadSession))
        rows = res.scalars().all()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_worker_role_privilege_boundary_and_tenant_isolation():
    org_id = uuid4()
    user_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_id), f"Org {org_id}", f"org-{org_id}"
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    async with WorkerSessionLocal() as session:
        # Verify exact worker role username
        res_user = await session.execute(text("SELECT current_user;"))
        assert res_user.scalar() == "db_ingestion_worker"

        # Set Tenant A context
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )

        # Seed prerequisite objects via ApiSessionLocal
        doc_id = uuid4()
        doc_ver_id = uuid4()
        obj_id = uuid4()

        async with ApiSessionLocal() as api_sess:
            await api_sess.execute(
                text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(org_id)},
            )
            stored_obj = StoredObject(
                id=obj_id,
                organization_id=org_id,
                opaque_object_key=f"{uuid4().hex}.csv",
                server_computed_sha256="dummy_hash_privilege_test",
                byte_size=10,
                detected_mime_type="text/csv",
                storage_provider="LOCAL",
                reference_count=1,
            )

            api_sess.add(stored_obj)
            await api_sess.flush()

            doc = Document(
                id=doc_id,
                organization_id=org_id,
                uploaded_by_user_id=user_id,
                display_name="privilege_test.csv",
                classification="CONFIDENTIAL",
                status="ACTIVE",
            )
            api_sess.add(doc)
            await api_sess.flush()

            doc_ver = DocumentVersion(
                id=doc_ver_id,
                organization_id=org_id,
                document_id=doc_id,
                version_number=1,
                stored_object_id=obj_id,
                content_hash_sha256="dummy_hash_privilege_test",
                file_size_bytes=10,
                declared_mime_type="text/csv",
                detected_mime_type="text/csv",
                ingestion_status="PARSING",
                extraction_status="PENDING",
            )
            api_sess.add(doc_ver)
            await api_sess.commit()

        # 1. Worker user CAN write to extraction_results
        ext_res = ExtractionResult(
            id=uuid4(),
            organization_id=org_id,
            document_version_id=doc_ver_id,
            parser_name="TestParser",
            parser_version="1.0.0",
            status="EXTRACTED",
            quality_score=0.95,
        )
        session.add(ext_res)
        await session.commit()

        # Re-set session context
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )

        # 2. Worker user CANNOT write to documents table
        illegal_doc = Document(
            id=uuid4(),
            organization_id=org_id,
            uploaded_by_user_id=user_id,
            display_name="illegal_worker_doc.pdf",
            status="ACTIVE",
        )
        session.add(illegal_doc)
        with pytest.raises(Exception) as exc_info:
            await session.commit()
        assert (
            "permission denied" in str(exc_info.value).lower() or "insufficientprivilege" in str(exc_info.value).lower()
        )

        await session.rollback()
