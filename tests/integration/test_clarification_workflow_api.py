import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.db.session import get_db_session
from app.db.tenant_context import tenant_transaction_context
from app.dependencies import get_execution_context
from app.main import app
from app.middleware.execution_context import ExecutionContext
from app.models.institution import Institution
from app.models.membership import Membership
from app.models.orchestration import AnalysisJob
from app.models.organization import Organization
from app.models.user import User
from app.services.clarification_service import ClarificationService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_clarification_full_lifecycle_and_security():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    mem_id = uuid4()
    inst_id = uuid4()
    job_id = uuid4()

    # 1. Setup Tenant & Entity
    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Clar Org", slug=f"clar-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Clar User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner:
        await db_owner.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        mem = Membership(id=mem_id, organization_id=org_id, user_id=user_id)
        db_owner.add(mem)
        await db_owner.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        inst = Institution(
            id=inst_id, canonical_name="Garanti Bank", display_name="Garanti Bank", organization_id=org_id
        )
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="UNDERSTANDING_REQUEST",
            request_prompt="Analiz yapınız.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_api.add_all([inst, job])
        await db_api.commit()

    # 2. Require Clarification via Service
    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        service = ClarificationService(db_api, organization_id=org_id, user_id=user_id)
        clar = await service.require_clarification(
            analysis_job_id=job_id,
            clarification_code="INSTITUTION_REQUIRED",
            prompt_key="clarification.select_institution",
            question="Lütfen kurumu seçiniz.",
            allowed_response_schema={"type": "object", "properties": {"institution_id": {"type": "string"}}},
        )
        clar_id = clar.id

    async def override_get_db_session():
        async with ApiSession() as session:
            await session.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            yield session

    async def override_get_execution_context():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=mem_id,
            roles=["ANALYST"],
            permissions=["analyses:read", "analyses:run", "analyses:clarifications:respond", "analyses:cancel"],
            request_id="req-clar-test",
            correlation_id="corr-clar-test",
            authentication_method="development",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 3. GET /clarification
            get_res = await client.get(f"/api/v1/analyses/{job_id}/clarification")
            assert get_res.status_code == 200
            data = get_res.json()
            assert data["id"] == str(clar_id)
            assert data["clarification_code"] == "INSTITUTION_REQUIRED"

            # 4. Reject forbidden key in payload
            bad_res = await client.post(
                f"/api/v1/analyses/{job_id}/clarification/respond",
                json={
                    "clarification_id": str(clar_id),
                    "idempotency_key": "idem-clar-001",
                    "response_payload": {"institution_id": str(inst_id), "organization_id": str(org_id)},
                },
            )
            assert bad_res.status_code == 400
            assert bad_res.json()["detail"]["error"]["code"] == "CLARIFICATION_RESPONSE_INVALID"

            # 5. Reject cross-tenant entity ID
            fake_inst_id = uuid4()
            cross_res = await client.post(
                f"/api/v1/analyses/{job_id}/clarification/respond",
                json={
                    "clarification_id": str(clar_id),
                    "idempotency_key": "idem-clar-002",
                    "response_payload": {"institution_id": str(fake_inst_id)},
                },
            )
            assert cross_res.status_code == 400
            assert cross_res.json()["detail"]["error"]["code"] == "CLARIFICATION_RESPONSE_INVALID"

            # 6. Valid respond
            valid_res = await client.post(
                f"/api/v1/analyses/{job_id}/clarification/respond",
                json={
                    "clarification_id": str(clar_id),
                    "idempotency_key": "idem-clar-003",
                    "response_payload": {"institution_id": str(inst_id)},
                },
            )
            assert valid_res.status_code == 200
            assert valid_res.json()["status"] == "UNDERSTANDING_REQUEST"
    finally:
        app.dependency_overrides.clear()

    # 7. Verify DB side effects & Trigger Immutability
    async with OwnerSession() as db_verify:
        await db_verify.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))

        # Verify clarification status
        res_clar = await db_verify.execute(
            text(f"SELECT status, response_fingerprint FROM analysis_clarifications WHERE id = '{clar_id}';")
        )
        row = res_clar.fetchone()
        assert row[0] == "CLARIFICATION_RECEIVED"
        assert row[1] is not None

        # Verify Trigger Immutability (Attempt update on terminal record raises exception)
        with pytest.raises(Exception) as exc_info:
            await db_verify.execute(
                text(f"UPDATE analysis_clarifications SET status = 'AWAITING_CLARIFICATION' WHERE id = '{clar_id}';")
            )
        assert "TERMINAL_CLARIFICATION_IMMUTABLE" in str(exc_info.value)


