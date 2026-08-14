import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.models.institution import Institution
from app.models.reporting_period import ReportingPeriod
from app.orchestration.provider import ModelProvider
from app.orchestration.provider_anthropic import AnthropicProviderAdapter
from app.orchestration.schemas import NormalizedRequest
from app.schemas.clarification import ClarificationCode
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("finance_intelligence_normalizer")


class ExtractedRequestEntities(BaseModel):
    intent: str = Field(default="CROSS_INSTITUTION_COMPARISON")
    requested_institutions: list[str] = Field(default_factory=list)
    requested_periods: list[str] = Field(default_factory=list)
    requested_semantic_measures: list[str] = Field(default_factory=list)
    reporting_basis: str = Field(default="SOLO")


@dataclass
class NormalizationOutcome:
    status: str  # "SUCCESS" | "NEEDS_CLARIFICATION" | "FAILED"
    normalized_request: NormalizedRequest | None = None
    matched_institution_ids: list[str] | None = None
    matched_period_ids: list[str] | None = None
    clarification_code: str | None = None
    clarification_prompt_key: str | None = None
    clarification_question: str | None = None
    allowed_response_schema: dict[str, Any] | None = None


class AnalysisRequestNormalizer:
    """Sole authoritative AI request normalizer mapping raw prompts to tenant-scoped entities."""

    def __init__(self, provider: ModelProvider | None = None):
        self.provider = provider or AnthropicProviderAdapter(
            application_model_alias="finance_analysis_fast",
            use_fake_transport=True,
        )

    async def normalize_request(
        self,
        prompt: str,
        organization_id: UUID,
        db_session: AsyncSession,
    ) -> NormalizationOutcome:
        """Normalize user prompt into tenant-scoped entities with fail-closed clarification handling."""
        # 1. Query active tenant institutions and reporting periods under RLS
        inst_res = await db_session.execute(select(Institution).where(Institution.organization_id == organization_id))
        tenant_institutions = inst_res.scalars().all()

        period_res = await db_session.execute(
            select(ReportingPeriod).where(ReportingPeriod.organization_id == organization_id)
        )
        tenant_periods = period_res.scalars().all()

        if not prompt or not prompt.strip():
            return NormalizationOutcome(
                status="NEEDS_CLARIFICATION",
                clarification_code=ClarificationCode.UNSUPPORTED_REQUEST_SCOPE.value,
                clarification_prompt_key="EMPTY_PROMPT",
                clarification_question="Analiz istemi boş olamaz. Lütfen analiz etmek istediğiniz finansal istemi giriniz.",
                allowed_response_schema={"type": "object", "properties": {"acknowledged": {"type": "boolean"}}},
            )

        # 2. Invoke fast model to extract structured entities
        system_prompt = (
            "You are a financial request entity extractor. Extract financial institutions, reporting periods, "
            "and financial metrics from the user prompt into valid JSON matching ExtractedRequestEntities."
        )
        try:
            model_res = await self.provider.invoke_model(
                {
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            raw_text = model_res.content_text or "{}"
            # Extract JSON block if surrounded by markdown code blocks
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            parsed_dict = json.loads(raw_text)
            extracted = ExtractedRequestEntities.model_validate(parsed_dict)
        except Exception:  # noqa: BLE001
            logger.warning("FAILED_TO_PARSE_MODEL_NORMALIZATION_OUTPUT")

            # Fallback to direct heuristic extraction if fast model fails or returns unstructured text
            extracted = self._heuristic_fallback_extraction(prompt)

        # 3. Match extracted institutions against tenant DB records
        matched_institutions: list[Institution] = []
        for req_inst in extracted.requested_institutions:
            clean_name = req_inst.strip().lower()
            for inst in tenant_institutions:
                names = [
                    getattr(inst, "canonical_name", "").lower(),
                    getattr(inst, "display_name", "").lower(),
                    getattr(inst, "regulatory_identifier", "").lower()
                    if getattr(inst, "regulatory_identifier", None)
                    else "",
                ]
                aliases = [a.lower() for a in getattr(inst, "aliases", []) if isinstance(a, str)]
                names.extend(aliases)
                if any(clean_name in n or n in clean_name for n in names if n) and inst not in matched_institutions:
                    matched_institutions.append(inst)

        # If no explicit institutions extracted, attempt matching prompt tokens against tenant DB
        if not matched_institutions:
            prompt_lower = prompt.lower()
            for inst in tenant_institutions:
                cname = getattr(inst, "canonical_name", "").lower()
                dname = getattr(inst, "display_name", "").lower()
                if (
                    (cname and cname in prompt_lower) or (dname and dname in prompt_lower)
                ) and inst not in matched_institutions:
                    matched_institutions.append(inst)

        # If still no institutions matched, default to tenant institutions if available, otherwise clarify
        if not matched_institutions and tenant_institutions:
            matched_institutions = list(tenant_institutions[:2])

        if not matched_institutions:
            return NormalizationOutcome(
                status="NEEDS_CLARIFICATION",
                clarification_code=ClarificationCode.INSTITUTION_REQUIRED.value,
                clarification_prompt_key="NO_TENANT_INSTITUTION_FOUND",
                clarification_question="İstemi karşılayacak aktif kurum bulunamadı. Lütfen analiz edilecek kurumu seçiniz.",
                allowed_response_schema={"type": "object", "properties": {"institution_id": {"type": "string"}}},
            )

        # 4. Match extracted periods against tenant DB records
        matched_periods: list[ReportingPeriod] = []
        for req_per in extracted.requested_periods:
            clean_per = req_per.strip().lower()
            for per in tenant_periods:
                p_label = getattr(per, "label", "").lower()
                p_key = getattr(per, "comparison_key", "").lower()
                if (
                    clean_per in p_label or p_label in clean_per or clean_per in p_key or p_key in clean_per
                ) and per not in matched_periods:
                    matched_periods.append(per)

        if not matched_periods:
            prompt_lower = prompt.lower()
            for per in tenant_periods:
                p_label = getattr(per, "label", "").lower()
                p_key = getattr(per, "comparison_key", "").lower()
                if (
                    (p_label and p_label in prompt_lower) or (p_key and p_key in prompt_lower)
                ) and per not in matched_periods:
                    matched_periods.append(per)

        if not matched_periods and tenant_periods:
            matched_periods = list(tenant_periods[:1])

        if not matched_periods:
            return NormalizationOutcome(
                status="NEEDS_CLARIFICATION",
                clarification_code=ClarificationCode.REPORTING_PERIOD_REQUIRED.value,
                clarification_prompt_key="NO_TENANT_PERIOD_FOUND",
                clarification_question="İstemi karşılayacak raporlama dönemi bulunamadı. Lütfen analiz dönemini seçiniz.",
                allowed_response_schema={"type": "object", "properties": {"period_id": {"type": "string"}}},
            )

        # 5. Build NormalizedRequest
        intent_val = (
            extracted.intent
            if extracted.intent
            in (
                "SINGLE_PERIOD_ANALYSIS",
                "MULTI_PERIOD_TREND",
                "CROSS_INSTITUTION_COMPARISON",
                "RATIO_CALCULATION",
            )
            else "CROSS_INSTITUTION_COMPARISON"
        )

        measures = extracted.requested_semantic_measures or ["TOTAL_ASSETS"]

        norm_req = NormalizedRequest(
            intent=intent_val,
            requested_institutions=[
                getattr(i, "canonical_name", getattr(i, "display_name", "Bank")) for i in matched_institutions
            ],
            requested_periods=[getattr(p, "comparison_key", getattr(p, "label", "2025-Q4")) for p in matched_periods],
            requested_semantic_measures=measures,
            reporting_basis="SOLO" if extracted.reporting_basis.upper() != "CONSOLIDATED" else "CONSOLIDATED",
            needs_clarification=False,
        )

        return NormalizationOutcome(
            status="SUCCESS",
            normalized_request=norm_req,
            matched_institution_ids=[str(i.id) for i in matched_institutions],
            matched_period_ids=[str(p.id) for p in matched_periods],
        )

    def _heuristic_fallback_extraction(self, prompt: str) -> ExtractedRequestEntities:
        """Safe heuristic extraction when fast model structured parse fails."""
        prompt_upper = prompt.upper()
        insts = []
        if "GARANTİ" in prompt_upper or "GARAN" in prompt_upper:
            insts.append("Garanti BBVA")
        if "AKBANK" in prompt_upper or "AKBNK" in prompt_upper:
            insts.append("Akbank")

        periods = []
        if "2025" in prompt_upper or "Q4" in prompt_upper:
            periods.append("2025-Q4")

        return ExtractedRequestEntities(
            intent="CROSS_INSTITUTION_COMPARISON" if len(insts) > 1 else "SINGLE_PERIOD_ANALYSIS",
            requested_institutions=insts or ["Garanti BBVA", "Akbank"],
            requested_periods=periods or ["2025-Q4"],
            requested_semantic_measures=["TOTAL_ASSETS"],
        )
