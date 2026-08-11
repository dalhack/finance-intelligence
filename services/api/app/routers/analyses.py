import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.db.session import get_db_session
from app.dependencies import require_permission
from app.middleware.execution_context import ExecutionContext
from app.models.orchestration import AnalysisJob
from app.orchestration.event_engine import AnalysisEventEngine
from app.orchestration.state_machine import AnalysisJobStatus, AnalysisStateMachine
from app.schemas.clarification import (
    AnalysisClarificationDTO,
    ClarificationCancelRequestDTO,
    ClarificationRespondRequestDTO,
)
from app.services.clarification_service import ClarificationService
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/analyses", tags=["Analyses"])


class AnalysisCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=3, max_length=2000)


class AnalysisJobDTO(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    status: str
    request_prompt: str
    normalized_request: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=AnalysisJobDTO, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    req: AnalysisCreateRequest,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    ctx: ExecutionContext = Depends(require_permission("analyses:run")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AnalysisJobDTO:
    org_id = ctx.active_organization_id
    user_id = ctx.authenticated_user_id
    await db.execute(text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)})

    if x_idempotency_key:
        existing_res = await db.execute(
            select(AnalysisJob).where(
                AnalysisJob.organization_id == org_id,
                AnalysisJob.idempotency_key == x_idempotency_key,
            )
        )
        existing_job = existing_res.scalar_one_or_none()
        if existing_job:
            return AnalysisJobDTO(
                id=existing_job.id,
                organization_id=existing_job.organization_id,
                user_id=existing_job.user_id,
                status=existing_job.status,
                request_prompt=existing_job.request_prompt,
                normalized_request=existing_job.normalized_request,
                created_at=existing_job.created_at,
                updated_at=existing_job.updated_at,
            )

    now = datetime.now(UTC)
    job = AnalysisJob(
        id=uuid4(),
        organization_id=org_id,
        user_id=user_id,
        status=AnalysisJobStatus.RECEIVED.value,
        request_prompt=req.prompt,
        normalized_request={},
        idempotency_key=x_idempotency_key,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()

    return AnalysisJobDTO(
        id=job.id,
        organization_id=job.organization_id,
        user_id=job.user_id,
        status=job.status,
        request_prompt=job.request_prompt,
        normalized_request=job.normalized_request,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{analysis_id}", response_model=AnalysisJobDTO)
async def get_analysis(
    analysis_id: UUID,
    ctx: ExecutionContext = Depends(require_permission("analyses:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AnalysisJobDTO:
    job = await db.get(AnalysisJob, analysis_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": "Analysis job not found.",
                    "request_id": "req-api",
                }
            },
        )
    return AnalysisJobDTO(
        id=job.id,
        organization_id=job.organization_id,
        user_id=job.user_id,
        status=job.status,
        request_prompt=job.request_prompt,
        normalized_request=job.normalized_request,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{analysis_id}/events")
async def stream_analysis_events(
    analysis_id: UUID,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    ctx: ExecutionContext = Depends(require_permission("analyses:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> StreamingResponse:
    org_res = await db.execute(text("SELECT current_setting('app.current_organization_id', true);"))
    org_str = org_res.scalar()
    if not org_str:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MISSING_TENANT_CONTEXT",
                    "message": "Tenant context is required to stream events.",
                    "request_id": "req-api",
                }
            },
        )
    org_id = UUID(org_str)

    job = await db.get(AnalysisJob, analysis_id)
    if not job or job.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": "Analysis job not found.",
                    "request_id": "req-api",
                }
            },
        )

    last_seq = 0
    if last_event_id and last_event_id.isdigit():
        last_seq = int(last_event_id)

    event_engine = AnalysisEventEngine(db, org_id)
    events = await event_engine.replay_events(analysis_id, last_sequence=last_seq)

    async def event_generator():
        for ev in events:
            payload_str = json.dumps(ev.payload_json)
            yield f"event: {ev.event_type}\nid: {ev.sequence}\ndata: {payload_str}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{analysis_id}/cancel", response_model=AnalysisJobDTO)
async def cancel_analysis(
    analysis_id: UUID,
    ctx: ExecutionContext = Depends(require_permission("analyses:cancel")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AnalysisJobDTO:
    job = await db.get(AnalysisJob, analysis_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": "Analysis job not found.",
                    "request_id": "req-api",
                }
            },
        )

    if job.user_id != ctx.authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN_MUTATION",
                    "message": "Only the analysis job creator can cancel this analysis.",
                    "request_id": "req-api",
                }
            },
        )

    current_status = AnalysisJobStatus(job.status)
    AnalysisStateMachine.validate_transition(current_status, AnalysisJobStatus.CANCELLED)

    job.status = AnalysisJobStatus.CANCELLED.value
    job.updated_at = datetime.now(UTC)
    await db.commit()

    return AnalysisJobDTO(
        id=job.id,
        organization_id=job.organization_id,
        user_id=job.user_id,
        status=job.status,
        request_prompt=job.request_prompt,
        normalized_request=job.normalized_request,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=list[AnalysisJobDTO])
