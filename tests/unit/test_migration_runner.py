"""Unit and Semantic Tests for Migration Container Infrastructure."""

import re
import subprocess
import sys
from pathlib import Path

# Ensure services/api is in sys.path
API_DIR = Path(__file__).resolve().parent.parent.parent / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.migration_entrypoint import redact_sensitive_string


def test_redact_sensitive_string_masks_passwords():
    raw_url = "postgresql://db_user:SuperSecretPass123!@10.200.0.3:5432/finance_db"
    redacted = redact_sensitive_string(raw_url)
    assert "SuperSecretPass123!" not in redacted
    assert "[REDACTED]" in redacted


def test_migration_entrypoint_no_args_exits_one():
    cmd = [sys.executable, "-m", "app.migration_entrypoint"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(API_DIR))
    assert res.returncode == 1
    assert "No subcommand provided" in res.stderr


def test_migration_entrypoint_preflight_succeeds():
    cmd = [sys.executable, "-m", "app.migration_entrypoint", "preflight"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(API_DIR))
    assert res.returncode == 0
    assert "[MIGRATION_PREFLIGHT] SUCCESS" in res.stdout


def test_dockerfile_migration_semantic_validations():
    dockerfile_path = API_DIR / "Dockerfile.migration"
    assert dockerfile_path.exists()
    content = dockerfile_path.read_text()

    # Base image must use full sha256 digest
    assert "@sha256:" in content
    # Non-root user must be set
    assert "USER 10001:10001" in content
    # Entrypoint must be set
    assert 'ENTRYPOINT ["python", "-m", "app.migration_entrypoint"]' in content


def test_workflow_deploy_staging_semantic_validations():
    workflow_path = API_DIR.parent.parent / ".github" / "workflows" / "deploy-staging.yml"
    assert workflow_path.exists()
    content = workflow_path.read_text()

    # Must only trigger on workflow_dispatch
    assert "workflow_dispatch:" in content
    assert "push:" not in content
    # Third-party actions must be pinned to 40-character SHAs
    sha_matches = re.findall(r"uses:\s+[\w-]+/[\w-]+@([a-f0-9]{40})", content)
    assert len(sha_matches) >= 3
    # Must NOT contain Cloud Run deploy or execute commands
    assert "gcloud run deploy" not in content
    assert "gcloud run jobs execute" not in content
