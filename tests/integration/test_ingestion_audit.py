import os
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy import select, text

from services.api.app.db.session import ApiSessionLocal, WorkerSessionLocal, get_db_session
from services.api.app.dependencies import get_execution_context
from services.api.app.main import app
from services.api.app.middleware.execution_context import ExecutionContext
from services.api.app.models.audit_event import AuditEvent
from services.api.app.services.audit_service import SENSITIVE_KEYS
from services.worker.app.ingestion_worker import IngestionWorker, WorkerOutcomeStatus

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")
RAW_WORKER_URL = os.environ.get("TEST_WORKER_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None
WORKER_URL = RAW_WORKER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_WORKER_URL else None


@pytest.mark.asyncio
async def test_audit_full_lifecycle_event_trail_and_sanitization():
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
    await conn_owner.close()

    async def override_get_db_session():
        async with ApiSessionLocal() as session:
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
            permissions=["documents:upload", "documents:finalize", "documents:read", "ingestion:read"],
            request_id="req-audit-123",
            correlation_id="corr-audit-123",
            authentication_method="test",
            environment="development",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = b"header1,header2\naudit_test_cell,12345"

            # 1. Upload API call (triggers UPLOAD_INITIATED)
            up = await client.post(
                "/api/v1/documents/uploads",
                data={"display_name": "secret_statement.csv", "classification": "CONFIDENTIAL"},
                files={"file": ("secret_statement.csv", payload, "text/csv")},
            )
            assert up.status_code == 201
            session_id = up.json()["session_id"]

            fin = await client.post(f"/api/v1/documents/uploads/{session_id}/finalize")
            assert fin.status_code == 200
            assert fin.json()["ingestion_job_id"] is not None

            # 3. Worker process job (triggers PARSING_STARTED, PARSING_COMPLETED) using WorkerSessionLocal
            async with WorkerSessionLocal() as w_session:
                await w_session.execute(
                    text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                    {"org_id": str(org_id)},
                )
                from tests.fixtures.envelope_factory import TEST_HMAC_SECRET, make_signed_envelope

                worker = IngestionWorker(w_session)
                worker_id = f"worker-audit-{uuid4().hex[:6]}"
                job_id = UUID(fin.json()["ingestion_job_id"])
                env = make_signed_envelope(job_id=job_id)

                outcome = await worker.claim_and_process_envelope(
                    env, worker_id, secret_resolver=lambda k: TEST_HMAC_SECRET
                )
                assert outcome.claimed is True
                assert outcome.outcome_status == WorkerOutcomeStatus.PROCESSED_SUCCESS

            # 4. Verify persistent audit log sequence in DB via ApiSessionLocal
            async with ApiSessionLocal() as v_session:
                await v_session.execute(
                    text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                    {"org_id": str(org_id)},
                )

                events_res = await v_session.execute(
                    select(AuditEvent).where(AuditEvent.organization_id == org_id).order_by(AuditEvent.created_at.asc())
                )
                events = events_res.scalars().all()
                event_types = [e.event_type for e in events]

                assert "UPLOAD_INITIATED" in event_types
                assert "SESSION_STATE_FINALIZED" in event_types
                assert "FINALIZE_COMPLETED" in event_types
                assert "INGESTION_QUEUED" in event_types
                assert "PARSING_STARTED" in event_types
                assert "PARSING_COMPLETED" in event_types

                # Assert payload sanitization across all recorded audit events
                for e in events:
                    summary = e.payload_summary
                    for sensitive_key in SENSITIVE_KEYS:
                        assert sensitive_key not in summary, (
                            f"Sensitive key '{sensitive_key}' found in audit event {e.event_type}"
                        )

            # 5. Tenant isolation check: Tenant B cannot see Tenant A's audit events
            async with ApiSessionLocal() as v_session_b:
                await v_session_b.execute(
                    text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                    {"org_id": str(org_b)},
                )
                events_b = (
                    (await v_session_b.execute(select(AuditEvent).where(AuditEvent.organization_id == org_id)))
                    .scalars()
                    .all()
                )
                assert len(events_b) == 0

    finally:
        app.dependency_overrides.clear()
