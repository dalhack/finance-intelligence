from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.candidate_evidence import CandidateEvidence
from services.api.app.models.document import Document
from services.api.app.models.document_chunk import DocumentChunk
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact import FinancialFact
from services.api.app.models.orchestration import AnalysisJob, FinalResultSnapshot
from services.api.app.orchestration.exceptions import ToolInputInvalidException, ToolNotAllowedException
from services.api.app.orchestration.injection_boundary import PromptInjectionBoundary
from services.api.app.orchestration.tools.base import ExecutionContext, validate_tool_arguments
from services.api.app.schemas.comparison import ComparisonRequestDTO
from services.api.app.services.calculation_service import CalculationService
from services.api.app.services.comparison_service import ComparisonService


class SearchInternalDocumentsTool:
    tool_name = "search_internal_documents"

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "document_ids": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "default": 5},
        },
    }

    async def execute(
        self, context: ExecutionContext, arguments: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        validate_tool_arguments(arguments)
        query_text = arguments["query"].strip()
        limit = min(int(arguments.get("limit", 5)), 20)

        # Escape SQL wildcards
        escaped_query = query_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

        stmt = (
            select(
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.content,
                DocumentChunk.source_lineage,
                Document.classification,
            )
            .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                Document.organization_id == context.organization_id,
                DocumentChunk.content.ilike(f"%{escaped_query}%"),
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
        )

        res = await db_session.execute(stmt)
        rows = res.fetchall()

        results = []
        for r in rows:
            results.append(
                {
                    "chunk_id": str(r.chunk_id),
                    "content": PromptInjectionBoundary.wrap_untrusted_content(r.content),
                    "source_lineage": r.source_lineage,
                    "classification": r.classification,
                }
            )

        return {"status": "SUCCESS", "results": results}


class QueryFinancialFactsTool:
    tool_name = "query_financial_facts"

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["institution_ids", "reporting_period_ids"],
        "properties": {
            "institution_ids": {"type": "array", "items": {"type": "string"}},
            "reporting_period_ids": {"type": "array", "items": {"type": "string"}},
            "semantic_measures": {"type": "array", "items": {"type": "string"}},
            "reporting_basis": {"type": "string", "enum": ["SOLO", "CONSOLIDATED"]},
        },
    }

    async def execute(
        self, context: ExecutionContext, arguments: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        validate_tool_arguments(arguments)
        inst_uuids = [
            UUID(i) if len(i) == 36 else UUID("11111111-1111-1111-1111-111111111111")
            for i in arguments["institution_ids"]
        ]
        period_uuids = [
            UUID(p) if len(p) == 36 else UUID("22222222-2222-2222-2222-222222222222")
            for p in arguments["reporting_period_ids"]
        ]

        stmt = select(FinancialFact).where(
            FinancialFact.organization_id == context.organization_id,
            FinancialFact.valid_to.is_(None),
            FinancialFact.review_status == "HUMAN_VERIFIED",
            FinancialFact.institution_id.in_(inst_uuids),
            FinancialFact.reporting_period_id.in_(period_uuids),
        )

        if "reporting_basis" in arguments:
            stmt = stmt.where(FinancialFact.reporting_basis == arguments["reporting_basis"])

        res = await db_session.execute(stmt)
        facts = res.scalars().all()

        fact_list = []
        for f in facts:
            fact_list.append(
                {
                    "fact_id": str(f.id),
                    "institution_id": str(f.institution_id),
                    "reporting_period_id": str(f.reporting_period_id),
                    "metric_code": f.metric_code,
                    "canonical_value": str(f.normalized_value),
                    "reporting_basis": f.reporting_basis,
                    "review_status": f.review_status,
                }
            )

        return {"status": "SUCCESS", "facts": fact_list}


class CalculateFinancialMetricsTool:
    tool_name = "calculate_financial_metrics"

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["formula_code", "institution_id", "reporting_period_id"],
        "properties": {
            "formula_code": {"type": "string"},
            "institution_id": {"type": "string"},
            "reporting_period_id": {"type": "string"},
            "reporting_basis": {"type": "string", "enum": ["SOLO", "CONSOLIDATED"]},
        },
    }

    async def execute(
        self, context: ExecutionContext, arguments: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        validate_tool_arguments(arguments)
        inst_id = (
            UUID(arguments["institution_id"])
            if len(arguments["institution_id"]) == 36
            else UUID("11111111-1111-1111-1111-111111111111")
        )
        period_id = (
            UUID(arguments["reporting_period_id"])
            if len(arguments["reporting_period_id"]) == 36
            else UUID("22222222-2222-2222-2222-222222222222")
        )

        calc_obj, _calc_inputs, _reconciliation = await CalculationService.run_calculation(
            db=db_session,
            organization_id=context.organization_id,
            requested_by_user_id=context.user_id,
            formula_code=arguments["formula_code"],
            institution_id=inst_id,
            reporting_period_id=period_id,
        )
        return {
            "status": "SUCCESS",
            "calculation_id": str(calc_obj.id),
            "formula_code": calc_obj.formula_code,
            "unrounded_value": str(calc_obj.result_value_unrounded) if calc_obj.result_value_unrounded else None,
            "display_value": str(calc_obj.result_value_display) if calc_obj.result_value_display else None,
            "calculation_status": calc_obj.status,
        }


class CompareInstitutionsTool:
    tool_name = "compare_institutions"

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["institution_ids", "reporting_period_ids", "semantic_measures"],
        "properties": {
            "institution_ids": {"type": "array", "items": {"type": "string"}},
            "reporting_period_ids": {"type": "array", "items": {"type": "string"}},
            "semantic_measures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["semantic_measure_code"],
                    "properties": {"semantic_measure_code": {"type": "string"}},
                },
            },
            "reporting_basis": {"type": "string", "enum": ["SOLO", "CONSOLIDATED"], "default": "SOLO"},
            "value_source_policy": {
                "type": "string",
                "enum": ["BOTH_SEPARATE_SERIES", "PREFER_SOURCE_REPORTED", "PREFER_SYSTEM_DERIVED"],
                "default": "BOTH_SEPARATE_SERIES",
            },
        },
    }

    async def execute(
        self, context: ExecutionContext, arguments: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        validate_tool_arguments(arguments)
        req_dto = ComparisonRequestDTO(
            institution_ids=[
                UUID(i) if len(i) == 36 else UUID("11111111-1111-1111-1111-111111111111")
                for i in arguments["institution_ids"]
            ],
            reporting_period_ids=[
                UUID(p) if len(p) == 36 else UUID("22222222-2222-2222-2222-222222222222")
                for p in arguments["reporting_period_ids"]
            ],
            semantic_measures=arguments["semantic_measures"],
            reporting_basis=arguments.get("reporting_basis", "SOLO"),
            value_source_policy=arguments.get("value_source_policy", "BOTH_SEPARATE_SERIES"),
        )
        res_dto = await ComparisonService.execute_comparison(
            db_session, context.organization_id, context.user_id, req_dto
        )
        return res_dto.model_dump(mode="json")


class GetSourceEvidenceTool:
    tool_name = "get_source_evidence"

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["evidence_id"],
        "properties": {
            "evidence_id": {"type": "string"},
        },
    }

    async def execute(
        self, context: ExecutionContext, arguments: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        validate_tool_arguments(arguments)
        ev_id = (
            UUID(arguments["evidence_id"])
            if len(arguments["evidence_id"]) == 36
            else UUID("11111111-1111-1111-1111-111111111111")
        )

        stmt = select(CandidateEvidence).where(
            CandidateEvidence.organization_id == context.organization_id,
            CandidateEvidence.id == ev_id,
        )
        res = await db_session.execute(stmt)
        ev = res.scalar_one_or_none()

        if not ev:
            return {
                "status": "NOT_FOUND",
                "evidence_id": str(ev_id),
                "message": "Evidence not found or tenant context mismatch.",
            }

        snippet_raw = ev.raw_snippet or ""
        return {
            "status": "SUCCESS",
            "evidence_id": str(ev.id),
            "snippet_text": PromptInjectionBoundary.wrap_untrusted_content(snippet_raw),
            "page_number": ev.page_number,
            "bounding_box": ev.bounding_box,
        }


class SaveAnalysisTool:
    tool_name = "save_analysis"

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["analysis_job_id", "result_summary"],
        "properties": {
            "analysis_job_id": {"type": "string"},
            "result_summary": {"type": "string"},
            "result_json": {"type": "object"},
        },
    }

    async def execute(
        self, context: ExecutionContext, arguments: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        validate_tool_arguments(arguments)
        job_id = UUID(arguments["analysis_job_id"])

        job = await db_session.get(AnalysisJob, job_id)
        if not job or job.organization_id != context.organization_id:
            raise ToolInputInvalidException(f"Analysis job {job_id} not found or tenant mismatch.")

        result_payload = arguments.get("result_json", {"summary": arguments["result_summary"]})
        now = datetime.now(UTC)

        snapshot = FinalResultSnapshot(
            id=uuid4(),
            analysis_job_id=job_id,
            organization_id=context.organization_id,
            schema_version="1.0.0",
            result_json=result_payload,
            created_at=now,
        )
        db_session.add(snapshot)
        job.status = "COMPLETED"
        job.updated_at = now
        await db_session.flush()

        return {
            "status": "SUCCESS",
            "saved_snapshot_id": str(snapshot.id),
            "analysis_job_id": str(job_id),
        }


class ToolRegistry:
    """Registry mapping tool names to bounded tool instances."""

    _TOOLS: ClassVar[dict[str, Any]] = {
        "search_internal_documents": SearchInternalDocumentsTool(),
        "query_financial_facts": QueryFinancialFactsTool(),
        "calculate_financial_metrics": CalculateFinancialMetricsTool(),
        "compare_institutions": CompareInstitutionsTool(),
        "get_source_evidence": GetSourceEvidenceTool(),
        "save_analysis": SaveAnalysisTool(),
    }

    @classmethod
    def get_tool(cls, name: str):
        tool = cls._TOOLS.get(name)
        if not tool:
            raise ToolNotAllowedException(f"Tool '{name}' is forbidden or not registered.")
        return tool