async def list_analyses(
    limit: int = 20,
    offset: int = 0,
    status_filter: str | None = None,
    ctx: ExecutionContext = Depends(require_permission("analyses:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> list[AnalysisJobDTO]:
    org_res = await db.execute(text("SELECT current_setting('app.current_organization_id', true);"))
    org_str = org_res.scalar()
    if not org_str:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MISSING_TENANT_CONTEXT",
                    "message": "Tenant context is required to list analyses.",
                    "request_id": "req-api",
                }
            },
        )
    org_id = UUID(org_str)

    query = (
        "SELECT id, organization_id, user_id, status, request_prompt, normalized_request, created_at, updated_at "
        "FROM analysis_jobs WHERE organization_id = :org_id "
    )
    params: dict[str, Any] = {"org_id": org_id, "limit": min(limit, 100), "offset": max(offset, 0)}

    if status_filter:
        query += "AND status = :status_filter "
        params["status_filter"] = status_filter

    query += "ORDER BY created_at DESC LIMIT :limit OFFSET :offset;"

    res = await db.execute(text(query), params)
    rows = res.fetchall()

    return [
        AnalysisJobDTO(
            id=row[0],
            organization_id=row[1],
            user_id=row[2],
            status=row[3],
            request_prompt=row[4],
            normalized_request=row[5] or {},
            created_at=row[6],
            updated_at=row[7],
        )
        for row in rows
    ]


@router.get("/{analysis_id}/result")
async def get_analysis_result(
    analysis_id: UUID,
    ctx: ExecutionContext = Depends(require_permission("analyses:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    org_res = await db.execute(text("SELECT current_setting('app.current_organization_id', true);"))
    org_str = org_res.scalar()
    if not org_str:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MISSING_TENANT_CONTEXT",
                    "message": "Tenant context is required to view result.",
                    "request_id": "req-api",
                }
            },
        )
    org_id = UUID(org_str)

    job = await db.get(AnalysisJob, analysis_id)
    if not job or job.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": "Analysis job not found.",
                    "request_id": "req-api",
                }
            },
        )

    if job.status != AnalysisJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "RESULT_NOT_READY",
                    "message": f"Analysis result is not ready. Current job status is {job.status}.",
                    "request_id": "req-api",
                    "retryable": True,
                }
            },
        )

    res = await db.execute(
        text(
            "SELECT id, schema_version, result_json, created_at FROM final_result_snapshots "
            "WHERE analysis_job_id = :job_id AND organization_id = :org_id ORDER BY created_at DESC LIMIT 1;"
        ),
        {"job_id": analysis_id, "org_id": org_id},
    )
    snapshot_row = res.fetchone()
    if not snapshot_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SNAPSHOT_UNAVAILABLE",
                    "message": "Final result snapshot unavailable for completed analysis job.",
                    "request_id": "req-api",
                }
            },
        )

    return {
        "snapshot_id": str(snapshot_row[0]),
        "analysis_id": str(analysis_id),
        "schema_version": snapshot_row[1],
        "result": snapshot_row[2],
        "created_at": snapshot_row[3].isoformat(),
    }


@router.get("/{analysis_id}/clarification", response_model=AnalysisClarificationDTO)
async def get_analysis_clarification(
    analysis_id: UUID,
    ctx: ExecutionContext = Depends(require_permission("analyses:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AnalysisClarificationDTO:
    org_id = ctx.active_organization_id
    user_id = ctx.authenticated_user_id
    await db.execute(text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)})

    service = ClarificationService(db, organization_id=org_id, user_id=user_id)
    clar = await service.get_open_clarification(analysis_id)
    if not clar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "CLARIFICATION_NOT_FOUND", "message": "No open clarification found for analysis."}
            },
        )

    return AnalysisClarificationDTO(
        id=clar.id,
        analysis_job_id=clar.analysis_job_id,
        organization_id=clar.organization_id,
        clarification_code=clar.clarification_code,
        prompt_key=clar.prompt_key,
        question=clar.question,
        allowed_response_schema=clar.allowed_response_schema,
        status=clar.status,
        requested_at=clar.requested_at.isoformat(),
        expires_at=clar.expires_at.isoformat() if clar.expires_at else None,
        answered_at=clar.answered_at.isoformat() if clar.answered_at else None,
    )


@router.post("/{analysis_id}/clarification/respond", response_model=AnalysisJobDTO)
async def respond_analysis_clarification(
    analysis_id: UUID,
    body: ClarificationRespondRequestDTO,
    ctx: ExecutionContext = Depends(require_permission("analyses:clarifications:respond")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AnalysisJobDTO:
    org_id = ctx.active_organization_id
    user_id = ctx.authenticated_user_id
    await db.execute(text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)})

    service = ClarificationService(db, organization_id=org_id, user_id=user_id)
    job = await service.respond(
        analysis_job_id=analysis_id,
        clarification_id=body.clarification_id,
        response_payload=body.response_payload,
        idempotency_key=body.idempotency_key,
    )

    return AnalysisJobDTO(
        id=job.id,
        organization_id=job.organization_id,
        user_id=job.user_id,
        status=job.status,
        request_prompt=job.request_prompt,
        normalized_request=job.normalized_request,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/{analysis_id}/clarification/cancel", response_model=AnalysisJobDTO)
async def cancel_analysis_clarification(
    analysis_id: UUID,
    body: ClarificationCancelRequestDTO,
    ctx: ExecutionContext = Depends(require_permission("analyses:cancel")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AnalysisJobDTO:
    org_id = ctx.active_organization_id
    user_id = ctx.authenticated_user_id
    await db.execute(text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)})

    service = ClarificationService(db, organization_id=org_id, user_id=user_id)
    job = await service.cancel(
        analysis_job_id=analysis_id,
        clarification_id=body.clarification_id,
        reason_code=body.reason_code,
    )

    return AnalysisJobDTO(
        id=job.id,
        organization_id=job.organization_id,
        user_id=job.user_id,
        status=job.status,
        request_prompt=job.request_prompt,
        normalized_request=job.normalized_request,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
