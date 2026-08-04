"""Comprehensive Unit, Semantic, Redaction, Action SHA Manifest, PEP 440, and Validation Workflow Contract Tests."""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

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
    "grpc-google-iam-v1==0.13.1",
]

GENERATOR_PATH = API_DIR.parent.parent / "scripts" / "generate_migration_lock.py"
GENERATOR_SPEC = importlib.util.spec_from_file_location("generate_migration_lock", GENERATOR_PATH)
assert GENERATOR_SPEC and GENERATOR_SPEC.loader
GENERATOR_MODULE = importlib.util.module_from_spec(GENERATOR_SPEC)
sys.modules[GENERATOR_SPEC.name] = GENERATOR_MODULE
GENERATOR_SPEC.loader.exec_module(GENERATOR_MODULE)

EXPECTED_NINE_IMPORTS = [
    "alembic",
    "sqlalchemy",
    "google.cloud.sql.connector",
    "google.cloud.secretmanager",
    "pg8000",
    "cryptography",
    "cffi",
    "pycparser",
    "scramp",
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
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(API_DIR), check=False)
    assert res.returncode == 1
    assert "No subcommand provided" in res.stderr


def test_migration_entrypoint_preflight_succeeds():
    cmd = [sys.executable, "-m", "app.migration_entrypoint", "preflight"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(API_DIR), check=False)
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
        "cryptography==50.0.0",
        "cffi==2.1.1",
        "pycparser==3.0",
        "greenlet==3.5.4",
        "scramp==1.4.15",
        "python-dateutil==2.9.0.post0",
        "grpc-google-iam-v1==0.12.4",
    ]
    for pin in required_pins:
        assert pin in content, f"Required recursive closure pin {pin} missing from lock file!"


def test_pep440_specifier_evaluation_and_rejection_fixtures():
    spec = SpecifierSet(">=0.12.3,<0.13dev")

    # Reject upper bound and prerelease violations
    rejected_candidates = ["0.13.1", "0.13.0", "0.13.0rc1", "0.13.1rc0", "0.14.0"]
    for cand in rejected_candidates:
        assert Version(cand) not in spec, f"Candidate {cand} incorrectly accepted by specifier {spec}!"

    # Accept valid in-range releases
    allowed_candidates = ["0.12.3", "0.12.4", "0.12.6", "0.12.7"]
    for cand in allowed_candidates:
        assert Version(cand) in spec, f"Candidate {cand} incorrectly rejected by specifier {spec}!"

    # Verify pip's full-graph backtracking result is compatible. It selects
    # 0.12.4 after considering the complete protobuf/grpc constraint graph.
    lock_path = API_DIR / "requirements-migration.lock"
    content = lock_path.read_text()
    assert "grpc-google-iam-v1==0.12.4" in content
    assert "grpc-google-iam-v1==0.13.1" not in content


def test_lock_generator_uses_pep440_backtracking_without_hardcoded_closure():
    content = GENERATOR_PATH.read_text()
    assert "RECURSIVE_DEPENDENCY_CLOSURE" not in content
    assert 'UV_VERSION = "0.12.1"' in content
    assert '"pip",\n        "compile"' in content
    assert '"--python-platform"' in content
    assert "TARGET_UV_PLATFORM" in content
    assert '"--exclude-newer"' in content
    assert '"--generate-hashes"' in content


