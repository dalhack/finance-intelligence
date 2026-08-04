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


_firebase_app_initialized = False


def _initialize_firebase_app(project_id: str | None = None) -> None:
    global _firebase_app_initialized
    if not _firebase_app_initialized:
        pid = project_id or settings.FIREBASE_PROJECT_ID or "finance-intel-staging-8f2a"
        try:
            import firebase_admin
            from firebase_admin import credentials

            try:
                firebase_admin.get_app()
            except ValueError:
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {"projectId": pid})
        except Exception as e:  # noqa: BLE001
            # App already initialized or ADC unavailable in dev mode
            _ = e
        _firebase_app_initialized = True


class FirebaseIdentityVerifier:
    def __init__(self, expected_project_id: str | None = None):
        self.expected_project_id = expected_project_id or settings.FIREBASE_PROJECT_ID or "finance-intel-staging-8f2a"
        _initialize_firebase_app(self.expected_project_id)

    async def verify_token(self, token: str) -> AuthenticatedIdentity:
        if not token or not isinstance(token, str):
            raise InvalidCredentialsException("Bearer token required.")

        try:
            from firebase_admin import auth

            decoded = auth.verify_id_token(token, check_revoked=False)
        except Exception as e:
            err_type = type(e).__name__
            if "Expired" in err_type or "expired" in str(e).lower():
                raise InvalidCredentialsException("Firebase ID token has expired.") from e
            if "Revoked" in err_type or "revoked" in str(e).lower():
                raise InvalidCredentialsException("Firebase ID token has been revoked.") from e
            raise InvalidCredentialsException(f"Invalid Firebase ID token: {e}") from e

        aud = decoded.get("aud")
        if aud != self.expected_project_id:
            raise InvalidCredentialsException(f"Token audience mismatch: expected '{self.expected_project_id}'.")

        uid = decoded.get("uid") or decoded.get("sub")
        if not uid:
            raise InvalidCredentialsException("Firebase token missing UID/sub claim.")

        email = decoded.get("email")
        display_name = decoded.get("name") or email or "Firebase User"

        return AuthenticatedIdentity(
            external_subject=uid,
            identity_provider="firebase",
            display_name=display_name,
            email_masked=email,
        )
