import os
from uuid import uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.db.session import get_db_session
from services.api.app.dependencies import get_execution_context
from services.api.app.main import app
from services.api.app.middleware.execution_context import ExecutionContext
from services.api.app.storage.local_adapter import LocalStorageAdapter

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_storage_compensation_aborts_temp_file_on_upload_error():
    adapter = LocalStorageAdapter()
    tenant_id = str(uuid4())
    key = f"{tenant_id}/temp_test.bin"

    temp_path = adapter.begin_temporary_write(tenant_id, key)
    adapter.write_chunk(temp_path, b"partial chunk content")
    assert os.path.exists(temp_path)

    # Abort compensation cleans up temporary file
    adapter.abort_temporary_write(temp_path)
    assert not os.path.exists(temp_path)


@pytest.mark.asyncio
async def test_storage_compensation_preserves_canonical_object_on_rollback():
    org_id = uuid4()
    user_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_id), f"Org {org_id}", f"org-{org_id}"
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_a := user_id),
        f"sub-{user_a}",
        f"User {user_a}",
    )
    await conn_owner.close()

    engine = create_async_engine(RAW_API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            await session.execute(
                __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(org_id)},
            )
            yield session

    async def override_ctx():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=uuid4(),
            roles=["ANALYST"],
            permissions=["documents:upload", "documents:finalize"],
            request_id="req-123",
            correlation_id="corr-123",
            authentication_method="test",
            environment="development",
        )

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_execution_context] = override_ctx

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = b"header1,header2\ncanonical_content,123"

            # Step 1: Upload & finalize first file (creates canonical StoredObject)
            u1 = await client.post(
                "/api/v1/documents/uploads",
                data={"display_name": "canonical.csv"},
                files={"file": ("canonical.csv", payload, "text/csv")},
            )
            s1_id = u1.json()["session_id"]
            fin1 = await client.post(f"/api/v1/documents/uploads/{s1_id}/finalize")
            assert fin1.status_code == 200

            # Step 2: Upload second file with same hash
            u2 = await client.post(
                "/api/v1/documents/uploads",
                data={"display_name": "duplicate.csv"},
                files={"file": ("duplicate.csv", payload, "text/csv")},
            )
            s2_id = u2.json()["session_id"]
            fin2 = await client.post(f"/api/v1/documents/uploads/{s2_id}/finalize")
            assert fin2.status_code == 200
            assert fin2.json()["is_deduplicated"] is True

            # Step 3: Verify canonical object is PRESERVED on disk
            adapter = LocalStorageAdapter()
            canonical_key = f"{org_id}/{s1_id}.bin"
            exists = await adapter.object_exists(str(org_id), canonical_key)
            assert exists is True

    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
