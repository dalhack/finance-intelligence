import os
from uuid import uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.db.session import get_db_session
from services.api.app.dependencies import DEV_SYNTHETIC_ORG_ID, DEV_SYNTHETIC_USER_ID, get_execution_context
from services.api.app.main import app
from services.api.app.middleware.execution_context import ExecutionContext
from services.worker.app.ingestion_worker import IngestionWorker, WorkerOutcomeStatus

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")
RAW_WORKER_URL = os.environ.get("TEST_WORKER_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None
WORKER_URL = RAW_WORKER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_WORKER_URL else None

GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden"))

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_full_api_upload_finalize_worker_flow():
    org_id = uuid4()
    user_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;",
        str(org_id),
        f"Org {org_id}",
        f"org-{org_id}",
    )

    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    engine_api = create_async_engine(RAW_API_USER_URL)
    session_factory_api = async_sessionmaker(bind=engine_api, class_=AsyncSession, expire_on_commit=False)

    engine_worker = create_async_engine(RAW_WORKER_URL)
    session_factory_worker = async_sessionmaker(bind=engine_worker, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db_session():
        async with session_factory_api() as session:
            await session.execute(
                text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(org_id)},
            )
            yield session

    async def override_get_execution_context():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=uuid4(),
            roles=["ANALYST"],
            permissions=["documents:upload", "documents:finalize", "documents:read", "ingestion:read", "read_facts"],
            request_id="req-123",
            correlation_id="corr-123",
            authentication_method="test",
            environment="development",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            xlsx_path = os.path.join(GOLDEN_DIR, "sample_ledger.xlsx")
            with open(xlsx_path, "rb") as f:  # noqa: ASYNC230
                xlsx_bytes = f.read()

            res_upload = await client.post(
                "/api/v1/documents/uploads",
                data={"display_name": "sample_ledger.xlsx", "classification": "CONFIDENTIAL"},
                files={
                    "file": (
                        "sample_ledger.xlsx",
                        xlsx_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
            assert res_upload.status_code == 201
            session_id = res_upload.json()["session_id"]

            res_finalize = await client.post(f"/api/v1/documents/uploads/{session_id}/finalize")
            assert res_finalize.status_code == 200
            fin_data = res_finalize.json()
            doc_id = fin_data["document_id"]
            doc_version_id = fin_data["document_version_id"]
            _job_id = fin_data["ingestion_job_id"]

            res_status = await client.get(f"/api/v1/documents/{doc_id}/versions/{doc_version_id}/status")
            assert res_status.status_code == 200
            assert res_status.json()["ingestion_status"] == "QUEUED"

            async with session_factory_worker() as worker_session:
                from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

                worker = IngestionWorker(worker_session)
                worker_id = f"worker-test-{uuid4().hex[:6]}"
                env = make_signed_envelope(job_id=_job_id)
                outcome = await worker.claim_and_process_envelope(
                    env, worker_id, secret_resolver=lambda k: TEST_HMAC_SECRET
                )

                assert outcome.claimed is True
                assert outcome.outcome_status == WorkerOutcomeStatus.PROCESSED_SUCCESS

            res_status_after = await client.get(f"/api/v1/documents/{doc_id}/versions/{doc_version_id}/status")
            assert res_status_after.status_code == 200
            assert res_status_after.json()["ingestion_status"] in [
                "COMPLETED",
                "COMPLETED_WITH_WARNINGS",
                "EXTRACTED",
            ]

    finally:
        app.dependency_overrides.clear()
        await engine_api.dispose()
        await engine_worker.dispose()


@pytest.mark.asyncio
async def test_api_upload_unsupported_file_type_returns_415():
    org_id = DEV_SYNTHETIC_ORG_ID
    user_id = DEV_SYNTHETIC_USER_ID

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;",
        str(org_id),
        f"Org {org_id}",
        f"org-{org_id}",
    )
    await conn_owner.close()

    engine_api = create_async_engine(RAW_API_USER_URL)
    session_factory_api = async_sessionmaker(bind=engine_api, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db_session():
        async with session_factory_api() as session:
            await session.execute(
                text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(org_id)},
            )
            yield session

    async def override_get_execution_context():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=uuid4(),
            roles=["ANALYST"],
            permissions=["documents:upload", "documents:finalize", "documents:read", "ingestion:read", "read_facts"],
            request_id="req-123",
            correlation_id="corr-123",
            authentication_method="test",
            environment="development",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res_upload = await client.post(
                "/api/v1/documents/uploads",
                data={"display_name": "malicious_script.sh", "classification": "CONFIDENTIAL"},
                files={"file": ("malicious_script.sh", b"echo 'malware'", "application/x-sh")},
            )
            assert res_upload.status_code == 415
    finally:
        app.dependency_overrides.clear()
        await engine_api.dispose()
