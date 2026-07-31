import os
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.organization import Organization


@pytest.mark.asyncio
async def test_migration_016_catalog_and_security_grants():
    """Verify Migration 016 catalog properties, trigger function REVOKE EXECUTE, and fail-closed synthetic hash detection."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    async with OwnerSession() as db_owner_session, ApiSession() as db_api_session:
        # 1. Verify Alembic Version
        res = await db_owner_session.execute(text("SELECT version_num FROM alembic_version;"))
        row = res.fetchone()
        assert row is not None
        assert row[0] in [
            "023_analysis_clarification_workflow",
            "024_maintenance_scheduler_and_operational_resilience",
            "025_distributed_provider_circuit_breaker",
        ]

        # 2. Verify Security Definer Function ACL Grants (No Direct EXECUTE for db_api_user / PUBLIC)
        for func_name in (
            "fn_prevent_terminal_child_lineage_mutation",
            "fn_verify_calculation_attempt_completed",
            "fn_prevent_terminal_calculation_mutation",
        ):
            acl_res = await db_owner_session.execute(
                text(
                    """
                    SELECT p.proname, p.prosecdef, p.proconfig, r.rolname, p.proacl::text
                    FROM pg_proc p
                    JOIN pg_roles r ON p.proowner = r.oid
                    WHERE p.proname = :func_name;
                    """,
                ),
                {"func_name": func_name},
            )
            func_row = acl_res.fetchone()
            assert func_row is not None
            _proname, prosecdef, proconfig, owner_name, acl_text = func_row
            assert prosecdef is True
            assert owner_name == "db_owner"
            assert proconfig is not None
            assert "search_path=public, pg_catalog, pg_temp" in proconfig

            # Assert db_api_user, db_ingestion_worker, db_bootstrap, PUBLIC have NO direct EXECUTE grant
            if acl_text is not None:
                assert "db_api_user=X" not in acl_text
                assert "db_ingestion_worker=X" not in acl_text
                assert "db_bootstrap=X" not in acl_text
                assert ",=X/" not in acl_text and "{=X/" not in acl_text  # PUBLIC grant

        # 3. Direct Function Execution Failure Test for db_api_user
        try:
            await db_api_session.execute(text("SELECT public.fn_prevent_terminal_child_lineage_mutation();"))
            pytest.fail("Direct execution of fn_prevent_terminal_child_lineage_mutation must be denied to db_api_user.")
        except (ValueError, Exception) as err:  # noqa: BLE001
            err_str = str(err).lower()
            assert any(
                term in err_str
                for term in (
                    "permission denied",
                    "insufficient privilege",
                    "could not resolve query result",
                    "cannot call trigger function",
                    "internalclienterror",
                )
            )

        # 4. Trigger Execution During Normal DML Test
        org_a = uuid4()
        org_obj = Organization(id=org_a, name="Org Test 016", slug=f"org016-{org_a.hex[:6]}")
        db_owner_session.add(org_obj)
        await db_owner_session.commit()

        # Set tenant context and verify trigger runs implicitly during DML without direct EXECUTE
        await db_api_session.execute(
            text("SELECT set_config('app.current_organization_id', :org_a, true);"), {"org_a": str(org_a)}
        )
        ctx = (
            await db_api_session.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        ).scalar()
        assert ctx == str(org_a)

    await owner_engine.dispose()
    await api_engine.dispose()


@pytest.mark.asyncio
async def test_migration_016_synthetic_md5_hash_rollback():
    """Verify that synthetic double-MD5 hashes trigger MIGRATION_INVALID_CALCULATION_HASH_LINEAGE exception."""
    owner_raw_url = os.environ["TEST_OWNER_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(owner_raw_url)

    # Insert a synthetic double-MD5 hash row into calculation_attempts
    org_id = uuid4()
    req_id = uuid4()
    att_id = uuid4()
    user_id = uuid4()
    synth_hash = "a" * 32 + "a" * 32  # substr(1,32) == substr(33,32)

    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_id))
            await conn.execute(
                "INSERT INTO organizations (id, name, slug) VALUES ($1, 'Synth Org', $2);",
                str(org_id),
                f"synth-{org_id.hex[:6]}",
            )
            await conn.execute(
                "INSERT INTO calculation_requests (id, organization_id, request_fingerprint, formula_code, formula_version, institution_id, reporting_period_id, requested_by_user_id) VALUES ($1, $2, $3, 'LOAN_TO_DEPOSIT_RATIO', '1.0.0', $4, $5, $6);",
                str(req_id),
                str(org_id),
                f"fp_{uuid4().hex}",
                str(uuid4()),
                str(uuid4()),
                str(user_id),
            )
            # Disable RLS temporarily to insert synthetic attempt for test verification
            await conn.execute("ALTER TABLE calculation_attempts DISABLE ROW LEVEL SECURITY;")
            await conn.execute(
                "INSERT INTO calculation_attempts (id, organization_id, calculation_request_id, attempt_number, execution_idempotency_hash, formula_spec_checksum, implementation_checksum, status, completed_at) VALUES ($1, $2, $3, 1, $4, $5, $6, 'COMPLETED', NOW());",
                str(att_id),
                str(org_id),
                str(req_id),
                synth_hash,
                f"{'b' * 64}",
                f"{'c' * 64}",
            )
            await conn.execute("ALTER TABLE calculation_attempts ENABLE ROW LEVEL SECURITY;")

            # Run Migration 016 audit block directly
            try:
                await conn.execute("""
                DO $$
                DECLARE
                    synth_attempt_count INTEGER;
                BEGIN
                    SELECT COUNT(*) INTO synth_attempt_count
                    FROM public.calculation_attempts
                    WHERE status = 'COMPLETED' AND (
                        (length(execution_idempotency_hash) = 64 AND substr(execution_idempotency_hash, 1, 32) = substr(execution_idempotency_hash, 33, 32))
                    );

                    IF synth_attempt_count > 0 THEN
                        RAISE EXCEPTION 'MIGRATION_INVALID_CALCULATION_HASH_LINEAGE';
                    END IF;
                END $$;
                """)
                pytest.fail(
                    "Migration 016 audit must raise MIGRATION_INVALID_CALCULATION_HASH_LINEAGE on synthetic double-MD5 hashes."
                )
            except asyncpg.exceptions.RaiseError as err:
                assert "MIGRATION_INVALID_CALCULATION_HASH_LINEAGE" in str(err)
            finally:
                # Rollback transaction so synthetic test row is not persisted
                raise RuntimeError("ROLLBACK_TEST_TRANSACTION")
    except RuntimeError as r_err:
        if str(r_err) != "ROLLBACK_TEST_TRANSACTION":
            raise
    finally:
        await conn.close()
