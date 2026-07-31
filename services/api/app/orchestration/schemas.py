from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.api.app.orchestration.exceptions import AnalysisPlanInvalidException

FORBIDDEN_KEYWORD_PATTERNS = {
    "organization_id",
    "tenant_id",
    "user_id",
    "role",
    "permission",
    "sql",
    "shell",
    "python",
    "file_path",
    "secret",
    "api_key",
}


class NormalizedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "SINGLE_PERIOD_ANALYSIS",
        "MULTI_PERIOD_TREND",
        "CROSS_INSTITUTION_COMPARISON",
        "RATIO_CALCULATION",
    ]
    requested_institutions: list[str] = Field(default_factory=list)
    requested_periods: list[str] = Field(default_factory=list)
    requested_semantic_measures: list[str] = Field(default_factory=list)
    reporting_basis: Literal["SOLO", "CONSOLIDATED"] = "SOLO"
    source_policy: Literal[
        "BOTH_SEPARATE_SERIES",
        "PREFER_SOURCE_REPORTED",
        "PREFER_SYSTEM_DERIVED",
    ] = "BOTH_SEPARATE_SERIES"
    requested_chart_type: Literal["vertical_bar", "horizontal_bar", "grouped_bar", "line", "stacked_bar", "pie"] = (
        "vertical_bar"
    )
    ambiguities: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    proposed_clarification_questions: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(ge=1)
    tool_name: Literal[
        "search_internal_documents",
        "query_financial_facts",
        "calculate_financial_metrics",
        "compare_institutions",
        "get_source_evidence",
        "save_analysis",
    ]
    tool_arguments: dict[str, Any]

    @model_validator(mode="after")
    def validate_no_forbidden_arguments(self) -> "PlanStep":
        args = self.tool_arguments
        for key in args:
            if key.lower() in FORBIDDEN_KEYWORD_PATTERNS:
                raise AnalysisPlanInvalidException(f"Forbidden keyword argument '{key}' is prohibited in tool step.")
        return self


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_version: Literal["1.0.0"] = "1.0.0"
    analysis_job_id: UUID
    ordered_steps: list[PlanStep]
    max_tool_steps: int = Field(default=5, le=10)
    estimated_max_cost_usd: str = "0.0500"
