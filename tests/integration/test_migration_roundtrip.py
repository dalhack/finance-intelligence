import os
import subprocess
import sys

import asyncpg
import pytest

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
    # Step 1: Upgrade to head (010_fact_revision_uniqueness)
    run_alembic_cmd("upgrade", "head")

    conn1 = await asyncpg.connect(RAW_ROUNDTRIP_URL)
    up_tables = await conn1.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    up_table_names = [t["table_name"] for t in up_tables]
    assert "organizations" in up_table_names
    assert "memberships" in up_table_names
    assert "documents" in up_table_names
    assert "ingestion_jobs" in up_table_names
    assert "financial_facts" in up_table_names
    assert "ingestion_command_logs" in up_table_names

    final_rev = await conn1.fetchrow("SELECT version_num FROM alembic_version;")
    assert final_rev is not None
    assert final_rev["version_num"] in [
        "023_analysis_clarification_workflow",
        "024_maintenance_scheduler_and_operational_resilience",
        "025_distributed_provider_circuit_breaker",
        "026_public_schema_acl_hardening",
    ]
    await conn1.close()

    # Step 2: Verify guarded downgrade raises error preventing tokenless/integrity vulnerability
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
        "downgrade",
        "009_facts_integrity",
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)  # noqa: ASYNC221
    assert res.returncode != 0
    assert "IRREVERSIBLE MIGRATION" in res.stderr

    conn3 = await asyncpg.connect(RAW_ROUNDTRIP_URL)

    # Verify db_app_user has NO effective table, sequence, or schema privileges
    has_select_doc = await conn3.fetchval("SELECT has_table_privilege('db_app_user', 'documents', 'SELECT');")
    has_insert_mem = await conn3.fetchval("SELECT has_table_privilege('db_app_user', 'memberships', 'INSERT');")
    has_schema_usage = await conn3.fetchval("SELECT has_schema_privilege('db_app_user', 'public', 'USAGE');")

    assert has_select_doc is False
    assert has_insert_mem is False
    assert has_schema_usage is False

    # Verify db_api_user and db_ingestion_worker have appropriate privileges
    has_api_select_doc = await conn3.fetchval("SELECT has_table_privilege('db_api_user', 'documents', 'SELECT');")
    has_worker_insert_chunk = await conn3.fetchval(
        "SELECT has_table_privilege('db_ingestion_worker', 'document_chunks', 'INSERT');"
    )

    assert has_api_select_doc is True
    assert has_worker_insert_chunk is True

    await conn3.close()
