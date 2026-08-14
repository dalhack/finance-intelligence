import uuid

from app.core.config import settings
from app.core.errors import InvalidCredentialsException
from app.core.security import (
    DevelopmentIdentityVerifier,
    FirebaseIdentityVerifier,
)
from app.db.session import BootstrapSessionLocal
from app.dependencies import get_execution_context
from app.middleware.execution_context import ExecutionContext
from app.schemas.common import OrganizationSummaryDTO
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter()


@router.get("/organizations/current", response_model=OrganizationSummaryDTO)
async def get_current_organization(ctx: ExecutionContext = Depends(get_execution_context)):  # noqa: B008
    return OrganizationSummaryDTO(
        organization_id=ctx.active_organization_id,
        name="Synthetic Dev Organization",
        slug="dev-org-synthetic",
        role=ctx.roles[0] if ctx.roles else None,
        status="ACTIVE",
    )


class BootstrapResponseDTO(BaseModel):
    organization_id: uuid.UUID
    created: bool


@router.post("/organizations/bootstrap", response_model=BootstrapResponseDTO)
async def bootstrap_self_organization(
    authorization: str | None = Header(None),
) -> BootstrapResponseDTO:
    """Identity-only onboarding: verifies the bearer token (no organization
    header required) and provisions a personal organization + ANALYST
    membership via the SECURITY DEFINER function owned by db_owner.
    db_bootstrap holds EXECUTE on that function and nothing else.
    Idempotent for returning users."""
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidCredentialsException("Bearer token required.")
    token = authorization.split("Bearer ")[1].strip()
    if not token:
        raise InvalidCredentialsException("Bearer token required.")

    if settings.is_development and token.startswith("dev-token"):
        identity = await DevelopmentIdentityVerifier().verify_token(token)
    else:
        identity = await FirebaseIdentityVerifier().verify_token(token)

    async with BootstrapSessionLocal() as session:
        result = await session.execute(
            text("SELECT org_id, was_created FROM public.bootstrap_self_organization(:sub, :provider, :name)"),
            {
                "sub": identity.external_subject,
                "provider": identity.identity_provider,
                "name": identity.display_name or "Kullanıcı",
            },
        )
        row = result.fetchone()
        await session.commit()

    return BootstrapResponseDTO(organization_id=row[0], created=row[1])
