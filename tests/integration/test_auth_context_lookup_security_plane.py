import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_resolve_auth_context_dynamic_permissions_and_acl_isolation():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    viewer_user_id = uuid.uuid4()
    sub_analyst = f"sub-analyst-{user_id.hex[:6]}"
    sub_viewer = f"sub-viewer-{viewer_user_id.hex[:6]}"

    async with OwnerSession() as db_owner:
        # Seed org, users, memberships
        await db_owner.execute(
            text(
                "INSERT INTO public.organizations (id, name, slug, status, created_at) VALUES (:id, 'Auth Test Org', :slug, 'active', now())"
            ),
            {"id": org_id, "slug": f"auth-org-{org_id.hex[:6]}"},
        )
        await db_owner.execute(
            text(
                "INSERT INTO public.users (id, external_subject, identity_provider, display_name, status, created_at, updated_at) VALUES (:id, :sub, 'firebase', 'Analyst User', 'active', now(), now())"
            ),
            {"id": user_id, "sub": sub_analyst},
        )
        await db_owner.execute(
            text(
                "INSERT INTO public.users (id, external_subject, identity_provider, display_name, status, created_at, updated_at) VALUES (:id, :sub, 'firebase', 'Viewer User', 'active', now(), now())"
            ),
            {"id": viewer_user_id, "sub": sub_viewer},
        )

        mem_analyst_id = uuid.uuid4()
        mem_viewer_id = uuid.uuid4()
        await db_owner.execute(
            text(
                "INSERT INTO public.memberships (id, user_id, organization_id, status, created_at, updated_at) VALUES (:id, :user_id, :org_id, 'active', now(), now())"
            ),
            {"id": mem_analyst_id, "user_id": user_id, "org_id": org_id},
        )
        await db_owner.execute(
            text(
                "INSERT INTO public.memberships (id, user_id, organization_id, status, created_at, updated_at) VALUES (:id, :user_id, :org_id, 'active', now(), now())"
            ),
            {"id": mem_viewer_id, "user_id": viewer_user_id, "org_id": org_id},
        )

        # Assign ANALYST role to analyst user
        await db_owner.execute(
            text("""
                INSERT INTO public.membership_roles (id, membership_id, role_id, organization_id)
                SELECT gen_random_uuid(), :mem_id, r.id, :org_id
                  FROM public.roles r WHERE r.name = 'ANALYST';
            """),
            {"mem_id": mem_analyst_id, "org_id": org_id},
        )

        # Assign VIEWER role to viewer user
        await db_owner.execute(
            text("""
                INSERT INTO public.membership_roles (id, membership_id, role_id, organization_id)
                SELECT gen_random_uuid(), :mem_id, r.id, :org_id
                  FROM public.roles r WHERE r.name = 'VIEWER';
            """),
            {"mem_id": mem_viewer_id, "org_id": org_id},
        )
        await db_owner.commit()

    # 1. Verify db_api_user execution and dynamic ANALYST permission resolution
    async with ApiSession() as db_api:
        res = await db_api.execute(
            text("SELECT * FROM public.resolve_auth_context(:sub, :org_id);"),
            {"sub": sub_analyst, "org_id": org_id},
        )
        row = res.fetchone()
        assert row is not None
        assert row.actor_user_id == user_id
        assert row.active_organization_id == org_id
        assert row.roles == ["ANALYST"]
        # Exactly 15 permissions assigned to ANALYST (11 base + 4 analyses)
        assert len(row.permissions) == 15
        assert "documents:upload" in row.permissions
        assert "documents:finalize" in row.permissions
        assert "analyses:run" in row.permissions
        assert "facts:candidates:review" not in row.permissions
        assert "facts:verify_revision" not in row.permissions

    # 2. Verify dynamic VIEWER permission resolution
    async with ApiSession() as db_api:
        res = await db_api.execute(
            text("SELECT * FROM public.resolve_auth_context(:sub, :org_id);"),
            {"sub": sub_viewer, "org_id": org_id},
        )
        row = res.fetchone()
        assert row is not None
        assert row.roles == ["VIEWER"]
        # Exactly 8 permissions assigned to VIEWER (7 base + 1 analyses:read)
        assert len(row.permissions) == 8
        assert "documents:read" in row.permissions
        assert "analyses:read" in row.permissions
        assert "documents:upload" not in row.permissions

    # 3. Verify Direct Table SELECT Revocation (Option 3B) for db_api_user
    async with ApiSession() as db_api:
        with pytest.raises(Exception) as exc_users:
            await db_api.execute(text("SELECT count(*) FROM public.users;"))
        assert "permission denied" in str(exc_users.value).lower()

    async with ApiSession() as db_api:
        with pytest.raises(Exception) as exc_mem:
            await db_api.execute(text("SELECT count(*) FROM public.memberships;"))
        assert "permission denied" in str(exc_mem.value).lower()

    # Cleanup with owner role
    async with OwnerSession() as db_owner:
        await db_owner.execute(
            text("DELETE FROM public.membership_roles WHERE organization_id = :org_id;"), {"org_id": org_id}
        )
        await db_owner.execute(
            text("DELETE FROM public.memberships WHERE organization_id = :org_id;"), {"org_id": org_id}
        )
        await db_owner.execute(
            text("DELETE FROM public.users WHERE id IN (:u1, :u2);"), {"u1": user_id, "u2": viewer_user_id}
        )
        await db_owner.execute(text("DELETE FROM public.organizations WHERE id = :org_id;"), {"org_id": org_id})
        await db_owner.commit()

    await owner_engine.dispose()
    await api_engine.dispose()
