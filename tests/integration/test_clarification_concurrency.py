import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.institution import Institution
from services.api.app.models.membership import Membership
from services.api.app.models.orchestration import AnalysisJob
from services.api.app.models.organization import Organization
from services.api.app.models.user import User
from services.api.app.services.clarification_service import ClarificationService


@pytest.mark.asyncio
async def test_clarification_concurrency_and_expiry_scenarios():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    job_id = uuid4()

    # 1. Setup Tenant & Entities
    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Conc Org", slug=f"conc-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Conc User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner:
        await db_owner.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        mem = Membership(id=uuid4(), organization_id=org_id, user_id=user_id)
        inst = Institution(id=inst_id, canonical_name="Akbank", display_name="Akbank", organization_id=org_id)
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="UNDERSTANDING_REQUEST",
            request_prompt="Akbank analizi yapınız.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_owner.add_all([mem, inst, job])
        await db_owner.commit()

    # 2. Test require_clarification
    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        service = ClarificationService(db_api, organization_id=org_id, user_id=user_id)
        clar = await service.require_clarification(
            analysis_job_id=job_id,
            clarification_code="INSTITUTION_REQUIRED",
            prompt_key="clar.test",
            question="Kurumu seçiniz.",
            allowed_response_schema={},
            ttl_minutes=-1,  # Expired immediately for expiry test
        )
        clar_id = clar.id

    # 3. Test expire_due_clarifications
    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        service = ClarificationService(db_api, organization_id=org_id, user_id=user_id)
        expired_count = await service.expire_due_clarifications()
        assert expired_count == 1

    # Verify status in DB
    async with OwnerSession() as db_verify:
        await db_verify.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        job_res = await db_verify.execute(text(f"SELECT status FROM analysis_jobs WHERE id = '{job_id}';"))
        assert job_res.scalar() == "EXPIRED"

        clar_res = await db_verify.execute(text(f"SELECT status FROM analysis_clarifications WHERE id = '{clar_id}';"))
        assert clar_res.scalar() == "CLARIFICATION_EXPIRED"
