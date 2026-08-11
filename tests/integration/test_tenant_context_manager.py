import os
from uuid import uuid4

import pytest
from app.db.tenant_context import tenant_transaction_context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_tenant_context_manager_valid_uuid_and_cleanup():
    engine = create_async_engine(API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    org_id = uuid4()

    async with session_factory() as session:
        async with session.begin(), tenant_transaction_context(session, org_id):
            res = await session.execute(text("SELECT current_setting('app.current_organization_id', true);"))
            val = res.scalar()
            assert val == str(org_id)

        # Outside transaction context block
        res_after = await session.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        val_after = res_after.scalar()
        assert val_after == "" or val_after is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_tenant_context_manager_rejects_none_organization_id():
    engine = create_async_engine(API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        with pytest.raises(ValueError, match="organization_id cannot be null or empty"):
            async with tenant_transaction_context(session, None):
                pass

    await engine.dispose()


@pytest.mark.asyncio
async def test_tenant_context_manager_exception_propagation():
    engine = create_async_engine(API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    org_id = uuid4()

    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="Custom Business Logic Exception"):
            async with session.begin():
                async with tenant_transaction_context(session, org_id):
                    raise RuntimeError("Custom Business Logic Exception")

    await engine.dispose()
