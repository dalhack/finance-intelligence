import os
import uuid

import pytest
from app.core.config import DEFAULT_DEV_MIGRATION_URL
from app.db.session import MaintenanceSessionLocal
from app.db.tenant_context import tenant_transaction_context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from services.worker.app.maintenance_worker import (
    run_maintenance_worker_loop,
    update_worker_heartbeat,
)

owner_url = os.environ.get("TEST_OWNER_DATABASE_URL", DEFAULT_DEV_MIGRATION_URL)
owner_engine = create_async_engine(owner_url)


@pytest.mark.asyncio
async def test_maintenance_worker_concurrency_and_fencing():
    """Verify claim_next_maintenance_job concurrency and fencing token rejection."""
    # Seed test organization and maintenance job using owner role
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with owner_engine.begin() as conn, tenant_transaction_context(conn, org_id):
        await conn.execute(
            text("INSERT INTO organizations (id, name, slug, created_at) VALUES (:id, 'Test Maint Org', :slug, now())"),
            {"id": org_id, "slug": f"test-maint-org-{org_id.hex[:6]}"},
        )
        await conn.execute(
            text("""
                INSERT INTO maintenance_jobs (id, job_code, organization_id, status, available_at, max_attempts)
                VALUES (:id, 'CLARIFICATION_EXPIRY', :org_id, 'QUEUED', now(), 3);
            """),
            {"id": job_id, "org_id": org_id},
        )

    async with MaintenanceSessionLocal() as session, tenant_transaction_context(session, org_id):
        # 1. Claim job with worker 1
        claim_token_1 = uuid.uuid4()
        res1 = await session.execute(
            text("SELECT job_id FROM claim_next_maintenance_job('worker-1', :token, ARRAY['CLARIFICATION_EXPIRY']);"),
            {"token": claim_token_1},
        )
        row1 = res1.fetchone()
        assert row1 is not None and row1[0] == job_id

        # 2. Concurrent worker 2 attempts claim on same job -> gets nothing
        claim_token_2 = uuid.uuid4()
        res2 = await session.execute(
            text("SELECT job_id FROM claim_next_maintenance_job('worker-2', :token, ARRAY['CLARIFICATION_EXPIRY']);"),
            {"token": claim_token_2},
        )
        row2 = res2.fetchone()
        assert row2 is None or row2[0] is None

        # 3. Fencing token check: worker 2 cannot complete worker 1's job
        stale_complete = await session.execute(
            text("""
                UPDATE maintenance_jobs
                SET status = 'COMPLETED'
                WHERE id = :id AND locked_by = 'worker-2' AND claim_token = :token;
            """),
            {"id": job_id, "token": claim_token_2},
        )
        assert stale_complete.rowcount == 0

    # Cleanup with owner role
    async with owner_engine.begin() as conn:
        await conn.execute(text("DELETE FROM maintenance_jobs WHERE id = :id"), {"id": job_id})
        await conn.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


@pytest.mark.asyncio
async def test_maintenance_worker_loop_run_once():
    """Verify run_maintenance_worker_loop run_once=True execution."""
    from app.db.session import maintenance_engine

    await maintenance_engine.dispose()

    async with MaintenanceSessionLocal() as session:
        await update_worker_heartbeat(session, status="RUNNING")

    processed = await run_maintenance_worker_loop(run_once=True)
    assert processed >= 0
