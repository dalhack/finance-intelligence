import asyncio
import os
from uuid import uuid4

import asyncpg
import pytest
from app.db.tenant_context import tenant_transaction_context
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.document import Document
from services.api.app.models.document_chunk import DocumentChunk
from services.api.app.models.document_page import DocumentPage
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.extraction_result import ExtractionResult
from services.api.app.models.ingestion_job import IngestionAttempt, IngestionJob
from services.api.app.models.stored_object import StoredObject
from services.worker.app.ingestion_worker import IngestionWorker

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_WORKER_URL = os.environ.get("TEST_WORKER_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
WORKER_URL = RAW_WORKER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_WORKER_URL else None

GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden"))

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_worker_concurrency_strict_invariants():
    org_id = uuid4()
    user_id = uuid4()

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

    engine_owner = create_async_engine(RAW_OWNER_URL)
    session_factory_owner = async_sessionmaker(bind=engine_owner, class_=AsyncSession, expire_on_commit=False)

    engine_worker = create_async_engine(RAW_WORKER_URL)
    session_factory_worker = async_sessionmaker(bind=engine_worker, class_=AsyncSession, expire_on_commit=False)

    # Seed Document and QUEUED Job via Owner Engine
    job_id = uuid4()
    async with session_factory_owner() as setup_session, tenant_transaction_context(setup_session, org_id):
        csv_path = os.path.join(GOLDEN_DIR, "sample_bom.csv")
        with open(csv_path, "rb") as f:  # noqa: ASYNC230
            csv_bytes = f.read()

        adapter = __import__(
            "services.api.app.storage.local_adapter", fromlist=["LocalStorageAdapter"]
        ).LocalStorageAdapter()
        opaque_key = f"{org_id}/{job_id}.bin"
        await adapter.put_object(str(org_id), opaque_key, __import__("io").BytesIO(csv_bytes))

        stored_obj = StoredObject(
            id=uuid4(),
            organization_id=org_id,
            opaque_object_key=opaque_key,
            byte_size=len(csv_bytes),
            server_computed_sha256="test_worker_strict_conc_sha256",
            detected_mime_type="text/csv",
        )
        setup_session.add(stored_obj)
        await setup_session.flush()

        doc = Document(id=uuid4(), organization_id=org_id, uploaded_by_user_id=user_id, display_name="sample_bom.csv")
        setup_session.add(doc)
        await setup_session.flush()

        doc_ver = DocumentVersion(
            id=uuid4(),
            organization_id=org_id,
            document_id=doc.id,
            stored_object_id=stored_obj.id,
            version_number=1,
            content_hash_sha256="test_worker_strict_conc_sha256",
            file_size_bytes=len(csv_bytes),
            declared_mime_type="text/csv",
            detected_mime_type="text/csv",
            ingestion_status="QUEUED",
        )

        setup_session.add(doc_ver)
        await setup_session.flush()

        job = IngestionJob(
            id=job_id,
            organization_id=org_id,
            document_version_id=doc_ver.id,
            status="QUEUED",
        )
        setup_session.add(job)
        await setup_session.commit()

    # Concurrent worker execution
    async def worker_task(w_id: str):
        async with session_factory_worker() as w_session:
            from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

            worker = IngestionWorker(w_session)
            env = make_signed_envelope(job_id=job_id)
            return await worker.claim_and_process_envelope(env, w_id, secret_resolver=lambda k: TEST_HMAC_SECRET)

    results = await asyncio.gather(worker_task("worker-conc-1"), worker_task("worker-conc-2"))
    assert sum(1 for r in results if r.claimed) == 1
    assert sum(1 for r in results if not r.claimed) == 1

    # Invariant Verification on DB
    async with session_factory_owner() as v_session, tenant_transaction_context(v_session, org_id):
        # Invariant 1: Exactly 1 IngestionAttempt
        att_res = await v_session.execute(select(IngestionAttempt).where(IngestionAttempt.ingestion_job_id == job_id))
        attempts = att_res.scalars().all()
        assert len(attempts) == 1
        assert attempts[0].attempt_number == 1

        # Invariant 2: Exactly 1 ExtractionResult
        ext_res = await v_session.execute(
            select(ExtractionResult).where(ExtractionResult.document_version_id == doc_ver.id)
        )
        results_list = ext_res.scalars().all()
        assert len(results_list) == 1

        # Invariant 3: Unique chunk indexes, no duplicate chunks
        chunk_res = await v_session.execute(
            select(DocumentChunk.chunk_index).where(DocumentChunk.document_version_id == doc_ver.id)
        )
        chunk_indexes = chunk_res.scalars().all()
        assert len(chunk_indexes) == len(set(chunk_indexes))

        # Invariant 4: No duplicate DocumentPage page_numbers
        page_res = await v_session.execute(
            select(DocumentPage.page_number).where(DocumentPage.document_version_id == doc_ver.id)
        )
        pages = page_res.scalars().all()
        assert len(pages) == len(set(pages))

        # Invariant 5: Re-running completed job returns False and creates 0 new attempt records
        async with session_factory_worker() as w_again_session:
            from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

            worker_again = IngestionWorker(w_again_session)
            env_again = make_signed_envelope(job_id=job_id)
            rerun_result = await worker_again.claim_and_process_envelope(
                env_again, "worker-conc-rerun", secret_resolver=lambda k: TEST_HMAC_SECRET
            )
            assert rerun_result.claimed is False

        att_again_res = await v_session.execute(
            select(func.count(IngestionAttempt.id)).where(IngestionAttempt.ingestion_job_id == job_id)
        )
        assert att_again_res.scalar() == 1

    await engine_owner.dispose()
    await engine_worker.dispose()
