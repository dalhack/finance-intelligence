import os
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.core.errors import BaseAPIException
from services.api.app.services.reference_service import ReferenceService

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

    async with session_factory() as session:
        await session.execute(
            __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )

        # 1. create_or_acquire (New object)
        obj1, dedup1 = await ReferenceService.create_or_acquire(session, org_id, sha256_hash, key1, 1024, "text/csv")
        await session.commit()
        assert dedup1 is False
        assert obj1.reference_count == 1

        # 2. acquire_existing
        await session.execute(
            __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )
        obj_acq = await ReferenceService.acquire_existing(session, org_id, obj1.id)
        await session.commit()
        assert obj_acq.reference_count == 2

        # 3. release reference
        await session.execute(
            __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )
        r_count1 = await ReferenceService.release_reference(session, org_id, obj1.id)
        assert r_count1 == 1

        r_count2 = await ReferenceService.release_reference(session, org_id, obj1.id)
        assert r_count2 == 0

        # 4. Double release (below 0) raises exception
        with pytest.raises(BaseAPIException) as exc_info:
            await ReferenceService.release_reference(session, org_id, obj1.id)
        assert exc_info.value.code == "INVALID_REFERENCE_COUNT"

        await session.commit()

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

    async with session_factory() as session:
        await session.execute(
            __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_a)},
        )
        obj_a, _ = await ReferenceService.create_or_acquire(
            session, org_a, "sha256_tenant_a", f"{org_a}/key.bin", 512, "text/csv"
        )
        await session.commit()

        # Tenant B attempting to acquire Tenant A's stored_object_id
        await session.execute(
            __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_b)},
        )
        with pytest.raises(BaseAPIException) as exc_info:
            await ReferenceService.acquire_existing(session, org_b, obj_a.id)
        assert exc_info.value.code == "STORED_OBJECT_NOT_FOUND"

    await engine.dispose()
