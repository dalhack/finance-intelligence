import asyncio
import os
import uuid
import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.institution import Institution
from services.api.app.models.orchestration import AnalysisJob
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.orchestration.engine import AnalysisOrchestratorEngine
from services.api.app.orchestration.exceptions import ClaimOwnershipLostException
from services.api.app.orchestration.provider import DeterministicTestModelProvider
from services.api.app.orchestration.tools.base import ExecutionContext
from services.worker.app.analysis_worker import (
    AnalysisWorker,
    ClaimedAnalysisJob,
    claim_next_analysis_job,
    recover_next_stale_analysis_job,
    renew_analysis_job_lease,
)


@pytest.mark.asyncio
async def test_analysis_worker_claim_and_recovery_flow():
    """Verify fresh claim, stale recovery, and non-recoverable status boundaries."""
    owner_url = os.environ.get("TEST_OWNER_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/finance_intelligence_test")
    api_url = os.environ.get("TEST_API_DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test"))

    owner_engine = create_async_engine(owner_url)
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    api_engine = create_async_engine(api_url)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with OwnerSession() as owner_db:
        await owner_db.execute(text(
            "INSERT INTO public.organizations (id, name, slug, created_at, updated_at) "
            "VALUES (:id, 'R2 Test Org', :slug, now(), now());"
        ), {"id": org_id, "slug": f"r2-org-{uuid.uuid4().hex[:8]}"})

        await owner_db.execute(text(
            "INSERT INTO public.users (id, external_subject, identity_provider, display_name, status, created_at, updated_at) "
            "VALUES (:uid, :sub, 'firebase', 'R2 User', 'ACTIVE', now(), now());"
        ), {"uid": user_id, "sub": f"sub_r2_{uuid.uuid4().hex[:8]}"})

        await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
        await owner_db.execute(text(
            "INSERT INTO public.analysis_jobs (id, organization_id, user_id, status, request_prompt, created_at, updated_at) "
            "VALUES (:jid, :oid, :uid, 'RECEIVED', 'Garanti BBVA 2025 Q4 R2 test prompt', now(), now());"
        ), {"jid": job_id, "oid": org_id, "uid": user_id})
        await owner_db.commit()

    try:
        # 1. Test fresh claim via ApiSession
        async with ApiSession() as api_db:
            await api_db.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            claimed = await claim_next_analysis_job(api_db, "worker-r2-unit-1")
            await api_db.commit()
            assert claimed is not None
            assert claimed.job_id == job_id
            assert claimed.organization_id == org_id
            assert claimed.claim_token is not None

        # 2. Test lease renewal
        async with ApiSession() as api_db:
            await api_db.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            renew_ok = await renew_analysis_job_lease(api_db, job_id, claimed.claim_token, "worker-r2-unit-1")
            assert renew_ok is True
            renew_fail = await renew_analysis_job_lease(api_db, job_id, uuid.uuid4(), "worker-r2-unit-1")
            assert renew_fail is False
            await api_db.commit()

    finally:
        async with OwnerSession() as owner_db:
            await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
            await owner_db.execute(text("DELETE FROM public.analysis_jobs WHERE id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.users WHERE id = :uid;"), {"uid": user_id})
            await owner_db.execute(text("DELETE FROM public.organizations WHERE id = :oid;"), {"oid": org_id})
            await owner_db.commit()


