import hashlib
import json
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.candidate_evidence import CandidateEvidence
from services.api.app.models.financial_fact_candidate import FinancialFactCandidate
from services.api.app.models.metric_alias import MetricAlias
from services.api.app.models.metric_definition import MetricDefinition
from services.api.app.services.audit_service import AuditService
from services.api.app.services.normalization_service import NormalizationService


class FactCandidateService:
    @staticmethod
    async def match_metric_alias(db: AsyncSession, organization_id: UUID, raw_label: str) -> MetricDefinition | None:
        """Match raw label against canonical metric definitions and tenant metric aliases."""
        cleaned_label = raw_label.strip().lower()

        # 1. Search tenant metric aliases
        alias_res = await db.execute(
            select(MetricAlias).where(
                MetricAlias.organization_id == organization_id,
                MetricAlias.alias_pattern.ilike(cleaned_label),
            )
        )
        alias = alias_res.scalar_one_or_none()
        if alias:
            metric_res = await db.execute(
                select(MetricDefinition).where(MetricDefinition.id == alias.metric_definition_id)
            )
            return metric_res.scalar_one_or_none()

        # 2. Search canonical metric definitions by code or canonical name
        def_res = await db.execute(
            select(MetricDefinition).where(
                (MetricDefinition.metric_code.ilike(cleaned_label))
                | (MetricDefinition.canonical_name.ilike(cleaned_label))
            )
        )
        return def_res.scalar_one_or_none()

    @staticmethod
    async def create_candidate(
        db: AsyncSession,
        organization_id: UUID,
        institution_id: UUID,
        reporting_period_id: UUID,
        raw_label: str,
        raw_value: str,
        source_document_id: UUID,
        source_document_version_id: UUID,
        raw_currency: str = "TRY",
        raw_unit: str = "CURRENCY",
        raw_scale: str = "ONE",
        detected_reporting_basis: str = "UNKNOWN",
        source_page_id: UUID | None = None,
        source_chunk_id: UUID | None = None,
        source_location: dict[str, Any] | None = None,
        extraction_method: str = "PARSER_TABLE",
        evidence_snippet: str | None = None,
    ) -> FinancialFactCandidate:
        """Extract and normalize candidate cell without automatically creating verified facts."""
        warning_codes: list[str] = []

        # 1. Compute Idempotency Hash
        loc_str = json.dumps(source_location or {}, sort_keys=True)
        idempotency_raw = (
            f"{organization_id}:{source_document_version_id}:{raw_label.strip()}:{raw_value.strip()}:{loc_str}"
        )
        idempotency_hash = hashlib.sha256(idempotency_raw.encode()).hexdigest()

        # Check existing candidate by idempotency_hash
        existing_cand_res = await db.execute(
            select(FinancialFactCandidate).where(
                FinancialFactCandidate.organization_id == organization_id,
                FinancialFactCandidate.idempotency_hash == idempotency_hash,
            )
        )
        existing_cand = existing_cand_res.scalar_one_or_none()
        if existing_cand:
            return existing_cand

        # 2. Metric Matching
        metric_def = await FactCandidateService.match_metric_alias(db, organization_id, raw_label)
        suggested_code = metric_def.metric_code if metric_def else None

        # 3. Number Normalization
        parse_res = NormalizationService.parse_financial_decimal(raw_value)
        parsed_val = parse_res.value
        warning_codes.extend(parse_res.warning_codes)

        # 4. Scale & Unit Normalization
        normalized_val = None
        if parsed_val is not None:
            normalized_val = NormalizationService.normalize_scale(parsed_val, raw_scale)
            if parse_res.is_percentage:
                raw_unit = "PERCENT"

        # 5. Confidence & Validation Status Calculation
        confidence = Decimal("0.500")
        if metric_def and parsed_val is not None:
            confidence = Decimal("0.850") if not warning_codes else Decimal("0.650")
        elif not metric_def:
            warning_codes.append("UNMATCHED_METRIC_ALIAS")

        if detected_reporting_basis == "UNKNOWN":
            warning_codes.append("UNKNOWN_REPORTING_BASIS")

        validation_status = "NORMALIZED" if (parsed_val is not None and metric_def) else "NEEDS_REVIEW"
        if warning_codes:
            validation_status = "NEEDS_REVIEW"

        # ALL candidates require human review
        review_status = "PENDING"

        candidate = FinancialFactCandidate(
            organization_id=organization_id,
            institution_id=institution_id,
            reporting_period_id=reporting_period_id,
            metric_definition_id=metric_def.id if metric_def else None,
            suggested_metric_code=suggested_code,
            raw_label=raw_label,
            raw_value=raw_value,
            parsed_decimal_value=parsed_val,
            raw_currency=raw_currency,
            raw_unit=raw_unit,
            raw_scale=raw_scale,
            normalized_currency=raw_currency,
            normalized_unit=raw_unit,
            normalized_scale=raw_scale,
            normalized_value=normalized_val,
            detected_reporting_basis=detected_reporting_basis,
            source_document_id=source_document_id,
            source_document_version_id=source_document_version_id,
            source_page_id=source_page_id,
            source_chunk_id=source_chunk_id,
            source_location=source_location or {},
            extraction_method=extraction_method,
            confidence_score=confidence,
            validation_status=validation_status,
            review_status=review_status,
            warning_codes=warning_codes,
            idempotency_hash=idempotency_hash,
            value_origin="SOURCE_REPORTED",
        )
        from sqlalchemy.exc import IntegrityError

        try:
            async with db.begin_nested():
                db.add(candidate)
                await db.flush()

                # Add candidate evidence (must contain real snippet or location lineage)
                snip = evidence_snippet or f"Table Cell: {raw_label} = {raw_value}"
                ev_col = None
                if source_location and isinstance(source_location, dict):
                    if "col_index" in source_location or "columnIndex" in source_location:
                        raise ValueError("LEGACY_LINEAGE_FIELD_REJECTED")
                    ev_col = source_location.get("column_index")
                    bbox = source_location.get("bounding_box")
                    if (
                        not bbox
                        and isinstance(source_location, dict)
                        and all(k in source_location for k in ("x0", "y0", "x1", "y1"))
                    ):
                        bbox = source_location
                    elif not bbox:
                        bbox = {}

                    evidence = CandidateEvidence(
                        id=uuid4(),
                        organization_id=candidate.organization_id,
                        candidate_id=candidate.id,
                        source_document_version_id=candidate.source_document_version_id,
                        page_number=source_location.get("page_number") or source_location.get("page") or 1,
                        sheet_name=source_location.get("sheet_name"),
                        cell_coordinate=source_location.get("cell_coordinate"),
                        header_name=source_location.get("header_name"),
                        row_index=source_location.get("row_index"),
                        column_index=ev_col,
                        bounding_box=bbox,
                        raw_snippet=snip,
                    )
                    db.add(evidence)
                await db.flush()
        except IntegrityError:
            # Race condition: Candidate created concurrently by another worker execution
            dup_res = await db.execute(
                select(FinancialFactCandidate).where(
                    FinancialFactCandidate.organization_id == organization_id,
                    FinancialFactCandidate.idempotency_hash == idempotency_hash,
                )
            )
            dup_cand = dup_res.scalar_one_or_none()
            if dup_cand:
                return dup_cand
            raise

        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type="FACT_CANDIDATE_CREATED",
            target_type="financial_fact_candidate",
            target_id=candidate.id,
            actor_id=None,
            payload={
                "raw_label": raw_label,
                "extraction_method": extraction_method,
            },
        )

        return candidate
