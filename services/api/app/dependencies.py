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
    FirebaseIdentityVerifier,
)
from services.api.app.middleware.execution_context import ExecutionContext

# Dev auth instance
dev_identity_verifier = DevelopmentIdentityVerifier()
dev_app_check_verifier = DevelopmentAppAttestationVerifier()

# Synthetic test membership database for development mode
DEV_SYNTHETIC_USER_ID = UUID("44444444-4444-4444-4444-444444444444")
DEV_SYNTHETIC_ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
DEV_SYNTHETIC_MEMBERSHIP_ID = UUID("22222222-2222-2222-2222-222222222222")


async def resolve_auth_context_from_db(
    firebase_uid: str, organization_id: UUID
) -> tuple[UUID, UUID, list[str], list[str]] | None:
    """Pre-tenant auth lookup DB execution plane using db_api_user via resolve_auth_context SECURITY DEFINER function."""
    from sqlalchemy import text

    from services.api.app.db.session import ApiSessionLocal

    try:
        async with ApiSessionLocal() as session:
            res = await session.execute(
                text(
                    "SELECT actor_user_id, active_organization_id, roles, permissions "
                    "FROM public.resolve_auth_context(:uid, :org_id);"
                ),
                {"uid": firebase_uid, "org_id": organization_id},
            )
            row = res.fetchone()
            if not row or not row[0]:
                return None
            return (row[0], row[1], list(row[2] or []), list(row[3] or []))
    except Exception:  # noqa: BLE001
        return None


async def get_execution_context(
    authorization: str | None = Header(None),
    x_firebase_appcheck: str | None = Header(None),
    x_organization_id: str | None = Header(None),
    x_request_id: str | None = Header(None),
    x_correlation_id: str | None = Header(None),
) -> ExecutionContext:
    request_id = x_request_id if isinstance(x_request_id, str) and x_request_id else str(uuid.uuid4())
    correlation_id = x_correlation_id if isinstance(x_correlation_id, str) and x_correlation_id else request_id

    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidCredentialsException("Bearer token required.")

    token = authorization.split("Bearer ")[1].strip()
    if not token:
        raise InvalidCredentialsException("Bearer token required.")

    if not x_organization_id:
        raise MembershipRequiredException("Active organization ID header ('X-Organization-ID') is required.")

    try:
        requested_org_uuid = UUID(x_organization_id)
    except ValueError:
        raise MembershipRequiredException("Invalid organization ID format.")

    # Select auth strategy based on token and environment
    if settings.is_development and (token.startswith("dev-token") or token == "dev-token-valid"):
        identity = await dev_identity_verifier.verify_token(token)
        if x_firebase_appcheck:
            await dev_app_check_verifier.verify_attestation(x_firebase_appcheck)

        resolved_db = await resolve_auth_context_from_db(identity.external_subject, requested_org_uuid)
        if resolved_db:
            actor_user_id, active_org_id, roles, permissions = resolved_db
            return ExecutionContext(
                authenticated_user_id=actor_user_id,
                active_organization_id=active_org_id,
                membership_id=DEV_SYNTHETIC_MEMBERSHIP_ID,
                roles=roles,
                permissions=permissions,
                request_id=request_id,
                correlation_id=correlation_id,
                authentication_method="development_adapter",
                environment=settings.ENVIRONMENT,
            )

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
                "analyses:create",
            ],
            request_id=request_id,
            correlation_id=correlation_id,
            authentication_method="development_adapter",
            environment=settings.ENVIRONMENT,
        )

    # Firebase Authentication Pipeline (Staging & Production)
    verifier = FirebaseIdentityVerifier()
    identity = await verifier.verify_token(token)

    resolved = await resolve_auth_context_from_db(identity.external_subject, requested_org_uuid)
    if not resolved:
        raise MembershipRequiredException("Active organization membership is required to access target resource.")

    actor_user_id, active_org_id, roles, permissions = resolved

    return ExecutionContext(
        authenticated_user_id=actor_user_id,
        active_organization_id=active_org_id,
        membership_id=UUID("00000000-0000-0000-0000-000000000000"),
        roles=roles,
        permissions=permissions,
        request_id=request_id,
        correlation_id=correlation_id,
        authentication_method="firebase",
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
