import os
from uuid import uuid4

import asyncpg
import pytest
from app.core.errors import BaseAPIException
from app.db.tenant_context import tenant_transaction_context
from app.services.reference_service import ReferenceService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_reference_service_full_lifecycle():
    org_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org {org_id}",
        f"org-{org_id}",
    )
    await conn_owner.close()

    engine = create_async_engine(RAW_API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    sha256_hash = "lifecycle_sha256_hash_12345"
    key1 = f"{org_id}/key1.bin"

    # 1. create_or_acquire (New object)
    async with session_factory() as session1, tenant_transaction_context(session1, org_id):
        obj1, dedup1 = await ReferenceService.create_or_acquire(session1, org_id, sha256_hash, key1, 1024, "text/csv")
        await session1.commit()
        assert dedup1 is False
        assert obj1.reference_count == 1
        obj1_id = obj1.id

    # 2. acquire_existing
    async with session_factory() as session2, tenant_transaction_context(session2, org_id):
        obj_acq = await ReferenceService.acquire_existing(session2, org_id, obj1_id)
        await session2.commit()
        assert obj_acq.reference_count == 2

    # 3. release reference
    async with session_factory() as session3, tenant_transaction_context(session3, org_id):
        r_count1 = await ReferenceService.release_reference(session3, org_id, obj1_id)
        assert r_count1 == 1

        r_count2 = await ReferenceService.release_reference(session3, org_id, obj1_id)
        assert r_count2 == 0

        # 4. Double release (below 0) raises exception
        with pytest.raises(BaseAPIException) as exc_info:
            await ReferenceService.release_reference(session3, org_id, obj1_id)
        assert exc_info.value.code == "INVALID_REFERENCE_COUNT"

        await session3.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_reference_service_cross_tenant_rejection():
    org_a = uuid4()
    org_b = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_a), f"Org {org_a}", f"org-{org_a}"
    )
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_b), f"Org {org_b}", f"org-{org_b}"
    )
    await conn_owner.close()

    engine = create_async_engine(RAW_API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session_a, tenant_transaction_context(session_a, org_a):
        obj_a, _ = await ReferenceService.create_or_acquire(
            session_a, org_a, "sha256_tenant_a", f"{org_a}/key.bin", 512, "text/csv"
        )
        await session_a.commit()

    # Tenant B attempting to acquire Tenant A's stored_object_id
    async with session_factory() as session_b, tenant_transaction_context(session_b, org_b):
        with pytest.raises(BaseAPIException) as exc_info:
            await ReferenceService.acquire_existing(session_b, org_b, obj_a.id)
        assert exc_info.value.code == "STORED_OBJECT_NOT_FOUND"

    await engine.dispose()