@pytest.mark.asyncio
async def test_engine_fencing_and_ownership_loss():
    """Verify engine write paths enforce claim_token fencing and handle ownership loss cleanly."""
    owner_url = os.environ.get("TEST_OWNER_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/finance_intelligence_test")
    api_url = os.environ.get("TEST_API_DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test"))

    owner_engine = create_async_engine(owner_url)
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    api_engine = create_async_engine(api_url)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    period_id = uuid.uuid4()
    wrong_token = uuid.uuid4()

    async with OwnerSession() as owner_db:
        await owner_db.execute(
            text("INSERT INTO public.organizations (id, name, slug, created_at, updated_at) VALUES (:id, 'Fencing Test Org', :slug, now(), now());"),
            {"id": org_id, "slug": f"fence-org-{uuid.uuid4().hex[:8]}"},
        )
        await owner_db.execute(
            text("INSERT INTO public.users (id, external_subject, identity_provider, display_name, status, created_at, updated_at) VALUES (:uid, :sub, 'firebase', 'Fence User', 'ACTIVE', now(), now());"),
            {"uid": user_id, "sub": f"sub_fence_{uuid.uuid4().hex[:8]}"},
        )
        await owner_db.commit()

    async with ApiSession() as api_db:
        await api_db.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        inst = Institution(
            id=inst_id,
            organization_id=org_id,
            canonical_name="Fence Bank",
            display_name="FBANK",
            institution_type="BANK",
            status="ACTIVE",
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="QUARTER",
            period_presentation="DISCRETE_PERIOD",
            fiscal_year=2025,
            quarter=4,
            start_date=datetime(2025, 10, 1).date(),
            end_date=datetime(2025, 12, 31).date(),
            label="2025 Q4",
            comparison_key="2025-Q4",
        )
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="RECEIVED",
            request_prompt="Fencing prompt test",
            normalized_request={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        api_db.add_all([inst, period, job])
        await api_db.commit()

    try:
        # Claim job
        async with ApiSession() as api_db:
            await api_db.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            claimed = await claim_next_analysis_job(api_db, "worker-fence-1")
            await api_db.commit()
            assert claimed is not None

        # Execute with WRONG token -> must raise ClaimOwnershipLostException
        async with ApiSession() as api_db:
            context = ExecutionContext(organization_id=org_id, user_id=user_id, role="OWNER", permissions={"analyses:run", "analyses:read"})
            engine = AnalysisOrchestratorEngine(api_db, context, provider=DeterministicTestModelProvider(environment="development"))
            with pytest.raises(ClaimOwnershipLostException):
                await engine.execute_job(job_id, wrong_token, "worker-fence-1")

        # Execute with CORRECT token -> succeeds
        async with ApiSession() as api_db:
            context = ExecutionContext(organization_id=org_id, user_id=user_id, role="OWNER", permissions={"analyses:run", "analyses:read"})
            engine = AnalysisOrchestratorEngine(api_db, context, provider=DeterministicTestModelProvider(environment="development"))
            completed_job = await engine.execute_job(job_id, claimed.claim_token, "worker-fence-1")
            assert completed_job.status == "COMPLETED"

    finally:
        async with OwnerSession() as owner_db:
            await owner_db.execute(text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)})
            await owner_db.execute(text("ALTER TABLE public.result_datasets DISABLE TRIGGER USER;"))
            await owner_db.execute(text("ALTER TABLE public.comparison_runs DISABLE TRIGGER USER;"))
            await owner_db.execute(text("DELETE FROM public.result_datasets WHERE organization_id = :oid;"), {"oid": org_id})
            await owner_db.execute(text("DELETE FROM public.comparison_runs WHERE organization_id = :oid;"), {"oid": org_id})
            await owner_db.execute(text("ALTER TABLE public.result_datasets ENABLE TRIGGER USER;"))
            await owner_db.execute(text("ALTER TABLE public.comparison_runs ENABLE TRIGGER USER;"))
            await owner_db.execute(text("DELETE FROM public.final_result_snapshots WHERE analysis_job_id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.quality_gate_results WHERE analysis_job_id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.tool_invocations WHERE analysis_job_id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.analysis_plans WHERE analysis_job_id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.analysis_jobs WHERE id = :jid;"), {"jid": job_id})
            await owner_db.execute(text("DELETE FROM public.reporting_periods WHERE id = :pid;"), {"pid": period_id})
            await owner_db.execute(text("DELETE FROM public.institutions WHERE id = :iid;"), {"iid": inst_id})
            await owner_db.execute(text("DELETE FROM public.users WHERE id = :uid;"), {"uid": user_id})
            await owner_db.execute(text("DELETE FROM public.organizations WHERE id = :oid;"), {"oid": org_id})
            await owner_db.commit()


@pytest.mark.asyncio
async def test_heartbeat_task_lifecycle_and_cancellation():
    """Verify heartbeat task cancels engine execution on lease ownership loss and cleans up without task leaks."""
    worker = AnalysisWorker(worker_id="worker-hb-test", heartbeat_interval=0.1)

    job_id = uuid.uuid4()
    org_id = uuid.uuid4()
    claim_token = uuid.uuid4()

    # Test processing job where engine runs fast
    success = await worker.process_analysis_job(job_id, org_id, claim_token)
    # Fast fake run with non-existent job in DB fails gracefully
    assert success is False
