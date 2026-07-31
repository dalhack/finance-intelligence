from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

FORBIDDEN_PAYLOAD_KEYS = {
    "organization_id",
    "tenant_id",
    "user_id",
    "role",
    "permission",
    "provider",
    "model_id",
    "api_key",
    "prompt_template",
    "tool",
    "tool_plan",
    "sql",
    "shell",
    "python",
    "system_prompt",
}


class ClarificationCode(str, Enum):
    INSTITUTION_REQUIRED = "INSTITUTION_REQUIRED"
    REPORTING_PERIOD_REQUIRED = "REPORTING_PERIOD_REQUIRED"
    REPORTING_BASIS_REQUIRED = "REPORTING_BASIS_REQUIRED"
    MEASURE_REQUIRED = "MEASURE_REQUIRED"
    DOCUMENT_SCOPE_REQUIRED = "DOCUMENT_SCOPE_REQUIRED"
    COMPARISON_SCOPE_AMBIGUOUS = "COMPARISON_SCOPE_AMBIGUOUS"
    UNSUPPORTED_REQUEST_SCOPE = "UNSUPPORTED_REQUEST_SCOPE"


class ClarificationResponseBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def check_forbidden_keys(cls, value: Any) -> Any:
        return value


def sanitize_and_check_keys(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise TypeError("Response payload must be a JSON object.")

    for key in payload:
        if key.lower() in FORBIDDEN_PAYLOAD_KEYS:
            raise ValueError(f"Forbidden security parameter in clarification response: '{key}'.")


class InstitutionSelectionPayload(ClarificationResponseBase):
    institution_id: UUID


class PeriodSelectionPayload(ClarificationResponseBase):
    period_id: UUID


class BasisSelectionPayload(ClarificationResponseBase):
    reporting_basis: str = Field(pattern="^(SOLO|CONSOLIDATED)$")


class MeasureSelectionPayload(ClarificationResponseBase):
    metric_code: str = Field(min_length=2, max_length=100)


class DocumentScopeSelectionPayload(ClarificationResponseBase):
    document_id: UUID


class ComparisonScopeSelectionPayload(ClarificationResponseBase):
    institution_ids: list[UUID] = Field(min_length=2, max_length=5)


class AcknowledgeScopePayload(ClarificationResponseBase):
    acknowledged: bool = True


CLARIFICATION_SCHEMAS: dict[ClarificationCode, type[BaseModel]] = {
    ClarificationCode.INSTITUTION_REQUIRED: InstitutionSelectionPayload,
    ClarificationCode.REPORTING_PERIOD_REQUIRED: PeriodSelectionPayload,
    ClarificationCode.REPORTING_BASIS_REQUIRED: BasisSelectionPayload,
    ClarificationCode.MEASURE_REQUIRED: MeasureSelectionPayload,
    ClarificationCode.DOCUMENT_SCOPE_REQUIRED: DocumentScopeSelectionPayload,
    ClarificationCode.COMPARISON_SCOPE_AMBIGUOUS: ComparisonScopeSelectionPayload,
    ClarificationCode.UNSUPPORTED_REQUEST_SCOPE: AcknowledgeScopePayload,
}


def validate_clarification_response(code: str, payload: dict[str, Any]) -> dict[str, Any]:
    sanitize_and_check_keys(payload)

    try:
        enum_code = ClarificationCode(code)
    except ValueError:
        raise ValueError(f"Invalid clarification code: '{code}'.")

    schema_cls = CLARIFICATION_SCHEMAS.get(enum_code)
    if not schema_cls:
        raise ValueError(f"No schema validator found for clarification code: '{code}'.")

    validated_obj = schema_cls.model_validate(payload)
    return validated_obj.model_dump(mode="json")


class ClarificationRespondRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clarification_id: UUID
    idempotency_key: str = Field(min_length=3, max_length=255)
    response_payload: dict[str, Any]


class ClarificationCancelRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clarification_id: UUID
    idempotency_key: str = Field(min_length=3, max_length=255)
    reason_code: str = Field(default="USER_CANCELLED", max_length=100)


class AnalysisClarificationDTO(BaseModel):
    id: UUID
    analysis_job_id: UUID
    organization_id: UUID
    clarification_code: str
    prompt_key: str
    question: str
    allowed_response_schema: dict[str, Any]
    status: str
    requested_at: str
    expires_at: str | None = None
    answered_at: str | None = None
