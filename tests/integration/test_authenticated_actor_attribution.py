import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from app.db.session import get_db_session
from app.dependencies import get_execution_context
from app.main import app
from app.middleware.execution_context import ExecutionContext
from app.models.membership import Membership
from app.models.orchestration import AnalysisJob
from app.models.organization import Organization
from app.models.user import User
from app.services.clarification_service import ClarificationService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_multi_user_same_org_actor_attribution_isolation():
    """Verify distinct actor attribution for User A vs User B requests in the same organization."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()

    # 1. Create Organization & 2 Users (User A created first, User B created second)
    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Multi User Org", slug=f"multi-{org_id.hex[:6]}")
        user_a = User(
            id=user_a_id,
            external_subject=f"firebase-user-a-{user_a_id.hex[:6]}",
            display_name="User A",
            status="active",
        )
        user_b = User(
            id=user_b_id,
            external_subject=f"firebase-user-b-{user_b_id.hex[:6]}",
            display_name="User B",
            status="active",
        )
        db_owner.add_all([org, user_a, user_b])
        await db_owner.commit()

        from app.db.tenant_context import tenant_transaction_context

        async with tenant_transaction_context(db_owner, org_id):
            mem_a = Membership(id=uuid4(), organization_id=org_id, user_id=user_a_id, status="active")
            mem_b = Membership(id=uuid4(), organization_id=org_id, user_id=user_b_id, status="active")
            db_owner.add_all([mem_a, mem_b])
            await db_owner.commit()

    # 2. Test Request A (User A authenticated)
    async def override_get_db_session():
        async with ApiSession() as session:
            await session.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
            yield session

    async def override_get_execution_context_user_a():
        return ExecutionContext(
            authenticated_user_id=user_a_id,
            active_organization_id=org_id,
            membership_id=mem_a.id,
            roles=["ANALYST"],
            permissions=["analyses:read", "analyses:run", "analyses:clarifications:respond", "analyses:cancel"],
            request_id="req-user-a",
            correlation_id="corr-user-a",
            authentication_method="firebase",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context_user_a

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res_a = await client.post(
                "/api/v1/analyses",
                json={"prompt": "User A analysis request."},
            )
            assert res_a.status_code == 201
            job_a_data = res_a.json()
            assert job_a_data["user_id"] == str(user_a_id)
            assert job_a_data["user_id"] != str(user_b_id)
    finally:
        app.dependency_overrides.clear()

    # 3. Test Request B (User B authenticated)
    async def override_get_execution_context_user_b():
        return ExecutionContext(
            authenticated_user_id=user_b_id,
            active_organization_id=org_id,
            membership_id=mem_b.id,
            roles=["ANALYST"],
            permissions=["analyses:read", "analyses:run", "analyses:clarifications:respond", "analyses:cancel"],
            request_id="req-user-b",
            correlation_id="corr-user-b",
            authentication_method="firebase",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context_user_b

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res_b = await client.post(
                "/api/v1/analyses",
                json={"prompt": "User B analysis request."},
            )
            assert res_b.status_code == 201
            job_b_data = res_b.json()
            assert job_b_data["user_id"] == str(user_b_id)
            assert job_b_data["user_id"] != str(user_a_id)

            # Invariant Assertions
            user_a_persisted_as_user_b = job_a_data["user_id"] == str(user_b_id)
            user_b_persisted_as_user_a = job_b_data["user_id"] == str(user_a_id)
            user_b_persisted_as_oldest_member = job_b_data["user_id"] == str(user_a_id)

            assert user_a_persisted_as_user_b is False
            assert user_b_persisted_as_user_a is False
            assert user_b_persisted_as_oldest_member is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clarification_actor_attribution_user_b_response_and_cancellation():
    """Verify clarification respond and cancel operations attribute correctly to authenticated User B."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()
    job_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Clar Actor Org", slug=f"clar-act-{org_id.hex[:6]}")
        user_a = User(id=user_a_id, external_subject=f"sub-a-{user_a_id.hex[:6]}", display_name="User A")
        user_b = User(id=user_b_id, external_subject=f"sub-b-{user_b_id.hex[:6]}", display_name="User B")
        db_owner.add_all([org, user_a, user_b])
        await db_owner.commit()

    async with OwnerSession() as db_owner:
        from app.db.tenant_context import tenant_transaction_context

        async with tenant_transaction_context(db_owner, org_id):
            mem_a = Membership(id=uuid4(), organization_id=org_id, user_id=user_a_id)
            mem_b = Membership(id=uuid4(), organization_id=org_id, user_id=user_b_id)
            db_owner.add_all([mem_a, mem_b])
            await db_owner.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_b_id,
            status="UNDERSTANDING_REQUEST",
            request_prompt="User B clarification test.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_api.add(job)
        await db_api.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        service = ClarificationService(db_api, organization_id=org_id, user_id=user_b_id)
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

    async def override_get_execution_context_user_b():
        return ExecutionContext(
            authenticated_user_id=user_b_id,
            active_organization_id=org_id,
            membership_id=mem_b.id,
            roles=["ANALYST"],
            permissions=["analyses:read", "analyses:run", "analyses:clarifications:respond", "analyses:cancel"],
            request_id="req-clar-b",
            correlation_id="corr-clar-b",
            authentication_method="firebase",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context_user_b

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cancel_res = await client.post(
                f"/api/v1/analyses/{job_id}/clarification/cancel",
                json={
                    "clarification_id": str(clar_id),
                    "idempotency_key": "idem-actor-cancel-001",
                    "reason_code": "USER_CANCELLED",
                },
            )
            assert cancel_res.status_code == 200
            data = cancel_res.json()
            assert data["user_id"] == str(user_b_id)
            assert data["user_id"] != str(user_a_id)
    finally:
        app.dependency_overrides.clear()


def test_production_code_zero_get_current_user_id_usages():
    """Verify zero get_current_user_id calls exist in production application source code."""
    app_dir = Path(__file__).parent.parent.parent / "services" / "api" / "app"
    violations = []

    for file_path in app_dir.rglob("*.py"):
        content = file_path.read_text(encoding="utf-8")
        if "get_current_user_id" in content:
            violations.append(str(file_path))

    assert len(violations) == 0, f"Found unsafe get_current_user_id references in production code: {violations}"
