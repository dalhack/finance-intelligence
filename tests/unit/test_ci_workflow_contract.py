from pathlib import Path

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

    # Assert zero-skip verification check is present
    assert "assert skips == 0, 'CRITICAL CI FAILURE: Integration tests contained skipped tests!'" in raw_content
