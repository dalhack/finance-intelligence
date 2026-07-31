from fastapi import APIRouter

from services.api.app.core.config import settings
from services.api.app.schemas.common import VersionResponseDTO

router = APIRouter()


@router.get("/version", response_model=VersionResponseDTO)
async def get_version():
    return VersionResponseDTO(version=settings.VERSION, environment=settings.ENVIRONMENT, api_baseline="v1-phase1")
