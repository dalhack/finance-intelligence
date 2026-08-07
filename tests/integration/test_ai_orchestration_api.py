import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.db.session import get_db_session
from services.api.app.dependencies import get_execution_context
from services.api.app.main import app
from services.api.app.middleware.execution_context import ExecutionContext
from services.api.app.models.membership import Membership
from services.api.app.models.organization import Organization
from services.api.app.models.user import User


@pytest.mark.asyncio
async def test_create_and_get_analysis_job():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    mem_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="AI Org", slug=f"ai-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="AI User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner:
        await db_owner.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        mem = Membership(id=mem_id, organization_id=org_id, user_id=user_id)
        db_owner.add(mem)
        await db_owner.commit()

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
            request_id="req-test",
            correlation_id="corr-test",
            authentication_method="development",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create analysis job
            create_res = await client.post(
                "/api/v1/analyses",
                json={"prompt": "Karşılaştırma analizi yapınız."},
            )
            assert create_res.status_code == 201
            data = create_res.json()
            assert data["status"] == "RECEIVED"
            job_id = data["id"]

            async with OwnerSession() as owner_db:
                await owner_db.execute(
                    text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)}
                )
                await owner_db.execute(
                    text("UPDATE public.analysis_jobs SET status = 'NEEDS_CLARIFICATION' WHERE id = :jid;"),
                    {"jid": job_id},
                )
                await owner_db.commit()

            # 2. Get analysis job
            get_res = await client.get(f"/api/v1/analyses/{job_id}")
            assert get_res.status_code == 200
            get_data = get_res.json()
            assert get_data["id"] == job_id
            assert get_data["status"] in ("RECEIVED", "NEEDS_CLARIFICATION")

            # 3. List analyses
            list_res = await client.get("/api/v1/analyses?limit=10")
            assert list_res.status_code == 200
            list_data = list_res.json()
            assert len(list_data) >= 1
            assert any(item["id"] == job_id for item in list_data)

            # 4. Result not ready check
            result_res = await client.get(f"/api/v1/analyses/{job_id}/result")
            assert result_res.status_code == 409
            assert result_res.json()["detail"]["error"]["code"] == "RESULT_NOT_READY"

            # 5. Cancel analysis job
            cancel_res = await client.post(f"/api/v1/analyses/{job_id}/cancel")
            assert cancel_res.status_code == 200
            cancel_data = cancel_res.json()
            assert cancel_data["status"] == "CANCELLED"
    finally:
        app.dependency_overrides.clear()
        async with OwnerSession() as db_clean:
            await db_clean.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            await db_clean.execute(text(f"DELETE FROM analysis_jobs WHERE organization_id = '{org_id}';"))
            await db_clean.execute(text(f"DELETE FROM memberships WHERE organization_id = '{org_id}';"))
            await db_clean.execute(text(f"DELETE FROM users WHERE id = '{user_id}';"))
            await db_clean.execute(text(f"DELETE FROM organizations WHERE id = '{org_id}';"))
            await db_clean.commit()


@pytest.mark.asyncio
async def test_concurrent_idempotency_create_analysis():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    mem_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Idem Org", slug=f"idem-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Idem User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner:
        await db_owner.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        mem = Membership(id=mem_id, organization_id=org_id, user_id=user_id)
        db_owner.add(mem)
        await db_owner.commit()

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
            request_id="req-test",
            correlation_id="corr-test",
            authentication_method="development",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res1 = await client.post(
                "/api/v1/analyses",
                json={"prompt": "Idempotent POST test"},
                headers={"X-Idempotency-Key": "idem-key-998"},
            )
            res2 = await client.post(
                "/api/v1/analyses",
                json={"prompt": "Idempotent POST test"},
                headers={"X-Idempotency-Key": "idem-key-998"},
            )
            assert res1.status_code == 201
            assert res2.status_code in [200, 201]
            assert res1.json()["id"] == res2.json()["id"]

            async with OwnerSession() as owner_db:
                await owner_db.execute(
                    text("SELECT set_config('app.current_organization_id', :oid, true);"), {"oid": str(org_id)}
                )
                await owner_db.execute(
                    text("UPDATE public.analysis_jobs SET status = 'NEEDS_CLARIFICATION' WHERE id = :jid;"),
                    {"jid": res1.json()["id"]},
                )
                await owner_db.commit()
    finally:
        app.dependency_overrides.clear()
        async with OwnerSession() as db_clean:
            await db_clean.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            await db_clean.execute(text(f"DELETE FROM analysis_jobs WHERE organization_id = '{org_id}';"))
            await db_clean.execute(text(f"DELETE FROM memberships WHERE organization_id = '{org_id}';"))
            await db_clean.execute(text(f"DELETE FROM users WHERE id = '{user_id}';"))
            await db_clean.execute(text(f"DELETE FROM organizations WHERE id = '{org_id}';"))
            await db_clean.commit()
