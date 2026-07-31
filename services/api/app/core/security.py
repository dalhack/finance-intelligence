from typing import Protocol

from pydantic import BaseModel

from services.api.app.core.config import settings
from services.api.app.core.errors import (
    DevelopmentAuthDisabledException,
    InvalidCredentialsException,
)


class AuthenticatedIdentity(BaseModel):
    external_subject: str
    identity_provider: str
    display_name: str
    email_masked: str | None = None


class IdentityVerifier(Protocol):
    async def verify_token(self, token: str) -> AuthenticatedIdentity: ...


class AppAttestationVerifier(Protocol):
    async def verify_attestation(self, attestation_token: str) -> bool: ...


class DevelopmentIdentityVerifier:
    async def verify_token(self, token: str) -> AuthenticatedIdentity:
        if not settings.is_development:
            raise DevelopmentAuthDisabledException()

        if not token or token == "invalid":
            raise InvalidCredentialsException("Invalid development authentication token.")

        return AuthenticatedIdentity(
            external_subject="dev_sub_synthetic_99182",
            identity_provider="development_adapter",
            display_name="Dev Synthetic Analyst User",
            email_masked="dev.analyst@synthetic.internal",
        )


class DevelopmentAppAttestationVerifier:
    async def verify_attestation(self, attestation_token: str) -> bool:
        if not settings.is_development:
            return False
        return bool(attestation_token and attestation_token != "invalid")
