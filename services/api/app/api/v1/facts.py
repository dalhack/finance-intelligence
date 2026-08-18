from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.db.session import get_db_session
from app.dependencies import require_permission
from app.middleware.execution_context import ExecutionContext
from app.models.candidate_evidence import CandidateEvidence
from app.models.financial_fact import FinancialFact
from app.models.financial_fact_candidate import FinancialFactCandidate
from app.models.institution import Institution
from app.models.metric_definition import MetricDefinition
from app.models.reporting_period import ReportingPeriod
from app.services.financial_fact_service import FinancialFactService
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# --- DTO Schemas ---
class InstitutionCreateDTO(BaseModel):
    canonical_name: str = Field(..., max_length=255)
    display_name: str = Field(..., max_length=255)
    institution_type: str = Field("BANK", max_length=50)
    country_code: str = Field("TR", max_length=2)
    regulatory_identifier: str | None = Field(None, max_length=100)


class InstitutionResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    canonical_name: str
    display_name: str
    institution_type: str
    country_code: str
    regulatory_identifier: str | None
    status: str
    created_at: datetime


class ReportingPeriodCreateDTO(BaseModel):
    period_type: str = Field(..., description="YEAR, QUARTER, MONTH, DATE_POINT, TTM")
    fiscal_year: int = Field(..., ge=1900, le=2100)
    quarter: int | None = Field(None, ge=1, le=4)
    month: int | None = Field(None, ge=1, le=12)
    start_date: date
    end_date: date
    label: str = Field(..., max_length=100)


class ReportingPeriodResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    period_type: str
    fiscal_year: int
    quarter: int | None
    month: int | None
    start_date: date
    end_date: date
    label: str
    comparison_key: str
    created_at: datetime


class MetricDefinitionResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    metric_code: str
    canonical_name: str
    description: str | None
    value_type: str
    default_unit: str
    status: str


class CandidateResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    institution_id: UUID
    reporting_period_id: UUID
    suggested_metric_code: str | None
    raw_label: str
    raw_value: str
    parsed_decimal_value: Decimal | None
    raw_currency: str
    raw_unit: str
    raw_scale: str
    normalized_currency: str
    normalized_unit: str
    normalized_scale: str
    normalized_value: Decimal | None
    detected_reporting_basis: str
    confidence_score: Decimal
    validation_status: str
    review_status: str
    warning_codes: list[str]
    conflicting_fact_id: UUID | None = None
    conflict_detected_at: datetime | None = None
    conflict_reason: str | None = None
    created_at: datetime

    # Human-readable context. A reviewer cannot judge a bare number and an id:
    # these say which institution, which line item, which period, and where in
    # the document the value was read from.
    institution_name: str | None = None
    metric_label: str | None = None
    period_label: str | None = None
    extraction_method: str | None = None
    evidence_snippet: str | None = None
    source_page: int | None = None


class ApproveCandidateRequestDTO(BaseModel):
    target_reporting_basis: str | None = Field(None, description="Explicit SOLO or CONSOLIDATED basis selection")
    notes: str | None = Field(None, max_length=1000)


class ApproveCandidateRevisionRequestDTO(BaseModel):
    expected_existing_fact_id: UUID = Field(..., description="Target active fact ID to supersede")
    target_reporting_basis: str | None = Field(None, description="Explicit SOLO or CONSOLIDATED basis selection")
    notes: str | None = Field(None, max_length=1000)


class RejectCandidateRequestDTO(BaseModel):
    reason_code: str = Field(..., max_length=100)
    notes: str | None = Field(None, max_length=1000)


class FinancialFactResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    institution_id: UUID
    reporting_period_id: UUID
    metric_code: str
    value: Decimal
    currency: str
    unit: str
    scale: str
    normalized_value: Decimal
    reporting_basis: str
    confidence_score: Decimal
    review_status: str
    verified_at: datetime
    supersedes_fact_id: UUID | None
    value_origin: str


