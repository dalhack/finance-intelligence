from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorDetail(BaseDTO):
    field: str | None = None
    issue: str


class ErrorContent(BaseDTO):
    code: str
    message: str
    request_id: str = Field(alias="requestId")
    retryable: bool = False
    details: list[ErrorDetail] | dict[str, Any] = Field(default_factory=list)


class ErrorEnvelopeDTO(BaseDTO):
    error: ErrorContent


class HealthResponseDTO(BaseDTO):
    status: str = Field(pattern="^(pass|fail)$")
    timestamp: str


class VersionResponseDTO(BaseDTO):
    version: str
    environment: str
    api_baseline: str


class UserSummaryDTO(BaseDTO):
    user_id: UUID
    identity_provider: str
    display_name: str
    status: str


class OrganizationSummaryDTO(BaseDTO):
    organization_id: UUID
    name: str
    slug: str
    role: str
    status: str


class ExecutionContextSummaryDTO(BaseDTO):
    user_id: UUID
    active_organization_id: UUID
    roles: list[str]
    request_id: str
    environment: str
