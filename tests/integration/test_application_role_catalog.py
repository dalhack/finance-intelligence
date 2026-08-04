import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.db.session import get_db_session
from services.api.app.dependencies import get_execution_context
from services.api.app.main import app
from services.api.app.middleware.execution_context import ExecutionContext


@pytest.mark.asyncio
async def test_migration_030_uppercase_constraint_and_admin_cleanup():
    """Verify Migration 030 uppercase check constraint on roles and ADMIN cleanup."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    async with OwnerSession() as db:
        # 1. Verify ADMIN role is absent
        res_admin = await db.execute(text("SELECT COUNT(*) FROM public.roles WHERE name = 'ADMIN';"))
        assert res_admin.scalar() == 0

        # 2. Verify case-variant insert 'analyst' is rejected by check constraint
        with pytest.raises(IntegrityError):
            async with OwnerSession() as err_db:
                await err_db.execute(
                    text("INSERT INTO public.roles (id, name, description) VALUES (:id, 'analyst', 'Lower Analyst');"),
                    {"id": uuid4()},
                )
                await err_db.commit()


@pytest.mark.asyncio
async def test_organization_summary_dto_zero_roles_fallback_removed():
    """Verify that user with zero roles gets role=None in OrganizationSummaryDTO, never 'ANALYST'."""
    org_id = uuid4()
    user_id = uuid4()

    async def override_get_db_session():
        owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
        factory = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield session

    async def override_get_execution_context_zero_roles():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=uuid4(),
            roles=[],  # Zero roles
            permissions=[],
            request_id="req-zero-roles",
            correlation_id="corr-zero-roles",
            authentication_method="test",
            environment="test",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context_zero_roles

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/organizations/current")
            assert resp.status_code == 200
            data = resp.json()
            assert data["role"] is None
            assert data["role"] != "ANALYST"
    finally:
        app.dependency_overrides.clear()
