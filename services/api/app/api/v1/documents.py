import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from app.core.security_pipeline import (
    MAX_PDF_SIZE_BYTES,
    MAX_XLSX_SIZE_BYTES,
    SecurityPipelineException,
    sanitize_filename,
    security_validation_read_size,
    validate_file_security,
)
from app.db.session import get_db_session
from app.dependencies import require_permission
from app.middleware.execution_context import ExecutionContext
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.extraction_result import ExtractionResult, ExtractionWarning
from app.models.ingestion_job import IngestionJob
from app.models.upload_session import UploadSession
from app.schemas.document import (
    DocumentResponse,
    DocumentVersionResponse,
    IngestionStatusResponse,
    UploadFinalizeResponse,
    UploadInitiateResponse,
    WarningResponse,
)
from app.services.audit_service import AuditService
from app.services.fact_extraction_service import FactExtractionService
from app.services.reference_service import ReferenceService
from app.services.state_machine import StateMachineService
from app.storage.factory import get_storage_adapter
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

ALLOWED_CLASSIFICATIONS = {
    "PUBLIC",
    "INTERNAL",
    "CONFIDENTIAL",
    "STRICTLY_CONFIDENTIAL",
    "PERSONAL_DATA",
}


@router.post("/uploads", response_model=UploadInitiateResponse, status_code=status.HTTP_201_CREATED)
async def initiate_and_stream_upload(
    display_name: Annotated[str, Form(...)],
    file: Annotated[UploadFile, File(...)],
    ctx: Annotated[ExecutionContext, Depends(require_permission("documents:upload"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    classification: Annotated[str, Form()] = "CONFIDENTIAL",
):
    org_id = ctx.active_organization_id
    user_id = ctx.authenticated_user_id

    # Classification Validation & Preservation
    clean_classification = classification.upper().strip()
    if clean_classification not in ALLOWED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid classification '{classification}'. Allowed values: {', '.join(sorted(ALLOWED_CLASSIFICATIONS))}",
        )

    original_filename = file.filename or display_name
    sanitized_name = sanitize_filename(original_filename)
    _, ext = os.path.splitext(sanitized_name.lower())

    if ext not in [".pdf", ".xlsx", ".csv"]:
        await AuditService.record_event(
            db=db,
            organization_id=org_id,
            event_type="UPLOAD_REJECTED",
            target_type="UPLOAD_SESSION",
            target_id=uuid4(),
            actor_id=user_id,
            payload={"reason": "UNSUPPORTED_FILE_TYPE", "extension": ext},
        )
        raise SecurityPipelineException(
            code="UNSUPPORTED_FILE_TYPE",
            message=f"Extension '{ext}' is not supported. Supported extensions: .pdf, .xlsx, .csv",
            status_code=415,
        )

    max_allowed = MAX_PDF_SIZE_BYTES if ext == ".pdf" else MAX_XLSX_SIZE_BYTES
    declared_mime = file.content_type or "application/octet-stream"

    session_id = uuid4()
    opaque_key = f"{org_id}/{session_id}.bin"
    expires_at = datetime.now(UTC) + timedelta(hours=24)

    adapter = get_storage_adapter()
    temp_path = adapter.begin_temporary_write(str(org_id), opaque_key)

    # TRUE BOUNDED STREAMING (No BytesIO RAM buffers)
    sha256 = __import__("hashlib").sha256()
    received_bytes = 0

    try:
        while chunk := await file.read(65536):
            received_bytes += len(chunk)
            if received_bytes > max_allowed:
                adapter.abort_temporary_write(temp_path)
                await AuditService.record_event(
                    db=db,
                    organization_id=org_id,
                    event_type="UPLOAD_REJECTED",
                    target_type="UPLOAD_SESSION",
                    target_id=session_id,
                    actor_id=user_id,
                    payload={"reason": "FILE_TOO_LARGE", "received_bytes": received_bytes},
                )
                raise SecurityPipelineException(
                    code="FILE_TOO_LARGE",
                    message=f"File size exceeds maximum limit of {max_allowed} bytes.",
                    status_code=413,
                )
            sha256.update(chunk)
            adapter.write_chunk(temp_path, chunk)

        adapter.finalize_temporary_write(temp_path, str(org_id), opaque_key)

    except Exception:
        adapter.abort_temporary_write(temp_path)
        raise

    server_hash = sha256.hexdigest()

    # Record Upload Session with classification metadata & incremental hash
    session = UploadSession(
        id=session_id,
        organization_id=org_id,
        created_by_user_id=user_id,
        original_filename=original_filename,
        sanitized_filename=sanitized_name,
        normalized_extension=ext,
        declared_mime_type=declared_mime,
        classification=clean_classification,
        expected_size_bytes=received_bytes,
        received_size_bytes=received_bytes,
        server_computed_sha256=server_hash,
        status="UPLOADED",
        temporary_object_key=opaque_key,
        expires_at=expires_at,
    )
    db.add(session)

    await AuditService.record_event(
        db=db,
        organization_id=org_id,
        event_type="UPLOAD_INITIATED",
        target_type="UPLOAD_SESSION",
        target_id=session_id,
        actor_id=user_id,
        payload={
            "byte_size": received_bytes,
            "classification": clean_classification,
            "sha256_prefix": server_hash[:8],
        },
    )

    await db.commit()

    return UploadInitiateResponse(
        session_id=session.id,
        organization_id=session.organization_id,
        status=session.status,
        expires_at=session.expires_at,
    )


@router.post("/uploads/{session_id}/finalize", response_model=UploadFinalizeResponse)
async def finalize_upload(
    session_id: UUID,
    ctx: Annotated[ExecutionContext, Depends(require_permission("documents:finalize"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    org_id = ctx.active_organization_id
    user_id = ctx.authenticated_user_id

    session_res = await db.execute(
        select(UploadSession)
        .where(
            UploadSession.id == session_id,
            UploadSession.organization_id == org_id,
        )
        .with_for_update()
    )
    session = session_res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found.")

    if session.status == "FINALIZED" or session.status == "EXPIRED":
        raise HTTPException(status_code=400, detail=f"Upload session is already in terminal state '{session.status}'.")

    if datetime.now(UTC) > session.expires_at:
        await StateMachineService.transition_upload_session(
            db, session.id, session.status, "EXPIRED", org_id, actor_id=user_id
        )
        await db.commit()
        raise HTTPException(status_code=400, detail="Upload session has expired.")

    if not session.temporary_object_key:
        raise HTTPException(status_code=400, detail="Upload session has no associated temporary object.")

    adapter = get_storage_adapter()

    # Streamed Bounded Hash & Size Verification (No full file read into RAM)
    recalculated_hash, file_size = await adapter.compute_hash_and_size(str(org_id), session.temporary_object_key)
    if session.server_computed_sha256 and recalculated_hash != session.server_computed_sha256:
        await AuditService.record_event(
            db=db,
            organization_id=org_id,
            event_type="FINALIZE_FAILED",
            target_type="UPLOAD_SESSION",
            target_id=session_id,
            actor_id=user_id,
            payload={"reason": "UPLOAD_INTEGRITY_FAILED"},
        )
        raise SecurityPipelineException(
            code="UPLOAD_INTEGRITY_FAILED",
            message="Server re-computed hash does not match upload session hash. Upload tampered or corrupted.",
            status_code=400,
        )

    # Read the bytes the security pipeline needs: a bounded header sample for
    # header-only formats, the whole object for PDF/XLSX whose structure index
    # sits at the end of the file.
    validation_read_size = security_validation_read_size(session.sanitized_filename, file_size)
    sample_bytes = await adapter.read_sample_bytes(str(org_id), session.temporary_object_key, validation_read_size)
    sec_result = validate_file_security(sample_bytes, session.sanitized_filename, session.declared_mime_type)
    detected_mime = sec_result["detected_mime"]

    is_deduplicated = False
    try:
        # Atomic ON CONFLICT create_or_acquire via ReferenceService
        stored_object, is_deduplicated = await ReferenceService.create_or_acquire(
            db=db,
            organization_id=org_id,
            sha256_hash=recalculated_hash,
            opaque_key=session.temporary_object_key,
            byte_size=file_size,
            detected_mime=detected_mime,
        )

        # Create Logical Document with classification preserved from session
        document = Document(
            id=uuid4(),
            organization_id=org_id,
            uploaded_by_user_id=user_id,
            display_name=session.sanitized_filename,
            document_type="GENERAL",
            classification=session.classification,
            status="ACTIVE",
        )
        db.add(document)
        await db.flush()

        # Create Document Version
        doc_version = DocumentVersion(
            id=uuid4(),
            organization_id=org_id,
            document_id=document.id,
            stored_object_id=stored_object.id,
            version_number=1,
            content_hash_sha256=recalculated_hash,
            file_size_bytes=file_size,
            declared_mime_type=session.declared_mime_type,
            detected_mime_type=detected_mime,
            ingestion_status="QUEUED",
            extraction_status="NOT_STARTED",
        )
        db.add(doc_version)
        await db.flush()

        # Create Ingestion Job
        job = IngestionJob(
            id=uuid4(),
            organization_id=org_id,
            document_version_id=doc_version.id,
            status="QUEUED",
            current_attempt=0,
            max_attempts=3,
        )
        db.add(job)

        # Transition upload session via StateMachineService
        await StateMachineService.transition_upload_session(
            db, session.id, "UPLOADED", "FINALIZED", org_id, actor_id=user_id
        )

        if is_deduplicated:
            await AuditService.record_event(
                db=db,
                organization_id=org_id,
                event_type="DUPLICATE_DETECTED",
                target_type="STORED_OBJECT",
                target_id=stored_object.id,
                actor_id=user_id,
                payload={"sha256_prefix": recalculated_hash[:8]},
            )

        await AuditService.record_event(
            db=db,
            organization_id=org_id,
            event_type="FINALIZE_COMPLETED",
            target_type="DOCUMENT_VERSION",
            target_id=doc_version.id,
            actor_id=user_id,
            payload={"document_id": str(document.id), "is_deduplicated": is_deduplicated},
        )
        await AuditService.record_event(
            db=db,
            organization_id=org_id,
            event_type="INGESTION_QUEUED",
            target_type="INGESTION_JOB",
            target_id=job.id,
            actor_id=user_id,
            payload={"job_id": str(job.id)},
        )

        # Provision the institution and reporting period this filing refers to.
        # Creating reference data needs privileges the ingestion worker does not
        # have, so it happens here; extraction later reads what was provisioned.
        await FactExtractionService.ensure_reference_data(db, org_id, session.sanitized_filename)

        await db.commit()

        # Storage Compensation: If deduplicated, delete duplicate temp file after commit
        if is_deduplicated:
            await adapter.delete_object(str(org_id), session.temporary_object_key)

    except Exception:
        await db.rollback()
        # Compensation: If new (non-deduplicated) file creation failed on DB, clean up storage object
        if not is_deduplicated and session.temporary_object_key:
            try:
                await adapter.delete_object(str(org_id), session.temporary_object_key)
            except Exception:  # noqa: S110, BLE001
                pass
        raise

    return UploadFinalizeResponse(
        document_id=document.id,
        document_version_id=doc_version.id,
        ingestion_job_id=job.id,
        stored_object_id=stored_object.id,
        version_number=doc_version.version_number,
        content_hash_sha256=recalculated_hash,
        ingestion_status="QUEUED",
        is_deduplicated=is_deduplicated,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    ctx: Annotated[ExecutionContext, Depends(require_permission("documents:read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    org_id = ctx.active_organization_id

    res = await db.execute(
        select(Document)
        .where(
            Document.organization_id == org_id,
            Document.status == "ACTIVE",
        )
        .order_by(Document.created_at.desc())
    )
    documents = res.scalars().all()

    result = []
    for doc in documents:
        ver_res = await db.execute(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.organization_id == org_id,
            )
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        latest_ver = ver_res.scalar_one_or_none()
        ver_schema = None
        if latest_ver:
            ver_schema = DocumentVersionResponse(
                id=latest_ver.id,
                version_number=latest_ver.version_number,
                content_hash_sha256=latest_ver.content_hash_sha256,
                file_size_bytes=latest_ver.file_size_bytes,
                declared_mime_type=latest_ver.declared_mime_type,
                detected_mime_type=latest_ver.detected_mime_type,
                ingestion_status=latest_ver.ingestion_status,
                extraction_status=latest_ver.extraction_status,
                created_at=latest_ver.created_at,
            )

        result.append(
            DocumentResponse(
                id=doc.id,
                organization_id=doc.organization_id,
                uploaded_by_user_id=doc.uploaded_by_user_id,
                display_name=doc.display_name,
                document_type=doc.document_type,
                classification=doc.classification,
                status=doc.status,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                latest_version=ver_schema,
            )
        )
    return result


@router.get("/{document_id}/versions/{version_id}/status", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    document_id: UUID,
    version_id: UUID,
    ctx: Annotated[ExecutionContext, Depends(require_permission("ingestion:read"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    org_id = ctx.active_organization_id

    # Document-Version-Organization Exact Relationship Verification
    ver_res = await db.execute(
        select(DocumentVersion)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(
            Document.id == document_id,
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
            Document.organization_id == org_id,
            DocumentVersion.organization_id == org_id,
            Document.status == "ACTIVE",
        )
    )
    ver = ver_res.scalar_one_or_none()
    if not ver:
        raise HTTPException(
            status_code=404,
            detail="Document version not found or does not belong to specified document and organization.",
        )

    res_result = await db.execute(
        select(ExtractionResult).where(
            ExtractionResult.document_version_id == version_id,
            ExtractionResult.organization_id == org_id,
        )
    )
    ext_result = res_result.scalar_one_or_none()

    warnings_list = []
    if ext_result:
        warn_res = await db.execute(
            select(ExtractionWarning).where(
                ExtractionWarning.extraction_result_id == ext_result.id,
                ExtractionWarning.organization_id == org_id,
            )
        )
        warns = warn_res.scalars().all()
        for w in warns:
            warnings_list.append(
                WarningResponse(
                    warning_code=w.warning_code,
                    warning_message=w.warning_message,
                    lineage_ref=w.lineage_ref,
                )
            )

    return IngestionStatusResponse(
        document_id=ver.document_id,
        document_version_id=ver.id,
        ingestion_status=ver.ingestion_status,
        extraction_status=ver.extraction_status,
        warnings=warnings_list,
    )
