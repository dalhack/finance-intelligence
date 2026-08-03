"""Comprehensive Unit, Semantic, Redaction, Action SHA Manifest, and Validation Workflow Tests."""

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
    "0b58c1de1358c17001f26005565067eefe7f8aaf",
}

TARGET_WORKFLOW_FILES = [
    "deploy-staging.yml",
    "diagnose-staging-oidc.yml",
    "verify-staging-wif.yml",
    "validate-migration-lock.yml",
]

SQLALCHEMY_TARGET_WHEEL_HASH = "2196208432deebdfe3b22185d46b08f00ac9d7b01284e168c212919891289396"

FORBIDDEN_LOCK_PACKAGES = [
    "google-cloud-secret-manager-v1",
    "scamper",
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


def test_requirements_lock_recursive_closure_cryptography_cffi_pycparser():
    lock_path = API_DIR / "requirements-migration.lock"
    assert lock_path.exists()
    content = lock_path.read_text()

    # Verify forbidden packages are ABSENT
    for bad_pkg in FORBIDDEN_LOCK_PACKAGES:
        assert bad_pkg not in content, f"Forbidden nonexistent package {bad_pkg} found in lock file!"

    # Verify complete recursive dependency closure elements are PRESENT and exact-pinned
    required_pins = [
        "cryptography==42.0.0",
        "cffi==1.16.0",
        "pycparser==2.22",
        "scramp==1.4.5",
        "python-dateutil==2.9.0.post0",
    ]
    for pin in required_pins:
        assert pin in content, f"Required recursive closure pin {pin} missing from lock file!"


def test_requirements_lock_sqlalchemy_wheel_hash_provenance_and_ownership():
    lock_path = API_DIR / "requirements-migration.lock"
    assert lock_path.exists()
    content = lock_path.read_text()

    # Extract SQLAlchemy block
    sqla_match = re.search(r"SQLAlchemy==2\.0\.31\s*\\?\n((?:\s*--hash=sha256:[a-f0-9]{64}\s*\\?\n?)+)", content)
    assert sqla_match, "SQLAlchemy==2.0.31 entry missing from lock file"
    sqla_hashes = sqla_match.group(1)
    assert SQLALCHEMY_TARGET_WHEEL_HASH in sqla_hashes, f"SQLAlchemy target wheel hash {SQLALCHEMY_TARGET_WHEEL_HASH} missing from SQLAlchemy entry!"

    # Extract greenlet block and verify SQLALCHEMY_TARGET_WHEEL_HASH is NOT owned by greenlet
    greenlet_match = re.search(r"greenlet==3\.0\.3\s*\\?\n((?:\s*--hash=sha256:[a-f0-9]{64}\s*\\?\n?)+)", content)
    assert greenlet_match, "greenlet==3.0.3 entry missing from lock file"
    greenlet_hashes = greenlet_match.group(1)
    assert SQLALCHEMY_TARGET_WHEEL_HASH not in greenlet_hashes, f"Hash {SQLALCHEMY_TARGET_WHEEL_HASH} incorrectly assigned to greenlet!"


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


def test_workflow_validate_migration_lock_semantic_scanner():
    wf_path = API_DIR.parent.parent / ".github" / "workflows" / "validate-migration-lock.yml"
    assert wf_path.exists()
    content = wf_path.read_text()

    # Must ONLY trigger on workflow_dispatch with expected_commit_sha input
    assert "workflow_dispatch:" in content
    assert "expected_commit_sha:" in content
    assert "push:" not in content
    assert "pull_request:" not in content

    # Runner must be explicit ubuntu-24.04
    assert "runs-on: ubuntu-24.04" in content

    # Permissions must be contents: read ONLY
    assert "contents: read" in content
    assert "id-token: write" not in content

    # Must NOT contain setup-python, pip upgrade pip, GCP auth, or Docker push
    assert "actions/setup-python" not in content
    assert "pip install --upgrade pip" not in content
    assert "google-github-actions/auth" not in content
    assert "docker push" not in content

    # Must use exact pinned python base image container
    assert "python:3.11-slim@sha256:00af38ae2ed311628970782e8a2d7f014d8909dbc63cb97bc0a158187f4db045" in content

    # Must contain clean bash syntax for SHA check
    assert 'if [ "${CHECKED_OUT_SHA}" != "${{ inputs.expected_commit_sha }}" ]; then' in content
