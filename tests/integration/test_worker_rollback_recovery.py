import os
from uuid import uuid4

import asyncpg
import pytest
from app.db.session import ApiSessionLocal, WorkerSessionLocal
from app.db.tenant_context import tenant_transaction_context
from app.models.audit_event import AuditEvent
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionAttempt, IngestionJob
from app.models.stored_object import StoredObject
from sqlalchemy import select

from services.worker.app.ingestion_worker import IngestionWorker, WorkerOutcomeStatus

OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    "postgresql://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test",
).replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.asyncio
async def test_worker_rollback_recovery_retry_and_audit():
    """Verify that when processing fails, worker transaction rolls back cleanly."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    obj_id = uuid4()
    opaque_key = f"nonexistent_keys/{uuid4().hex}.csv"

    # Seed org and user
    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        "Rollback Test Org",
        f"org-{org_id}",
    )

    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    # Seed physical storage with non-existent key to force adapter error during parse
    payload = b"dummy_content"

    async with ApiSessionLocal() as session, tenant_transaction_context(session, org_id):
        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=opaque_key,
            server_computed_sha256="dummy_hash_rollback",
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
            display_name="rollback_test.csv",
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
            content_hash_sha256="dummy_hash_rollback",
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

    # Process job via WorkerSessionLocal (expected to trigger exception and rollback recovery)
    async with WorkerSessionLocal() as w_session, tenant_transaction_context(w_session, org_id):
        from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

        worker = IngestionWorker(w_session)
        worker_id = f"worker-rollback-{uuid4().hex[:6]}"
        env = make_signed_envelope(job_id=job_id)
        outcome = await worker.claim_and_process_envelope(env, worker_id, secret_resolver=lambda k: TEST_HMAC_SECRET)

        assert outcome.claimed is True
        assert outcome.outcome_status == WorkerOutcomeStatus.PROCESSED_FAILED

    # Verify post-rollback state via ApiSessionLocal
    async with ApiSessionLocal() as v_session, tenant_transaction_context(v_session, org_id):
        job_obj = (await v_session.execute(select(IngestionJob).where(IngestionJob.id == job_id))).scalar_one()
        assert job_obj.status == "QUEUED"
        assert job_obj.current_attempt == 1

        attempts = (
            (await v_session.execute(select(IngestionAttempt).where(IngestionAttempt.ingestion_job_id == job_id)))
            .scalars()
            .all()
        )
        assert len(attempts) >= 1
        assert attempts[-1].status == "FAILED"
        assert attempts[-1].error_code is not None

        audit_events = (
            (
                await v_session.execute(
                    select(AuditEvent).where(
                        AuditEvent.organization_id == org_id, AuditEvent.event_type == "PARSING_FAILED"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_events) >= 1
