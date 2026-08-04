import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from services.api.app.core.migration_policy import (
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

    # 2. Upgrade to head (028)
    run_alembic_cmd("upgrade", "head")

    conn1 = await asyncpg.connect(RAW_ROUNDTRIP_URL)
    up_tables = await conn1.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    up_table_names = [t["table_name"] for t in up_tables]
    assert "organizations" in up_table_names
    assert "memberships" in up_table_names
    assert "documents" in up_table_names

    final_rev = await conn1.fetchrow("SELECT version_num FROM alembic_version;")
    assert final_rev is not None
    assert final_rev["version_num"] == "028_remove_organization_only_actor_lookup"

    helper_exists_028 = await conn1.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'get_current_user_id');"
    )
    assert helper_exists_028 is False
    await conn1.close()

    # 3. Roundtrip downgrade 028 -> 027
    run_alembic_cmd("downgrade", "027_auth_context_lookup_security_plane")

    conn2 = await asyncpg.connect(RAW_ROUNDTRIP_URL)
    downgrade_rev = await conn2.fetchrow("SELECT version_num FROM alembic_version;")
    assert downgrade_rev is not None
    assert downgrade_rev["version_num"] == "027_auth_context_lookup_security_plane"

    helper_exists_027 = await conn2.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'get_current_user_id');"
    )
    assert helper_exists_027 is True
    await conn2.close()

    # 4. Re-upgrade 027 -> 028
    run_alembic_cmd("upgrade", "head")

    conn3 = await asyncpg.connect(RAW_ROUNDTRIP_URL)
    re_up_rev = await conn3.fetchrow("SELECT version_num FROM alembic_version;")
    assert re_up_rev is not None
    assert re_up_rev["version_num"] == "028_remove_organization_only_actor_lookup"

    helper_exists_028_again = await conn3.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'get_current_user_id');"
    )
    assert helper_exists_028_again is False

    func_exists_028 = await conn3.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'resolve_auth_context');"
    )
    assert func_exists_028 is True

    # 5. Verify ACL Privileges for resolve_auth_context
    has_api_exec = await conn3.fetchval(
        "SELECT has_function_privilege('db_api_user', 'resolve_auth_context(text, uuid)', 'EXECUTE');"
    )
    has_public_exec = await conn3.fetchval(
        "SELECT has_function_privilege('public', 'resolve_auth_context(text, uuid)', 'EXECUTE');"
    )
    has_worker_exec = await conn3.fetchval(
        "SELECT has_function_privilege('db_ingestion_worker', 'resolve_auth_context(text, uuid)', 'EXECUTE');"
    )
    assert has_api_exec is True
    assert has_public_exec is False
    assert has_worker_exec is False

    await conn3.close()
