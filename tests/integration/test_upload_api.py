import os
from uuid import uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.db.session import get_db_session
from services.api.app.dependencies import DEV_SYNTHETIC_ORG_ID, DEV_SYNTHETIC_USER_ID, get_execution_context
from services.api.app.main import app
from services.api.app.middleware.execution_context import ExecutionContext

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None

GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden"))

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_upload_api_streamed_success():
    org_id = DEV_SYNTHETIC_ORG_ID
    user_id = DEV_SYNTHETIC_USER_ID

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;",
        str(org_id),
        f"Org {org_id}",
        f"org-{org_id}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    engine = create_async_engine(RAW_API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db_session():
        async with session_factory() as session:
            await session.execute(
                __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(org_id)},
            )
            yield session

    async def override_get_execution_context():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=uuid4(),
            roles=["ANALYST"],
            permissions=["documents:upload", "documents:finalize", "documents:read", "ingestion:read"],
            request_id="req-123",
            correlation_id="corr-123",
            authentication_method="test",
            environment="development",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            csv_path = os.path.join(GOLDEN_DIR, "sample_turkish.csv")
            with open(csv_path, "rb") as f:  # noqa: ASYNC230
                csv_bytes = f.read()

            res = await client.post(
                "/api/v1/documents/uploads",
                data={"display_name": "sample_turkish.csv", "classification": "CONFIDENTIAL"},
                files={"file": ("sample_turkish.csv", csv_bytes, "text/csv")},
            )
            assert res.status_code == 201
            data = res.json()
            assert "session_id" in data
            assert data["status"] == "UPLOADED"

    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_upload_api_classifications_preservation():
    org_id = DEV_SYNTHETIC_ORG_ID
    user_id = DEV_SYNTHETIC_USER_ID

    engine = create_async_engine(RAW_API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db_session():
        async with session_factory() as session:
            await session.execute(
                __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(org_id)},
            )
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
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for cls in ["INTERNAL", "STRICTLY_CONFIDENTIAL", "PERSONAL_DATA"]:
                res = await client.post(
                    "/api/v1/documents/uploads",
                    data={"display_name": f"sample_{cls}.csv", "classification": cls},
                    files={"file": (f"sample_{cls}.csv", b"h1,h2\n1,2", "text/csv")},
                )
                assert res.status_code == 201
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_upload_api_missing_permission_returns_403():
    org_id = DEV_SYNTHETIC_ORG_ID
    user_id = DEV_SYNTHETIC_USER_ID

    engine = create_async_engine(RAW_API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    async def override_get_execution_context():
        return ExecutionContext(
            authenticated_user_id=user_id,
            active_organization_id=org_id,
            membership_id=uuid4(),
            roles=["ANALYST"],
            permissions=["documents:read"],  # Missing documents:upload permission
            request_id="req-123",
            correlation_id="corr-123",
            authentication_method="test",
            environment="development",
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_execution_context] = override_get_execution_context

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.post(
                "/api/v1/documents/uploads",
                data={"display_name": "sample.csv", "classification": "CONFIDENTIAL"},
                files={"file": ("sample.csv", b"col1,col2\n1,2", "text/csv")},
            )
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
