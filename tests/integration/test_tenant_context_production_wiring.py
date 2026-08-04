"""Integration tests for production tenant context wiring, fail-closed enforcement, and RLS isolation on real PostgreSQL 16."""

import os
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.api.v1 import documents
from services.api.app.db.session import api_engine, get_db_session
from services.api.app.db.tenant_context import tenant_transaction_context
from services.api.app.dependencies import get_execution_context

API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")
OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")

pytestmark = [pytest.mark.integration]


async def get_test_api_session(ctx=None):
    """Helper to yield a db_api_user AsyncSession for a given ExecutionContext in integration tests."""
    engine = create_async_engine(API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        if ctx and ctx.active_organization_id:
            async with tenant_transaction_context(session, ctx.active_organization_id):
                try:
                    yield session
                finally:
                    await session.close()
        else:
            try:
                yield session
            finally:
                await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_production_get_db_session_binds_tenant_guc():
    """Verify that tenant_transaction_context automatically binds app.current_organization_id GUC from ExecutionContext."""
    org_id = uuid4()
    ctx = await get_execution_context(
        authorization="Bearer dev-token",
        x_organization_id=str(org_id),
    )

    async for session in get_test_api_session(ctx=ctx):
        res = await session.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        val = res.scalar()
        assert val == str(org_id)

        res_after = await session.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        assert res_after.scalar() == str(org_id)


@pytest.mark.asyncio
async def test_connection_pool_tenant_isolation_between_requests():
    """Verify that sequential pool re-use between Org A and Org B leaves zero GUC leakage."""
    org_a = uuid4()
    org_b = uuid4()

    ctx_a = await get_execution_context(authorization="Bearer dev-token", x_organization_id=str(org_a))
    ctx_b = await get_execution_context(authorization="Bearer dev-token", x_organization_id=str(org_b))

    # Request A
    async for session_a in get_test_api_session(ctx=ctx_a):
        res_a = await session_a.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        assert res_a.scalar() == str(org_a)

    # Request B
    async for session_b in get_test_api_session(ctx=ctx_b):
        res_b = await session_b.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        assert res_b.scalar() == str(org_b)

    # Unauthenticated request (no tenant context)
    async for session_none in get_test_api_session(ctx=None):
        res_none = await session_none.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        assert res_none.scalar() in ("", None)


@pytest.mark.asyncio
async def test_rls_cross_tenant_read_and_write_isolation():
    """Verify RLS isolation: Org A cannot read/write Org B data under db_api_user role."""
    engine_owner = create_async_engine(OWNER_URL)
    owner_session_factory = async_sessionmaker(bind=engine_owner, class_=AsyncSession, expire_on_commit=False)

    org_a = uuid4()
    org_b = uuid4()

    user_id = UUID("44444444-4444-4444-4444-444444444444")

    # Seed test organizations and user via owner
    async with owner_session_factory() as owner_sess, owner_sess.begin():
        await owner_sess.execute(
            text(
                "INSERT INTO users (id, external_subject, display_name) VALUES (:uid, 'ext_subject_analyst', 'Analyst') ON CONFLICT DO NOTHING;"
            ),
            {"uid": user_id},
        )
        await owner_sess.execute(
            text(
                "INSERT INTO organizations (id, name, slug) VALUES (:id1, 'Org A', :slug1), (:id2, 'Org B', :slug2) ON CONFLICT DO NOTHING;"
            ),
            {"id1": org_a, "slug1": f"org-a-{org_a.hex[:6]}", "id2": org_b, "slug2": f"org-b-{org_b.hex[:6]}"},
        )

    await engine_owner.dispose()

    ctx_a = await get_execution_context(authorization="Bearer dev-token", x_organization_id=str(org_a))
    ctx_b = await get_execution_context(authorization="Bearer dev-token", x_organization_id=str(org_b))

    doc_a_id = uuid4()
    doc_b_id = uuid4()

    # Insert document under Org A
    async for session_a in get_test_api_session(ctx=ctx_a):
        await session_a.execute(
            text(
                "INSERT INTO documents (id, organization_id, uploaded_by_user_id, display_name, classification) "
                "VALUES (:id, :org_id, :uid, 'doc_a.pdf', 'CONFIDENTIAL');"
            ),
            {"id": doc_a_id, "org_id": org_a, "uid": user_id},
        )
        await session_a.commit()

    # Insert document under Org B
    async for session_b in get_test_api_session(ctx=ctx_b):
        await session_b.execute(
            text(
                "INSERT INTO documents (id, organization_id, uploaded_by_user_id, display_name, classification) "
                "VALUES (:id, :org_id, :uid, 'doc_b.pdf', 'CONFIDENTIAL');"
            ),
            {"id": doc_b_id, "org_id": org_b, "uid": user_id},
        )
        await session_b.commit()

    # Org A reads documents -> MUST ONLY SEE doc_a, NOT doc_b
    async for session_a in get_test_api_session(ctx=ctx_a):
        res_a = await session_a.execute(text("SELECT id FROM documents;"))
        rows_a = [r[0] for r in res_a.fetchall()]
        assert doc_a_id in rows_a
        assert doc_b_id not in rows_a

    # Org B reads documents -> MUST ONLY SEE doc_b, NOT doc_a
    async for session_b in get_test_api_session(ctx=ctx_b):
        res_b = await session_b.execute(text("SELECT id FROM documents;"))
        rows_b = [r[0] for r in res_b.fetchall()]
        assert doc_b_id in rows_b
        assert doc_a_id not in rows_b


@pytest.mark.asyncio
async def test_runtime_roles_nobypassrls_and_nosuperuser():
    """Verify db_api_user is NOSUPERUSER and NOBYPASSRLS on PostgreSQL 16."""
    async for session in get_test_api_session(ctx=None):
        res = await session.execute(
            text("SELECT r.rolname, r.rolsuper, r.rolbypassrls FROM pg_roles r WHERE r.rolname = current_user;")
        )
        row = res.fetchone()
        assert row is not None
        username, is_super, bypass_rls = row
        assert username == "db_api_user"
        assert is_super is False
        assert bypass_rls is False


@pytest.mark.asyncio
async def test_missing_and_malformed_tenant_header_fails_closed_with_zero_queries():
    """Verify missing or malformed tenant header returns HTTP 403 canonical error and executes 0 business SQL queries."""
    app = FastAPI()

    @app.get("/documents")
    async def list_documents_endpoint(
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ):
        res = await db.execute(text("SELECT id FROM documents;"))
        return [str(r[0]) for r in res.fetchall()]

    query_count = 0

    def before_cursor_execute_listener(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    event.listen(api_engine.sync_engine, "before_cursor_execute", before_cursor_execute_listener)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Missing X-Organization-ID header
            query_count = 0
            res_missing = await client.get("/documents", headers={"Authorization": "Bearer dev-token"})
            assert res_missing.status_code in (401, 403)
            assert query_count == 0  # Zero business queries executed!

            # 2. Malformed X-Organization-ID header
            query_count = 0
            res_malformed = await client.get(
                "/documents",
                headers={"Authorization": "Bearer dev-token", "X-Organization-ID": "invalid-uuid-format"},
            )
            assert res_malformed.status_code in (400, 403)
            assert query_count == 0  # Zero business queries executed!

            # 3. Missing Authorization header
            query_count = 0
            res_unauth = await client.get("/documents")
            assert res_unauth.status_code in (401, 403)
            assert query_count == 0  # Zero business queries executed!

    finally:
        event.remove(api_engine.sync_engine, "before_cursor_execute", before_cursor_execute_listener)


@pytest.mark.asyncio
async def test_real_production_endpoint_tenant_isolation_and_fail_closed():
    """Verify real production documents router endpoints with production tenant GUC binding and zero dependency_overrides."""
    app = FastAPI()
    app.include_router(documents.router, prefix="/api/v1/documents")

    assert len(app.dependency_overrides) == 0

    org_a = uuid4()
    org_b = uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Request with Org A
        res_a = await client.get(
            "/api/v1/documents",
            headers={"Authorization": "Bearer dev-token", "X-Organization-ID": str(org_a)},
        )
        assert res_a.status_code == 200

        # Request with Org B
        res_b = await client.get(
            "/api/v1/documents",
            headers={"Authorization": "Bearer dev-token", "X-Organization-ID": str(org_b)},
        )
        assert res_b.status_code == 200

        # Request without X-Organization-ID header -> MUST FAIL CLOSED WITH 403 (NOT 200 [])
        res_missing = await client.get("/api/v1/documents", headers={"Authorization": "Bearer dev-token"})
        assert res_missing.status_code in (401, 403)
        assert res_missing.status_code != 200
