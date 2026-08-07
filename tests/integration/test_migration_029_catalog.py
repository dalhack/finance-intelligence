import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_migration_029_catalog_counts():
    """Verify Migration 029 catalog head revision, canonical permissions, and role mappings."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    async with OwnerSession() as session:
        head_res = await session.execute(text("SELECT version_num FROM alembic_version;"))
        version = head_res.scalar()
        assert version in (
            "029_analysis_authorization_policy",
            "030_reconcile_application_role_catalog",
            "031_analysis_job_claim_authority",
        )

        total_perms = (await session.execute(text("SELECT COUNT(*) FROM public.permissions;"))).scalar()
        assert total_perms == 17

        viewer_perms = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM public.role_permissions rp "
                    "JOIN public.roles r ON r.id = rp.role_id WHERE r.name = 'VIEWER';"
                )
            )
        ).scalar()
        assert viewer_perms == 8

        analyst_perms = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM public.role_permissions rp "
                    "JOIN public.roles r ON r.id = rp.role_id WHERE r.name = 'ANALYST';"
                )
            )
        ).scalar()
        assert analyst_perms == 15
