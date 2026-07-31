from unittest.mock import patch

import pytest

from services.api.app.core.errors import (
    DevelopmentAuthDisabledException,
    InvalidCredentialsException,
)
from services.api.app.core.security import DevelopmentIdentityVerifier


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dev_auth_fails_closed_in_production():
    verifier = DevelopmentIdentityVerifier()
    with (
        patch("services.api.app.core.config.settings.ENVIRONMENT", "production"),
        pytest.raises(DevelopmentAuthDisabledException),
    ):
        await verifier.verify_token("dev_token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dev_auth_rejects_invalid_token():
    verifier = DevelopmentIdentityVerifier()
    with (
        patch("services.api.app.core.config.settings.ENVIRONMENT", "development"),
        pytest.raises(InvalidCredentialsException),
    ):
        await verifier.verify_token("invalid")
