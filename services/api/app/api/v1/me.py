from fastapi import APIRouter, Depends

from services.api.app.dependencies import get_execution_context
from services.api.app.middleware.execution_context import ExecutionContext
from services.api.app.schemas.common import UserSummaryDTO

router = APIRouter()


@router.get("/me", response_model=UserSummaryDTO)
async def get_current_user(ctx: ExecutionContext = Depends(get_execution_context)):  # noqa: B008
    return UserSummaryDTO(
        user_id=ctx.authenticated_user_id,
        identity_provider=ctx.authentication_method,
        display_name="Dev Synthetic Analyst User",
        status="ACTIVE",
    )
