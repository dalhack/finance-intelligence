from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalculationRunDTO(BaseModel):
    formula_code: str = Field(..., max_length=100)
    institution_id: UUID
    reporting_period_id: UUID
    comparison_period_id: UUID | None = None
    comparison_policy: str = Field("PREVIOUS_PERIOD", max_length=50)
    explicit_fact_ids: dict[str, UUID] | None = None


class CalculationInputResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    calculation_id: UUID
    financial_fact_id: UUID
    input_role: str
    normalized_value_snapshot: Decimal
    currency_snapshot: str
    unit_snapshot: str
    scale_snapshot: str
    reporting_basis_snapshot: str


class CalculationReconciliationResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    calculation_id: UUID
    source_reported_fact_id: UUID | None
    source_reported_value: Decimal | None
    system_derived_value: Decimal
    derived_unrounded_value: Decimal | None = None
    difference: Decimal | None
    tolerance: Decimal
    reconciliation_status: str
    reconciled_at: datetime


class CalculationResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    institution_id: UUID
    reporting_period_id: UUID
    comparison_period_id: UUID | None
    formula_code: str
    formula_version: str
    status: str
    result_value: Decimal | None = None  # @deprecated -> result_value_display
    result_value_unrounded: Decimal | None = None
    result_value_display: Decimal | None = None
    result_unit: str
    result_scale: str
    result_currency: str | None = None
    value_representation: str
    idempotency_hash: str
    error_code: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class FormulaDefinitionResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    formula_code: str
    formula_version: str
    display_name: str
    description: str | None = None
    calculation_type: str
    required_input_roles: list[Any]
    expected_metric_codes: list[Any]
    result_unit: str
    result_scale: str
    rounding_policy: str
    display_precision: int
    tolerance_kind: str = "ABSOLUTE"
    tolerance_value: Decimal = Decimal("0.05")
    tolerance_unit: str = "PERCENTAGE_POINTS"
