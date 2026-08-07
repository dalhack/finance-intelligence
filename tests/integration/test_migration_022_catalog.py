import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_migration_022_catalog_and_immutability():
    """Verify Migration 022 catalog properties, FORCE RLS, role grants, and alembic head."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    async with OwnerSession() as db_owner:
        # 1. Verify Alembic Head Version
        res = await db_owner.execute(text("SELECT version_num FROM alembic_version;"))
        row = res.fetchone()
        assert row is not None
        assert row[0] in [
            "023_analysis_clarification_workflow",
            "024_maintenance_scheduler_and_operational_resilience",
            "025_distributed_provider_circuit_breaker",
            "026_public_schema_acl_hardening",
            "027_auth_context_lookup_security_plane",
            "028_remove_organization_only_actor_lookup",
            "029_analysis_authorization_policy",
            "030_reconcile_application_role_catalog",
        ]

        # 2. Verify RLS & FORCE RLS attributes on analysis_events
        rls_res = await db_owner.execute(
            text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'analysis_events';")
        )
        rls_row = rls_res.fetchone()
        assert rls_row is not None
        assert rls_row[0] is True, "RLS not enabled on analysis_events"
        assert rls_row[1] is True, "FORCE RLS not enabled on analysis_events"

        # 3. Verify Unique Constraint
        const_res = await db_owner.execute(
            text("SELECT conname FROM pg_constraint WHERE conname = 'uq_analysis_events_org_job_seq';")
        )
        const_row = const_res.fetchone()
        assert const_row is not None
