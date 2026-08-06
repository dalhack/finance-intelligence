import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.main import app
from services.api.app.models.membership import Membership
from services.api.app.models.organization import Organization
from services.api.app.models.user import User


@pytest.mark.asyncio
async def test_migration_029_permission_catalog_counts():
    """Verify Migration 029 canonical permission count = 17, VIEWER = 8, ANALYST = 15."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    async with OwnerSession() as session:
        res_total = await session.execute(text("SELECT COUNT(*) FROM public.permissions;"))
        total_perms = res_total.scalar()
        assert total_perms == 17, f"Expected 17 canonical permissions, got {total_perms}"

        res_viewer = await session.execute(
            text(
                "SELECT COUNT(*) FROM public.role_permissions rp "
                "JOIN public.roles r ON r.id = rp.role_id WHERE r.name = 'VIEWER';"
            )
        )
        assert res_viewer.scalar() == 8

        res_analyst = await session.execute(
            text(
                "SELECT COUNT(*) FROM public.role_permissions rp "
                "JOIN public.roles r ON r.id = rp.role_id WHERE r.name = 'ANALYST';"
            )
        )
        assert res_analyst.scalar() == 15


@pytest.mark.asyncio
async def test_analyses_authorization_and_ownership_matrix():
    """Comprehensive test matrix for VIEWER, ANALYST Owner, ANALYST Non-owner, and Cross-Tenant."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    org_a_id = uuid4()
    org_b_id = uuid4()

    user_analyst_a_id = uuid4()
    user_analyst_b_id = uuid4()
    user_viewer_id = uuid4()

    sub_analyst_a = f"sub_analyst_a_{org_a_id.hex[:6]}"
    sub_analyst_b = f"sub_analyst_b_{org_a_id.hex[:6]}"
    sub_viewer = f"sub_viewer_{org_a_id.hex[:6]}"

    mem_analyst_a_id = uuid4()
    mem_analyst_b_id = uuid4()
    mem_viewer_id = uuid4()

    async with OwnerSession() as db:
        # Seed Organizations
        org_a = Organization(id=org_a_id, name="Auth Test Org A", slug=f"org-a-{org_a_id.hex[:6]}")
        org_b = Organization(id=org_b_id, name="Auth Test Org B", slug=f"org-b-{org_b_id.hex[:6]}")
        db.add_all([org_a, org_b])

        # Seed Users
        u_analyst_a = User(
            id=user_analyst_a_id,
            external_subject=sub_analyst_a,
            identity_provider="dev",
            display_name="Analyst A",
            status="active",
        )
        u_analyst_b = User(
            id=user_analyst_b_id,
            external_subject=sub_analyst_b,
            identity_provider="dev",
            display_name="Analyst B",
            status="active",
        )
        u_viewer = User(
            id=user_viewer_id,
            external_subject=sub_viewer,
            identity_provider="dev",
            display_name="Viewer",
            status="active",
        )
        db.add_all([u_analyst_a, u_analyst_b, u_viewer])
        await db.commit()

        # Retrieve Role IDs
        r_analyst = (await db.execute(text("SELECT id FROM roles WHERE name = 'ANALYST';"))).scalar()
        r_viewer = (await db.execute(text("SELECT id FROM roles WHERE name = 'VIEWER';"))).scalar()

        from app.db.tenant_context import tenant_transaction_context

        # Seed Memberships in Org A
        async with tenant_transaction_context(db, org_a_id):
            m_a = Membership(id=mem_analyst_a_id, organization_id=org_a_id, user_id=user_analyst_a_id, status="active")
            m_b = Membership(id=mem_analyst_b_id, organization_id=org_a_id, user_id=user_analyst_b_id, status="active")
            m_v = Membership(id=mem_viewer_id, organization_id=org_a_id, user_id=user_viewer_id, status="active")
            db.add_all([m_a, m_b, m_v])
            await db.commit()

        # Seed Role Permissions Mapping
        await db.execute(
            text(
                "INSERT INTO public.membership_roles (id, membership_id, role_id, organization_id) VALUES "
                "(:id1, :m_a, :r_analyst_1, :org_a_1), "
                "(:id2, :m_b, :r_analyst_2, :org_a_2), "
                "(:id3, :m_v, :r_viewer, :org_a_3);"
            ),
            {
                "id1": uuid4(),
                "m_a": mem_analyst_a_id,
                "r_analyst_1": r_analyst,
                "org_a_1": org_a_id,
                "id2": uuid4(),
                "m_b": mem_analyst_b_id,
                "r_analyst_2": r_analyst,
                "org_a_2": org_a_id,
                "id3": uuid4(),
                "m_v": mem_viewer_id,
                "r_viewer": r_viewer,
                "org_a_3": org_a_id,
            },
        )
        await db.commit()

    token_analyst_a = f"dev-token-{sub_analyst_a}"
    token_analyst_b = f"dev-token-{sub_analyst_b}"
    token_viewer = f"dev-token-{sub_viewer}"

    headers_analyst_a = {"Authorization": f"Bearer {token_analyst_a}", "X-Organization-ID": str(org_a_id)}
    headers_analyst_b = {"Authorization": f"Bearer {token_analyst_b}", "X-Organization-ID": str(org_a_id)}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}", "X-Organization-ID": str(org_a_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. VIEWER Rejections on Mutation Endpoints (403 Forbidden)
        resp_v_create = await client.post(
            "/api/v1/analyses", headers=headers_viewer, json={"prompt": "Viewer create attempt"}
        )
        assert resp_v_create.status_code == 403

        # 2. ANALYST User A Creates Job (201 Created & Owner Attribution)
        resp_a_create = await client.post(
            "/api/v1/analyses", headers=headers_analyst_a, json={"prompt": "Analyst A prompt"}
        )
        assert resp_a_create.status_code == 201
        job_data = resp_a_create.json()
        job_id = job_data["id"]
        assert job_data["user_id"] == str(user_analyst_a_id)

        # 3. VIEWER Allowed to Read Analysis Job & List (200 OK)
        resp_v_get = await client.get(f"/api/v1/analyses/{job_id}", headers=headers_viewer)
        assert resp_v_get.status_code == 200

        resp_v_list = await client.get("/api/v1/analyses", headers=headers_viewer)
        assert resp_v_list.status_code == 200

        # 4. ANALYST User B (Non-Owner) Tries to Cancel User A's Job -> 403 Forbidden
        resp_b_cancel = await client.post(f"/api/v1/analyses/{job_id}/cancel", headers=headers_analyst_b)
        assert resp_b_cancel.status_code == 403

        # 5. ANALYST User A (Owner) Cancels Own Job -> 200 OK
        resp_a_cancel = await client.post(f"/api/v1/analyses/{job_id}/cancel", headers=headers_analyst_a)
        assert resp_a_cancel.status_code == 200
        assert resp_a_cancel.json()["status"] == "CANCELLED"

        # 6. Cross-Tenant Test: Organization B User cannot read Organization A Job
        headers_org_b = {"Authorization": f"Bearer {token_analyst_a}", "X-Organization-ID": str(org_b_id)}
        resp_cross = await client.get(f"/api/v1/analyses/{job_id}", headers=headers_org_b)
        # Should be 403 (membership required in Org B) or 404
        assert resp_cross.status_code in (403, 404)
