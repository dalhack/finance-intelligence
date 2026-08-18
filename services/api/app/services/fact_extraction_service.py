"""Turns parsed document chunks into reviewable financial fact candidates.

Parsing a filing produces text and table chunks; on its own that yields nothing
a user can act on. This service reads those chunks, recognises the rows whose
labels match the canonical metric dictionary, and records each one as a
candidate awaiting human review. Nothing here creates verified facts: every
value still has to be approved in the review queue before calculations may use
it.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from app.models.institution import Institution
from app.models.metric_definition import MetricDefinition
from app.models.reporting_period import ReportingPeriod
from app.services.fact_candidate_service import FactCandidateService
from app.services.normalization_service import NormalizationService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# A filing repeats the same caption across dozens of note tables; without a
# ceiling a single document could flood the review queue.
MAX_CANDIDATES_PER_VERSION = 200

_DMY_DATE = re.compile(r"(?<!\d)(\d{2})[._\-/](\d{2})[._\-/](\d{4})(?!\d)")
_YMD_DATE = re.compile(r"(?<!\d)(\d{4})[._\-/](\d{2})[._\-/](\d{2})(?!\d)")
_SOLO_HINTS = ("solo", "unconsolidated", "banka")
_CONSOLIDATED_HINTS = ("konsolide", "consolidated", "konsol")
# Tokens that describe the document rather than the institution.
_CONTEXT_TOKENS = {
    "solo",
    "konsolide",
    "consolidated",
    "unconsolidated",
    "tr",
    "en",
    "pdf",
    "xlsx",
    "csv",
    "finansal",
    "rapor",
    "report",
    "bilanco",
    "bilanço",
}


@dataclass(frozen=True)
class DocumentContext:
    """Institution, period and reporting basis inferred from a document name."""

    institution_code: str | None
    period_end: date | None
    reporting_basis: str


@dataclass(frozen=True)
class ExtractionSummary:
    candidates_created: int
    rows_considered: int
    matched_labels: int
    context: DocumentContext


class FactExtractionService:
    @staticmethod
    def parse_document_context(display_name: str) -> DocumentContext:
        """Infer institution, period end and reporting basis from a file name.

        Filings are published with names such as `Solo_VAKBN_31.03.2026__TR.pdf`,
        which carry the reporting basis, the institution code and the period end.
        """
        stem = display_name.rsplit(".", 1)[0]
        lowered = stem.lower()

        basis = "UNKNOWN"
        if any(hint in lowered for hint in _CONSOLIDATED_HINTS):
            basis = "CONSOLIDATED"
        elif any(hint in lowered for hint in _SOLO_HINTS):
            basis = "SOLO"

        period_end: date | None = None
        dmy = _DMY_DATE.search(stem)
        ymd = _YMD_DATE.search(stem)
        try:
            if dmy:
                period_end = date(int(dmy.group(3)), int(dmy.group(2)), int(dmy.group(1)))
            elif ymd:
                period_end = date(int(ymd.group(1)), int(ymd.group(2)), int(ymd.group(3)))
        except ValueError:
            period_end = None

        cleaned = _DMY_DATE.sub(" ", stem)
        cleaned = _YMD_DATE.sub(" ", cleaned)
        tokens = [t for t in re.split(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü]+", cleaned) if t]
        candidates = [t for t in tokens if t.lower() not in _CONTEXT_TOKENS and not t.isdigit()]
        institution_code = max(candidates, key=len).upper() if candidates else None

        return DocumentContext(
            institution_code=institution_code,
            period_end=period_end,
            reporting_basis=basis,
        )

    @staticmethod
    async def resolve_institution(db: AsyncSession, organization_id: UUID, institution_code: str) -> Institution:
        """Return the tenant's institution for this code, creating it if new."""
        existing = await db.execute(
            select(Institution).where(
                Institution.organization_id == organization_id,
                Institution.canonical_name.ilike(institution_code),
            )
        )
        found = existing.scalar_one_or_none()
        if found:
            return found

        institution = Institution(
            organization_id=organization_id,
            canonical_name=institution_code,
            display_name=institution_code,
            institution_type="BANK",
            country_code="TR",
            status="ACTIVE",
            aliases=[],
        )
        db.add(institution)
        await db.flush()
        return institution

    @staticmethod
    async def resolve_reporting_period(db: AsyncSession, organization_id: UUID, period_end: date) -> ReportingPeriod:
        """Return the quarterly period ending on this date, creating it if new."""
        quarter = (period_end.month - 1) // 3 + 1
        comparison_key = NormalizationService.generate_comparison_key("QUARTER", period_end.year, quarter)

        existing = await db.execute(
            select(ReportingPeriod).where(
                ReportingPeriod.organization_id == organization_id,
                ReportingPeriod.comparison_key == comparison_key,
            )
        )
        found = existing.scalar_one_or_none()
        if found:
            return found

        period = ReportingPeriod(
            organization_id=organization_id,
            period_type="QUARTER",
            period_presentation="YEAR_TO_DATE",
            fiscal_year=period_end.year,
            quarter=quarter,
            start_date=date(period_end.year, 3 * (quarter - 1) + 1, 1),
            end_date=period_end,
            label=f"{period_end.year}/Q{quarter}",
            comparison_key=comparison_key,
        )
        db.add(period)
        await db.flush()
        return period

    @staticmethod
    def iter_table_rows(chunk_content: str) -> list[tuple[str, str]]:
        """Yield (label, first numeric cell) pairs from a parsed table chunk."""
        rows: list[tuple[str, str]] = []
        for line in chunk_content.split("\n"):
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) < 2:
                continue
            label = cells[0]
            if not label:
                continue
            for cell in cells[1:]:
                if not cell:
                    continue
                parsed = NormalizationService.parse_financial_decimal(cell)
                if parsed.value is not None:
                    rows.append((label, cell))
                    break
        return rows

    @staticmethod
    async def _match_metric(db: AsyncSession, organization_id: UUID, label: str) -> MetricDefinition | None:
        return await FactCandidateService.match_metric_alias(db, organization_id, label)

    @staticmethod
    async def extract_candidates(
        db: AsyncSession,
        organization_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        display_name: str,
        chunks: list[dict[str, Any]],
    ) -> ExtractionSummary:
        """Create review candidates for table rows matching the metric dictionary.

        Only rows whose label resolves to a canonical metric are recorded: a
        filing contains hundreds of note rows, and admitting them all would bury
        the reviewer instead of helping them.
        """
        context = FactExtractionService.parse_document_context(display_name)
        if context.institution_code is None or context.period_end is None:
            return ExtractionSummary(0, 0, 0, context)

        institution = await FactExtractionService.resolve_institution(db, organization_id, context.institution_code)
        period = await FactExtractionService.resolve_reporting_period(db, organization_id, context.period_end)

        rows_considered = 0
        matched_labels = 0
        created = 0

        for chunk in chunks:
            if chunk.get("chunk_type") != "TABLE":
                continue
            for label, raw_value in FactExtractionService.iter_table_rows(chunk.get("content", "")):
                if created >= MAX_CANDIDATES_PER_VERSION:
                    return ExtractionSummary(created, rows_considered, matched_labels, context)

                rows_considered += 1
                metric = await FactExtractionService._match_metric(db, organization_id, label)
                if metric is None:
                    continue

                matched_labels += 1
                await FactCandidateService.create_candidate(
                    db=db,
                    organization_id=organization_id,
                    institution_id=institution.id,
                    reporting_period_id=period.id,
                    raw_label=label,
                    raw_value=raw_value,
                    source_document_id=document_id,
                    source_document_version_id=document_version_id,
                    detected_reporting_basis=context.reporting_basis,
                    source_location=chunk.get("source_lineage") or {},
                    extraction_method="PARSER_TABLE",
                    evidence_snippet=f"{label} | {raw_value}"[:500],
                )
                created += 1

        return ExtractionSummary(created, rows_considered, matched_labels, context)
