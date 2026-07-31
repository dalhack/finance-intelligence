from fastapi import APIRouter
from pydantic import BaseModel

from services.api.app.core.config import settings
from services.api.app.core.errors import DevelopmentAuthDisabledException

router = APIRouter()


class DevSessionRequest(BaseModel):
    requested_role: str = "ANALYST"


class DevSessionResponse(BaseModel):
    token_type: str = "Bearer"
    access_token: str
    expires_in_seconds: int = 3600
    environment: str


@router.post("/development/session", response_model=DevSessionResponse)
async def create_development_session(body: DevSessionRequest):
    """
    Development-only session token endpoint.
    STRICTLY DISABLED IN PRODUCTION / RELEASE BUILDS.
    """
    if not settings.is_development:
        raise DevelopmentAuthDisabledException()

    return DevSessionResponse(access_token="dev_synthetic_bearer_token_99182", environment=settings.ENVIRONMENT)
