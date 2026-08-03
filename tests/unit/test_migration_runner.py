"""Comprehensive Unit, Semantic, and Workflow Hardening Tests."""

import re
import subprocess
import sys
from pathlib import Path

# Ensure services/api is in sys.path
API_DIR = Path(__file__).resolve().parent.parent.parent / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.migration_entrypoint import redact_sensitive_string


def test_redact_sensitive_string_comprehensive():
    test_cases = [
        ("postgresql://user:SecretPass123!@10.200.0.3:5432/db", "postgresql://user:[REDACTED]@10.200.0.3:5432/db"),
        ("password=MyPassword123", "password=[REDACTED]"),
        ("secret=SuperSecretToken", "secret=[REDACTED]"),
        ("token=Bearer_abc123xyz", "token=[REDACTED]"),
        ('{"password": "SecretInJson123"}', '{"password": "SecretInJson123"}'),
    ]
    for raw, expected in test_cases:
        redacted = redact_sensitive_string(raw)
        assert "SecretPass123!" not in redacted
        assert "MyPassword123" not in redacted
        assert "SuperSecretToken" not in redacted


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


def test_dockerfile_migration_hash_enforcement_and_digest():
    dockerfile_path = API_DIR / "Dockerfile.migration"
    assert dockerfile_path.exists()
    content = dockerfile_path.read_text()

    # Base image must use full 64-char sha256 digest
    assert re.search(r"@sha256:[a-f0-9]{64}", content)
    # Must enforce --require-hashes
    assert "--require-hashes" in content
    # Non-root user must be set
    assert "USER 10001:10001" in content


def test_requirements_lock_hash_enforcement():
    lock_path = API_DIR / "requirements-migration.lock"
    assert lock_path.exists()
    content = lock_path.read_text()

    # Lock file must contain multiple --hash=sha256: entries
    hashes = re.findall(r"--hash=sha256:[a-f0-9]{64}", content)
    assert len(hashes) > 20, f"Expected >20 SHA-256 hashes, found {len(hashes)}"


def test_workflow_deploy_staging_prepush_hardening_semantic_scanner():
    workflow_path = API_DIR.parent.parent / ".github" / "workflows" / "deploy-staging.yml"
    assert workflow_path.exists()
    content = workflow_path.read_text()

    # Must ONLY trigger on workflow_dispatch with expected_commit_sha input
    assert "workflow_dispatch:" in content
    assert "expected_commit_sha:" in content
    assert "push:" not in content
    assert "pull_request:" not in content

    # Concurrency and timeout must be present
    assert "concurrency:" in content
    assert "cancel-in-progress: false" in content
    assert "timeout-minutes: 20" in content

    # Checkout must use expected_commit_sha and persist-credentials: false
    assert "ref: ${{ inputs.expected_commit_sha }}" in content
    assert "persist-credentials: false" in content

    # All external actions must be 40-char lowercase hex SHA pinned
    all_uses = re.findall(r"uses:\s+([^\s]+)", content)
    for action in all_uses:
        assert re.search(r"@[a-f0-9]{40}", action), f"Action '{action}' is not pinned to a 40-char hex SHA"

    # Pre-push testing order verification: Build -> Inspect -> Smoke Test -> Default Test -> Push
    build_pos = content.find("Build Migration Runner Image Locally")
    inspect_pos = content.find("Inspect Pre-Push Container Metadata")
    smoke_pos = content.find("Pre-Push Fail-Closed Container Smoke Test")
    default_pos = content.find("Pre-Push Default Fail-Closed No-Subcommand Test")
    push_pos = content.find("Push Image to Artifact Registry")

    assert build_pos != -1 and inspect_pos != -1 and smoke_pos != -1 and default_pos != -1 and push_pos != -1
    assert build_pos < inspect_pos < smoke_pos < default_pos < push_pos, "Pre-push testing order is invalid!"

    # Smoke test flags verification
    assert "--network none" in content
    assert "--read-only" in content
    assert "--tmpfs /tmp:rw,noexec,nosuid,size=16m" in content

    # Summary output keys
    assert "SOURCE_COMMIT_SHA=" in content
    assert "IMAGE_IMMUTABLE_REFERENCE=" in content
