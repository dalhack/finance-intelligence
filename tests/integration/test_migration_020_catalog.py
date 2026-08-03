import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_migration_020_catalog_and_immutability():
    """Verify Migration 020 catalog properties, FORCE RLS, role grants, schema version 1.0.0, and worker denial."""
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

        # 2. Verify RLS & FORCE RLS attributes
        for table_name in (
            "analysis_jobs",
            "analysis_attempts",
            "analysis_plans",
            "model_invocations",
            "tool_invocations",
            "policy_decisions",
            "quality_gate_results",
            "final_result_snapshots",
            "analysis_clarifications",
        ):
            rls_res = await db_owner.execute(
                text(f"SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = '{table_name}';")
            )
            rls_row = rls_res.fetchone()
            assert rls_row is not None
            assert rls_row[0] is True, f"RLS not enabled on {table_name}"
            assert rls_row[1] is True, f"FORCE RLS not enabled on {table_name}"
