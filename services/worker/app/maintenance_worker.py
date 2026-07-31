import asyncio
import functools
import logging
import signal
import sys
import uuid
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.db.session import MaintenanceSessionLocal
from services.api.app.services.clarification_service import ClarificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finance_intelligence_maintenance_worker")

WORKER_INSTANCE_KEY = f"maintenance-node-{uuid4().hex[:8]}"
ALLOWED_JOB_CODES = ["CLARIFICATION_EXPIRY", "ANALYSIS_LEASE_RECOVERY"]
SYSTEM_MAINTENANCE_USER_ID = UUID("00000000-0000-0000-0000-000000000000")


class MaintenanceOutcomeStatus(str, Enum):
    PROCESSED_SUCCESS = "PROCESSED_SUCCESS"
    PROCESSED_FAILED = "PROCESSED_FAILED"
    NO_JOBS_FOUND = "NO_JOBS_FOUND"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


async def update_worker_heartbeat(session: AsyncSession, status: str = "RUNNING") -> None:
    """Update maintenance_worker_heartbeats table for worker readiness checking."""
    now = datetime.now(UTC)
    stmt = text("""
        INSERT INTO maintenance_worker_heartbeats (worker_instance_key, worker_role, started_at, last_seen_at, status, contract_version)
        VALUES (:wkey, 'db_maintenance_worker', :now, :now, :status, '1.0.0')
        ON CONFLICT (worker_instance_key) DO UPDATE
        SET last_seen_at = EXCLUDED.last_seen_at,
            status = EXCLUDED.status;
    """)
    await session.execute(stmt, {"wkey": WORKER_INSTANCE_KEY, "now": now, "status": status})
    await session.commit()


async def process_clarification_expiry(session: AsyncSession, org_id: str, target_entity_id: str | None) -> bool:
    """Execute CLARIFICATION_EXPIRY job code with tenant re-binding."""
    # 1. Bind tenant context
    await session.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": org_id})

    # 2. Expire open clarifications due for expiry
    clar_service = ClarificationService(
        session,
        organization_id=UUID(org_id),
        user_id=SYSTEM_MAINTENANCE_USER_ID,
    )
    expired_records = await clar_service.expire_due_clarifications()

    if expired_records:
        logger.info("CLARIFICATION_EXPIRED")
    return True


async def process_analysis_lease_recovery(session: AsyncSession, org_id: str, target_entity_id: str | None) -> bool:
    """Execute ANALYSIS_LEASE_RECOVERY job code with tenant re-binding and fencing protection."""
    # 1. Bind tenant context
    await session.execute(text("SELECT set_config('app.current_organization_id', :org_id, true)"), {"org_id": org_id})

    stale_threshold = datetime.now(UTC)
    stmt = text("""
        SELECT id, status, locked_by, attempt_count
        FROM analysis_jobs
        WHERE organization_id = :org_id
          AND status IN ('UNDERSTANDING', 'PLANNING', 'EXECUTING')
          AND lease_expires_at < :now
        FOR UPDATE SKIP LOCKED
        LIMIT 5;
    """)
    res = await session.execute(stmt, {"org_id": org_id, "now": stale_threshold})
    rows = res.fetchall()

    for row in rows:
        job_id = row[0]
        attempt_count = row[3] or 0

        if attempt_count >= 3:
            # Transition to FAILED via state machine
            update_stmt = text("""
                UPDATE analysis_jobs
                SET status = 'FAILED',
                    error_code = 'LEASE_TIMEOUT_EXCEEDED',
                    lease_expires_at = NULL,
                    updated_at = now()
                WHERE id = :job_id AND organization_id = :org_id;
            """)
            await session.execute(update_stmt, {"job_id": job_id, "org_id": org_id})
            logger.info("ANALYSIS_LEASE_FAILED")
        else:
            # Re-queue stale job
            update_stmt = text("""
                UPDATE analysis_jobs
                SET status = 'QUEUED',
                    locked_by = NULL,
                    locked_at = NULL,
                    lease_expires_at = NULL,
                    updated_at = now()
                WHERE id = :job_id AND organization_id = :org_id;
            """)
            await session.execute(update_stmt, {"job_id": job_id, "org_id": org_id})
            logger.info("ANALYSIS_LEASE_RECOVERED")

    await session.commit()
    return True