# --- Endpoints ---
@router.get("/institutions", response_model=list[InstitutionResponseDTO])
async def list_institutions(
    ctx: ExecutionContext = Depends(require_permission("facts:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    res = await db.execute(select(Institution).where(Institution.organization_id == ctx.active_organization_id))
    return res.scalars().all()


@router.post("/institutions", response_model=InstitutionResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_institution(
    dto: InstitutionCreateDTO,
    ctx: ExecutionContext = Depends(require_permission("facts:candidates:review")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    inst = Institution(
        organization_id=ctx.active_organization_id,
        canonical_name=dto.canonical_name,
        display_name=dto.display_name,
        institution_type=dto.institution_type,
        country_code=dto.country_code,
        regulatory_identifier=dto.regulatory_identifier,
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


@router.get("/reporting-periods", response_model=list[ReportingPeriodResponseDTO])
async def list_reporting_periods(
    ctx: ExecutionContext = Depends(require_permission("facts:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    res = await db.execute(select(ReportingPeriod).where(ReportingPeriod.organization_id == ctx.active_organization_id))
    return res.scalars().all()


@router.post("/reporting-periods", response_model=ReportingPeriodResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_reporting_period(
    dto: ReportingPeriodCreateDTO,
    ctx: ExecutionContext = Depends(require_permission("facts:candidates:review")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    if dto.start_date > dto.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

    comparison_key = f"{dto.fiscal_year}-Q{dto.quarter}" if dto.quarter else f"{dto.fiscal_year}-FY"
    period = ReportingPeriod(
        organization_id=ctx.active_organization_id,
        period_type=dto.period_type,
        fiscal_year=dto.fiscal_year,
        quarter=dto.quarter,
        month=dto.month,
        start_date=dto.start_date,
        end_date=dto.end_date,
        label=dto.label,
        comparison_key=comparison_key,
    )
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period


@router.get("/metric-definitions", response_model=list[MetricDefinitionResponseDTO])
async def list_metric_definitions(
    ctx: ExecutionContext = Depends(require_permission("facts:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    res = await db.execute(select(MetricDefinition).where(MetricDefinition.status == "ACTIVE"))
    return res.scalars().all()


def _to_candidate_dto(
    candidate: FinancialFactCandidate,
    institution_name: str | None,
    period_label: str | None,
    metric_label: str | None,
    evidence_snippet: str | None,
    source_page: int | None,
) -> CandidateResponseDTO:
    """Attach the labels a reviewer needs to the raw candidate row."""
    dto = CandidateResponseDTO.model_validate(candidate)
    return dto.model_copy(
        update={
            "institution_name": institution_name,
            "period_label": period_label,
            "metric_label": metric_label,
            "extraction_method": candidate.extraction_method,
            "evidence_snippet": evidence_snippet,
            "source_page": source_page,
        }
    )


@router.get("/fact-candidates", response_model=list[CandidateResponseDTO])
async def list_fact_candidates(
    review_status: str | None = Query(None),
    validation_status: str | None = Query(None),
    ctx: ExecutionContext = Depends(require_permission("facts:candidates:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    stmt = (
        select(
            FinancialFactCandidate,
            Institution.display_name,
            ReportingPeriod.label,
            MetricDefinition.canonical_name,
            CandidateEvidence.raw_snippet,
            CandidateEvidence.page_number,
        )
        .outerjoin(Institution, Institution.id == FinancialFactCandidate.institution_id)
        .outerjoin(ReportingPeriod, ReportingPeriod.id == FinancialFactCandidate.reporting_period_id)
        .outerjoin(
            MetricDefinition,
            MetricDefinition.metric_code == FinancialFactCandidate.suggested_metric_code,
        )
        .outerjoin(CandidateEvidence, CandidateEvidence.candidate_id == FinancialFactCandidate.id)
        .where(FinancialFactCandidate.organization_id == ctx.active_organization_id)
        .order_by(FinancialFactCandidate.created_at.desc())
    )
    if review_status:
        stmt = stmt.where(FinancialFactCandidate.review_status == review_status)
    if validation_status:
        stmt = stmt.where(FinancialFactCandidate.validation_status == validation_status)

    res = await db.execute(stmt)
    return [
        _to_candidate_dto(candidate, institution_name, period_label, metric_label, snippet, page)
        for candidate, institution_name, period_label, metric_label, snippet, page in res.all()
    ]


@router.get("/fact-candidates/{candidate_id}", response_model=CandidateResponseDTO)
async def get_fact_candidate(
    candidate_id: UUID,
    ctx: ExecutionContext = Depends(require_permission("facts:candidates:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    res = await db.execute(
        select(FinancialFactCandidate).where(
            FinancialFactCandidate.id == candidate_id,
            FinancialFactCandidate.organization_id == ctx.active_organization_id,
        )
    )
    cand = res.scalar_one_or_none()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return cand


@router.post("/fact-candidates/{candidate_id}/approve")
async def approve_fact_candidate(
    candidate_id: UUID,
    dto: ApproveCandidateRequestDTO,
    ctx: ExecutionContext = Depends(require_permission("facts:candidates:review")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    try:
        cand, fact = await FinancialFactService.approve_candidate(
            db=db,
            organization_id=ctx.active_organization_id,
            candidate_id=candidate_id,
            reviewer_user_id=ctx.authenticated_user_id,
            target_reporting_basis=dto.target_reporting_basis,
            notes=dto.notes,
        )
        return {
            "status": "APPROVED",
            "candidate_id": str(cand.id),
            "fact_id": str(fact.id),
            "metric_code": fact.metric_code,
            "normalized_value": str(fact.normalized_value),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fact-candidates/{candidate_id}/approve-as-revision")
async def approve_fact_candidate_as_revision(
    candidate_id: UUID,
    dto: ApproveCandidateRevisionRequestDTO,
    ctx: ExecutionContext = Depends(require_permission("facts:verify_revision")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    try:
        cand, fact = await FinancialFactService.approve_candidate_as_revision(
            db=db,
            organization_id=ctx.active_organization_id,
            candidate_id=candidate_id,
            expected_existing_fact_id=dto.expected_existing_fact_id,
            reviewer_user_id=ctx.authenticated_user_id,
            target_reporting_basis=dto.target_reporting_basis,
            notes=dto.notes,
        )
        return {
            "status": "REVISED",
            "candidate_id": str(cand.id),
            "created_fact_id": str(fact.id),
            "superseded_fact_id": str(fact.supersedes_fact_id),
            "metric_code": fact.metric_code,
            "normalized_value": str(fact.normalized_value),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fact-candidates/{candidate_id}/reject")
async def reject_fact_candidate(
    candidate_id: UUID,
    dto: RejectCandidateRequestDTO,
    ctx: ExecutionContext = Depends(require_permission("facts:candidates:review")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    try:
        cand = await FinancialFactService.reject_candidate(
            db=db,
            organization_id=ctx.active_organization_id,
            candidate_id=candidate_id,
            reviewer_user_id=ctx.authenticated_user_id,
            reason_code=dto.reason_code,
            notes=dto.notes,
        )
        return {"status": "REJECTED", "candidate_id": str(cand.id), "reason_code": dto.reason_code}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/financial-facts", response_model=list[FinancialFactResponseDTO])
async def list_financial_facts(
    metric_code: str | None = Query(None),
    institution_id: UUID | None = Query(None),  # noqa: B008
    ctx: ExecutionContext = Depends(require_permission("facts:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    stmt = select(FinancialFact).where(
        FinancialFact.organization_id == ctx.active_organization_id,
        FinancialFact.valid_to.is_(None),
    )
    if metric_code:
        stmt = stmt.where(FinancialFact.metric_code == metric_code)
    if institution_id:
        stmt = stmt.where(FinancialFact.institution_id == institution_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/financial-facts/{fact_id}", response_model=FinancialFactResponseDTO)
async def get_financial_fact(
    fact_id: UUID,
    ctx: ExecutionContext = Depends(require_permission("facts:read")),  # noqa: B008
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
):
    res = await db.execute(
        select(FinancialFact).where(
            FinancialFact.id == fact_id,
            FinancialFact.organization_id == ctx.active_organization_id,
        )
    )
    fact = res.scalar_one_or_none()
    if not fact:
        raise HTTPException(status_code=404, detail="Financial fact not found")
    return fact
