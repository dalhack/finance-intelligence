from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.db.session import get_db_session
from services.api.app.dependencies import require_permission
from services.api.app.middleware.execution_context import ExecutionContext
from services.api.app.models.calculation import Calculation
from services.api.app.models.formula_definition import FormulaDefinition
from services.api.app.schemas.calculation import (
    CalculationResponseDTO,
    CalculationRunDTO,
    FormulaDefinitionResponseDTO,
)
from services.api.app.services.calculation_service import CalculationService

router = APIRouter()

perm_run = require_permission("calculations:run")
perm_read = require_permission("calculations:read")


@router.post("", response_model=CalculationResponseDTO, status_code=status.HTTP_201_CREATED)
async def run_calculation(
    payload: CalculationRunDTO,
    ctx: ExecutionContext = Depends(perm_run),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> CalculationResponseDTO:
    """Execute a deterministic calculation in strict working Decimal precision."""
    try:
        calc, _calc_inputs, _reconciliation = await CalculationService.run_calculation(
            db=session,
            organization_id=ctx.active_organization_id,
            requested_by_user_id=ctx.authenticated_user_id,
            formula_code=payload.formula_code,
            institution_id=payload.institution_id,
            reporting_period_id=payload.reporting_period_id,
            comparison_period_id=payload.comparison_period_id,
            comparison_policy=payload.comparison_policy,
            explicit_fact_ids=payload.explicit_fact_ids,
        )
        return CalculationResponseDTO.model_validate(calc)
    except ValueError as e:
        err_msg = str(e)
        if err_msg in (
            "FACT_NOT_ACTIVE",
            "FACT_NOT_HUMAN_VERIFIED",
            "FACT_EVIDENCE_INCOMPLETE",
            "INSTITUTION_MISMATCH",
            "PERIOD_MISMATCH",
            "PERIOD_TYPE_MISMATCH",
            "REPORTING_BASIS_MISMATCH",
            "CURRENCY_MISMATCH",
            "UNIT_MISMATCH",
            "METRIC_MISMATCH",
            "DIVISION_BY_ZERO",
            "INSUFFICIENT_INPUT_FACTS",
            "FORMULA_NOT_SUPPORTED",
            "FORMULA_INPUT_METRIC_UNAVAILABLE",
            "FORMULA_VERSION_MISMATCH",
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": err_msg, "message": f"Calculation failed with error: {err_msg}"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CALCULATION_FAILED", "message": err_msg},
        )


@router.get("/{id}", response_model=CalculationResponseDTO)
async def get_calculation(
    id: UUID,
    ctx: ExecutionContext = Depends(perm_read),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> CalculationResponseDTO:
    """Get calculation by ID for active organization."""
    res = await session.execute(
        select(Calculation).where(
            Calculation.id == id,
            Calculation.organization_id == ctx.active_organization_id,
        )
    )
    calc = res.scalar_one_or_none()
    if not calc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found.")
    return CalculationResponseDTO.model_validate(calc)


@router.get("", response_model=list[CalculationResponseDTO])
async def list_calculations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: ExecutionContext = Depends(perm_read),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> list[CalculationResponseDTO]:
    """List paginated calculations for active organization."""
    res = await session.execute(
        select(Calculation)
        .where(Calculation.organization_id == ctx.active_organization_id)
        .order_by(Calculation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    calcs = res.scalars().all()
    return [CalculationResponseDTO.model_validate(c) for c in calcs]


@router.get("/formula-definitions", response_model=list[FormulaDefinitionResponseDTO])
async def list_formula_definitions(
    ctx: ExecutionContext = Depends(perm_read),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> list[FormulaDefinitionResponseDTO]:
    """List available canonical formula definitions."""
    res = await session.execute(
        select(FormulaDefinition).where(FormulaDefinition.status == "ACTIVE").order_by(FormulaDefinition.formula_code)
    )
    defs = res.scalars().all()
    return [FormulaDefinitionResponseDTO.model_validate(d) for d in defs]
