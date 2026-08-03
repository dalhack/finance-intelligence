import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_migration_023_catalog_and_security():
    """Verify Migration 023 catalog properties, FORCE RLS, role grants, immutability trigger, and partial unique index."""
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
        ]

        # 2. Verify RLS & FORCE RLS attributes on analysis_clarifications
        rls_res = await db_owner.execute(
            text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'analysis_clarifications';")
        )
        rls_row = rls_res.fetchone()
        assert rls_row is not None
        assert rls_row[0] is True, "RLS not enabled on analysis_clarifications"
        assert rls_row[1] is True, "FORCE RLS not enabled on analysis_clarifications"

        # 3. Verify Partial Unique Index
        idx_res = await db_owner.execute(
            text("SELECT indexname FROM pg_indexes WHERE indexname = 'uq_active_clarification_per_job';")
        )
        idx_row = idx_res.fetchone()
        assert idx_row is not None, "Partial unique index uq_active_clarification_per_job missing"

        # 4. Verify Immutability Trigger
        trg_res = await db_owner.execute(
            text("SELECT tgname FROM pg_trigger WHERE tgname = 'check_analysis_clarifications_immutability';")
        )
        trg_row = trg_res.fetchone()
        assert trg_row is not None, "Immutability trigger check_analysis_clarifications_immutability missing"
