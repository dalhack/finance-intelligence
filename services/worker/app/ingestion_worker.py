import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.models.extraction_result import ExtractionResult, ExtractionWarning
from app.models.ingestion_job import IngestionAttempt, IngestionJob
from app.models.stored_object import StoredObject
from app.orchestration.provider_anthropic import AnthropicProviderAdapter
from app.parsers.registry import parser_registry
from app.services.audit_service import AuditService
from app.services.fact_extraction_service import FactExtractionService
from app.services.state_machine import StateMachineService
from app.storage.factory import get_storage_adapter
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("finance_intelligence_worker")

KNOWN_SAFE_ERROR_CODES = {
    "DOCUMENT_VERSION_NOT_FOUND",
    "UNSUPPORTED_MIME_TYPE",
    "ENCRYPTED_DOCUMENT",
    "MALFORMED_DOCUMENT",
    "RESOURCE_LIMIT_EXCEEDED",
    "ENCODING_UNCERTAIN",
    "NULL_BYTE_DETECTED",
    "ZIP_BOMB_LIMIT_EXCEEDED",
    "UNKNOWN_PARSER_STATUS",
}

# Strict 5 Canonical Parser Status Mapping (No un-documented aliases)
VALID_PARSER_STATUS_MAP = {
    "COMPLETED": "COMPLETED",
    "COMPLETED_WITH_WARNINGS": "COMPLETED_WITH_WARNINGS",
    "AWAITING_REVIEW": "AWAITING_REVIEW",
    "REJECTED": "REJECTED",
    "FAILED": "FAILED",
}


class WorkerOutcomeStatus(str, Enum):
    NO_JOB_CLAIMED = "NO_JOB_CLAIMED"
    PROCESSED_SUCCESS = "PROCESSED_SUCCESS"  # COMPLETED, COMPLETED_WITH_WARNINGS
    PROCESSED_REVIEW_REQUIRED = "PROCESSED_REVIEW_REQUIRED"  # AWAITING_REVIEW
    PROCESSED_REJECTED = "PROCESSED_REJECTED"  # REJECTED
    PROCESSED_FAILED = "PROCESSED_FAILED"  # FAILED, UNKNOWN_PARSER_STATUS
    STALE_CLAIM_ABORTED = "STALE_CLAIM_ABORTED"
    REJECTED = "REJECTED"


from app.models.ingestion_command_log import IngestionCommandLog

from services.worker.app.command_envelope import IngestionCommandEnvelope, InvalidCommandEnvelopeError


@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    organization_id: UUID
    document_version_id: UUID
    worker_id: str
    claim_token: UUID


@dataclass(frozen=True)
class WorkerProcessOutcome:
    claimed: bool
    outcome_status: WorkerOutcomeStatus
    job_id: UUID | None = None
    error_code: str | None = None


def _build_extraction_provider() -> AnthropicProviderAdapter | None:
    """Fast-model reader for filings whose tables defeat deterministic parsing.

    Returns None when the feature is disabled or no key is configured, in which
    case ingestion keeps working with deterministic extraction alone.
    """
    if not settings.ENABLE_LLM_FACT_EXTRACTION or not settings.ANTHROPIC_API_KEY:
        return None
    return AnthropicProviderAdapter(
        application_model_alias="finance_analysis_fast",
        environment=settings.ENVIRONMENT,
    )


