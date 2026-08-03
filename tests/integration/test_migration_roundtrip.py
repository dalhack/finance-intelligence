import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from services.api.app.core.migration_policy import (
    get_minimum_safe_downgrade_target,
    validate_downgrade_target,
)

DEFAULT_ROUNDTRIP_URL = os.environ.get("TEST_OWNER_DATABASE_URL", "").replace(
    "/finance_intelligence_test", "/finance_intelligence_roundtrip_test"
)
ROUNDTRIP_URL = os.environ.get("TEST_ROUNDTRIP_DATABASE_URL") or DEFAULT_ROUNDTRIP_URL
RAW_ROUNDTRIP_URL = ROUNDTRIP_URL.replace("postgresql+asyncpg://", "postgresql://") if ROUNDTRIP_URL else None


def run_alembic_cmd(action: str, target: str):
    env = os.environ.copy()
    env["ALEMBIC_TARGET_URL"] = ROUNDTRIP_URL
    env["DATABASE_URL"] = ROUNDTRIP_URL
    env["TEST_OWNER_DATABASE_URL"] = ROUNDTRIP_URL

    ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "services", "api", "alembic.ini"))

    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        ini_path,
        "-x",
        f"sqlalchemy.url={ROUNDTRIP_URL}",
        action,
        target,
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)

    if res.returncode != 0:
        pytest.fail(
            f"Alembic {action} {target} failed with exit code {res.returncode}.\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        )


@pytest.mark.asyncio
async def test_migration_upgrade_downgrade_roundtrip():
    # 1. Test pre-execution rejection of targets below safe boundary (022, base)
    for unsafe_target in ("022", "base"):
        with pytest.raises(RuntimeError) as exc_info:
            validate_downgrade_target(unsafe_target)
        assert "MIGRATION_IRREVERSIBLE_BOUNDARY_VIOLATION" in str(exc_info.value)
        assert "postgresql" not in str(exc_info.value).lower()
        assert "owner_pass" not in str(exc_info.value).lower()

    # 2. Upgrade to head (026)
    run_alembic_cmd("upgrade", "head")

    conn1 = await asyncpg.connect(RAW_ROUNDTRIP_URL)
    up_tables = await conn1.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    up_table_names = [t["table_name"] for t in up_tables]
    assert "organizations" in up_table_names
    assert "memberships" in up_table_names
    assert "documents" in up_table_names

    final_rev = await conn1.fetchrow("SELECT version_num FROM alembic_version;")
    assert final_rev is not None
    assert final_rev["version_num"] == "026_public_schema_acl_hardening"
    await conn1.close()

    # 3. Safe roundtrip downgrade to safe boundary (023_analysis_clarification_workflow)
    safe_target = get_minimum_safe_downgrade_target("head")
    assert safe_target == "023_analysis_clarification_workflow"
    validate_downgrade_target(safe_target)

    run_alembic_cmd("downgrade", safe_target)

    conn2 = await asyncpg.connect(RAW_ROUNDTRIP_URL)
    boundary_rev = await conn2.fetchrow("SELECT version_num FROM alembic_version;")
    assert boundary_rev is not None
    assert boundary_rev["version_num"] == "023_analysis_clarification_workflow"
    await conn2.close()

    # 4. Re-upgrade to head (026)
    run_alembic_cmd("upgrade", "head")

    conn3 = await asyncpg.connect(RAW_ROUNDTRIP_URL)
    re_up_rev = await conn3.fetchrow("SELECT version_num FROM alembic_version;")
    assert re_up_rev is not None
    assert re_up_rev["version_num"] == "026_public_schema_acl_hardening"

    # Verify db_app_user has NO effective privileges
    has_select_doc = await conn3.fetchval("SELECT has_table_privilege('db_app_user', 'documents', 'SELECT');")
    has_schema_usage = await conn3.fetchval("SELECT has_schema_privilege('db_app_user', 'public', 'USAGE');")
    assert has_select_doc is False
    assert has_schema_usage is False

    # Verify db_bootstrap has NO EXECUTE on runtime functions
    has_boot_exec = await conn3.fetchval(
        "SELECT has_function_privilege('db_bootstrap', 'claim_ingestion_job(uuid, text, uuid)', 'EXECUTE');"
    )
    assert has_boot_exec is False

    await conn3.close()
