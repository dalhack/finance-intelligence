from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import BaseAPIException
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.models.upload_session import UploadSession
from app.services.audit_service import AuditService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class InvalidStateTransitionException(BaseAPIException):
    def __init__(self, current_state: str, target_state: str, entity_name: str = "IngestionJob"):
        super().__init__(
            status_code=400,
            code="INVALID_STATE_TRANSITION",
            message=f"{entity_name} state transition from '{current_state}' to '{target_state}' is forbidden.",
        )


SESSION_TRANSITIONS: dict[str, set[str]] = {
    "PENDING_UPLOAD": {"UPLOADED", "FAILED", "EXPIRED"},
    "UPLOADED": {"FINALIZED", "FAILED", "EXPIRED"},
    "FINALIZED": set(),
    "EXPIRED": set(),
    "FAILED": set(),
}

VERSION_TRANSITIONS: dict[str, set[str]] = {
    "PENDING_UPLOAD": {"QUEUED", "FAILED"},
    "QUEUED": {"PARSING", "FAILED"},
    "PARSING": {"EXTRACTED", "COMPLETED", "COMPLETED_WITH_WARNINGS", "AWAITING_REVIEW", "REJECTED", "FAILED", "QUEUED"},
    "EXTRACTED": {"COMPLETED", "COMPLETED_WITH_WARNINGS", "AWAITING_REVIEW", "REJECTED", "FAILED"},
    "COMPLETED": set(),
    "COMPLETED_WITH_WARNINGS": set(),
    "AWAITING_REVIEW": set(),
    "REJECTED": set(),
    "FAILED": set(),
}


JOB_TRANSITIONS: dict[str, set[str]] = {
    "PENDING_UPLOAD": {"UPLOADED", "FAILED", "EXPIRED"},
    "UPLOADED": {"VALIDATING", "QUEUED", "FAILED", "CANCELLED"},
    "VALIDATING": {"VALIDATED", "REJECTED", "FAILED"},
    "VALIDATED": {"QUEUED", "FAILED"},
    "QUEUED": {"PARSING", "FAILED", "CANCELLED"},
    "PARSING": {"EXTRACTED", "COMPLETED", "COMPLETED_WITH_WARNINGS", "AWAITING_REVIEW", "REJECTED", "FAILED", "QUEUED"},
    "EXTRACTED": {"COMPLETED", "COMPLETED_WITH_WARNINGS", "AWAITING_REVIEW", "REJECTED", "FAILED"},
    "FAILED": {"QUEUED"},  # Allowed retry path
    "CANCELLED": set(),
    "EXPIRED": set(),
    "COMPLETED": set(),
    "COMPLETED_WITH_WARNINGS": set(),
    "AWAITING_REVIEW": set(),
    "REJECTED": set(),
}


class StateMachineService:
    @staticmethod
    async def transition_upload_session(
        db: AsyncSession,
        session_id: UUID,
        expected_state: str,
        target_state: str,
        organization_id: UUID,
        actor_id: UUID | None = None,
    ) -> UploadSession:
        res = await db.execute(
            select(UploadSession)
            .where(UploadSession.id == session_id, UploadSession.organization_id == organization_id)
            .with_for_update()
        )
        session = res.scalar_one_or_none()
        if not session:
            raise BaseAPIException(
                status_code=404, code="UPLOAD_SESSION_NOT_FOUND", message="Upload session not found."
            )

        current_state = session.status
        if current_state != expected_state or target_state not in SESSION_TRANSITIONS.get(current_state, set()):
            raise InvalidStateTransitionException(current_state, target_state, entity_name="UploadSession")

        session.status = target_state
        if target_state == "FINALIZED":
            session.finalized_at = datetime.now(UTC)

        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type=f"SESSION_STATE_{target_state}",
            target_type="UPLOAD_SESSION",
            target_id=session_id,
            actor_id=actor_id,
            payload={"from_state": current_state, "to_state": target_state},
        )
        await db.flush()
        return session

    @staticmethod
    async def transition_version(
        db: AsyncSession,
        version_id: UUID,
        expected_state: str,
        target_state: str,
        organization_id: UUID,
        actor_id: UUID | None = None,
    ) -> DocumentVersion:
        res = await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.id == version_id, DocumentVersion.organization_id == organization_id)
            .with_for_update()
        )
        ver = res.scalar_one_or_none()
        if not ver:
            raise BaseAPIException(status_code=404, code="VERSION_NOT_FOUND", message="Document version not found.")

        current_state = ver.ingestion_status
        if current_state != expected_state or target_state not in VERSION_TRANSITIONS.get(current_state, set()):
            raise InvalidStateTransitionException(current_state, target_state, entity_name="DocumentVersion")

        ver.ingestion_status = target_state
        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type=f"VERSION_STATE_{target_state}",
            target_type="DOCUMENT_VERSION",
            target_id=version_id,
            actor_id=actor_id,
            payload={"from_state": current_state, "to_state": target_state},
        )
        await db.flush()
        return ver

    @staticmethod
    async def transition_job(
        db: AsyncSession,
        job_id: UUID,
        expected_state: str,
        target_state: str,
        organization_id: UUID,
        actor_id: UUID | None = None,
    ) -> IngestionJob:
        res = await db.execute(
            select(IngestionJob)
            .where(IngestionJob.id == job_id, IngestionJob.organization_id == organization_id)
            .with_for_update()
        )
        job = res.scalar_one_or_none()
        if not job:
            raise BaseAPIException(status_code=404, code="JOB_NOT_FOUND", message="Ingestion job not found.")

        current_state = job.status
        if current_state != expected_state or target_state not in JOB_TRANSITIONS.get(current_state, set()):
            raise InvalidStateTransitionException(current_state, target_state, entity_name="IngestionJob")

        job.status = target_state
        if target_state in ["COMPLETED", "COMPLETED_WITH_WARNINGS", "AWAITING_REVIEW", "FAILED", "CANCELLED"]:
            job.completed_at = datetime.now(UTC)

        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type=f"JOB_STATE_{target_state}",
            target_type="INGESTION_JOB",
            target_id=job_id,
            actor_id=actor_id,
            payload={"from_state": current_state, "to_state": target_state},
        )
        await db.flush()
        return job

    # Alias for backward compatibility
    @staticmethod
    async def transition(
        db: AsyncSession,
        job_id: UUID,
        expected_state: str,
        target_state: str,
        actor: str = "WORKER",
    ) -> IngestionJob:
        res = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id).with_for_update())
        job = res.scalar_one()
        return await StateMachineService.transition_job(
            db=db,
            job_id=job_id,
            expected_state=expected_state,
            target_state=target_state,
            organization_id=job.organization_id,
        )