class IngestionWorker:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def claim_and_process_envelope(
        self,
        envelope: IngestionCommandEnvelope,
        worker_id: str,
        secret_resolver: Callable[[str], str] | None = None,
    ) -> WorkerProcessOutcome:
        """Validate envelope, record persistent replay log, claim targeted job_id, and process under RLS context."""
        if not worker_id or not worker_id.strip() or len(worker_id) > 255:
            raise ValueError("CRITICAL_SECURITY_VIOLATION: Invalid worker ID")

        # 1. Pre-database fail-closed validation
        try:
            envelope.validate_envelope(secret_resolver=secret_resolver)
        except InvalidCommandEnvelopeError as e:
            safe_err = str(e).split(":")[0].strip()
            logger.error(f"Command envelope validation failed: {safe_err}")
            return WorkerProcessOutcome(
                claimed=False,
                outcome_status=WorkerOutcomeStatus.REJECTED,
                job_id=envelope.job_id,
                error_code=safe_err,
            )

        # 2. Call targeted SQL claim function
        claim_token = uuid4()
        claim_res = await self.db.execute(
            text(
                "SELECT job_id, organization_id, document_version_id, claim_token "
                "FROM claim_ingestion_job(:job_id, :worker_id, :claim_token);"
            ),
            {
                "job_id": envelope.job_id,
                "worker_id": worker_id,
                "claim_token": claim_token,
            },
        )
        row = claim_res.fetchone()

        if not row or not row.job_id:
            await self.db.commit()
            return WorkerProcessOutcome(claimed=False, outcome_status=WorkerOutcomeStatus.NO_JOB_CLAIMED)

        resolved_org_id = row.organization_id

        # 3. Set org context and Atomic Persistent Replay Logging
        try:
            await self.db.execute(
                text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(resolved_org_id)},
            )
            cmd_log = IngestionCommandLog(
                command_id=envelope.command_id,
                job_id=row.job_id,
                organization_id=resolved_org_id,
                command_type=envelope.command_type,
                idempotency_key=envelope.idempotency_key,
                schema_version=envelope.schema_version,
                issued_at=envelope.issued_at,
            )
            self.db.add(cmd_log)
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            logger.warning("Replay attempt detected for envelope")
            return WorkerProcessOutcome(
                claimed=False,
                outcome_status=WorkerOutcomeStatus.REJECTED,
                job_id=envelope.job_id,
                error_code="COMMAND_REPLAYED",
            )

        await self.db.commit()

        claimed_job = ClaimedJob(
            job_id=row.job_id,
            organization_id=resolved_org_id,
            document_version_id=row.document_version_id,
            worker_id=worker_id,
            claim_token=row.claim_token,
        )

        # Bind transaction-scoped tenant context (SET LOCAL)
        await self.db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(claimed_job.organization_id)},
        )

        return await self._process_claimed_job(claimed_job)

    async def _process_claimed_job(self, claimed_job: ClaimedJob) -> WorkerProcessOutcome:
        """Internal processing method accepting ONLY a valid, immutable ClaimedJob instance."""
        # Atomic lock verification verifying job_id + locked_by + claim_token
        res = await self.db.execute(
            select(IngestionJob)
            .where(
                IngestionJob.id == claimed_job.job_id,
                IngestionJob.locked_by == claimed_job.worker_id,
                IngestionJob.claim_token == claimed_job.claim_token,
                IngestionJob.status.in_(["QUEUED", "PARSING"]),
            )
            .with_for_update(skip_locked=True)
        )
        job = res.scalar_one_or_none()
        if not job:
            return WorkerProcessOutcome(
                claimed=True,
                outcome_status=WorkerOutcomeStatus.STALE_CLAIM_ABORTED,
                job_id=claimed_job.job_id,
            )

        # Transition job status if not already set to PARSING
        if job.status != "PARSING":
            await StateMachineService.transition_job(self.db, job.id, "QUEUED", "PARSING", claimed_job.organization_id)
        job.current_attempt += 1
        job.started_at = datetime.now(UTC)
        await self.db.flush()

        attempt = IngestionAttempt(
            organization_id=claimed_job.organization_id,
            ingestion_job_id=job.id,
            attempt_number=job.current_attempt,
            status="PARSING",
            started_at=datetime.now(UTC),
        )
        self.db.add(attempt)
        await self.db.flush()

        await AuditService.record_event(
            db=self.db,
            organization_id=claimed_job.organization_id,
            event_type="PARSING_STARTED",
            target_type="INGESTION_JOB",
            target_id=job.id,
            payload={"attempt_number": job.current_attempt},
        )

        ver_res = await self.db.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == job.document_version_id,
                DocumentVersion.organization_id == claimed_job.organization_id,
            )
        )
        version = ver_res.scalar_one_or_none()
        if not version:
            await StateMachineService.transition_job(self.db, job.id, "PARSING", "FAILED", claimed_job.organization_id)
            attempt.status = "FAILED"
            attempt.error_code = "DOCUMENT_VERSION_NOT_FOUND"
            attempt.error_message = "Associated DocumentVersion record was not found."
            await self.db.commit()
            return WorkerProcessOutcome(
                claimed=True,
                outcome_status=WorkerOutcomeStatus.PROCESSED_FAILED,
                job_id=claimed_job.job_id,
                error_code="DOCUMENT_VERSION_NOT_FOUND",
            )

        await StateMachineService.transition_version(
            self.db, version.id, "QUEUED", "PARSING", claimed_job.organization_id
        )

        try:
            stored_obj_res = await self.db.execute(
                select(StoredObject).where(
                    StoredObject.id == version.stored_object_id,
                    StoredObject.organization_id == claimed_job.organization_id,
                )
            )
            stored_obj = stored_obj_res.scalar_one()

            adapter = get_storage_adapter()
            file_stream = await adapter.get_object(str(claimed_job.organization_id), stored_obj.opaque_object_key)
            file_bytes = file_stream.read()

            parser = parser_registry.get_parser(stored_obj.detected_mime_type)
            output = parser.parse(file_bytes, stored_obj.opaque_object_key)

            # Validate Parser Output Status Mapping (Fail-closed for unknown status)
            if output.status not in VALID_PARSER_STATUS_MAP:
                raise ValueError("UNKNOWN_PARSER_STATUS")

            target_status = VALID_PARSER_STATUS_MAP[output.status]

            # Persist Document Pages
            page_map: dict[int, UUID] = {}
            for page_data in output.pages:
                dp = DocumentPage(
                    organization_id=claimed_job.organization_id,
                    document_version_id=version.id,
                    page_number=page_data["page_number"],
                    width_px=page_data["width_px"],
                    height_px=page_data["height_px"],
                    text_layer_present=page_data["text_layer_present"],
                    raw_page_text=page_data["raw_page_text"],
                )
                self.db.add(dp)
                await self.db.flush()
                page_map[page_data["page_number"]] = dp.id

            # Persist Document Chunks
            for chunk_data in output.chunks:
                lineage = chunk_data["source_lineage"]
                page_num = lineage.get("page_number")
                page_id = page_map.get(page_num) if page_num else None

                dc = DocumentChunk(
                    organization_id=claimed_job.organization_id,
                    document_version_id=version.id,
                    document_page_id=page_id,
                    chunk_index=chunk_data["chunk_index"],
                    chunk_type=chunk_data["chunk_type"],
                    content=chunk_data["content"],
                    source_lineage=lineage,
                )
                self.db.add(dc)

            # Persist Extraction Result
            ext_result = ExtractionResult(
                organization_id=claimed_job.organization_id,
                document_version_id=version.id,
                parser_name=output.parser_name,
                parser_version=output.parser_version,
                status=output.status,
                quality_score=output.quality_score,
            )
            self.db.add(ext_result)
            await self.db.flush()

            # Persist Extraction Warnings
            for w in output.warnings:
                ew = ExtractionWarning(
                    organization_id=claimed_job.organization_id,
                    extraction_result_id=ext_result.id,
                    warning_code=w.warning_code,
                    warning_message=w.warning_message,
                    lineage_ref=w.lineage_ref,
                )
                self.db.add(ew)

            # Turn recognised table rows into review candidates. Parsing alone
            # only yields chunks; without this step the review queue stays empty
            # and no value can ever reach the fact store.
            if output.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS"):
                document = await self.db.get(Document, version.document_id)
                if document is not None:
                    summary = await FactExtractionService.extract_candidates(
                        db=self.db,
                        organization_id=claimed_job.organization_id,
                        document_id=document.id,
                        document_version_id=version.id,
                        display_name=document.display_name,
                        chunks=output.chunks,
                        provider=_build_extraction_provider(),
                    )
                    logger.info(
                        "FACT_CANDIDATES_EXTRACTED",
                        extra={
                            "candidates_created": summary.candidates_created,
                            "matched_labels": summary.matched_labels,
                            "rows_considered": summary.rows_considered,
                        },
                    )

            attempt.status = target_status
            attempt.completed_at = datetime.now(UTC)

            await StateMachineService.transition_job(
                self.db, job.id, "PARSING", target_status, claimed_job.organization_id
            )
            await StateMachineService.transition_version(
                self.db, version.id, "PARSING", target_status, claimed_job.organization_id
            )
            version.extraction_status = output.status

            if output.status == "AWAITING_REVIEW":
                audit_event_name = "REVIEW_REQUIRED"
                outcome_status = WorkerOutcomeStatus.PROCESSED_REVIEW_REQUIRED
            elif output.status == "REJECTED":
                audit_event_name = "PARSING_REJECTED"
                outcome_status = WorkerOutcomeStatus.PROCESSED_REJECTED
            elif output.status == "FAILED":
                audit_event_name = "PARSING_FAILED"
                outcome_status = WorkerOutcomeStatus.PROCESSED_FAILED
            else:
                audit_event_name = "PARSING_COMPLETED"
                outcome_status = WorkerOutcomeStatus.PROCESSED_SUCCESS

            await AuditService.record_event(
                db=self.db,
                organization_id=claimed_job.organization_id,
                event_type=audit_event_name,
                target_type="INGESTION_JOB",
                target_id=job.id,
                payload={"quality_score": output.quality_score, "status": output.status},
            )

            await self.db.commit()
            return WorkerProcessOutcome(
                claimed=True,
                outcome_status=outcome_status,
                job_id=claimed_job.job_id,
            )

        except Exception as err:  # noqa: BLE001
            # Safe production logging without raw tracebacks or sensitive data
            logger.error("Worker processing failed for claimed job")

            # 1. Rollback aborted transaction to clear failed state
            await self.db.rollback()

            # 2. Re-bind tenant context in new transaction block using saved organization_id
            await self.db.execute(
                text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                {"org_id": str(claimed_job.organization_id)},
            )

            raw_err_str = str(err)
            if "UNKNOWN_PARSER_STATUS" in raw_err_str:
                error_code = "UNKNOWN_PARSER_STATUS"
                error_msg = "Unknown or unmapped parser output status."
            else:
                raw_code = getattr(err, "code", "PARSER_EXCEPTION")
                error_code = str(raw_code) if str(raw_code) in KNOWN_SAFE_ERROR_CODES else "PARSER_FAILED"
                error_msg = (
                    str(getattr(err, "message", "A parsing or worker processing error occurred."))
                    if error_code in KNOWN_SAFE_ERROR_CODES
                    else "Document parsing failed due to a worker exception."
                )

            # 3. Re-lock job verifying claim ownership token
            rec_query = select(IngestionJob).where(IngestionJob.id == claimed_job.job_id).with_for_update()

            res_retry = await self.db.execute(rec_query)
            r_job = res_retry.scalar_one_or_none()

            if not r_job or r_job.locked_by != claimed_job.worker_id or r_job.claim_token != claimed_job.claim_token:
                return WorkerProcessOutcome(
                    claimed=True,
                    outcome_status=WorkerOutcomeStatus.STALE_CLAIM_ABORTED,
                    job_id=claimed_job.job_id,
                    error_code=error_code,
                )

            current_attempt_num = (
                attempt.attempt_number if "attempt" in locals() and attempt is not None else (r_job.current_attempt + 1)
            )
            next_status = "QUEUED" if current_attempt_num < r_job.max_attempts else "FAILED"
            if r_job.status != next_status:
                await StateMachineService.transition_job(
                    self.db, r_job.id, r_job.status, next_status, r_job.organization_id
                )

            r_job.current_attempt = current_attempt_num
            self.db.add(r_job)
            await self.db.flush()

            att_fail = IngestionAttempt(
                organization_id=r_job.organization_id,
                ingestion_job_id=r_job.id,
                attempt_number=r_job.current_attempt,
                status="FAILED",
                error_code=error_code,
                error_message=error_msg,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            self.db.add(att_fail)

            ver_fail = await self.db.execute(
                select(DocumentVersion).where(
                    DocumentVersion.id == r_job.document_version_id,
                    DocumentVersion.organization_id == r_job.organization_id,
                )
            )
            v_fail = ver_fail.scalar_one_or_none()
            if v_fail:
                if v_fail.ingestion_status != next_status:
                    await StateMachineService.transition_version(
                        self.db, v_fail.id, v_fail.ingestion_status, next_status, r_job.organization_id
                    )
                v_fail.extraction_status = "FAILED"

            await AuditService.record_event(
                db=self.db,
                organization_id=r_job.organization_id,
                event_type="PARSING_FAILED",
                target_type="INGESTION_JOB",
                target_id=r_job.id,
                payload={"error_code": error_code},
            )

            await self.db.commit()

            return WorkerProcessOutcome(
                claimed=True,
                outcome_status=WorkerOutcomeStatus.PROCESSED_FAILED,
                job_id=claimed_job.job_id,
                error_code=error_code,
            )
