from app.dependencies import get_execution_context
from app.middleware.execution_context import ExecutionContext
from app.schemas.common import OrganizationSummaryDTO
from fastapi import APIRouter, Depends

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
