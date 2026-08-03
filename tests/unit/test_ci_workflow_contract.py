import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CI_YML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
PROVISION_SCRIPT_PATH = REPO_ROOT / "scripts" / "provision_ci_roles.py"


def validate_workflow_semantics(raw_content: str) -> None:
    """Enforces strict behavioral and safety contracts on workflow YAML content."""

    # 1. Reject push or pull_request triggers in top-level 'on:' block
    on_match = re.search(r"on:\s*\n((?:\s+.*\n)+)", raw_content)
    assert on_match, "Could not find 'on:' block in ci.yml!"
    on_block = on_match.group(1)

    assert "push:" not in on_block, "CRITICAL: push trigger is forbidden in ci.yml!"
    assert "pull_request:" not in on_block, "CRITICAL: pull_request trigger is forbidden in ci.yml!"
    assert "workflow_dispatch:" in on_block, "CRITICAL: workflow_dispatch must be present!"

    # 2. Reject echo placeholders, hardcoded skips=0, and duplicated inline CREATE ROLE statements
    forbidden_patterns = [
        'echo "Migration catalog verified."',
        'echo "Security catalog verified."',
        'echo "Contract drift verified."',
        "skips = 0; assert skips == 0",
        'xcrun simctl boot "$SIMULATOR_UDID" || true',
        'xcrun simctl boot "$UDID" || true',
        'grep "iPhone 15"',
        'psql -h localhost -U db_owner -d finance_intelligence_test -c "CREATE ROLE',
        'psql -h localhost -p 5433 -U db_owner -d finance_intelligence_roundtrip -c "CREATE ROLE',
    ]
    for ph in forbidden_patterns:
        assert ph not in raw_content, f"CRITICAL: Forbidden pattern detected: {ph}"

    # 3. Require pinned Flutter version
    assert "flutter-version: '3.44.8'" in raw_content, "CRITICAL: Flutter version must be explicitly pinned to 3.44.8!"

    # 4. Require requirements.lock in Python steps
    assert "pip install -r requirements.lock" in raw_content, (
        "CRITICAL: Python steps must install from requirements.lock!"
    )

    # 5. Require single canonical Python role provisioning tool across postgres jobs
    assert raw_content.count("python scripts/provision_ci_roles.py") >= 3, (
        "CRITICAL: All postgres jobs must execute python scripts/provision_ci_roles.py!"
    )

    # 6. Require early UDID persistence to GITHUB_ENV
    assert 'SIMULATOR_UDID=$SIM_UDID" >> "$GITHUB_ENV"' in raw_content or 'echo "SIMULATOR_UDID=' in raw_content

    # 7. Require genuine iOS build and Runner executable artifact checks
    assert "flutter build ios --simulator --no-codesign" in raw_content
    assert "test -d build/ios/iphonesimulator/Runner.app" in raw_content
    assert "test -f build/ios/iphonesimulator/Runner.app/Runner" in raw_content
    assert "shasum -a 256" in raw_content

    # 8. Require fail-closed boot and explicit device target
    assert 'xcrun simctl boot "$SIMULATOR_UDID"' in raw_content
    assert 'xcrun simctl bootstatus "$SIMULATOR_UDID" -b' in raw_content
    assert 'flutter test integration_test/device_e2e_test.dart -d "$SIMULATOR_UDID"' in raw_content

    # 9. Require cleanup teardown checking SIMULATOR_UDID
    assert 'if [ -n "$SIMULATOR_UDID" ]; then' in raw_content


def test_provision_script_has_zero_fallback_constants():
    """Scanner verifying provision_ci_roles.py has zero string fallback constants for passwords."""
    assert PROVISION_SCRIPT_PATH.exists()
    code = PROVISION_SCRIPT_PATH.read_text(encoding="utf-8")

    forbidden_fallbacks = [
        'os.environ.get("TEST_BOOTSTRAP_PASSWORD",',
        'os.environ.get("TEST_API_PASSWORD",',
        'os.environ.get("TEST_WORKER_PASSWORD",',
        'os.environ.get("TEST_MAINTENANCE_PASSWORD",',
        '"bootstrap_pass"',
        '"api_pass"',
        '"worker_pass"',
        '"dev_maintenance_pass_123"',
    ]
    for pattern in forbidden_fallbacks:
        assert pattern not in code, (
            f"CRITICAL SECURITY VIOLATION: Hardcoded fallback constant {pattern} found in provision_ci_roles.py!"
        )


