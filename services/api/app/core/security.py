from typing import Protocol

from app.core.config import settings
from app.core.errors import (
    DevelopmentAuthDisabledException,
    InvalidCredentialsException,
)
from pydantic import BaseModel


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

        subject = token[10:] if token.startswith("dev-token-") and len(token) > 10 else "dev_sub_synthetic_99182"

        return AuthenticatedIdentity(
            external_subject=subject,
            identity_provider="development_adapter",
            display_name=f"Dev User {subject}",
            email_masked=f"{subject}@synthetic.internal",
        )


import logging

logger = logging.getLogger("finance_intelligence_security")


class DevelopmentAppAttestationVerifier:
    async def verify_attestation(self, attestation_token: str) -> bool:
        if not settings.is_development:
            return False
        return bool(attestation_token and attestation_token != "invalid")


class FirebaseAppCheckVerifier:
    def __init__(self, expected_project_id: str | None = None):
        pid = expected_project_id or settings.FIREBASE_PROJECT_ID or "finance-intel-staging-8f2a"
        self.expected_project_id = pid
        try:
            self.app = get_or_create_firebase_app(self.expected_project_id)
        except Exception:  # noqa: BLE001
            self.app = None

    async def verify_token(self, token: str | None) -> bool:
        """Verify Firebase App Check token in audit mode. Does not emit secrets or strict rejections."""
        if not token:
            logger.info("APP_CHECK_AUDIT_EVENT: token_status=missing")
            return not settings.STRICT_APP_CHECK_ENFORCEMENT

        if getattr(self, "app", None) is None:
            logger.info("APP_CHECK_AUDIT_EVENT: token_status=app_not_configured")
            return not settings.STRICT_APP_CHECK_ENFORCEMENT

        try:
            from firebase_admin import app_check

            app_check.verify_token(token, app=self.app)
            logger.info("APP_CHECK_AUDIT_EVENT: token_status=valid")
            return True
        except Exception:  # noqa: BLE001
            logger.info("APP_CHECK_AUDIT_EVENT: token_status=invalid_token")
            return not settings.STRICT_APP_CHECK_ENFORCEMENT


import threading
from typing import Any

_firebase_init_lock = threading.Lock()


def get_or_create_firebase_app(project_id: str) -> Any:
    """Thread-safe, project-aware named Firebase app initializer and retriever."""
    if not project_id or not isinstance(project_id, str):
        raise InvalidCredentialsException("FIREBASE_PROJECT_ID must be a non-empty string.")

    with _firebase_init_lock:
        import firebase_admin
        from firebase_admin import credentials

        app_name = f"app-{project_id}"
        try:
            return firebase_admin.get_app(name=app_name)
        except ValueError:
            cred = credentials.ApplicationDefault()
            return firebase_admin.initialize_app(cred, options={"projectId": project_id}, name=app_name)


class FirebaseIdentityVerifier:
    def __init__(self, expected_project_id: str | None = None):
        pid = expected_project_id or settings.FIREBASE_PROJECT_ID
        if not pid or not pid.strip():
            if not settings.is_development:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: FIREBASE_PROJECT_ID must be explicitly configured in staging/production."
                )
            pid = "finance-intel-staging-8f2a"
        if "travel-mapper" in pid.lower():
            raise InvalidCredentialsException("Prohibited project ID cannot be configured.")

        self.expected_project_id = pid
        try:
            self.app = get_or_create_firebase_app(self.expected_project_id)
        except Exception as e:  # noqa: BLE001
            # Wrap initialization failure cleanly
            self.app = None
            self.init_error = e

    async def verify_token(self, token: str) -> AuthenticatedIdentity:
        if not token or not isinstance(token, str):
            raise InvalidCredentialsException("Bearer token required.")

        if getattr(self, "app", None) is None:
            raise InvalidCredentialsException("Firebase authentication app is not configured or initialized.")

        try:
            from firebase_admin import auth

            decoded = auth.verify_id_token(token, app=self.app, check_revoked=False)
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
