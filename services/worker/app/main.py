import asyncio
import logging
import os
import signal
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from services.api.app.db.session import WorkerSessionLocal
from services.api.app.models.ingestion_job import IngestionJob
from services.worker.app.command_envelope import IngestionCommandEnvelope
from services.worker.app.ingestion_worker import IngestionWorker, WorkerOutcomeStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finance_intelligence_worker")

WORKER_ID = f"worker-node-{uuid.uuid4().hex[:8]}"


async def fetch_and_sign_next_envelope(session) -> IngestionCommandEnvelope | None:
    """Fetch next queued job_id from DB and sign v2.0.0 command envelope using environment secret."""
    secret = os.environ.get("INGESTION_HMAC_SECRET")
    if not secret:
        return None

    stale_threshold = datetime.now(UTC) - timedelta(minutes=15)
    stmt = (
        select(IngestionJob.id)
        .where(
            (IngestionJob.status == "QUEUED")
            | ((IngestionJob.status == "PARSING") & (IngestionJob.locked_at < stale_threshold))
        )
        .limit(1)
    )
    res = await session.execute(stmt)
    row = res.fetchone()
    if not row or not row[0]:
        return None

    env = IngestionCommandEnvelope(job_id=row[0], schema_version="2.0.0")
    return env.with_signature(secret)


async def run_worker_loop(run_once: bool = False, poll_interval: float = 1.0, max_backoff: float = 5.0) -> int:
    """Run real ingestion worker loop using WorkerSessionLocal (db_ingestion_worker role)."""
    logger.info("WORKER_STARTED")
    processed_count = 0
    current_backoff = poll_interval
    shutdown_requested = False

    def handle_signal(sig, frame):
        nonlocal shutdown_requested
        logger.info("WORKER_STOP_SIGNAL_RECEIVED")
        shutdown_requested = True

    if sys.platform != "win32":
        try:
            import functools

            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, functools.partial(handle_signal, sig, None))

        except NotImplementedError:
            pass

    while not shutdown_requested:
        try:
            async with WorkerSessionLocal() as session:
                worker = IngestionWorker(session)
                envelope = await fetch_and_sign_next_envelope(session)
                if not envelope:
                    if run_once:
                        logger.info("WORKER_NO_QUEUED_JOBS_FOUND")
                        break
                    await asyncio.sleep(current_backoff)
                    current_backoff = min(current_backoff * 1.5, max_backoff)
                    continue

                outcome = await worker.claim_and_process_envelope(envelope, WORKER_ID)
                if outcome.claimed:
                    if outcome.outcome_status == WorkerOutcomeStatus.PROCESSED_SUCCESS:
                        processed_count += 1
                        current_backoff = poll_interval
                        logger.info("JOB_PROCESSED_SUCCESS")
                    else:
                        logger.info("JOB_PROCESSED_NON_SUCCESS")
                    if run_once:
                        break
                else:
                    if run_once:
                        logger.info("WORKER_NO_QUEUED_JOBS_FOUND")
                        break
                    await asyncio.sleep(current_backoff)
                    current_backoff = min(current_backoff * 1.5, max_backoff)

        except asyncio.CancelledError:
            logger.info("WORKER_LOOP_CANCELLED")
            break
        except Exception:
            logger.error("WORKER_LOOP_EXCEPTION_ENCOUNTERED")

            if run_once:
                raise
            await asyncio.sleep(current_backoff)

    logger.info("WORKER_STOPPED")
    return processed_count


if __name__ == "__main__":
    asyncio.run(run_worker_loop())
