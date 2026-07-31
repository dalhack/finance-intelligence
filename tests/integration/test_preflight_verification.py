import os
from unittest.mock import patch

import pytest

from tests.integration.conftest import run_real_preflight_checks


@pytest.mark.asyncio
async def test_preflight_passes_on_valid_environment():
    """Verify preflight fixture completes successfully on valid integration environment."""
    await run_real_preflight_checks()


@pytest.mark.asyncio
async def test_preflight_fails_on_missing_env_var():
    """Verify preflight fails immediately if required DB URL is missing without leaking secrets."""
    with patch.dict(os.environ, {"TEST_API_DATABASE_URL": ""}):
        with pytest.raises(pytest.fail.Exception, match="PREFLIGHT_URL_MISSING: TEST_API_DATABASE_URL") as exc_info:
            await run_real_preflight_checks()
        msg = str(exc_info.value)
        assert "db_api_user" not in msg
        assert "localhost" not in msg


@pytest.mark.asyncio
async def test_preflight_fails_on_wrong_username():
    """Verify preflight fails if connection URL has invalid username without leaking details."""
    invalid_url = "postgresql+asyncpg://wrong_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test"
    with patch.dict(os.environ, {"TEST_API_DATABASE_URL": invalid_url}):
        with pytest.raises(pytest.fail.Exception, match="PREFLIGHT_ROLE_MISMATCH: TEST_API_DATABASE_URL") as exc_info:
            await run_real_preflight_checks()
        msg = str(exc_info.value)
        assert "wrong_user" not in msg
        assert "pass" not in msg


@pytest.mark.asyncio
async def test_preflight_fails_on_same_main_and_roundtrip_db():
    """Verify preflight fails if TEST_ROUNDTRIP_DATABASE_URL targets the main test DB."""
    main_url = os.environ.get("TEST_OWNER_DATABASE_URL", "")
    with (
        patch.dict(os.environ, {"TEST_ROUNDTRIP_DATABASE_URL": main_url}),
        pytest.raises(pytest.fail.Exception, match="PREFLIGHT_DATABASE_POLICY_FAILED: TEST_ROUNDTRIP_DATABASE_URL"),
    ):
        await run_real_preflight_checks()