def test_gitignore_containment_and_repository_completeness():
    """Scanner verifying .gitignore does not swallow production source code and essential entrypoints are tracked."""
    assert GITIGNORE_PATH.exists()
    gitignore_lines = [line.strip() for line in GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()]

    # Reject unanchored 'lib/' or 'storage/' rules in .gitignore
    assert "lib/" not in gitignore_lines, (
        "CRITICAL: Unanchored 'lib/' rule found in .gitignore (swallows Flutter source)!"
    )
    assert "storage/" not in gitignore_lines, (
        "CRITICAL: Unanchored 'storage/' rule found in .gitignore (swallows backend storage package)!"
    )

    # Verify essential production entrypoints exist on filesystem
    main_dart = REPO_ROOT / "apps" / "mobile" / "lib" / "main.dart"
    storage_adapter = REPO_ROOT / "services" / "api" / "app" / "storage" / "local_adapter.py"

    assert main_dart.exists(), "apps/mobile/lib/main.dart missing!"
    assert storage_adapter.exists(), "services/api/app/storage/local_adapter.py missing!"

    # Verify git status / ls-files sees them as tracked or staged (not ignored)
    proc1 = subprocess.run(
        ["git", "status", "--porcelain", str(main_dart)], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    )
    assert "!?" not in proc1.stdout, "apps/mobile/lib/main.dart is ignored by git!"

    proc2 = subprocess.run(
        ["git", "status", "--porcelain", str(storage_adapter)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert "!?" not in proc2.stdout, "services/api/app/storage/local_adapter.py is ignored by git!"


def test_ci_workflow_structure_and_env_contract():
    """Verify .github/workflows/ci.yml enforces exact environment contract and contains required quality gates."""
    assert CI_YML_PATH.exists(), "ci.yml workflow file missing!"
    raw_content = CI_YML_PATH.read_text(encoding="utf-8")

    # Assert TEST_APP_DATABASE_URL is completely removed from CI configuration
    assert "TEST_APP_DATABASE_URL" not in raw_content, "TEST_APP_DATABASE_URL found in ci.yml!"

    # Assert jobs and quality gates exist
    assert "backend-foundation-gate:" in raw_content
    assert "mobile-gate:" in raw_content

    # Assert required integration environment variables exist
    assert 'TEST_OWNER_DATABASE_URL: "postgresql+asyncpg://db_owner:' in raw_content
    assert 'TEST_BOOTSTRAP_DATABASE_URL: "postgresql+asyncpg://db_bootstrap:' in raw_content
    assert 'TEST_API_DATABASE_URL: "postgresql+asyncpg://db_api_user:' in raw_content
    assert 'TEST_WORKER_DATABASE_URL: "postgresql+asyncpg://db_ingestion_worker:' in raw_content
    assert 'TEST_ROUNDTRIP_DATABASE_URL: "postgresql+asyncpg://db_owner:' in raw_content


def test_workflow_semantic_scanner_live():
    """Passes actual ci.yml through semantic scanner validator."""
    assert CI_YML_PATH.exists()
    raw_content = CI_YML_PATH.read_text(encoding="utf-8")
    validate_workflow_semantics(raw_content)


def test_negative_scanner_fixtures():
    """Self-test semantic scanner against invalid/defective workflow YAML fixtures."""
    valid_content = CI_YML_PATH.read_text(encoding="utf-8")

    # Negative Fixture 1: Late UDID export
    bad_fixture_1 = valid_content.replace('echo "SIMULATOR_UDID=$SIM_UDID" >> "$GITHUB_ENV"', "# late export")
    with pytest.raises(AssertionError):
        validate_workflow_semantics(bad_fixture_1)

    # Negative Fixture 2: Non-fail-closed boot (boot || true)
    bad_fixture_2 = valid_content.replace(
        'xcrun simctl boot "$SIMULATOR_UDID"', 'xcrun simctl boot "$SIMULATOR_UDID" || true'
    )
    with pytest.raises(AssertionError):
        validate_workflow_semantics(bad_fixture_2)

    # Negative Fixture 3: Fallback to existing simulator
    bad_fixture_3 = valid_content.replace(
        'SIM_UDID=$(xcrun simctl create "CI_Runner_${{ github.run_id }}_${{ github.run_attempt }}" "com.apple.CoreSimulator.SimDeviceType.iPhone-15")',
        'SIM_UDID=$(xcrun simctl create ... || grep "iPhone 15")',
    )
    with pytest.raises(AssertionError):
        validate_workflow_semantics(bad_fixture_3)

    # Negative Fixture 4: Missing app executable binary check
    bad_fixture_4 = valid_content.replace("test -f build/ios/iphonesimulator/Runner.app/Runner", "# no binary check")
    with pytest.raises(AssertionError):
        validate_workflow_semantics(bad_fixture_4)

    # Negative Fixture 5: Missing device target on E2E command
    bad_fixture_5 = valid_content.replace('-d "$SIMULATOR_UDID"', "")
    with pytest.raises(AssertionError):
        validate_workflow_semantics(bad_fixture_5)

    # Negative Fixture 6: Unprotected cleanup
    bad_fixture_6 = valid_content.replace('if [ -n "$SIMULATOR_UDID" ]; then', "if true; then")
    with pytest.raises(AssertionError):
        validate_workflow_semantics(bad_fixture_6)

    # Negative Fixture 7: Duplicated inline CREATE ROLE statements
    bad_fixture_7 = valid_content.replace(
        'python scripts/provision_ci_roles.py --target-url "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"',
        'psql -h localhost -U db_owner -d finance_intelligence_test -c "CREATE ROLE db_app_user ..."',
    )
    with pytest.raises(AssertionError):
        validate_workflow_semantics(bad_fixture_7)
