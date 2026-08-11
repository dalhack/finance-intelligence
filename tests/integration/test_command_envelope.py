import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import pytest
from app.db.session import ApiSessionLocal, WorkerSessionLocal
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.models.stored_object import StoredObject

from services.worker.app.command_envelope import IngestionCommandEnvelope, InvalidCommandEnvelopeError
from services.worker.app.ingestion_worker import IngestionWorker, WorkerOutcomeStatus

OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    "postgresql://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test",
).replace("+asyncpg", "")

HMAC_SECRET = "test_hmac_secret_key_rotation_32bytes"


def secret_resolver(key_id: str) -> str:
    return HMAC_SECRET


@pytest.mark.asyncio
async def test_claim_function_catalog_and_legacy_overloads_absent():
    """Verify ONLY claim_ingestion_job(uuid, text, uuid) exists in public schema and legacy claim_next_ingestion_job functions are dropped."""
    conn = await asyncpg.connect(OWNER_URL)

    # 1. Verify claim_ingestion_job signature identity
    proc_args = await conn.fetchval("""
        SELECT pg_get_function_identity_arguments(p.oid)
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'claim_ingestion_job';
    """)
    assert proc_args == "p_job_id uuid, p_worker_id text, p_claim_token uuid", (
        f"Expected exact signature 'p_job_id uuid, p_worker_id text, p_claim_token uuid', found '{proc_args}'"
    )

    # 2. Verify exactly 1 claim_ingestion_job exists
    count_new = await conn.fetchval("""
        SELECT count(*)
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'claim_ingestion_job';
    """)
    assert count_new == 1, f"Expected 1 claim_ingestion_job function, found {count_new}"

    # 3. Verify ALL legacy claim_next_ingestion_job overloads are completely DROPPED
    count_legacy = await conn.fetchval("""
        SELECT count(*)
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'claim_next_ingestion_job';
    """)
    assert count_legacy == 0, (
        f"CRITICAL SECURITY VIOLATION: Found {count_legacy} legacy claim_next_ingestion_job functions!"
    )

    await conn.close()


@pytest.mark.asyncio
async def test_command_envelope_lifecycle_and_persistent_replay_protection():
    """Verify HMAC command envelope validation, job claiming, and persistent replay protection via ingestion_command_logs."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    obj_id = uuid4()

    conn = await asyncpg.connect(OWNER_URL)
    await conn.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org Env {org_id}",
        f"org-env-{org_id}",
    )
    await conn.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn.close()

    async with ApiSessionLocal() as session:
        from app.db.tenant_context import tenant_transaction_context

        async with tenant_transaction_context(session, org_id):
            stored_obj = StoredObject(
                id=obj_id,
                organization_id=org_id,
                opaque_object_key=f"{uuid4().hex}.pdf",
                server_computed_sha256="dummy_hash_env",
                byte_size=500,
                detected_mime_type="application/pdf",
                storage_provider="LOCAL",
            )
            session.add(stored_obj)
            await session.flush()

            doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="env_test.pdf")
            session.add(doc)
            await session.flush()

            doc_ver = DocumentVersion(
                id=version_id,
                organization_id=org_id,
                document_id=doc_id,
                version_number=1,
                stored_object_id=obj_id,
                content_hash_sha256="dummy_hash_env",
                file_size_bytes=500,
                declared_mime_type="application/pdf",
                detected_mime_type="application/pdf",
                ingestion_status="QUEUED",
            )
            session.add(doc_ver)
            await session.flush()

            job = IngestionJob(id=job_id, organization_id=org_id, document_version_id=version_id, status="QUEUED")
            session.add(job)
            await session.commit()

    # 1. Valid Signed Envelope Claim Execution (v2.0.0, no organization_id field)
    env = IngestionCommandEnvelope(
        job_id=job_id,
        key_id="key-v1",
        schema_version="2.0.0",
    ).with_signature(HMAC_SECRET)

    async with WorkerSessionLocal() as worker_session:
        worker = IngestionWorker(worker_session)
        outcome = await worker.claim_and_process_envelope(env, "worker_env_1", secret_resolver=secret_resolver)
        assert outcome.claimed is True
        assert outcome.outcome_status in (
            WorkerOutcomeStatus.PROCESSED_SUCCESS,
            WorkerOutcomeStatus.PROCESSED_FAILED,
        )

    # 2. Replay Protection Test: Re-sending exact same envelope MUST be rejected atomically
    async with WorkerSessionLocal() as worker_session_2:
        worker_2 = IngestionWorker(worker_session_2)
        replay_outcome = await worker_2.claim_and_process_envelope(env, "worker_env_2", secret_resolver=secret_resolver)
        assert replay_outcome.claimed is False
        assert replay_outcome.outcome_status == WorkerOutcomeStatus.REJECTED
        assert replay_outcome.error_code == "COMMAND_REPLAYED"


@pytest.mark.asyncio
async def test_command_envelope_invalid_signature_and_clock_skew_fail_closed():
    """Verify invalid signature, expired timestamp, unsupported schema version, and clock skew fail-closed without DB query."""
    job_id = uuid4()

    # 1. Unsupported Schema Version 1.0.0 Rejection
    v1_env = IngestionCommandEnvelope(
        job_id=job_id,
        schema_version="1.0.0",
    ).with_signature(HMAC_SECRET)
    with pytest.raises(InvalidCommandEnvelopeError, match="COMMAND_SCHEMA_REJECTED"):
        v1_env.validate_envelope(secret_resolver=secret_resolver)

    # 2. Invalid Signature
    bad_sig_env = IngestionCommandEnvelope(
        job_id=job_id,
        signature="invalid_fake_hmac_hex_string_1234567890abcdef",
    )
    with pytest.raises(InvalidCommandEnvelopeError, match="COMMAND_SIGNATURE_INVALID"):
        bad_sig_env.validate_envelope(secret_resolver=secret_resolver)

    # 3. Expired Envelope
    past_time = datetime.now(UTC) - timedelta(minutes=20)
    expired_env = IngestionCommandEnvelope(
        job_id=job_id,
        issued_at=past_time - timedelta(minutes=15),
        expires_at=past_time,
    ).with_signature(HMAC_SECRET)

    with pytest.raises(InvalidCommandEnvelopeError, match="COMMAND_EXPIRED"):
        expired_env.validate_envelope(secret_resolver=secret_resolver)

    # 4. Clock Skew Exceeded (> 300 seconds in future)
    future_time = datetime.now(UTC) + timedelta(minutes=10)
    skewed_env = IngestionCommandEnvelope(
        job_id=job_id,
        issued_at=future_time,
        expires_at=future_time + timedelta(minutes=15),
    ).with_signature(HMAC_SECRET)

    with pytest.raises(InvalidCommandEnvelopeError, match="COMMAND_CLOCK_SKEW"):
        skewed_env.validate_envelope(secret_resolver=secret_resolver)
