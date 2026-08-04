import uuid
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from services.api.app.core.config import settings
from services.api.app.core.errors import (
    InvalidCredentialsException,
    MembershipRequiredException,
)
from services.api.app.core.security import (
    DevelopmentAppAttestationVerifier,
    DevelopmentIdentityVerifier,
)
from services.api.app.middleware.execution_context import ExecutionContext

# Dev auth instance
dev_identity_verifier = DevelopmentIdentityVerifier()
dev_app_check_verifier = DevelopmentAppAttestationVerifier()

# Synthetic test membership database for development mode
DEV_SYNTHETIC_USER_ID = UUID("44444444-4444-4444-4444-444444444444")
DEV_SYNTHETIC_ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
DEV_SYNTHETIC_MEMBERSHIP_ID = UUID("22222222-2222-2222-2222-222222222222")


async def get_execution_context(
    authorization: str | None = Header(None),
    x_firebase_appcheck: str | None = Header(None),
    x_organization_id: str | None = Header(None),
    x_request_id: str | None = Header(None),
    x_correlation_id: str | None = Header(None),
) -> ExecutionContext:
    request_id = x_request_id if isinstance(x_request_id, str) and x_request_id else str(uuid.uuid4())
    correlation_id = x_correlation_id if isinstance(x_correlation_id, str) and x_correlation_id else request_id

    # Enforce fail-closed check in production if development auth is used
    if not settings.is_development:
        if not authorization or not authorization.startswith("Bearer "):
            raise InvalidCredentialsException("Bearer token required.")
        raise InvalidCredentialsException("Production authentication pipeline is not configured in Phase 1.")

    # Development auth pipeline
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidCredentialsException("Bearer token required for development session.")

    token = authorization.split("Bearer ")[1].strip()
    _ = await dev_identity_verifier.verify_token(token)

    if x_firebase_appcheck:
        await dev_app_check_verifier.verify_attestation(x_firebase_appcheck)

    if not x_organization_id:
        raise MembershipRequiredException("Active organization ID header ('X-Organization-ID') is required.")

    try:
        requested_org_uuid = UUID(x_organization_id)
    except ValueError:
        raise MembershipRequiredException("Invalid organization ID format.")

    return ExecutionContext(
        authenticated_user_id=DEV_SYNTHETIC_USER_ID,
        active_organization_id=requested_org_uuid,
        membership_id=DEV_SYNTHETIC_MEMBERSHIP_ID,
        roles=["ANALYST"],
        permissions=[
            "documents:upload",
            "documents:finalize",
            "documents:read",
            "ingestion:read",
            "read_facts",
            "calculate_metrics",
            "calculations:run",
            "calculations:read",
            "calculations:reconcile",
            "comparisons:run",
            "comparisons:read",
            "evidence:read",
            "facts:review",
            "facts:verify",
            "facts:reject",
        ],
        request_id=request_id,
        correlation_id=correlation_id,
        authentication_method="development_adapter",
        environment=settings.ENVIRONMENT,
    )


def require_permission(permission_code: str):
    async def permission_checker(
        ctx: ExecutionContext = Depends(get_execution_context),  # noqa: B008
    ) -> ExecutionContext:
        if permission_code not in ctx.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission_code}' is required to perform this action.",
            )
        return ctx

    return permission_checker


async def get_optional_execution_context(
    authorization: str | None = Header(None),
    x_firebase_appcheck: str | None = Header(None),
    x_organization_id: str | None = Header(None),
    x_request_id: str | None = Header(None),
    x_correlation_id: str | None = Header(None),
) -> ExecutionContext | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return await get_execution_context(
        authorization=authorization,
        x_firebase_appcheck=x_firebase_appcheck,
        x_organization_id=x_organization_id,
        x_request_id=x_request_id,
        x_correlation_id=x_correlation_id,
    )
