import asyncio
import os
import shutil
from uuid import uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy import func, select

from services.api.app.db.session import ApiSessionLocal, get_db_session
from services.api.app.db.tenant_context import tenant_transaction_context
from services.api.app.dependencies import get_execution_context
from services.api.app.main import app
from services.api.app.middleware.execution_context import ExecutionContext
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.stored_object import StoredObject
from services.api.app.storage.local_adapter import LocalStorageAdapter

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_dedup_concurrency_same_tenant_api_finalize():
    org_id = uuid4()
    user_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org {org_id}",
        f"org-{org_id}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    adapter = LocalStorageAdapter()
    tenant_storage_dir = os.path.join(adapter.storage_root, os.path.basename(str(org_id)))

    if os.path.exists(tenant_storage_dir):
        shutil.rmtree(tenant_storage_dir)

    async def override_get_db_session():
        async with ApiSessionLocal() as session, tenant_transaction_context(session, org_id):
            yield session

    async def override_get_execution_context():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=uuid4(),
            roles=["ANALYST"],
            permissions=["documents:upload", "documents:finalize", "documents:read"],
            request_id="req-123",
            correlation_id="corr-123",
            authentication_method="test",
            environment="development",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        transport = httpx.ASGITransport(app=app)
        async with (
            httpx.AsyncClient(transport=transport, base_url="http://testserver") as client1,
            httpx.AsyncClient(transport=transport, base_url="http://testserver") as client2,
        ):
            payload = b"col1,col2\nval1,val2\n100,200"

            # Step 1: Upload 2 separate sessions with identical file content
            u1 = await client1.post(
                "/api/v1/documents/uploads",
                data={"display_name": "file1.csv"},
                files={"file": ("file1.csv", payload, "text/csv")},
            )
            u2 = await client2.post(
                "/api/v1/documents/uploads",
                data={"display_name": "file2.csv"},
                files={"file": ("file2.csv", payload, "text/csv")},
            )
            assert u1.status_code == 201
            assert u2.status_code == 201

            s1_id = u1.json()["session_id"]
            s2_id = u2.json()["session_id"]

            # Step 2: Concurrent API finalize calls
            fin1_task = client1.post(f"/api/v1/documents/uploads/{s1_id}/finalize")
            fin2_task = client2.post(f"/api/v1/documents/uploads/{s2_id}/finalize")

            r1, r2 = await asyncio.gather(fin1_task, fin2_task)
            assert r1.status_code == 200
            assert r2.status_code == 200

            # Verify exactly 1 is_deduplicated is True and 1 is False
            dedup_flags = [r1.json()["is_deduplicated"], r2.json()["is_deduplicated"]]
            assert True in dedup_flags
            assert False in dedup_flags

            # Invariant Verification in DB
            async with ApiSessionLocal() as verify_session, tenant_transaction_context(verify_session, org_id):
                # Invariant 1: StoredObject count = 1
                so_res = await verify_session.execute(
                    select(StoredObject).where(StoredObject.organization_id == org_id)
                )
                stored_objs = so_res.scalars().all()
                assert len(stored_objs) == 1

                # Invariant 2 & 3: active versions = 2, reference_count = 2
                ver_count_res = await verify_session.execute(
                    select(func.count(DocumentVersion.id)).where(DocumentVersion.organization_id == org_id)
                )
                ver_count = ver_count_res.scalar()
                assert ver_count == 2
                assert stored_objs[0].reference_count == 2

            # Invariant 4: Physical storage file count inspection (Exactly 1 canonical file, 0 .tmp files)
            files_in_storage = os.listdir(tenant_storage_dir) if os.path.exists(tenant_storage_dir) else []
            tmp_files = [f for f in files_in_storage if f.endswith(".tmp")]
            canonical_files = [f for f in files_in_storage if f.endswith(".bin")]

            assert len(tmp_files) == 0, f"Found orphan temporary files: {tmp_files}"
            assert len(canonical_files) == 1, f"Expected 1 canonical file, found {len(canonical_files)}"

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dedup_cross_tenant_isolation():
    org_a = uuid4()
    org_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_a),
        f"Org {org_a}",
        f"org-{org_a}",
    )
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_b),
        f"Org {org_b}",
        f"org-{org_b}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_a),
        f"sub-{user_a}",
        f"User {user_a}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_b),
        f"sub-{user_b}",
        f"User {user_b}",
    )
    await conn_owner.close()

    payload = b"col1,col2\nsame_content_for_both_tenants,100"

    async def run_tenant_flow(org_uuid, user_uuid):
        async def override_db():
            async with ApiSessionLocal() as session, tenant_transaction_context(session, org_uuid):
                yield session

        async def override_ctx():
            return ExecutionContext(
                authenticated_user_id=user_uuid,
                active_organization_id=org_uuid,
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
                up = await client.post(
                    "/api/v1/documents/uploads",
                    data={"display_name": "shared.csv"},
                    files={"file": ("shared.csv", payload, "text/csv")},
                )
                s_id = up.json()["session_id"]
                fin = await client.post(f"/api/v1/documents/uploads/{s_id}/finalize")
                return fin.json()
        finally:
            app.dependency_overrides.clear()

    res_a = await run_tenant_flow(org_a, user_a)
    res_b = await run_tenant_flow(org_b, user_b)

    # Both tenants get is_deduplicated = False because each has its OWN StoredObject
    assert res_a["is_deduplicated"] is False
    assert res_b["is_deduplicated"] is False
    assert res_a["stored_object_id"] != res_b["stored_object_id"]
