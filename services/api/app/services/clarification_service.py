import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.document import Document
from services.api.app.models.institution import Institution
from services.api.app.models.orchestration import (
    AnalysisAttempt,
    AnalysisClarification,
    AnalysisJob,
    AnalysisPlanModel,
)
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.orchestration.event_engine import AnalysisEventEngine
from services.api.app.orchestration.state_machine import TERMINAL_STATES, AnalysisJobStatus, AnalysisStateMachine
from services.api.app.schemas.clarification import validate_clarification_response
from services.api.app.services.audit_service import AuditService


class ClarificationService:
    def __init__(self, db: AsyncSession, organization_id: UUID, user_id: UUID):
        self.db = db
        self.organization_id = organization_id
        self.user_id = user_id

    async def require_clarification(
        self,
        analysis_job_id: UUID,
        clarification_code: str,
        prompt_key: str,
        question: str,
        allowed_response_schema: dict,
        attempt_number: int = 1,
        ttl_minutes: int = 15,
    ) -> AnalysisClarification:
        job_res = await self.db.execute(select(AnalysisJob).where(AnalysisJob.id == analysis_job_id).with_for_update())
        job = job_res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ANALYSIS_NOT_FOUND", "message": "Analysis job not found."}},
            )

        # Transition job status
        AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.NEEDS_CLARIFICATION)
        job.status = AnalysisJobStatus.NEEDS_CLARIFICATION.value
        job.updated_at = datetime.now(UTC)

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=ttl_minutes)

        clarification = AnalysisClarification(
            id=uuid4(),
            analysis_job_id=analysis_job_id,
            organization_id=self.organization_id,
            clarification_code=clarification_code,
            prompt_key=prompt_key,
            question=question,
            allowed_response_schema=allowed_response_schema,
            status="AWAITING_CLARIFICATION",
            requested_at=now,
            expires_at=expires_at,
            attempt_number=attempt_number,
            created_by_system="SYSTEM",
            created_at=now,
        )
        self.db.add(clarification)

        # Emit domain event & audit log
        event_engine = AnalysisEventEngine(self.db, self.organization_id)
        await event_engine.emit_event(
            analysis_job_id=analysis_job_id,
            event_type="analysis.clarification_required",
            payload={
                "analysisId": str(analysis_job_id),
                "clarificationId": str(clarification.id),
                "clarificationCode": clarification_code,
                "promptKey": prompt_key,
                "contractVersion": "3.0.0",
            },
        )

        await AuditService.record_event(
            db=self.db,
            organization_id=self.organization_id,
            event_type="CLARIFICATION_REQUIRED",
            target_type="ANALYSIS_JOB",
            target_id=analysis_job_id,
            actor_id=self.user_id,
            payload={"clarification_code": clarification_code},
        )

        await self.db.commit()
        return clarification

    async def get_open_clarification(self, analysis_job_id: UUID) -> AnalysisClarification | None:
        res = await self.db.execute(
            select(AnalysisClarification).where(
                AnalysisClarification.analysis_job_id == analysis_job_id,
                AnalysisClarification.status == "AWAITING_CLARIFICATION",
            )
        )
        return res.scalar_one_or_none()

    async def respond(
        self,
        analysis_job_id: UUID,
        clarification_id: UUID,
        response_payload: dict,
        idempotency_key: str,
    ) -> AnalysisJob:
        # Lock Job
        job_res = await self.db.execute(select(AnalysisJob).where(AnalysisJob.id == analysis_job_id).with_for_update())
        job = job_res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ANALYSIS_NOT_FOUND", "message": "Analysis job not found."}},
            )

        if job.status != AnalysisJobStatus.NEEDS_CLARIFICATION.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "CLARIFICATION_NOT_REQUIRED",
                        "message": f"Analysis job is in state '{job.status}' and not awaiting clarification.",
                        "retryable": False,
                    }
                },
            )

        # Lock Clarification
        clar_res = await self.db.execute(
            select(AnalysisClarification)
            .where(
                AnalysisClarification.id == clarification_id,
                AnalysisClarification.analysis_job_id == analysis_job_id,
            )
            .with_for_update()
        )
        clar = clar_res.scalar_one_or_none()
        if not clar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "CLARIFICATION_NOT_FOUND", "message": "Clarification not found."}},
            )

        if clar.status == "CLARIFICATION_RECEIVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "CLARIFICATION_ALREADY_ANSWERED",
                        "message": "Clarification already answered.",
                        "retryable": False,
                    }
                },
            )

        if clar.status != "AWAITING_CLARIFICATION":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "CLARIFICATION_EXPIRED",
                        "message": f"Clarification is in status '{clar.status}'.",
                        "retryable": False,
                    }
                },
            )

        now = datetime.now(UTC)
        if clar.expires_at and now > clar.expires_at:
            clar.status = "CLARIFICATION_EXPIRED"
            job.status = AnalysisJobStatus.EXPIRED.value
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "CLARIFICATION_EXPIRED",
                        "message": "Clarification response window has expired.",
                        "retryable": False,
                    }
                },
            )

        # Validate Schema & Sanitize Payload
        try:
            validated_payload = validate_clarification_response(clar.clarification_code, response_payload)
            await self._verify_referenced_entities_tenant_ownership(validated_payload)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "CLARIFICATION_RESPONSE_INVALID", "message": str(e), "retryable": False}},
            )

        # Compute Response Fingerprint
        fp_raw = f"{clar.id!s}:{json.dumps(validated_payload, sort_keys=True)}"
        fingerprint = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()

        # Update Clarification
        clar.status = "CLARIFICATION_RECEIVED"
        clar.answered_at = now
        clar.response_payload = validated_payload
        clar.response_fingerprint = fingerprint

        # Create New Incremented AnalysisAttempt & AnalysisPlanModel
        new_attempt_number = clar.attempt_number + 1
        new_attempt = AnalysisAttempt(
            id=uuid4(),
            analysis_job_id=analysis_job_id,
            organization_id=self.organization_id,
            attempt_number=new_attempt_number,
            status="IN_PROGRESS",
            created_at=now,
        )
        self.db.add(new_attempt)

        new_plan = AnalysisPlanModel(
            id=uuid4(),
            analysis_job_id=analysis_job_id,
            organization_id=self.organization_id,
            plan_version=f"{new_attempt_number}.0.0",
            plan_json={"clarification_response": validated_payload, "code": clar.clarification_code},
            created_at=now,
        )
        self.db.add(new_plan)

        # Transition Job Back to UNDERSTANDING_REQUEST
        AnalysisStateMachine.validate_transition(
            AnalysisJobStatus.NEEDS_CLARIFICATION, AnalysisJobStatus.UNDERSTANDING_REQUEST
        )
        job.status = AnalysisJobStatus.UNDERSTANDING_REQUEST.value
        job.updated_at = now

        # Publish Events & Audit Log
        event_engine = AnalysisEventEngine(self.db, self.organization_id)
        await event_engine.emit_event(
            analysis_job_id=analysis_job_id,
            event_type="analysis.clarification_received",
            payload={
                "analysisId": str(analysis_job_id),
                "clarificationId": str(clarification_id),
                "contractVersion": "3.0.0",
            },
        )
        await event_engine.emit_event(
            analysis_job_id=analysis_job_id,
            event_type="analysis.resumed",
            payload={
                "analysisId": str(analysis_job_id),
                "attemptNumber": new_attempt_number,
                "contractVersion": "3.0.0",
            },
        )

        await AuditService.record_event(
            db=self.db,
            organization_id=self.organization_id,
            event_type="CLARIFICATION_RESPONDED",
            target_type="ANALYSIS_JOB",
            target_id=analysis_job_id,
            actor_id=self.user_id,
            payload={"clarification_code": clar.clarification_code},
        )
        await AuditService.record_event(
            db=self.db,
            organization_id=self.organization_id,
            event_type="ANALYSIS_RESUMED_AFTER_CLARIFICATION",
            target_type="ANALYSIS_JOB",
            target_id=analysis_job_id,
            actor_id=self.user_id,
            payload={"attempt_number": new_attempt_number},
        )

        await self.db.commit()
        return job

    async def cancel(
        self,
        analysis_job_id: UUID,
        clarification_id: UUID,
        reason_code: str = "USER_CANCELLED",
    ) -> AnalysisJob:
        job_res = await self.db.execute(select(AnalysisJob).where(AnalysisJob.id == analysis_job_id).with_for_update())
        job = job_res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ANALYSIS_NOT_FOUND", "message": "Analysis job not found."}},
            )

        clar_res = await self.db.execute(
            select(AnalysisClarification)
            .where(
                AnalysisClarification.id == clarification_id,
                AnalysisClarification.analysis_job_id == analysis_job_id,
            )
            .with_for_update()
        )
        clar = clar_res.scalar_one_or_none()
        if not clar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "CLARIFICATION_NOT_FOUND", "message": "Clarification not found."}},
            )

        now = datetime.now(UTC)
        clar.status = "CLARIFICATION_CANCELLED"
        clar.cancelled_at = now

        AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.CANCELLED)
        job.status = AnalysisJobStatus.CANCELLED.value
        job.updated_at = now

        await AuditService.record_event(
            db=self.db,
            organization_id=self.organization_id,
            event_type="CLARIFICATION_CANCELLED",
            target_type="ANALYSIS_JOB",
            target_id=analysis_job_id,
            actor_id=self.user_id,
            payload={"reason_code": reason_code},
        )

        await self.db.commit()
        return job

    async def expire_due_clarifications(self, batch_size: int = 50) -> int:
        now = datetime.now(UTC)
        res = await self.db.execute(
            select(AnalysisClarification)
            .where(
                AnalysisClarification.status == "AWAITING_CLARIFICATION",
                AnalysisClarification.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        )
        expired_clarifications = res.scalars().all()
        expired_count = 0

        for clar in expired_clarifications:
            clar.status = "CLARIFICATION_EXPIRED"
            expired_count += 1

            # Lock & update job
            job_res = await self.db.execute(
                select(AnalysisJob).where(AnalysisJob.id == clar.analysis_job_id).with_for_update()
            )
            job = job_res.scalar_one_or_none()
            if job and job.status not in TERMINAL_STATES:
                AnalysisStateMachine.validate_transition(AnalysisJobStatus(job.status), AnalysisJobStatus.EXPIRED)
                job.status = AnalysisJobStatus.EXPIRED.value
                job.updated_at = now

            # Emit Event & Audit Log
            event_engine = AnalysisEventEngine(self.db, clar.organization_id)
            await event_engine.emit_event(
                analysis_job_id=clar.analysis_job_id,
                event_type="analysis.clarification_expired",
                payload={
                    "analysisId": str(clar.analysis_job_id),
                    "clarificationId": str(clar.id),
                    "contractVersion": "3.0.0",
                },
            )

            await AuditService.record_event(
                db=self.db,
                organization_id=clar.organization_id,
                event_type="CLARIFICATION_EXPIRED",
                target_type="ANALYSIS_JOB",
                target_id=clar.analysis_job_id,
                actor_id=self.user_id,
                payload={"clarification_code": clar.clarification_code},
            )

        if expired_count > 0:
            await self.db.commit()

        return expired_count

    async def _verify_referenced_entities_tenant_ownership(self, payload: dict) -> None:
        if "institution_id" in payload:
            inst_res = await self.db.execute(
                select(Institution).where(Institution.id == UUID(str(payload["institution_id"])))
            )
            if not inst_res.scalar_one_or_none():
                raise ValueError("Referenced institution not found in tenant context.")

        if "period_id" in payload:
            per_res = await self.db.execute(
                select(ReportingPeriod).where(ReportingPeriod.id == UUID(str(payload["period_id"])))
            )
            if not per_res.scalar_one_or_none():
                raise ValueError("Referenced reporting period not found in tenant context.")

        if "document_id" in payload:
            doc_res = await self.db.execute(select(Document).where(Document.id == UUID(str(payload["document_id"]))))
            if not doc_res.scalar_one_or_none():
                raise ValueError("Referenced document not found in tenant context.")
