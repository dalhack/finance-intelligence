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
from services.api.app.models.document import Document

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_document_rls_cross_tenant_probe_returns_empty():
    org_a = uuid4()
    org_b = uuid4()
    user_a = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_a), f"Org {org_a}", f"org-{org_a}"
    )
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", str(org_b), f"Org {org_b}", f"org-{org_b}"
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_a),
        f"sub-{user_a}",
        f"User {user_a}",
    )
    await conn_owner.close()

    doc_id = uuid4()

    engine = create_async_engine(RAW_API_USER_URL)
    async with AsyncSession(engine) as session:
        # Seed Document for Org A
        await session.execute(
            __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_a)},
        )
        doc_a = Document(id=doc_id, organization_id=org_a, uploaded_by_user_id=user_a, display_name="org_a_doc.pdf")
        session.add(doc_a)
        await session.commit()

        # Connect as Org B context and probe Org A's document
        await session.execute(
            __import__("sqlalchemy").text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_b)},
        )
        res = await session.execute(__import__("sqlalchemy").select(Document).where(Document.id == doc_id))
        probed_doc = res.scalar_one_or_none()
        assert probed_doc is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_document_version_mismatched_relationship_returns_404():
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
            permissions=["ingestion:read"],
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
            res = await client.get(f"/api/v1/documents/{uuid4()}/versions/{uuid4()}/status")
            assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
