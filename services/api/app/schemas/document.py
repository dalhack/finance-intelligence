from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class UploadInitiateRequest(BaseModel):
    display_name: str = Field(..., max_length=255)
    declared_mime_type: str = Field(..., max_length=100)
    expected_size_bytes: int = Field(..., gt=0)
    classification: str = Field(default="CONFIDENTIAL", max_length=50)


class UploadInitiateResponse(BaseModel):
    session_id: UUID
    organization_id: UUID
    status: str
    expires_at: datetime


class UploadFinalizeResponse(BaseModel):
    document_id: UUID
    document_version_id: UUID
    ingestion_job_id: UUID | None = None
    stored_object_id: UUID | None = None
    version_number: int
    content_hash_sha256: str
    ingestion_status: str
    is_deduplicated: bool


class DocumentVersionResponse(BaseModel):
    id: UUID
    version_number: int
    content_hash_sha256: str
    file_size_bytes: int
    declared_mime_type: str
    detected_mime_type: str
    ingestion_status: str
    extraction_status: str
    created_at: datetime


class DocumentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    uploaded_by_user_id: UUID
    display_name: str
    document_type: str
    classification: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: DocumentVersionResponse | None = None


class WarningResponse(BaseModel):
    warning_code: str
    warning_message: str
    lineage_ref: dict[str, Any]


class IngestionStatusResponse(BaseModel):
    document_id: UUID
    document_version_id: UUID
    ingestion_status: str
    extraction_status: str
    warnings: list[WarningResponse] = []
