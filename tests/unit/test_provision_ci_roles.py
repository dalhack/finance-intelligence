import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    env = {**os.environ, **VALID_ENV}
    env.pop("DATABASE_URL", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_TARGET_REQUIRED" in proc.stderr


def test_provision_ci_roles_ci_marker_required():
    """Negative Fixture: Missing CI environment marker fails closed."""
    env = {**os.environ, **VALID_ENV}
    env.pop("CI", None)
    proc = subprocess.run(
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
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CI_MARKER_REQUIRED" in proc.stderr


def test_provision_ci_roles_all_credentials_missing_fail_closed():
    """Negative Fixture 1: All credential environment variables missing fails closed before DB connection."""
    env = {
        **os.environ,
        "CI": "true",
        "DATABASE_URL": "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test",
    }
    for key in ("TEST_BOOTSTRAP_PASSWORD", "TEST_API_PASSWORD", "TEST_WORKER_PASSWORD", "TEST_MAINTENANCE_PASSWORD"):
        env.pop(key, None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CREDENTIAL_CONTRACT_INCOMPLETE" in proc.stderr


def test_provision_ci_roles_single_credential_missing_fail_closed():
    """Negative Fixture 2: Single credential env var missing fails closed."""
    env = {
        **os.environ,
        **VALID_ENV,
        "DATABASE_URL": "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test",
    }
    env.pop("TEST_API_PASSWORD", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CREDENTIAL_CONTRACT_INCOMPLETE" in proc.stderr
    assert "TEST_API_PASSWORD" in proc.stderr


def test_provision_ci_roles_empty_credential_fail_closed():
    """Negative Fixture 3: Empty string credential env var fails closed."""
    env = {
        **os.environ,
        **VALID_ENV,
        "TEST_WORKER_PASSWORD": "   ",
        "DATABASE_URL": "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test",
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CREDENTIAL_CONTRACT_INCOMPLETE" in proc.stderr
    assert "TEST_WORKER_PASSWORD" in proc.stderr


def test_provision_ci_roles_production_target_forbidden():
    """Negative Fixture: Target URL matching production environment fails closed."""
    env = {
        **os.environ,
        **VALID_ENV,
        "DATABASE_URL": "postgresql://user:pass@production-db.internal:5432/finance_intelligence_prod",
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_PRODUCTION_TARGET_FORBIDDEN" in proc.stderr


def test_provision_ci_roles_target_not_allowed():
    """Negative Fixture: Target DB host/name not in CI allowlist fails closed."""
    env = {**os.environ, **VALID_ENV, "DATABASE_URL": "postgresql://user:pass@external-host.com:5432/some_random_db"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_TARGET_NOT_ALLOWED" in proc.stderr


def test_provision_ci_roles_credential_redaction_on_connection_error():
    """Negative Fixture: Password and username are 100% redacted on connection failure."""
    sensitive_pass = "SuperSecretPassword123!"
    env = {
        **os.environ,
        **VALID_ENV,
        "DATABASE_URL": f"postgresql://db_owner:{sensitive_pass}@localhost:9999/finance_intelligence_test",
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode != 0

    combined_output = proc.stdout + proc.stderr
    assert sensitive_pass not in combined_output, "CRITICAL SECURITY LEAK: Password leaked in connection error log!"
    assert "db_owner" not in combined_output, "CRITICAL SECURITY LEAK: Username leaked in connection error log!"
    assert "postgresql://" not in combined_output, "CRITICAL SECURITY LEAK: Raw DSN leaked in connection error log!"
    assert "CI_ROLE_PROVISIONING_CONNECTION_FAILED" in combined_output


@pytest.mark.asyncio
async def test_provision_ci_roles_mock_quote_literal_parameterization():
    """Unit Test: Verifies quote_literal query parameterization is invoked for role passwords."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("provision_ci_roles", str(SCRIPT_PATH))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_conn = AsyncMock()

    async def mock_fetchval(query, *args):
        if "quote_literal" in query:
            return f"'{args[0]}'"
        if "COUNT" in query:
            return 0
        return False

    mock_conn.fetchval.side_effect = mock_fetchval
    mock_conn.fetchrow.return_value = {
        "rolname": "db_app_user",
        "rolcanlogin": False,
        "rolsuper": False,
        "rolbypassrls": False,
    }

    with (
        patch.dict(os.environ, {**VALID_ENV, "TEST_API_PASSWORD": "p'ass'; DROP TABLE users; --"}),
        patch("asyncpg.connect", return_value=mock_conn),
    ):
        target_dsn = "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"
        await mod.provision_ci_roles(target_dsn)

        assert mock_conn.fetchval.called
        fetchval_calls = mock_conn.fetchval.call_args_list
        quote_literal_called = any("quote_literal" in str(call) for call in fetchval_calls)
        assert quote_literal_called, "quote_literal parameterization was not invoked!"