def test_manifest_has_full_lock_parity_and_validated_edges():
    manifest_path = API_DIR / "requirements-migration.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    lock_text = (API_DIR / "requirements-migration.lock").read_text()
    packages = manifest["packages"]
    assert len(packages) == 45
    assert manifest["resolver"] == {
        "excludeNewer": "2026-08-04T00:00:00Z",
        "name": "uv",
        "version": "0.12.1",
    }
    assert manifest["target"]["platform"] == "linux/amd64"
    assert manifest["target"]["pythonVersion"] == "3.11"
    for package in packages:
        assert f"{canonicalize_name(package['package'])}=={package['version']}" in lock_text
        assert package["hashes"]
        assert package["targetArtifacts"]
        for digest in package["hashes"]:
            assert f"--hash=sha256:{digest}" in lock_text
    assert manifest["edges"]
    assert all(edge["constraint_result"] == "PASS" for edge in manifest["edges"])
    grpc_edges = [edge for edge in manifest["edges"] if edge["package"].lower() == "grpc-google-iam-v1"]
    assert any(
        edge
        == {
            "constraint": "<0.13dev,>=0.12.3",
            "constraint_result": "PASS",
            "package": "grpc-google-iam-v1",
            "required_by": "google-cloud-secret-manager",
            "selected_version": "0.12.4",
        }
        for edge in grpc_edges
    )


def test_graph_validator_rejects_pep440_constraint_violation():
    package_type = GENERATOR_MODULE.ResolvedPackage
    packages = [
        package_type(
            name="parent",
            version="1.0",
            hashes=("a" * 64,),
            target_artifacts=("parent-1.0-py3-none-any.whl",),
            requires_dist=("child>=1,<2",),
            requested=True,
        ),
        package_type(
            name="child",
            version="2.0",
            hashes=("b" * 64,),
            target_artifacts=("child-2.0-py3-none-any.whl",),
            requires_dist=(),
            requested=False,
        ),
    ]
    with pytest.raises(RuntimeError, match="FAIL_CLOSED_PEP440_ERROR"):
        GENERATOR_MODULE.validate_dependency_graph(packages, [GENERATOR_MODULE.Requirement("parent==1.0")])


def test_requirements_lock_sqlalchemy_wheel_hash_provenance_and_ownership():
    lock_path = API_DIR / "requirements-migration.lock"
    assert lock_path.exists()
    content = lock_path.read_text()

    # Extract SQLAlchemy block
    sqla_match = re.search(r"sqlalchemy==2\.0\.31\s*\\?\n((?:\s*--hash=sha256:[a-f0-9]{64}\s*\\?\n?)+)", content)
    assert sqla_match, "SQLAlchemy==2.0.31 entry missing from lock file"
    sqla_hashes = sqla_match.group(1)
    assert SQLALCHEMY_TARGET_WHEEL_HASH in sqla_hashes, (
        f"SQLAlchemy target wheel hash {SQLALCHEMY_TARGET_WHEEL_HASH} missing from SQLAlchemy entry!"
    )

    # Extract greenlet block and verify SQLALCHEMY_TARGET_WHEEL_HASH is NOT owned by greenlet
    greenlet_match = re.search(r"greenlet==3\.5\.4\s*\\?\n((?:\s*--hash=sha256:[a-f0-9]{64}\s*\\?\n?)+)", content)
    assert greenlet_match, "greenlet==3.5.4 entry missing from lock file"
    greenlet_hashes = greenlet_match.group(1)
    assert SQLALCHEMY_TARGET_WHEEL_HASH not in greenlet_hashes, (
        f"Hash {SQLALCHEMY_TARGET_WHEEL_HASH} incorrectly assigned to greenlet!"
    )


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


def test_workflow_validate_migration_lock_volume_lifecycle_scanner():
    wf_path = API_DIR.parent.parent / ".github" / "workflows" / "validate-migration-lock.yml"
    assert wf_path.exists()
    content = wf_path.read_text()

    # Stage A volume creation
    assert "docker volume create" in content
    assert 'if docker volume inspect "${VALIDATION_VOLUME}"' in content

    # Stage B volume pre-check
    assert 'if ! docker volume inspect "${VALIDATION_VOLUME}"' in content

    # Cleanup step with if: always() and absence assertion
    assert "Cleanup Exact Validation Volume" in content
    assert "if: always()" in content
    assert 'docker volume rm -f "${VALIDATION_VOLUME}"' in content
    assert "Validation volume still exists after cleanup!" in content
    assert "docker volume prune" not in content
