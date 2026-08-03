from pathlib import Path
import re

CI_YML_PATH = Path(__file__).resolve().parent.parent.parent / ".github" / "workflows" / "ci.yml"


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

    # Assert zero-skip XML machine verification check is present
    assert "assert skips == 0" in raw_content


def test_workflow_semantic_scanner():
    """Workflow Semantic Scanner enforcing zero placeholders, pinned Flutter, requirements.lock, and trigger isolation."""
    assert CI_YML_PATH.exists()
    raw_content = CI_YML_PATH.read_text(encoding="utf-8")

    # 1. Reject push or pull_request triggers in top-level 'on:' block
    on_match = re.search(r"on:\s*\n((?:\s+.*\n)+)", raw_content)
    assert on_match, "Could not find 'on:' block in ci.yml!"
    on_block = on_match.group(1)

    assert "push:" not in on_block, "CRITICAL: push trigger is forbidden in ci.yml!"
    assert "pull_request:" not in on_block, "CRITICAL: pull_request trigger is forbidden in ci.yml!"
    assert "workflow_dispatch:" in on_block, "CRITICAL: workflow_dispatch must be present!"

    # 2. Reject echo placeholders
    forbidden_placeholders = [
        'echo "Migration catalog verified."',
        'echo "Security catalog verified."',
        'echo "Contract drift verified."',
        'skips = 0; assert skips == 0',
    ]
    for ph in forbidden_placeholders:
        assert ph not in raw_content, f"CRITICAL: Placeholder detected: {ph}"

    # 3. Require pinned Flutter version
    assert "flutter-version: '3.44.8'" in raw_content, "CRITICAL: Flutter version must be explicitly pinned to 3.44.8!"

    # 4. Require requirements.lock in Python steps
    assert "pip install -r requirements.lock" in raw_content, "CRITICAL: Python steps must install from requirements.lock!"

    # 5. Require genuine iOS build, artifact checks, and simulator boot
    assert "flutter build ios --simulator --no-codesign" in raw_content
    assert "test -d build/ios/iphonesimulator/Runner.app" in raw_content
    assert "shasum -a 256" in raw_content
    assert "xcrun simctl boot" in raw_content
    assert "flutter test integration_test/device_e2e_test.dart -d" in raw_content

    # 6. Verify Android scope exclusion
    assert "if: inputs.validation_scope == 'all'" in raw_content
