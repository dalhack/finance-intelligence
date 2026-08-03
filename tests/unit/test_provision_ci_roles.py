import pytest
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "provision_ci_roles.py"


def test_provision_ci_roles_target_required():
    """Negative Fixture: Missing target URL fails closed with CI_ROLE_PROVISIONING_TARGET_REQUIRED."""
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_TARGET_REQUIRED" in proc.stderr


def test_provision_ci_roles_ci_marker_required():
    """Negative Fixture: Missing CI environment marker fails closed."""
    env = {"DATABASE_URL": "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"}
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_CI_MARKER_REQUIRED" in proc.stderr


def test_provision_ci_roles_production_target_forbidden():
    """Negative Fixture: Target URL matching production environment fails closed."""
    env = {"CI": "true", "DATABASE_URL": "postgresql://user:pass@production-db.internal:5432/finance_intelligence_prod"}
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_PRODUCTION_TARGET_FORBIDDEN" in proc.stderr


def test_provision_ci_roles_target_not_allowed():
    """Negative Fixture: Target DB host/name not in CI allowlist fails closed."""
    env = {"CI": "true", "DATABASE_URL": "postgresql://user:pass@external-host.com:5432/some_random_db"}
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0
    assert "CI_ROLE_PROVISIONING_TARGET_NOT_ALLOWED" in proc.stderr


def test_provision_ci_roles_credential_redaction_on_connection_error():
    """Negative Fixture: Password and username are 100% redacted on connection failure."""
    sensitive_pass = "SuperSecretPassword123!"
    env = {
        "CI": "true",
        "DATABASE_URL": f"postgresql://db_owner:{sensitive_pass}@localhost:9999/finance_intelligence_test",
    }
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, env=env, cwd=REPO_ROOT)
    assert proc.returncode != 0

    combined_output = proc.stdout + proc.stderr
    assert sensitive_pass not in combined_output, "CRITICAL SECURITY LEAK: Password leaked in connection error log!"
    assert "db_owner" not in combined_output, "CRITICAL SECURITY LEAK: Username leaked in connection error log!"
    assert "postgresql://" not in combined_output, "CRITICAL SECURITY LEAK: Raw DSN leaked in connection error log!"
    assert "CI_ROLE_PROVISIONING_CONNECTION_FAILED" in combined_output
