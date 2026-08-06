import os
from io import BytesIO
from uuid import uuid4

import asyncpg
import pytest
import sqlalchemy
from app.db.tenant_context import tenant_transaction_context
from sqlalchemy import text

from services.api.app.db.session import ApiSessionLocal, BootstrapSessionLocal, WorkerSessionLocal
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.ingestion_job import IngestionJob
from services.api.app.models.stored_object import StoredObject
from services.api.app.storage.local_adapter import LocalStorageAdapter
from services.worker.app.ingestion_worker import IngestionWorker, WorkerOutcomeStatus

OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    "postgresql://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test",
).replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.asyncio
async def test_worker_session_role_is_db_ingestion_worker():
    """Verify that WorkerSessionLocal executes as db_ingestion_worker role."""
    async with WorkerSessionLocal() as session:
        res = await session.execute(text("SELECT current_user;"))
        user = res.scalar_one()
        assert user == "db_ingestion_worker"


@pytest.mark.asyncio
async def test_api_session_role_is_db_api_user():
    """Verify that ApiSessionLocal executes as db_api_user role."""
    async with ApiSessionLocal() as session:
        res = await session.execute(text("SELECT current_user;"))
        user = res.scalar_one()
        assert user == "db_api_user"


@pytest.mark.asyncio
async def test_bootstrap_session_role_is_db_bootstrap():
    """Verify that BootstrapSessionLocal executes as db_bootstrap role."""
    async with BootstrapSessionLocal() as session:
        res = await session.execute(text("SELECT current_user;"))
        user = res.scalar_one()
        assert user == "db_bootstrap"


@pytest.mark.asyncio
async def test_worker_run_once_claims_and_processes_job():
    """Verify end-to-end execution of a QUEUED job by IngestionWorker."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    obj_id = uuid4()
    opaque_key = f"{uuid4().hex}.csv"
    payload = b"item_code,description,quantity\nA100,Widget,10\n"

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        "Runtime Test Org",
        f"org-{org_id}",
    )

    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    # Setup tenant data via ApiSessionLocal
    async with ApiSessionLocal() as session, tenant_transaction_context(session, org_id):
        # Seed physical storage
        adapter = LocalStorageAdapter()
        await adapter.put_object(str(org_id), opaque_key, BytesIO(payload))

        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=opaque_key,
            server_computed_sha256="dummy_hash_worker_runtime",
            byte_size=len(payload),
            detected_mime_type="text/csv",
            storage_provider="LOCAL",
            reference_count=1,
        )
        session.add(stored_obj)
        await session.flush()

        doc = Document(
            id=doc_id,
            organization_id=org_id,
            uploaded_by_user_id=user_id,
            display_name="worker_test.csv",
            classification="CONFIDENTIAL",
            status="ACTIVE",
        )
        session.add(doc)
        await session.flush()

        doc_ver = DocumentVersion(
            id=version_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=obj_id,
            content_hash_sha256="dummy_hash_worker_runtime",
            file_size_bytes=len(payload),
            declared_mime_type="text/csv",
            detected_mime_type="text/csv",
            ingestion_status="QUEUED",
            extraction_status="PENDING",
        )
        session.add(doc_ver)

        job = IngestionJob(
            id=job_id,
            organization_id=org_id,
            document_version_id=version_id,
            status="QUEUED",
            max_attempts=3,
        )
        session.add(job)

        await session.commit()

    async with WorkerSessionLocal() as w_session:
        from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

        worker = IngestionWorker(w_session)
        worker_id = f"worker-rt-{uuid4().hex[:6]}"
        env = make_signed_envelope(job_id=job_id)
        outcome = await worker.claim_and_process_envelope(env, worker_id, secret_resolver=lambda k: TEST_HMAC_SECRET)

        assert outcome.claimed is True
        assert outcome.outcome_status == WorkerOutcomeStatus.PROCESSED_SUCCESS

    # Verify document processing state via ApiSessionLocal
    async with ApiSessionLocal() as v_session, tenant_transaction_context(v_session, org_id):
        ver_res = await v_session.execute(sqlalchemy.select(DocumentVersion).where(DocumentVersion.id == version_id))
        ver = ver_res.scalar_one()
        assert ver.ingestion_status in ["COMPLETED", "COMPLETED_WITH_WARNINGS", "EXTRACTED"]