async def claim_and_process_maintenance_job(session: AsyncSession) -> MaintenanceOutcomeStatus:
    """Claim next available maintenance job using SECURITY DEFINER claim_next_maintenance_job function."""
    claim_token = uuid.uuid4()
    claim_stmt = text("""
        SELECT job_id, job_code, organization_id, target_entity_id, attempt_count
        FROM claim_next_maintenance_job(:wkey, :token, :codes);
    """)

    res = await session.execute(
        claim_stmt,
        {
            "wkey": WORKER_INSTANCE_KEY,
            "token": claim_token,
            "codes": ALLOWED_JOB_CODES,
        },
    )
    row = res.fetchone()

    if not row or not row[0]:
        return MaintenanceOutcomeStatus.NO_JOBS_FOUND

    job_id = row[0]
    job_code = row[1]
    org_id = str(row[2])
    target_entity_id = row[3]

    logger.info("MAINTENANCE_JOB_CLAIMED")

    success = False
    error_code = None

    try:
        if job_code == "CLARIFICATION_EXPIRY":
            success = await process_clarification_expiry(session, org_id, target_entity_id)
        elif job_code == "ANALYSIS_LEASE_RECOVERY":
            success = await process_analysis_lease_recovery(session, org_id, target_entity_id)
        else:
            return MaintenanceOutcomeStatus.NOT_IMPLEMENTED
    except Exception:  # noqa: BLE001
        logger.error("MAINTENANCE_JOB_FAILED")
        error_code = "HANDLER_EXCEPTION"
        success = False

    # Complete or fail maintenance_job with fencing protection
    now = datetime.now(UTC)
    if success:
        finish_stmt = text("""
            UPDATE maintenance_jobs
            SET status = 'COMPLETED',
                completed_at = :now
            WHERE id = :job_id AND locked_by = :wkey AND claim_token = :token;
        """)
        await session.execute(
            finish_stmt, {"now": now, "job_id": job_id, "wkey": WORKER_INSTANCE_KEY, "token": claim_token}
        )
        await session.commit()
        logger.info("MAINTENANCE_JOB_COMPLETED")
        return MaintenanceOutcomeStatus.PROCESSED_SUCCESS
    else:
        fail_stmt = text("""
            UPDATE maintenance_jobs
            SET status = 'FAILED',
                last_error_code = :err
            WHERE id = :job_id AND locked_by = :wkey AND claim_token = :token;
        """)
        await session.execute(
            fail_stmt,
            {
                "err": error_code or "EXECUTION_FAILED",
                "job_id": job_id,
                "wkey": WORKER_INSTANCE_KEY,
                "token": claim_token,
            },
        )
        await session.commit()
        return MaintenanceOutcomeStatus.PROCESSED_FAILED


async def run_maintenance_worker_loop(
    run_once: bool = False,
    poll_interval: float = 1.0,
    max_backoff: float = 5.0,
) -> int:
    """Run real maintenance worker loop using MaintenanceSessionLocal (db_maintenance_worker role)."""
    logger.info("MAINTENANCE_WORKER_STARTED")
    processed_count = 0
    current_backoff = poll_interval
    shutdown_requested = False

    def handle_signal(sig, frame):
        nonlocal shutdown_requested
        logger.info("MAINTENANCE_WORKER_DRAINING")
        shutdown_requested = True

    if sys.platform != "win32":
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, functools.partial(handle_signal, sig, None))
        except NotImplementedError:
            pass

    while not shutdown_requested:
        try:
            async with MaintenanceSessionLocal() as session:
                await update_worker_heartbeat(session, status="RUNNING")
                outcome = await claim_and_process_maintenance_job(session)

                if outcome == MaintenanceOutcomeStatus.PROCESSED_SUCCESS:
                    processed_count += 1
                    current_backoff = poll_interval
                    if run_once:
                        break
                elif outcome == MaintenanceOutcomeStatus.NO_JOBS_FOUND:
                    if run_once:
                        break
                    await asyncio.sleep(current_backoff)
                    current_backoff = min(current_backoff * 1.5, max_backoff)
                else:
                    if run_once:
                        break
                    await asyncio.sleep(current_backoff)

        except asyncio.CancelledError:
            logger.info("MAINTENANCE_WORKER_STOPPED")
            break
        except Exception:
            logger.error("MAINTENANCE_WORKER_FAILED")
            if run_once:
                raise
            await asyncio.sleep(current_backoff)

    logger.info("MAINTENANCE_WORKER_STOPPED")
    return processed_count


if __name__ == "__main__":
    asyncio.run(run_maintenance_worker_loop())
