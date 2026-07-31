import calendar
import hashlib
import json
import logging
import math
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from services.api.app.calculations.registry import (
    FormulaRegistry,
)
from services.api.app.models.calculation import Calculation
from services.api.app.models.calculation_attempt import CalculationAttempt
from services.api.app.models.calculation_evidence import CalculationEvidence
from services.api.app.models.calculation_input import CalculationInput
from services.api.app.models.calculation_reconciliation import CalculationReconciliation
from services.api.app.models.calculation_request import CalculationRequest
from services.api.app.models.candidate_evidence import CandidateEvidence
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact import FinancialFact
from services.api.app.models.formula_definition import FormulaDefinition
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.services.audit_service import AuditService

ALLOWLIST_ERROR_CODES = {
    "FORMULA_VERSION_MISMATCH",
    "FORMULA_NOT_SUPPORTED",
    "FORMULA_INPUT_METRIC_UNAVAILABLE",
    "INSUFFICIENT_INPUT_FACTS",
    "EVIDENCE_INCOMPLETE",
    "EVIDENCE_SOURCE_MISMATCH",
    "REPORTING_BASIS_REQUIRED",
    "REPORTING_BASIS_MISMATCH",
    "UNIT_MISMATCH",
    "SCALE_NORMALIZATION_ERROR",
    "CURRENCY_MISMATCH",
    "DIVISION_BY_ZERO",
    "COMPARISON_PERIOD_REQUIRED",
    "COMPARISON_PERIOD_NOT_FOUND",
    "PERIOD_TYPE_MISMATCH",
    "PERIOD_ORDER_INVALID",
    "BEGINNING_BALANCE_REQUIRED",
    "DUPLICATE_BALANCE_INPUT",
    "ANNUALIZATION_POLICY_UNRESOLVED",
    "CALCULATION_INTERNAL_ERROR",
}


def compute_request_fingerprint(
    organization_id: UUID,
    formula_code: str,
    formula_version: str,
    institution_id: UUID,
    reporting_period_id: UUID,
    comparison_period_id: UUID | None,
    comparison_policy: str,
) -> str:
    """Compute deterministically reproducible request fingerprint BEFORE facts/execution."""
    canonical_payload = {
        "organization_id": str(organization_id),
        "formula_code": formula_code,
        "formula_version": formula_version,
        "institution_id": str(institution_id),
        "reporting_period_id": str(reporting_period_id),
        "comparison_period_id": str(comparison_period_id) if comparison_period_id else None,
        "comparison_policy": comparison_policy,
        "contract_schema_version": "1.0.0",
    }
    raw_bytes = json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_canonical_idempotency_hash(
    organization_id: UUID,
    formula_code: str,
    formula_version: str,
    formula_spec_checksum: str,
    implementation_checksum: str,
    inputs_by_role: dict[str, dict[str, Any]],
    reporting_period_id: UUID,
    comparison_period_id: UUID | None,
    comparison_policy: str,
    annualization_policy_version: str = "1.0.0",
    rounding_policy_version: str = "1.0.0",
    reconciliation_policy_version: str = "1.0.0",
    idempotency_schema_version: str = "1.0.0",
) -> str:
    """Compute deterministic canonical SHA256 idempotency hash BEFORE calculation execution.

    MUST NOT contain calculation result values.
    Role inputs are sorted alphabetically to ensure canonical order.
    """
    sorted_roles = sorted(inputs_by_role.keys())
    role_snapshots = []
    for r in sorted_roles:
        f = inputs_by_role[r]
        role_snapshots.append(
            {
                "role": r,
                "fact_id": str(f["id"]),
                "revision_id": str(f.get("candidate_id") or f["id"]),
                "normalized_value": str(f["normalized_value"]),
                "currency": f.get("currency"),
                "unit": f.get("unit"),
                "scale": f.get("scale"),
                "reporting_basis": f.get("reporting_basis"),
            }
        )

    canonical_payload = {
        "organization_id": str(organization_id),
        "formula_code": formula_code,
        "formula_version": formula_version,
        "formula_spec_checksum": formula_spec_checksum,
        "implementation_checksum": implementation_checksum,
        "reporting_period_id": str(reporting_period_id),
        "comparison_period_id": str(comparison_period_id) if comparison_period_id else None,
        "comparison_policy": comparison_policy,
        "annualization_policy_version": annualization_policy_version,
        "rounding_policy_version": rounding_policy_version,
        "reconciliation_policy_version": reconciliation_policy_version,
        "idempotency_schema_version": idempotency_schema_version,
        "inputs": role_snapshots,
    }
    raw_bytes = json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


