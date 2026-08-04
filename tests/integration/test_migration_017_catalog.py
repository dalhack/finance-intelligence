import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.comparison_run import ComparisonRun
from services.api.app.models.organization import Organization
from services.api.app.models.result_dataset_model import ResultDatasetModel


@pytest.mark.asyncio
async def test_migration_017_catalog_and_immutability():
    """Verify Migration 017 catalog properties, FORCE RLS, role grants, and append-only immutability triggers."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])
    worker_engine = create_async_engine(os.environ["TEST_WORKER_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)
    WorkerSession = async_sessionmaker(worker_engine, class_=AsyncSession, expire_on_commit=False)

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

        # 2. Verify RLS & FORCE RLS attributes
        for table_name in ("comparison_runs", "result_datasets"):
            rls_res = await db_owner.execute(
                text(
                    """
                    SELECT relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    WHERE relname = :table_name AND relnamespace = 'public'::regnamespace;
                    """
                ),
                {"table_name": table_name},
            )
            rls_row = rls_res.fetchone()
            assert rls_row is not None
            assert rls_row[0] is True  # ENABLE RLS
            assert rls_row[1] is True  # FORCE RLS

        # Seed organization
        org_id = uuid4()
        org = Organization(id=org_id, name="Cat Org 017", slug=f"cat17-{org_id.hex[:6]}")
        db_owner.add(org)
        await db_owner.commit()

        # Set tenant context for db_owner due to FORCE RLS
        await db_owner.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )

        # Seed comparison run & dataset model
        run_id = uuid4()
        ds_id = uuid4()

        run_obj = ComparisonRun(
            id=run_id,
            organization_id=org_id,
            requested_by_user_id=uuid4(),
            comparison_mode="CROSS_INSTITUTION",
            value_source_policy="PREFER_SOURCE_REPORTED",
            query_snapshot={"mode": "test"},
        )
        db_owner.add(run_obj)
        await db_owner.commit()

        ds_obj = ResultDatasetModel(
            id=ds_id,
            organization_id=org_id,
            comparison_run_id=run_id,
            schema_version="1.0.0",
            query_snapshot={"mode": "test"},
            dimensions_snapshot={},
            measures_snapshot=[],
            rows_snapshot=[],
            table_spec_snapshot={},
            chart_specs_snapshot=[],
            data_quality_summary={},
            warnings_snapshot=[],
        )
        db_owner.add(ds_obj)
        await db_owner.commit()

    async with ApiSession() as db_api:
        await db_api.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )

        # 3. Verify db_api_user can SELECT
        r_res = await db_api.execute(
            text("SELECT id FROM comparison_runs WHERE id = :run_id;"), {"run_id": str(run_id)}
        )
        assert r_res.scalar_one_or_none() == run_id

        # 4. Verify db_api_user cannot UPDATE (Permission Denied)
        try:
            await db_api.execute(
                text("UPDATE comparison_runs SET comparison_mode = 'MUTATED' WHERE id = :run_id;"),
                {"run_id": str(run_id)},
            )
            await db_api.commit()
            pytest.fail("UPDATE on comparison_runs must be denied for db_api_user.")
        except Exception as err:  # noqa: BLE001
            assert "permission denied" in str(err).lower() or "insufficient privilege" in str(err).lower()
        finally:
            await db_api.rollback()

    async with OwnerSession() as db_owner:
        await db_owner.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        # 5. Verify Immutability Trigger prevents UPDATE for db_owner
        try:
            await db_owner.execute(
                text("UPDATE comparison_runs SET comparison_mode = 'MUTATED' WHERE id = :run_id;"),
                {"run_id": str(run_id)},
            )
            await db_owner.commit()
            pytest.fail("UPDATE on comparison_runs must be blocked by IMMUTABLE_DATASET trigger.")
        except Exception as err:  # noqa: BLE001
            assert "IMMUTABLE_DATASET" in str(err) or "IMMUTABLE" in str(err)
        finally:
            await db_owner.rollback()

    async with WorkerSession() as db_worker:
        # 5. Verify Worker access denial
        try:
            await db_worker.execute(text("SELECT COUNT(*) FROM comparison_runs;"))
            pytest.fail("Worker role must be denied access to comparison_runs.")
        except Exception as err:  # noqa: BLE001
            assert "permission denied" in str(err).lower() or "insufficient privilege" in str(err).lower()

    await owner_engine.dispose()
    await api_engine.dispose()
    await worker_engine.dispose()
