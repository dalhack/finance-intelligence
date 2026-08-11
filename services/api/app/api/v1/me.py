from app.dependencies import get_execution_context
from app.middleware.execution_context import ExecutionContext
from app.schemas.common import UserSummaryDTO
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/me", response_model=UserSummaryDTO)
async def get_current_user(ctx: ExecutionContext = Depends(get_execution_context)):  # noqa: B008
    return UserSummaryDTO(
        user_id=ctx.authenticated_user_id,
        identity_provider=ctx.authentication_method,
        display_name="Dev Synthetic Analyst User",
        status="ACTIVE",
    )
