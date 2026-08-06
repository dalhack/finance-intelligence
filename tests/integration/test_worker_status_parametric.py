import os
from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

import asyncpg
import pytest
from app.db.tenant_context import tenant_transaction_context
from sqlalchemy import select

from services.api.app.db.session import ApiSessionLocal, WorkerSessionLocal
from services.api.app.models.audit_event import AuditEvent
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.ingestion_job import IngestionAttempt, IngestionJob
from services.api.app.models.stored_object import StoredObject
from services.api.app.parsers.base import CanonicalExtractionOutput, ExtractionWarningItem
from services.api.app.parsers.registry import parser_registry
from services.api.app.storage.local_adapter import LocalStorageAdapter
from services.worker.app.ingestion_worker import IngestionWorker, WorkerOutcomeStatus

OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    "postgresql://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test",
).replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.parametrize(
    "parser_status,expected_target,expected_outcome,expected_audit_event",
    [
        ("COMPLETED", "COMPLETED", WorkerOutcomeStatus.PROCESSED_SUCCESS, "PARSING_COMPLETED"),
        (
            "COMPLETED_WITH_WARNINGS",
            "COMPLETED_WITH_WARNINGS",
            WorkerOutcomeStatus.PROCESSED_SUCCESS,
            "PARSING_COMPLETED",
        ),
        ("AWAITING_REVIEW", "AWAITING_REVIEW", WorkerOutcomeStatus.PROCESSED_REVIEW_REQUIRED, "REVIEW_REQUIRED"),
        ("REJECTED", "REJECTED", WorkerOutcomeStatus.PROCESSED_REJECTED, "PARSING_REJECTED"),
        ("FAILED", "FAILED", WorkerOutcomeStatus.PROCESSED_FAILED, "PARSING_FAILED"),
    ],
)
@pytest.mark.asyncio
async def test_canonical_5_status_parametric_matrix(
    monkeypatch, parser_status, expected_target, expected_outcome, expected_audit_event
):
    """Verify each of the 5 canonical parser statuses independently updates job, version, attempt, and audit records."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    obj_id = uuid4()
    opaque_key = f"{uuid4().hex}.mock"

    # Mock custom parser returning exact target status
    mock_parser = MagicMock()
    mock_parser.parse.return_value = CanonicalExtractionOutput(
        parser_name="MockStatusParser",
        parser_version="1.0.0",
        status=parser_status,
        quality_score=0.95 if parser_status != "FAILED" else 0.0,
        text_layer_present=True,
        pages=[],
        chunks=[],
        warnings=[ExtractionWarningItem(warning_code="STATUS_TEST", warning_message="Test warning")]
        if parser_status != "COMPLETED"
        else [],
    )
    monkeypatch.setattr(parser_registry, "get_parser", lambda mime: mock_parser)

    # Seed org and user
    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org {org_id}",
        f"org-{org_id}",
    )

    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    payload = b"dummy_mock_content"
    adapter = LocalStorageAdapter()
    await adapter.put_object(str(org_id), opaque_key, BytesIO(payload))

    async with ApiSessionLocal() as session, tenant_transaction_context(session, org_id):
        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=opaque_key,
            server_computed_sha256="dummy_hash_status_matrix",
            byte_size=len(payload),
            detected_mime_type="application/mock-status",
            storage_provider="LOCAL",
            reference_count=1,
        )
        session.add(stored_obj)
        await session.flush()

        doc = Document(
            id=doc_id,
            organization_id=org_id,
            uploaded_by_user_id=user_id,
            display_name="status_test.mock",
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
            content_hash_sha256="dummy_hash_status_matrix",
            file_size_bytes=len(payload),
            declared_mime_type="application/mock-status",
            detected_mime_type="application/mock-status",
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

    # Process via worker using real claim_and_process_next_job
    async with WorkerSessionLocal() as w_session:
        worker = IngestionWorker(w_session)
        worker_id = f"worker-test-{uuid4().hex[:6]}"
        from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

        env = make_signed_envelope(job_id=job_id)
        outcome = await worker.claim_and_process_envelope(env, worker_id, secret_resolver=lambda k: TEST_HMAC_SECRET)

        assert outcome.claimed is True
        assert outcome.outcome_status == expected_outcome
        assert outcome.job_id == job_id

    # Verify persisted DB records
    async with ApiSessionLocal() as v_session, tenant_transaction_context(v_session, org_id):
        job_obj = (await v_session.execute(select(IngestionJob).where(IngestionJob.id == job_id))).scalar_one()
        ver_obj = (
            await v_session.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
        ).scalar_one()
        att_obj = (
            await v_session.execute(select(IngestionAttempt).where(IngestionAttempt.ingestion_job_id == job_id))
        ).scalar_one()

        assert job_obj.status == expected_target
        assert ver_obj.ingestion_status == expected_target
        assert ver_obj.extraction_status == parser_status
        assert att_obj.status == expected_target

        audit_res = await v_session.execute(
            select(AuditEvent).where(
                AuditEvent.organization_id == org_id, AuditEvent.event_type == expected_audit_event
            )
        )
        assert len(audit_res.scalars().all()) >= 1


@pytest.mark.parametrize("unknown_status", ["EXTRACTED", "RANDOM_UNKNOWN_VALUE"])
@pytest.mark.asyncio
async def test_unknown_parser_status_fail_closed_matrix(monkeypatch, unknown_status):
    """Verify unknown or unmapped parser output statuses fail closed to FAILED with UNKNOWN_PARSER_STATUS."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    obj_id = uuid4()
    opaque_key = f"{uuid4().hex}.mock"

    mock_parser = MagicMock()
    mock_parser.parse.return_value = CanonicalExtractionOutput(
        parser_name="MockUnknownParser",
        parser_version="1.0.0",
        status=unknown_status,
        quality_score=0.5,
        text_layer_present=True,
        pages=[],
        chunks=[],
        warnings=[],
    )
    monkeypatch.setattr(parser_registry, "get_parser", lambda mime: mock_parser)

    # Seed org and user
    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org {org_id}",
        f"org-{org_id}",
    )

    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    payload = b"dummy_unknown_content"
    adapter = LocalStorageAdapter()
    await adapter.put_object(str(org_id), opaque_key, BytesIO(payload))

    async with ApiSessionLocal() as session, tenant_transaction_context(session, org_id):
        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=opaque_key,
            server_computed_sha256="dummy_hash_unknown_matrix",
            byte_size=len(payload),
            detected_mime_type="application/mock-unknown",
            storage_provider="LOCAL",
            reference_count=1,
        )
        session.add(stored_obj)
        await session.flush()

        doc = Document(
            id=doc_id,
            organization_id=org_id,
            uploaded_by_user_id=user_id,
            display_name="unknown_test.mock",
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
            content_hash_sha256="dummy_hash_unknown_matrix",
            file_size_bytes=len(payload),
            declared_mime_type="application/mock-unknown",
            detected_mime_type="application/mock-unknown",
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
        worker = IngestionWorker(w_session)
        worker_id = f"worker-test-{uuid4().hex[:6]}"
        from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

        env = make_signed_envelope(job_id=job_id)
        outcome = await worker.claim_and_process_envelope(env, worker_id, secret_resolver=lambda k: TEST_HMAC_SECRET)

        assert outcome.claimed is True
        assert outcome.outcome_status == WorkerOutcomeStatus.PROCESSED_FAILED
        assert outcome.error_code == "UNKNOWN_PARSER_STATUS"

    async with ApiSessionLocal() as v_session, tenant_transaction_context(v_session, org_id):
        job_obj = (await v_session.execute(select(IngestionJob).where(IngestionJob.id == job_id))).scalar_one()
        ver_obj = (
            await v_session.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
        ).scalar_one()
        attempts = (
            (await v_session.execute(select(IngestionAttempt).where(IngestionAttempt.ingestion_job_id == job_id)))
            .scalars()
            .all()
        )

        assert job_obj.status == "QUEUED"  # Under attempt < max_attempts retry policy
        assert ver_obj.ingestion_status == "QUEUED"
        assert ver_obj.extraction_status == "FAILED"

        assert len(attempts) >= 1
        assert attempts[-1].status == "FAILED"
        assert attempts[-1].error_code == "UNKNOWN_PARSER_STATUS"

        audit_res = await v_session.execute(
            select(AuditEvent).where(AuditEvent.organization_id == org_id, AuditEvent.event_type == "PARSING_FAILED")
        )
        assert len(audit_res.scalars().all()) >= 1