@pytest.mark.asyncio
async def test_clarification_cancellation_flow():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    mem_id = uuid4()
    job_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Cancel Org", slug=f"can-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Cancel User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner, tenant_transaction_context(db_owner, org_id):
        mem = Membership(id=mem_id, organization_id=org_id, user_id=user_id)
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="UNDERSTANDING_REQUEST",
            request_prompt="Analiz yapınız.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_owner.add_all([mem, job])
        await db_owner.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        service = ClarificationService(db_api, organization_id=org_id, user_id=user_id)
        clar = await service.require_clarification(
            analysis_job_id=job_id,
            clarification_code="MEASURE_REQUIRED",
            prompt_key="clarification.select_measure",
            question="Metriği seçiniz.",
            allowed_response_schema={"type": "object"},
        )
        clar_id = clar.id

    async def override_get_db_session():
        async with ApiSession() as session:
            await session.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            yield session

    async def override_get_execution_context():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=mem_id,
            roles=["ANALYST"],
            permissions=["analyses:read", "analyses:run", "analyses:clarifications:respond", "analyses:cancel"],
            request_id="req-clar-cancel",
            correlation_id="corr-clar-cancel",
            authentication_method="development",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cancel_res = await client.post(
                f"/api/v1/analyses/{job_id}/clarification/cancel",
                json={
                    "clarification_id": str(clar_id),
                    "idempotency_key": "idem-cancel-001",
                    "reason_code": "USER_CANCELLED",
                },
            )
            assert cancel_res.status_code == 200
            assert cancel_res.json()["status"] == "CANCELLED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clarification_partial_unique_constraint():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Uniq Org", slug=f"uniq-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Uniq User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner, tenant_transaction_context(db_owner, org_id):
        mem = Membership(id=uuid4(), organization_id=org_id, user_id=user_id)
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="NEEDS_CLARIFICATION",
            request_prompt="Analiz yapınız.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_owner.add_all([mem, job])
        await db_owner.commit()

    # First open clarification
    async with OwnerSession() as db1:
        await db1.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        await db1.execute(
            text(
                "INSERT INTO analysis_clarifications (id, organization_id, analysis_job_id, clarification_code, prompt_key, question, allowed_response_schema, status, requested_at, created_at) "
                "VALUES (:id, :org_id, :job_id, 'INSTITUTION_REQUIRED', 'clar.test', 'Select inst', '{}', 'AWAITING_CLARIFICATION', now(), now());"
            ),
            {"id": uuid4(), "org_id": org_id, "job_id": job_id},
        )
        await db1.commit()

    # Second open clarification for same job (Must fail with unique constraint)
    async with OwnerSession() as db2:
        await db2.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        with pytest.raises(Exception) as exc_info:
            await db2.execute(
                text(
                    "INSERT INTO analysis_clarifications (id, organization_id, analysis_job_id, clarification_code, prompt_key, question, allowed_response_schema, status, requested_at, created_at) "
                    "VALUES (:id, :org_id, :job_id, 'MEASURE_REQUIRED', 'clar.test2', 'Select measure', '{}', 'AWAITING_CLARIFICATION', now(), now());"
                ),
                {"id": uuid4(), "org_id": org_id, "job_id": job_id},
            )
            await db2.commit()
        assert "uq_active_clarification_per_job" in str(exc_info.value)
