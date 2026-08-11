import asyncio
import logging
import uuid
from dataclasses import dataclass
from uuid import UUID

from app.db.session import ApiSessionLocal
from app.orchestration.engine import AnalysisOrchestratorEngine
from app.orchestration.exceptions import ClaimOwnershipLostException
from app.orchestration.tools.base import ExecutionContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("finance_intelligence_analysis_worker")

WORKER_ID = f"worker-analysis-{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class ClaimedAnalysisJob:
    job_id: UUID
    organization_id: UUID
    claim_token: UUID


async def claim_next_analysis_job(session: AsyncSession, worker_id: str) -> ClaimedAnalysisJob | None:
    """Execute claim_next_analysis_job procedure via db_api_user role in a short transaction."""
    res = await session.execute(
        text("SELECT job_id, organization_id, claim_token FROM public.claim_next_analysis_job(:w);"),
        {"w": worker_id},
    )
    row = res.fetchone()
    if row and row.job_id:
        return ClaimedAnalysisJob(
            job_id=row.job_id,
            organization_id=row.organization_id,
            claim_token=row.claim_token,
        )
    return None


async def recover_next_stale_analysis_job(session: AsyncSession, worker_id: str) -> ClaimedAnalysisJob | None:
    """Execute recover_next_stale_analysis_job procedure via db_api_user role in a short transaction."""
    res = await session.execute(
        text("SELECT job_id, organization_id, claim_token FROM public.recover_next_stale_analysis_job(:w);"),
        {"w": worker_id},
    )
    row = res.fetchone()
    if row and row.job_id:
        return ClaimedAnalysisJob(
            job_id=row.job_id,
            organization_id=row.organization_id,
            claim_token=row.claim_token,
        )
    return None


async def renew_analysis_job_lease(
    session: AsyncSession,
    job_id: UUID,
    claim_token: UUID,
    worker_id: str,
) -> bool:
    """Execute renew_analysis_job_lease procedure. Returns True if renewed, False if ownership lost."""
    res = await session.execute(
        text("SELECT public.renew_analysis_job_lease(:jid, :tok, :w);"),
        {"jid": job_id, "tok": claim_token, "w": worker_id},
    )
    renewed = res.scalar()
    return bool(renewed)


class AnalysisWorker:
    def __init__(
        self,
        worker_id: str = WORKER_ID,
        heartbeat_interval: float = 60.0,
        session_factory=ApiSessionLocal,
    ):
        self.worker_id = worker_id
        self.heartbeat_interval = heartbeat_interval
        self.session_factory = session_factory

    async def _lease_heartbeat_loop(
        self,
        job_id: UUID,
        claim_token: UUID,
        engine_task: asyncio.Task,
    ) -> None:
        """Background heartbeat renewal loop using separate short-lived sessions per pulse."""
        try:
            while not engine_task.done():
                await asyncio.sleep(self.heartbeat_interval)
                if engine_task.done():
                    break

                renewed = False
                try:
                    async with self.session_factory() as hb_session:
                        renewed = await renew_analysis_job_lease(hb_session, job_id, claim_token, self.worker_id)
                        await hb_session.commit()
                except Exception as ex:  # noqa: BLE001
                    logger.error(f"HEARTBEAT_LEASE_RENEWAL_EXCEPTION for job {job_id}: {ex}")
                    renewed = False

                if not renewed:
                    logger.warning(
                        f"HEARTBEAT_OWNERSHIP_LOST_OR_EXCEPTION for job {job_id}. Cancelling engine task fail-closed."
                    )
                    engine_task.cancel()
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            logger.error(f"HEARTBEAT_UNHANDLED_EXCEPTION: {e}")

    async def process_analysis_job(
        self,
        job_id: UUID,
        organization_id: UUID,
        claim_token: UUID,
    ) -> bool:
        """Run canonical engine execution for a claimed analysis job with an independent heartbeat lifecycle."""
        context = ExecutionContext(
            organization_id=organization_id,
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            role="WORKER",
            permissions={"analyses:run", "analyses:read"},
        )

        async def _run_engine():
            async with self.session_factory() as processing_session:
                engine = AnalysisOrchestratorEngine(processing_session, context)
                return await engine.execute_job(job_id, claim_token, self.worker_id)

        loop = asyncio.get_running_loop()
        engine_task = loop.create_task(_run_engine())
        heartbeat_task = loop.create_task(self._lease_heartbeat_loop(job_id, claim_token, engine_task))

        try:
            await engine_task
            logger.info(f"ANALYSIS_JOB_SUCCESS: {job_id}")
            return True
        except ClaimOwnershipLostException:
            logger.warning(f"ANALYSIS_JOB_OWNERSHIP_LOST: {job_id}")
            return False
        except asyncio.CancelledError:
            logger.warning(f"ANALYSIS_JOB_CANCELLED_BY_HEARTBEAT: {job_id}")
            return False
        except Exception as e:  # noqa: BLE001
            logger.error(f"ANALYSIS_JOB_FAILED_EXCEPTION: {job_id} - {e}")
            return False
        finally:
            if not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def run_once(self) -> bool:
        """Poll once for fresh job or safe stale recovery job and process."""
        claimed: ClaimedAnalysisJob | None = None

        # 1. Try fresh claim in a short transaction
        async with self.session_factory() as claim_session:
            claimed = await claim_next_analysis_job(claim_session, self.worker_id)
            await claim_session.commit()

        # 2. If no fresh job, try safe stale recovery in a short transaction
        if not claimed:
            async with self.session_factory() as claim_session:
                claimed = await recover_next_stale_analysis_job(claim_session, self.worker_id)
                await claim_session.commit()

        if not claimed:
            return False

        return await self.process_analysis_job(claimed.job_id, claimed.organization_id, claimed.claim_token)


async def run_analysis_worker_once(worker_id: str = WORKER_ID) -> bool:
    """Helper function to execute a single polling and processing turn."""
    worker = AnalysisWorker(worker_id=worker_id)
    return await worker.run_once()
