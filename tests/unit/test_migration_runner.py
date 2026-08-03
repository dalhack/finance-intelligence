"""Comprehensive Unit, Semantic, Redaction, Action SHA Manifest, and Diagnostic Tests."""

import re
import subprocess
import sys
from pathlib import Path

# Ensure services/api is in sys.path
API_DIR = Path(__file__).resolve().parent.parent.parent / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.migration_entrypoint import redact_sensitive_string

ALLOWED_ACTION_SHAS = {
    "actions/checkout": "11bd71901bbe5b1630ceea73d27597364c9af683",
    "google-github-actions/auth": "71f986410dfbc7added4569d411d040a91dc6935",
    "google-github-actions/setup-gcloud": "77e7a554d41e2ee56fc945c52dfd3f33d12def9a",
    "actions/github-script": "60a0d83039c74a4aee543508d2ffcb1c3799cdea",
}

FORBIDDEN_INVALID_SHAS = {
    "6fc46f2b8ec9721d0282b89a87d096ef14abcf8e",
    "6189d56e4096ee891640bb02ac264be376592d63",
}

TARGET_WORKFLOW_FILES = [
    "deploy-staging.yml",
    "diagnose-staging-oidc.yml",
    "verify-staging-wif.yml",
]


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


def test_action_pin_manifest_parity_and_negative_fixtures():
    workflows_dir = API_DIR.parent.parent / ".github" / "workflows"
    for wf_name in TARGET_WORKFLOW_FILES:
        wf = workflows_dir / wf_name
        assert wf.exists(), f"Target workflow file {wf_name} missing!"
        content = wf.read_text()

        # Rejection of forbidden invalid SHAs
        for bad_sha in FORBIDDEN_INVALID_SHAS:
            assert bad_sha not in content, f"Forbidden invalid SHA {bad_sha} found in {wf_name}!"

        # Rejection of mutable tags/branches in uses: lines
        uses_lines = re.findall(r"uses:\s+([^\s]+)", content)
        for use in uses_lines:
            assert not re.search(r"@(v\d+|main|master|latest)$", use), f"Mutable tag/branch found in uses: {use}"
            repo_name, sha_part = use.split("@")
            assert repo_name in ALLOWED_ACTION_SHAS, f"Unallowed action repository: {repo_name} in {wf_name}"
            expected_sha = ALLOWED_ACTION_SHAS[repo_name]
            assert sha_part == expected_sha, f"SHA mismatch for {repo_name}: expected {expected_sha}, got {sha_part}"


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


def test_workflow_verify_staging_wif_semantic_scanner():
    wf_path = API_DIR.parent.parent / ".github" / "workflows" / "verify-staging-wif.yml"
    assert wf_path.exists()
    content = wf_path.read_text()

    # Must ONLY trigger on workflow_dispatch with expected_commit_sha input
    assert "workflow_dispatch:" in content
    assert "expected_commit_sha:" in content
    assert "push:" not in content
    assert "pull_request:" not in content

    # Environment must be staging
    assert "environment: staging" in content

    # Must NOT contain Docker build/push
    assert "docker build" not in content
    assert "docker push" not in content

    # GCP auth action must use verified SHA
    assert "google-github-actions/auth@71f986410dfbc7added4569d411d040a91dc6935" in content
