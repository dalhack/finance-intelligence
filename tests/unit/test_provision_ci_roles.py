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


def test_provision_ci_roles_target_required():
    """Negative Fixture: Missing target URL fails closed with CI_ROLE_PROVISIONING_TARGET_REQUIRED."""
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=VALID_ENV, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_TARGET_REQUIRED" in proc.stderr


def test_provision_ci_roles_ci_marker_required():
    """Negative Fixture: Missing CI environment marker fails closed."""
    env = {**VALID_ENV}
    env.pop("CI", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--target-url", "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CI_MARKER_REQUIRED" in proc.stderr


def test_provision_ci_roles_all_credentials_missing_fail_closed():
    """Negative Fixture 1: All credential environment variables missing fails closed before DB connection."""
    env = {"CI": "true", "DATABASE_URL": "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"}
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CREDENTIAL_CONTRACT_INCOMPLETE" in proc.stderr


def test_provision_ci_roles_single_credential_missing_fail_closed():
    """Negative Fixture 2: Single credential env var missing fails closed."""
    env = {**VALID_ENV, "DATABASE_URL": "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"}
    env.pop("TEST_API_PASSWORD")
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CREDENTIAL_CONTRACT_INCOMPLETE" in proc.stderr
    assert "TEST_API_PASSWORD" in proc.stderr


def test_provision_ci_roles_empty_credential_fail_closed():
    """Negative Fixture 3: Empty string credential env var fails closed."""
    env = {**VALID_ENV, "TEST_WORKER_PASSWORD": "   ", "DATABASE_URL": "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"}
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CREDENTIAL_CONTRACT_INCOMPLETE" in proc.stderr
    assert "TEST_WORKER_PASSWORD" in proc.stderr


def test_provision_ci_roles_production_target_forbidden():
    """Negative Fixture: Target URL matching production environment fails closed."""
    env = {**VALID_ENV, "DATABASE_URL": "postgresql://user:pass@production-db.internal:5432/finance_intelligence_prod"}
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_PRODUCTION_TARGET_FORBIDDEN" in proc.stderr


def test_provision_ci_roles_target_not_allowed():
    """Negative Fixture: Target DB host/name not in CI allowlist fails closed."""
    env = {**VALID_ENV, "DATABASE_URL": "postgresql://user:pass@external-host.com:5432/some_random_db"}
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_TARGET_NOT_ALLOWED" in proc.stderr


def test_provision_ci_roles_credential_redaction_on_connection_error():
    """Negative Fixture: Password and username are 100% redacted on connection failure."""
    sensitive_pass = "SuperSecretPassword123!"
    env = {
        **VALID_ENV,
        "DATABASE_URL": f"postgresql://db_owner:{sensitive_pass}@localhost:9999/finance_intelligence_test",
    }
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0

    combined_output = proc.stdout + proc.stderr
    assert sensitive_pass not in combined_output, "CRITICAL SECURITY LEAK: Password leaked in connection error log!"
    assert "db_owner" not in combined_output, "CRITICAL SECURITY LEAK: Username leaked in connection error log!"
    assert "postgresql://" not in combined_output, "CRITICAL SECURITY LEAK: Raw DSN leaked in connection error log!"
    assert "CI_ROLE_PROVISIONING_CONNECTION_FAILED" in combined_output


@pytest.mark.asyncio
async def test_provision_ci_roles_sql_injection_and_single_quote_safety():
    """Injection Test: Single quotes and SQL injection payloads in password string are safely handled via parameterization."""
    injection_pass = "p'ass'; DROP TABLE users; --"
    env = {
        **VALID_ENV,
        "TEST_API_PASSWORD": injection_pass,
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--target-url", "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"Script failed with injection payload! Stderr: {proc.stderr}"

    # Verify password containing single quotes was safely set without executing extra statements
    conn = await asyncpg.connect("postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test")
    try:
        # Verify db_api_user can connect with the injection password literal
        api_conn = await asyncpg.connect(
            user="db_api_user", password=injection_pass, host="localhost", port=5432, database="finance_intelligence_test"
        )
        await api_conn.close()
    finally:
        await conn.close()
