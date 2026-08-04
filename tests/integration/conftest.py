import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

REQUIRED_ENV_ROLES = {
    "TEST_OWNER_DATABASE_URL": "db_owner",
    "TEST_BOOTSTRAP_DATABASE_URL": "db_bootstrap",
    "TEST_API_DATABASE_URL": "db_api_user",
    "TEST_WORKER_DATABASE_URL": "db_ingestion_worker",
    "TEST_ROUNDTRIP_DATABASE_URL": "db_owner",
}

EXPECTED_HEAD_REVISION = "030_reconcile_application_role_catalog"


async def run_real_preflight_checks():
    """Execute redacted preflight checks across all required database environments."""
    for env_var in REQUIRED_ENV_ROLES:
        if not os.environ.get(env_var):
            pytest.fail(f"PREFLIGHT_URL_MISSING: {env_var}")

    for env_var, expected_role in REQUIRED_ENV_ROLES.items():
        raw_url = os.environ.get(env_var, "")
        if "prod" in raw_url.lower() or "staging" in raw_url.lower():
            pytest.fail(f"PREFLIGHT_URL_INVALID: {env_var}")

        try:
            parsed = make_url(raw_url)
            if not parsed.username or parsed.username != expected_role:
                pytest.fail(f"PREFLIGHT_ROLE_MISMATCH: {env_var}")
        except Exception:  # noqa: BLE001
            pytest.fail(f"PREFLIGHT_URL_INVALID: {env_var}")

        # Execute real database connection & SQL checks
        try:
            engine = create_async_engine(raw_url, pool_pre_ping=True)
            async with engine.connect() as conn:
                res = await conn.execute(text("SELECT current_user, current_database(), version();"))
                user, db_name, version_str = res.fetchone()

                if user != expected_role:
                    pytest.fail(f"PREFLIGHT_ROLE_MISMATCH: {env_var}")

                if "PostgreSQL 16" not in version_str:
                    pytest.fail(f"PREFLIGHT_POSTGRES_VERSION_MISMATCH: {env_var}")

                if env_var == "TEST_ROUNDTRIP_DATABASE_URL":
                    if db_name != "finance_intelligence_roundtrip_test":
                        pytest.fail(f"PREFLIGHT_DATABASE_POLICY_FAILED: {env_var}")
                else:
                    if db_name != "finance_intelligence_test":
                        pytest.fail(f"PREFLIGHT_DATABASE_POLICY_FAILED: {env_var}")

                # Check Alembic Head Revision
                head_res = await conn.execute(text("SELECT version_num FROM alembic_version;"))
                row = head_res.fetchone()
                if not row or row[0] != EXPECTED_HEAD_REVISION:
                    pytest.fail(f"PREFLIGHT_MIGRATION_HEAD_MISMATCH: {env_var}")

                # Check NOBYPASSRLS and NOSUPERUSER for runtime roles
                if expected_role in ("db_api_user", "db_ingestion_worker", "db_bootstrap"):
                    role_res = await conn.execute(
                        text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :role;"),
                        {"role": expected_role},
                    )
                    role_row = role_res.fetchone()
                    if role_row:
                        rolsuper, rolbypassrls = role_row
                        if rolsuper is True or rolbypassrls is True:
                            pytest.fail(f"PREFLIGHT_BYPASSRLS_VIOLATION: {env_var}")

            await engine.dispose()
        except Exception as err:
            err_str = str(err)
            if any(
                code in err_str
                for code in (
                    "PREFLIGHT_URL_MISSING",
                    "PREFLIGHT_URL_INVALID",
                    "PREFLIGHT_ROLE_MISMATCH",
                    "PREFLIGHT_DATABASE_POLICY_FAILED",
                    "PREFLIGHT_POSTGRES_VERSION_MISMATCH",
                    "PREFLIGHT_MIGRATION_HEAD_MISMATCH",
                    "PREFLIGHT_BYPASSRLS_VIOLATION",
                )
            ):
                raise
            pytest.fail(f"PREFLIGHT_CONNECTION_FAILED: {env_var}")


@pytest.fixture(scope="session", autouse=True)
async def verify_integration_test_environment():
    """Mandatory zero-skip integration test preflight fixture."""
    await run_real_preflight_checks()


@pytest.fixture(autouse=True)
async def cleanup_engine_pools():
    """Dispose pooled connections between async test executions to prevent cross-test loop contamination."""
    yield
    from services.api.app.db.session import api_engine, bootstrap_engine, worker_engine

    await api_engine.dispose()
    await worker_engine.dispose()
    await bootstrap_engine.dispose()
