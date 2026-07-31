from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.core.errors import BaseAPIException
from services.api.app.db.session import get_db_session
from services.api.app.dependencies import require_permission
from services.api.app.middleware.execution_context import ExecutionContext
from services.api.app.schemas.comparison import EvidenceDetailDTO
from services.api.app.services.comparison_service import ComparisonService

router = APIRouter()

perm_evidence_read = require_permission("evidence:read")


@router.get("/{evidence_id}", response_model=EvidenceDetailDTO)
async def get_evidence_detail(
    evidence_id: UUID,
    ctx: ExecutionContext = Depends(perm_evidence_read),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> EvidenceDetailDTO:
    """Get sanitized, tenant-scoped evidence drawer detail by ID."""
    try:
        return await ComparisonService.get_evidence_detail(
            db=session,
            organization_id=ctx.active_organization_id,
            evidence_id=evidence_id,
        )
    except ValueError as e:
        err_code = str(e)
        if err_code == "EVIDENCE_NOT_FOUND":
            raise BaseAPIException(
                code="EVIDENCE_NOT_FOUND",
                message="Evidence reference not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        raise BaseAPIException(
            code="EVIDENCE_INTERNAL_ERROR",
            message="Evidence retrieval failed.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:  # noqa: BLE001
        raise BaseAPIException(
            code="EVIDENCE_INTERNAL_ERROR",
            message="Evidence retrieval failed.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