class CalculationService:
    @staticmethod
    def compute_act_isda_annualization_factor(
        start_date: date,
        end_date: date,
        presentation: str,
        input_semantics: dict[str, str],
    ) -> Decimal:
        """Compute ACT/ACT_ISDA annualization factor based on reporting period presentation and metric semantics."""
        if presentation == "UNKNOWN":
            raise ValueError("ANNUALIZATION_POLICY_UNRESOLVED")
        elif presentation in ("FULL_YEAR", "TRAILING_TWELVE_MONTHS"):
            return Decimal("1.0")
        elif presentation == "DATE_POINT":
            has_flow = any(sem == "FLOW" for sem in input_semantics.values())
            if has_flow:
                raise ValueError("ANNUALIZATION_POLICY_UNRESOLVED")
            return Decimal("1.0")
        elif presentation in ("DISCRETE_PERIOD", "YEAR_TO_DATE", "QUARTERLY", "SEMI_ANNUAL"):
            if start_date > end_date:
                raise ValueError("ANNUALIZATION_POLICY_UNRESOLVED")

            if start_date.year == end_date.year:
                days_in_period = (end_date - start_date).days + 1
                days_in_year = 366 if calendar.isleap(start_date.year) else 365
                year_fraction = Decimal(days_in_period) / Decimal(days_in_year)
            else:
                d1 = (date(start_date.year, 12, 31) - start_date).days + 1
                y1_days = 366 if calendar.isleap(start_date.year) else 365
                frac1 = Decimal(d1) / Decimal(y1_days)

                d2 = (end_date - date(end_date.year, 1, 1)).days + 1
                y2_days = 366 if calendar.isleap(end_date.year) else 365
                frac2 = Decimal(d2) / Decimal(y2_days)

                year_fraction = frac1 + frac2

            if year_fraction <= Decimal("0.0"):
                raise ValueError("ANNUALIZATION_POLICY_UNRESOLVED")

            return Decimal("1.0") / year_fraction
        else:
            raise ValueError("ANNUALIZATION_POLICY_UNRESOLVED")

    @staticmethod
    async def run_calculation(
        db: AsyncSession,
        organization_id: UUID,
        requested_by_user_id: UUID,
        formula_code: str,
        institution_id: UUID,
        reporting_period_id: UUID,
        comparison_period_id: UUID | None = None,
        comparison_policy: str = "PREVIOUS_PERIOD",
        explicit_fact_ids: dict[str, UUID] | None = None,
    ) -> tuple[Calculation, list[CalculationInput], CalculationReconciliation | None]:
        """Execute a deterministic financial calculation with physical identity separation & atomic recovery."""

        # Enforce tenant context in DB session
        await db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(organization_id)},
        )

        request_fingerprint = compute_request_fingerprint(
            organization_id=organization_id,
            formula_code=formula_code,
            formula_version="1.0.0",
            institution_id=institution_id,
            reporting_period_id=reporting_period_id,
            comparison_period_id=comparison_period_id,
            comparison_policy=comparison_policy,
        )

        active_idempotency_hash: str | None = None
        code_spec_checksum: str | None = None
        code_impl_checksum: str | None = None

        # Audit: Request received (Sanitized: NO hashes, UUIDs, or financial values in payload)
        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type="CALCULATION_REQUESTED",
            target_type="CALCULATION_REQUEST",
            target_id=uuid4(),
            actor_id=requested_by_user_id,
            payload={
                "formula_code": formula_code,
                "comparison_policy": comparison_policy,
            },
        )

        try:
            # 1. Fetch & Verify Formula Definition and Checksums (Two-Layer)
            formula = FormulaRegistry.get_formula(formula_code, "1.0.0")

            f_def_res = await db.execute(
                select(FormulaDefinition).where(
                    FormulaDefinition.formula_code == formula_code,
                    FormulaDefinition.status == "ACTIVE",
                )
            )
            formula_def = f_def_res.scalar_one_or_none()
            if not formula_def:
                raise ValueError("FORMULA_NOT_SUPPORTED")

            code_spec_checksum, code_impl_checksum = FormulaRegistry.verify_checksum(
                formula_code,
                "1.0.0",
                formula_def.formula_spec_checksum,
                formula_def.implementation_checksum,
            )

            # 2. Period & Comparison Policy Resolution
            rep_period_res = await db.execute(
                select(ReportingPeriod).where(
                    ReportingPeriod.id == reporting_period_id,
                    ReportingPeriod.organization_id == organization_id,
                )
            )
            rep_period = rep_period_res.scalar_one_or_none()
            if not rep_period:
                raise ValueError("PERIOD_MISMATCH")

            resolved_comp_period_id = comparison_period_id
            comp_period: ReportingPeriod | None = None

            if formula.comparison_requirement in ("REQUIRED_COMPARISON", "REQUIRED_BEGINNING_BALANCE"):
                if comparison_policy not in ("PREVIOUS_PERIOD", "PREVIOUS_YEAR_SAME_PERIOD", "EXPLICIT_PERIOD"):
                    raise ValueError("COMPARISON_POLICY_UNSUPPORTED")

                if comparison_policy == "EXPLICIT_PERIOD" and not resolved_comp_period_id:
                    if formula.comparison_requirement == "REQUIRED_BEGINNING_BALANCE":
                        raise ValueError("BEGINNING_BALANCE_REQUIRED")
                    raise ValueError("COMPARISON_PERIOD_REQUIRED")

                if comparison_policy == "PREVIOUS_PERIOD" and not resolved_comp_period_id:
                    prev_p_res = await db.execute(
                        select(ReportingPeriod)
                        .where(
                            ReportingPeriod.organization_id == organization_id,
                            ReportingPeriod.period_type == rep_period.period_type,
                            ReportingPeriod.end_date < rep_period.start_date,
                        )
                        .order_by(ReportingPeriod.end_date.desc())
                        .limit(1)
                    )
                    comp_period = prev_p_res.scalar_one_or_none()
                    if not comp_period:
                        raise ValueError("COMPARISON_PERIOD_NOT_FOUND")
                    resolved_comp_period_id = comp_period.id

                elif comparison_policy == "PREVIOUS_YEAR_SAME_PERIOD" and not resolved_comp_period_id:
                    prev_y_res = await db.execute(
                        select(ReportingPeriod)
                        .where(
                            ReportingPeriod.organization_id == organization_id,
                            ReportingPeriod.period_type == rep_period.period_type,
                            ReportingPeriod.fiscal_year == rep_period.fiscal_year - 1,
                            ReportingPeriod.comparison_key == rep_period.comparison_key,
                        )
                        .limit(1)
                    )
                    comp_period = prev_y_res.scalar_one_or_none()
                    if not comp_period:
                        raise ValueError("COMPARISON_PERIOD_NOT_FOUND")
                    resolved_comp_period_id = comp_period.id

                elif resolved_comp_period_id:
                    comp_p_res = await db.execute(
                        select(ReportingPeriod).where(
                            ReportingPeriod.id == resolved_comp_period_id,
                            ReportingPeriod.organization_id == organization_id,
                        )
                    )
                    comp_period = comp_p_res.scalar_one_or_none()
                    if not comp_period:
                        raise ValueError("COMPARISON_PERIOD_NOT_FOUND")

                    if comp_period.period_type != rep_period.period_type:
                        raise ValueError("PERIOD_TYPE_MISMATCH")

            else:
                resolved_comp_period_id = None

            # 3. ROA / ROE Period Requirements
            if formula.comparison_requirement == "REQUIRED_BEGINNING_BALANCE":
                if not resolved_comp_period_id or not comp_period:
                    raise ValueError("BEGINNING_BALANCE_REQUIRED")
                if comp_period.id == rep_period.id:
                    raise ValueError("DUPLICATE_BALANCE_INPUT")
                if comp_period.start_date >= rep_period.start_date:
                    raise ValueError("PERIOD_ORDER_INVALID")

            # 4. Annualization Factor Computation via ACT/ACT_ISDA
            annualization_factor = CalculationService.compute_act_isda_annualization_factor(
                start_date=rep_period.start_date,
                end_date=rep_period.end_date,
                presentation=rep_period.period_presentation,
                input_semantics=formula.input_role_semantics,
            )

            # 5. Fetch Facts & SQL-level Fact Eligibility (FOR UPDATE Locks)
            inputs_by_role: dict[str, dict[str, Any]] = {}
            fact_objects: dict[str, FinancialFact] = {}

            if formula_code in ("LOAN_TO_DEPOSIT_RATIO", "NPL_RATIO"):
                num_metric = formula.expected_metric_codes[0]
                den_metric = formula.expected_metric_codes[1]

                num_res = await db.execute(
                    select(FinancialFact)
                    .where(
                        FinancialFact.organization_id == organization_id,
                        FinancialFact.institution_id == institution_id,
                        FinancialFact.reporting_period_id == reporting_period_id,
                        FinancialFact.metric_code == num_metric,
                        FinancialFact.valid_to.is_(None),
                        FinancialFact.review_status == "HUMAN_VERIFIED",
                        FinancialFact.value_origin == "SOURCE_REPORTED",
                        FinancialFact.reporting_basis.in_(["SOLO", "CONSOLIDATED"]),
                    )
                    .with_for_update()
                )
                num_fact = num_res.scalar_one_or_none()

                den_res = await db.execute(
                    select(FinancialFact)
                    .where(
                        FinancialFact.organization_id == organization_id,
                        FinancialFact.institution_id == institution_id,
                        FinancialFact.reporting_period_id == reporting_period_id,
                        FinancialFact.metric_code == den_metric,
                        FinancialFact.valid_to.is_(None),
                        FinancialFact.review_status == "HUMAN_VERIFIED",
                        FinancialFact.value_origin == "SOURCE_REPORTED",
                        FinancialFact.reporting_basis.in_(["SOLO", "CONSOLIDATED"]),
                    )
                    .with_for_update()
                )
                den_fact = den_res.scalar_one_or_none()

                if not num_fact or not den_fact:
                    raise ValueError("INSUFFICIENT_INPUT_FACTS")

                fact_objects["NUMERATOR"] = num_fact
                fact_objects["DENOMINATOR"] = den_fact

            elif formula_code == "GROWTH_RATE":
                cur_res = await db.execute(
                    select(FinancialFact)
                    .where(
                        FinancialFact.organization_id == organization_id,
                        FinancialFact.institution_id == institution_id,
                        FinancialFact.reporting_period_id == reporting_period_id,
                        FinancialFact.valid_to.is_(None),
                        FinancialFact.review_status == "HUMAN_VERIFIED",
                        FinancialFact.value_origin == "SOURCE_REPORTED",
                        FinancialFact.reporting_basis.in_(["SOLO", "CONSOLIDATED"]),
                    )
                    .with_for_update()
                )
                cur_fact = cur_res.scalar_one_or_none()

                comp_res = await db.execute(
                    select(FinancialFact)
                    .where(
                        FinancialFact.organization_id == organization_id,
                        FinancialFact.institution_id == institution_id,
                        FinancialFact.reporting_period_id == resolved_comp_period_id,
                        FinancialFact.valid_to.is_(None),
                        FinancialFact.review_status == "HUMAN_VERIFIED",
                        FinancialFact.value_origin == "SOURCE_REPORTED",
                        FinancialFact.reporting_basis.in_(["SOLO", "CONSOLIDATED"]),
                    )
                    .with_for_update()
                )
                comp_fact = comp_res.scalar_one_or_none()

                if not cur_fact or not comp_fact:
                    raise ValueError("INSUFFICIENT_INPUT_FACTS")

                fact_objects["CURRENT_VALUE"] = cur_fact
                fact_objects["COMPARISON_VALUE"] = comp_fact

            elif formula_code in ("RETURN_ON_ASSETS", "RETURN_ON_EQUITY"):
                income_metric = formula.expected_metric_codes[0]
                balance_metric = formula.expected_metric_codes[1]

                inc_res = await db.execute(
                    select(FinancialFact)
                    .where(
                        FinancialFact.organization_id == organization_id,
                        FinancialFact.institution_id == institution_id,
                        FinancialFact.reporting_period_id == reporting_period_id,
                        FinancialFact.metric_code == income_metric,
                        FinancialFact.valid_to.is_(None),
                        FinancialFact.review_status == "HUMAN_VERIFIED",
                        FinancialFact.value_origin == "SOURCE_REPORTED",
                        FinancialFact.reporting_basis.in_(["SOLO", "CONSOLIDATED"]),
                    )
                    .with_for_update()
                )
                inc_fact = inc_res.scalar_one_or_none()

                beg_res = await db.execute(
                    select(FinancialFact)
                    .where(
                        FinancialFact.organization_id == organization_id,
                        FinancialFact.institution_id == institution_id,
                        FinancialFact.reporting_period_id == resolved_comp_period_id,
                        FinancialFact.metric_code == balance_metric,
                        FinancialFact.valid_to.is_(None),
                        FinancialFact.review_status == "HUMAN_VERIFIED",
                        FinancialFact.value_origin == "SOURCE_REPORTED",
                        FinancialFact.reporting_basis.in_(["SOLO", "CONSOLIDATED"]),
                    )
                    .with_for_update()
                )
                beg_fact = beg_res.scalar_one_or_none()

                end_res = await db.execute(
                    select(FinancialFact)
                    .where(
                        FinancialFact.organization_id == organization_id,
                        FinancialFact.institution_id == institution_id,
                        FinancialFact.reporting_period_id == reporting_period_id,
                        FinancialFact.metric_code == balance_metric,
                        FinancialFact.valid_to.is_(None),
                        FinancialFact.review_status == "HUMAN_VERIFIED",
                        FinancialFact.value_origin == "SOURCE_REPORTED",
                        FinancialFact.reporting_basis.in_(["SOLO", "CONSOLIDATED"]),
                    )
                    .with_for_update()
                )
                end_fact = end_res.scalar_one_or_none()

                if not inc_fact or not beg_fact or not end_fact:
                    raise ValueError("INSUFFICIENT_INPUT_FACTS")

                if beg_fact.id == end_fact.id:
                    raise ValueError("DUPLICATE_BALANCE_INPUT")

                fact_objects["PERIOD_INCOME"] = inc_fact
                fact_objects["BEGINNING_BALANCE"] = beg_fact
                fact_objects["ENDING_BALANCE"] = end_fact

            # Construct input snapshots & Validate consistency
            for role, fact in fact_objects.items():
                if fact.reporting_basis in (None, "UNKNOWN"):
                    raise ValueError("REPORTING_BASIS_REQUIRED")

                inputs_by_role[role] = {
                    "id": fact.id,
                    "candidate_id": fact.source_candidate_id,
                    "metric_code": fact.metric_code,
                    "normalized_value": fact.normalized_value,
                    "currency": fact.currency,
                    "unit": fact.unit,
                    "scale": fact.scale,
                    "reporting_basis": fact.reporting_basis,
                }

            first_fact = next(iter(fact_objects.values()))
            ref_basis = first_fact.reporting_basis
            ref_currency = first_fact.currency

            for role, fact in fact_objects.items():
                if fact.reporting_basis != ref_basis:
                    raise ValueError("REPORTING_BASIS_MISMATCH")
                if fact.currency != ref_currency:
                    raise ValueError("CURRENCY_MISMATCH")

            # 6. Canonical Execution Idempotency Hash Computation (BEFORE execution, NO results)
            active_idempotency_hash = compute_canonical_idempotency_hash(
                organization_id=organization_id,
                formula_code=formula_code,
                formula_version="1.0.0",
                formula_spec_checksum=code_spec_checksum,
                implementation_checksum=code_impl_checksum,
                inputs_by_role=inputs_by_role,
                reporting_period_id=reporting_period_id,
                comparison_period_id=resolved_comp_period_id,
                comparison_policy=comparison_policy,
                annualization_policy_version="1.0.0",
            )

            # 7. Physical Identity Resolution & Atomic FOR UPDATE Row Lock
            req_res = await db.execute(
                select(CalculationRequest)
                .where(
                    CalculationRequest.organization_id == organization_id,
                    CalculationRequest.request_fingerprint == request_fingerprint,
                )
                .with_for_update()
            )
            calc_request = req_res.scalar_one_or_none()

            if not calc_request:
                try:
                    async with db.begin_nested():
                        calc_request = CalculationRequest(
                            id=uuid4(),
                            organization_id=organization_id,
                            request_fingerprint=request_fingerprint,
                            formula_code=formula_code,
                            formula_version="1.0.0",
                            institution_id=institution_id,
                            reporting_period_id=reporting_period_id,
                            comparison_period_id=resolved_comp_period_id,
                            comparison_policy=comparison_policy,
                            requested_by_user_id=requested_by_user_id,
                        )
                        db.add(calc_request)
                        await db.flush()
                except IntegrityError:
                    req_res = await db.execute(
                        select(CalculationRequest)
                        .where(
                            CalculationRequest.organization_id == organization_id,
                            CalculationRequest.request_fingerprint == request_fingerprint,
                        )
                        .with_for_update()
                    )
                    calc_request = req_res.scalar_one_or_none()
                    if not calc_request:
                        raise

            # Check if COMPLETED calculation already exists for this idempotency hash
            existing_res = await db.execute(
                select(Calculation).where(
                    Calculation.organization_id == organization_id,
                    Calculation.execution_idempotency_hash == active_idempotency_hash,
                    Calculation.status == "COMPLETED",
                )
            )
            existing_calc = existing_res.scalar_one_or_none()
            if existing_calc:
                inputs_res = await db.execute(
                    select(CalculationInput).where(CalculationInput.calculation_id == existing_calc.id)
                )
                existing_inputs = list(inputs_res.scalars().all())

                rec_res = await db.execute(
                    select(CalculationReconciliation).where(
                        CalculationReconciliation.calculation_id == existing_calc.id
                    )
                )
                existing_rec = rec_res.scalar_one_or_none()
                return existing_calc, existing_inputs, existing_rec

            # 8. Mandatory Evidence Validation BEFORE COMPLETED calculation
            pending_evidences: list[CalculationEvidence] = []
            calc_id = uuid4()
            calc_inputs: list[CalculationInput] = []

            for role, fact in fact_objects.items():
                if not fact.source_candidate_id:
                    raise ValueError("EVIDENCE_INCOMPLETE")

                ev_res = await db.execute(
                    select(CandidateEvidence).where(
                        CandidateEvidence.organization_id == organization_id,
                        CandidateEvidence.candidate_id == fact.source_candidate_id,
                    )
                )
                cand_evs = list(ev_res.scalars().all())
                if not cand_evs:
                    raise ValueError("EVIDENCE_INCOMPLETE")

                inp = CalculationInput(
                    id=uuid4(),
                    organization_id=organization_id,
                    calculation_id=calc_id,
                    financial_fact_id=fact.id,
                    input_role=role,
                    metric_code=fact.metric_code,
                    normalized_value_snapshot=fact.normalized_value,
                    currency_snapshot=fact.currency,
                    unit_snapshot=fact.unit,
                    scale_snapshot=fact.scale,
                    reporting_basis_snapshot=fact.reporting_basis,
                    reporting_period_id_snapshot=fact.reporting_period_id,
                    fact_revision_metadata={
                        "candidate_id": str(fact.source_candidate_id),
                        "annualization_factor": str(annualization_factor),
                    },
                    evidence_reference={},
                )
                calc_inputs.append(inp)

                for cand_ev in cand_evs:
                    if cand_ev.organization_id != organization_id:
                        raise ValueError("EVIDENCE_SOURCE_MISMATCH")

                    doc_ver_res = await db.execute(
                        select(DocumentVersion).where(
                            DocumentVersion.id == cand_ev.source_document_version_id,
                            DocumentVersion.organization_id == organization_id,
                        )
                    )
                    doc_ver = doc_ver_res.scalar_one_or_none()
                    if not doc_ver:
                        raise ValueError("EVIDENCE_SOURCE_MISMATCH")

                    mime = doc_ver.detected_mime_type or doc_ver.declared_mime_type

                    # Format-specific Lineage Validation
                    if mime == "application/pdf":
                        bbox = cand_ev.bounding_box or {}
                        if cand_ev.page_number is None or cand_ev.page_number <= 0 or not bbox:
                            raise ValueError("EVIDENCE_INCOMPLETE")
                        if not all(k in bbox for k in ("x0", "y0", "x1", "y1")):
                            raise ValueError("EVIDENCE_INCOMPLETE")
                        try:
                            x0, y0, x1, y1 = float(bbox["x0"]), float(bbox["y0"]), float(bbox["x1"]), float(bbox["y1"])
                            if math.isnan(x0) or math.isnan(y0) or math.isnan(x1) or math.isnan(y1):
                                raise ValueError("EVIDENCE_INCOMPLETE")
                            if math.isinf(x0) or math.isinf(y0) or math.isinf(x1) or math.isinf(y1):
                                raise ValueError("EVIDENCE_INCOMPLETE")
                            if not (x1 > x0 and y1 > y0):
                                raise ValueError("EVIDENCE_INCOMPLETE")
                        except (ValueError, TypeError):
                            raise ValueError("EVIDENCE_INCOMPLETE")

                    elif mime in (
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.ms-excel",
                    ):
                        if not cand_ev.sheet_name or not cand_ev.sheet_name.strip():
                            raise ValueError("EVIDENCE_INCOMPLETE")
                        has_cell = bool(cand_ev.cell_coordinate and cand_ev.cell_coordinate.strip())
                        has_indices = (cand_ev.row_index is not None and cand_ev.row_index > 0) and (
                            cand_ev.column_index is not None and cand_ev.column_index > 0
                        )
                        if not has_cell and not has_indices:
                            raise ValueError("EVIDENCE_INCOMPLETE")

                    elif mime == "text/csv":
                        if cand_ev.row_index is None or cand_ev.row_index <= 0:
                            raise ValueError("EVIDENCE_INCOMPLETE")
                        if cand_ev.column_index is None or cand_ev.column_index <= 0:
                            raise ValueError("EVIDENCE_INCOMPLETE")

                    calc_ev = CalculationEvidence(
                        id=uuid4(),
                        organization_id=organization_id,
                        calculation_id=calc_id,
                        calculation_input_id=inp.id,
                        financial_fact_id=fact.id,
                        candidate_id=fact.source_candidate_id,
                        candidate_evidence_id=cand_ev.id,
                        source_document_id=fact.source_document_id,
                        source_document_version_id=cand_ev.source_document_version_id,
                        page_number=cand_ev.page_number,
                        sheet_name=cand_ev.sheet_name,
                        cell_coordinate=cand_ev.cell_coordinate,
                        header_name=cand_ev.header_name,
                        column_index=cand_ev.column_index,
                        bounding_box=cand_ev.bounding_box,
                        raw_snippet=cand_ev.raw_snippet,
                    )
                    pending_evidences.append(calc_ev)

            # 9. Pure Calculation Execution
            result = formula.calculate(
                inputs_by_role,
                metadata={"annualization_factor": str(annualization_factor)},
            )

            res_currency = None if result.result_unit in ("PERCENT", "RATIO") else ref_currency

            # 10. Atomic Attempt Counter per CalculationRequest
            att_count_res = await db.execute(
                select(func.coalesce(func.max(CalculationAttempt.attempt_number), 0)).where(
                    CalculationAttempt.organization_id == organization_id,
                    CalculationAttempt.calculation_request_id == calc_request.id,
                )
            )
            current_att_count = att_count_res.scalar() or 0
            attempt_num = current_att_count + 1

            attempt_id = uuid4()
            calc_attempt = CalculationAttempt(
                id=attempt_id,
                organization_id=organization_id,
                calculation_request_id=calc_request.id,
                attempt_number=attempt_num,
                execution_idempotency_hash=active_idempotency_hash,
                status="COMPLETED",
                retry_classification="NON_RETRIABLE",
                error_code=None,
                formula_spec_checksum=code_spec_checksum,
                implementation_checksum=code_impl_checksum,
                completed_at=datetime.now(UTC),
            )
            db.add(calc_attempt)
            await db.flush()

            calc = Calculation(
                id=calc_id,
                organization_id=organization_id,
                calculation_request_id=calc_request.id,
                calculation_attempt_id=attempt_id,
                institution_id=institution_id,
                reporting_period_id=reporting_period_id,
                comparison_period_id=resolved_comp_period_id,
                formula_code=formula_code,
                formula_version="1.0.0",
                status="COMPLETED",
                result_value=result.result_value_display,  # @deprecated
                result_value_unrounded=result.result_value_unrounded,
                result_value_display=result.result_value_display,
                result_unit=result.result_unit,
                result_scale=result.result_scale,
                result_currency=res_currency,
                value_representation=result.value_representation,
                working_precision=38,
                rounding_policy=result.rounding_policy,
                rounding_mode="ROUND_HALF_UP",
                display_scale="ONE",
                calculation_precision=38,
                calculation_rounding_policy_version="1.0.0",
                idempotency_hash=active_idempotency_hash,
                implementation_checksum=code_impl_checksum,
                formula_spec_checksum=code_spec_checksum,
                annualization_factor=annualization_factor,
                annualization_policy_version="1.0.0",
                attempt_number=attempt_num,
                requested_by_user_id=requested_by_user_id,
                completed_at=datetime.now(UTC),
            )

            try:
                async with db.begin_nested():
                    db.add(calc_attempt)
                    await db.flush()
                    db.add(calc)
                    await db.flush()
            except IntegrityError:
                # Concurrent race condition recovery: read winning COMPLETED calculation
                existing_res = await db.execute(
                    select(Calculation).where(
                        Calculation.organization_id == organization_id,
                        Calculation.execution_idempotency_hash == active_idempotency_hash,
                        Calculation.status == "COMPLETED",
                    )
                )
                winner_calc = existing_res.scalar_one_or_none()
                if winner_calc:
                    inputs_res = await db.execute(
                        select(CalculationInput).where(CalculationInput.calculation_id == winner_calc.id)
                    )
                    existing_inputs = list(inputs_res.scalars().all())

                    rec_res = await db.execute(
                        select(CalculationReconciliation).where(
                            CalculationReconciliation.calculation_id == winner_calc.id
                        )
                    )
                    existing_rec = rec_res.scalar_one_or_none()
                    return winner_calc, existing_inputs, existing_rec
                else:
                    raise

            db.add_all(calc_inputs)
            db.add_all(pending_evidences)

            # 11. Reconciliation against unrounded value using absolute & relative difference
            source_fact_res = await db.execute(
                select(FinancialFact).where(
                    FinancialFact.organization_id == organization_id,
                    FinancialFact.institution_id == institution_id,
                    FinancialFact.reporting_period_id == reporting_period_id,
                    FinancialFact.metric_code == formula_code,
                    FinancialFact.valid_to.is_(None),
                    FinancialFact.review_status == "HUMAN_VERIFIED",
                    FinancialFact.value_origin == "SOURCE_REPORTED",
                )
            )
            source_fact = source_fact_res.scalar_one_or_none()

            reconciliation: CalculationReconciliation | None = None
            if source_fact and source_fact.normalized_value is not None:
                source_val = source_fact.normalized_value
                derived_unrounded = result.result_value_unrounded
                abs_diff = abs(derived_unrounded - source_val)

                if source_val == Decimal("0.0"):
                    rel_diff = None
                else:
                    rel_diff = abs((derived_unrounded - source_val) / source_val)

                tol_value = formula_def.tolerance_value
                tol_kind = formula_def.tolerance_kind

                if tol_kind == "RELATIVE":
                    if source_val == Decimal("0.0"):
                        allowed_tol = tol_value
                    else:
                        allowed_tol = abs(source_val * (tol_value / Decimal("100.0")))
                else:
                    allowed_tol = tol_value

                if abs_diff == Decimal("0.0"):
                    status_rec = "RECONCILED"
                elif abs_diff <= allowed_tol:
                    status_rec = "WITHIN_TOLERANCE"
                else:
                    status_rec = "OUTSIDE_TOLERANCE"

                reconciliation = CalculationReconciliation(
                    id=uuid4(),
                    organization_id=organization_id,
                    calculation_id=calc_id,
                    source_reported_fact_id=source_fact.id,
                    source_reported_value=source_val,
                    system_derived_value=result.result_value_display,  # @deprecated
                    derived_unrounded_value=derived_unrounded,
                    difference=abs_diff,  # @deprecated
                    absolute_difference=abs_diff,
                    relative_difference=rel_diff,
                    tolerance=formula_def.tolerance_value,
                    applied_tolerance_kind=formula_def.tolerance_kind,
                    applied_tolerance_value=formula_def.tolerance_value,
                    applied_tolerance_unit=formula_def.tolerance_unit,
                    tolerance_policy_version=formula_def.tolerance_policy_version,
                    reconciliation_status=status_rec,
                )
                db.add(reconciliation)

            # Audit: Calculation Completed (Sanitized: NO hashes or UUIDs in payload)
            await AuditService.record_event(
                db=db,
                organization_id=organization_id,
                event_type="CALCULATION_COMPLETED",
                target_type="CALCULATION_ATTEMPT",
                target_id=attempt_id,
                actor_id=requested_by_user_id,
                payload={
                    "formula_code": formula_code,
                    "attempt_number": attempt_num,
                    "status": "COMPLETED",
                },
            )

            await db.commit()

            return calc, calc_inputs, reconciliation

        except Exception as err:  # noqa: BLE001
            raw_str = str(err)
            classified_code = raw_str if raw_str in ALLOWLIST_ERROR_CODES else "CALCULATION_INTERNAL_ERROR"

            await db.rollback()

            # Isolated Non-Silent Recovery Block
            try:
                await db.execute(
                    text("SELECT set_config('app.current_organization_id', :org_id, true);"),
                    {"org_id": str(organization_id)},
                )

                # Lock request row or insert with race condition handling
                req_res = await db.execute(
                    select(CalculationRequest)
                    .where(
                        CalculationRequest.organization_id == organization_id,
                        CalculationRequest.request_fingerprint == request_fingerprint,
                    )
                    .with_for_update()
                )
                calc_request = req_res.scalar_one_or_none()

                if not calc_request:
                    try:
                        async with db.begin_nested():
                            calc_request = CalculationRequest(
                                id=uuid4(),
                                organization_id=organization_id,
                                request_fingerprint=request_fingerprint,
                                formula_code=formula_code,
                                formula_version="1.0.0",
                                institution_id=institution_id,
                                reporting_period_id=reporting_period_id,
                                comparison_period_id=comparison_period_id,
                                comparison_policy=comparison_policy,
                                requested_by_user_id=requested_by_user_id,
                            )
                            db.add(calc_request)
                            await db.flush()
                    except IntegrityError:
                        req_res = await db.execute(
                            select(CalculationRequest)
                            .where(
                                CalculationRequest.organization_id == organization_id,
                                CalculationRequest.request_fingerprint == request_fingerprint,
                            )
                            .with_for_update()
                        )
                        calc_request = req_res.scalar_one_or_none()
                        if not calc_request:
                            raise

                # Get attempt number for FAILED attempt
                fail_att_count_res = await db.execute(
                    select(func.coalesce(func.max(CalculationAttempt.attempt_number), 0)).where(
                        CalculationAttempt.organization_id == organization_id,
                        CalculationAttempt.calculation_request_id == calc_request.id,
                    )
                )
                fail_current_count = fail_att_count_res.scalar() or 0
                fail_attempt_num = fail_current_count + 1

                failed_attempt = CalculationAttempt(
                    id=uuid4(),
                    organization_id=organization_id,
                    calculation_request_id=calc_request.id,
                    attempt_number=fail_attempt_num,
                    execution_idempotency_hash=active_idempotency_hash,  # None if failed pre-facts
                    status="FAILED",
                    retry_classification="NON_RETRIABLE",
                    error_code=classified_code,
                    formula_spec_checksum=code_spec_checksum,
                    implementation_checksum=code_impl_checksum,
                    completed_at=datetime.now(UTC),
                )
                db.add(failed_attempt)

                # Audit: Calculation Failed (Sanitized: NO hashes or tracebacks in payload)
                await AuditService.record_event(
                    db=db,
                    organization_id=organization_id,
                    event_type="CALCULATION_FAILED",
                    target_type="CALCULATION_ATTEMPT",
                    target_id=failed_attempt.id,
                    actor_id=requested_by_user_id,
                    payload={
                        "formula_code": formula_code,
                        "error_code": classified_code,
                        "attempt_number": fail_attempt_num,
                    },
                )

                await db.commit()
            except Exception:  # noqa: BLE001
                await db.rollback()
                logger.error("CALCULATION_FAILURE_PERSISTENCE_FAILED")
                raise ValueError("CALCULATION_FAILURE_PERSISTENCE_FAILED") from None

            raise ValueError(classified_code)
