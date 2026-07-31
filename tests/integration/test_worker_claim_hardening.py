import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text

from services.api.app.db.session import ApiSessionLocal, WorkerSessionLocal
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.ingestion_job import IngestionJob
from services.api.app.models.stored_object import StoredObject
from services.worker.app.ingestion_worker import ClaimedJob, IngestionWorker, WorkerOutcomeStatus

OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    "postgresql://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test",
).replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.asyncio
async def test_legacy_single_param_overload_is_dropped_and_catalog_hardened():
    """Verify legacy single-param claim_next_ingestion_job(text) is dropped and full signature is restricted."""
    conn = await asyncpg.connect(OWNER_URL)

    # 1. Assert legacy single-parameter function overload does NOT exist
    legacy_count = await conn.fetchval("""
        SELECT count(*) 
        FROM pg_proc p 
        JOIN pg_namespace n ON n.oid = p.pronamespace 
        WHERE n.nspname = 'public' 
          AND p.proname = 'claim_next_ingestion_job' 
          AND pg_get_function_identity_arguments(p.oid) = 'text';
    """)
    assert legacy_count == 0, "CRITICAL SECURITY VIOLATION: Legacy single-param claim function overload still exists!"

    # 2. Assert EXACTLY ONE claim_next_ingestion_job function exists in public schema
    total_count = await conn.fetchval("""
        SELECT count(*) 
        FROM pg_proc p 
        JOIN pg_namespace n ON n.oid = p.pronamespace 
        WHERE n.nspname = 'public' AND p.proname = 'claim_ingestion_job';
    """)
    assert total_count == 1, f"Expected exactly 1 claim function in public schema, found {total_count}"

    # 3. Assert full signature attributes
    row = await conn.fetchrow("""
        SELECT 
            p.prosecdef,
            pg_get_userbyid(p.proowner) AS owner_name,
            p.proacl::text AS acl_text,
            array_to_string(p.proconfig, ',') AS proconfig_str,
            has_function_privilege('public', p.oid, 'EXECUTE') AS public_can_execute,
            has_function_privilege('db_ingestion_worker', p.oid, 'EXECUTE') AS worker_can_execute,
            has_function_privilege('db_bootstrap', p.oid, 'EXECUTE') AS bootstrap_can_execute,
            has_function_privilege('db_api_user', p.oid, 'EXECUTE') AS api_user_can_execute
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'claim_ingestion_job';
    """)

    await conn.close()

    assert row is not None
    assert row["prosecdef"] is True
    assert row["owner_name"] == "db_owner"
    assert row["public_can_execute"] is False, "PUBLIC MUST NOT have EXECUTE privilege!"
    assert row["worker_can_execute"] is True, "db_ingestion_worker MUST have EXECUTE privilege!"
    assert row["bootstrap_can_execute"] is False, "db_bootstrap MUST NOT have EXECUTE privilege!"
    assert row["api_user_can_execute"] is False, "db_api_user MUST NOT have EXECUTE privilege!"
    assert "search_path=public, pg_catalog, pg_temp" in str(row["proconfig_str"])


@pytest.mark.asyncio
async def test_legacy_single_param_call_fails():
    """Verify db_ingestion_worker attempting to call single-param function raises undefined_function error."""
    async with WorkerSessionLocal() as session:
        with pytest.raises(Exception) as exc_info:
            await session.execute(text("SELECT * FROM claim_next_ingestion_job('worker_1');"))
        assert "undefined_function" in str(exc_info.value).lower() or "function" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "invalid_worker_id,invalid_token",
    [
        ("", uuid4()),
        ("   ", uuid4()),
        ("x" * 300, uuid4()),
        ("valid_worker", None),
    ],
)
@pytest.mark.asyncio
async def test_claim_function_isolated_input_validation(invalid_worker_id, invalid_token):
    """Verify claim_next_ingestion_job rejects invalid worker_id or null claim_token in isolated transactions."""
    async with WorkerSessionLocal() as session:
        with pytest.raises(Exception) as exc_info:
            await session.execute(
                text("SELECT * FROM claim_next_ingestion_job(:worker_id, :claim_token);"),
                {"worker_id": invalid_worker_id, "claim_token": invalid_token},
            )
        await session.rollback()
        assert exc_info.value is not None


@pytest.mark.asyncio
async def test_stale_lease_recovery_concurrency():
    """Verify stale PARSING job is re-claimed by Worker B with new token, aborting Worker A updates."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    obj_id = uuid4()
    worker_a = "worker-a-stale"
    worker_b = "worker-b-fresh"
    token_a = uuid4()

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

    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )

        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=f"{uuid4().hex}.csv",
            server_computed_sha256="dummy_hash_lease",
            byte_size=10,
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
            display_name="lease_test.csv",
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
            content_hash_sha256="dummy_hash_lease",
            file_size_bytes=10,
            declared_mime_type="text/csv",
            detected_mime_type="text/csv",
            ingestion_status="QUEUED",
            extraction_status="PENDING",
        )
        session.add(doc_ver)

        # Create job pre-locked by Worker A with a stale locked_at timestamp (20 minutes ago)
        job = IngestionJob(
            id=job_id,
            organization_id=org_id,
            document_version_id=version_id,
            status="PARSING",
            current_attempt=1,
            max_attempts=3,
            locked_by=worker_a,
            claim_token=token_a,
            locked_at=datetime.now(UTC) - timedelta(minutes=20),
        )
        session.add(job)
        await session.commit()

    # Worker B claims stale job
    async with WorkerSessionLocal() as w_session_b:
        from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

        worker_obj_b = IngestionWorker(w_session_b)
        env_b = make_signed_envelope(job_id=job_id)
        outcome_b = await worker_obj_b.claim_and_process_envelope(
            env_b, worker_b, secret_resolver=lambda k: TEST_HMAC_SECRET
        )

        assert outcome_b.claimed is True

    # Worker A attempts to process with stale ClaimedJob
    async with WorkerSessionLocal() as w_session_a:
        await w_session_a.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )
        stale_claimed_job = ClaimedJob(
            job_id=job_id,
            organization_id=org_id,
            document_version_id=version_id,
            worker_id=worker_a,
            claim_token=token_a,
        )
        worker_obj_a = IngestionWorker(w_session_a)
        outcome_a = await worker_obj_a._process_claimed_job(stale_claimed_job)
        assert outcome_a.outcome_status == WorkerOutcomeStatus.STALE_CLAIM_ABORTED
