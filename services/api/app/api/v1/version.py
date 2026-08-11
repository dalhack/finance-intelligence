from app.core.config import settings
from app.schemas.common import VersionResponseDTO
from fastapi import APIRouter

router = APIRouter()


@router.get("/version", response_model=VersionResponseDTO)
async def get_version():
    return VersionResponseDTO(version=settings.VERSION, environment=settings.ENVIRONMENT, api_baseline="v1-phase1")
