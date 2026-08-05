import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "provision_ci_roles.py"

VALID_ENV = {
    "CI": "true",
    "TEST_BOOTSTRAP_PASSWORD": "bootstrap_pass",
    "TEST_API_PASSWORD": "api_pass",
    "TEST_WORKER_PASSWORD": "worker_pass",
    "TEST_MAINTENANCE_PASSWORD": "dev_maintenance_pass_123",
}


@pytest.mark.asyncio
async def test_provision_ci_roles_live_postgres_sql_injection_and_single_quote_safety():
    """Live Integration Test: Verifies single quotes and injection payloads pass safely against active PostgreSQL."""
    injection_pass = "p'ass'; DROP TABLE users; --"
    env = {
        **os.environ,
        **VALID_ENV,
        "TEST_API_PASSWORD": injection_pass,
    }

    loop = asyncio.get_running_loop()
    proc = await loop.run_in_executor(
        None,
        lambda: subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--target-url",
                "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
            check=False,
        ),
    )
    assert proc.returncode == 0, f"Script failed with injection payload! Stderr: {proc.stderr}"

    conn = await asyncpg.connect("postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test")
    try:
        api_conn = await asyncpg.connect(
            user="db_api_user",
            password=injection_pass,
            host="localhost",
            port=5432,
            database="finance_intelligence_test",
        )
        await api_conn.close()
    finally:
        # Restore canonical role passwords so subsequent integration tests retain password parity
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--target-url",
                    "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test",
                ],
                capture_output=True,
                text=True,
                env=VALID_ENV,
                cwd=REPO_ROOT,
                check=False,
            ),
        )
        await conn.close()
