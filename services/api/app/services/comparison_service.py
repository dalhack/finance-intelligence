from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Literal
from uuid import UUID, uuid4

from app.calculations.registry import FormulaRegistry
from app.calculations.semantic_measure_registry import (
    SemanticMeasureDefinition,
    SemanticMeasureRegistry,
)
from app.models.calculation import Calculation
from app.models.calculation_attempt import CalculationAttempt
from app.models.calculation_evidence import CalculationEvidence
from app.models.calculation_input import CalculationInput
from app.models.calculation_reconciliation import CalculationReconciliation
from app.models.candidate_evidence import CandidateEvidence
from app.models.comparison_run import ComparisonRun
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.financial_fact import FinancialFact
from app.models.financial_fact_candidate import FinancialFactCandidate
from app.models.institution import Institution
from app.models.reporting_period import ReportingPeriod
from app.models.result_dataset_model import ResultDatasetModel
from app.schemas.comparison import (
    ComparisonFiltersDTO,
    ComparisonRequestDTO,
    ComparisonResponseDTO,
    EvidenceDetailDTO,
)
from app.schemas.result_dataset import (
    ChartSeriesDTO,
    ChartSeriesItemDTO,
    ChartSpecDTO,
    DataQualitySummaryDTO,
    DatasetRowCellDTO,
    DatasetRowDTO,
    MeasureItemDTO,
    PaginationDTO,
    QuerySnapshotDTO,
    ResultDatasetDTO,
    TableCellDTO,
    TableColumnDTO,
    TableRowDTO,
    TableSpecDTO,
)
from app.services.audit_service import AuditService
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


class ComparisonService:
    # ──────────────────────────── helpers ────────────────────────────

    @staticmethod
    def _scale_divisor(display_scale: str) -> Decimal:
        _MAP = {
            "ONE": Decimal(1),
            "THOUSAND": Decimal(1000),
            "MILLION": Decimal(1000000),
            "BILLION": Decimal(1000000000),
        }
        if display_scale not in _MAP:
            raise ValueError("SCALE_NORMALIZATION_ERROR")
        return _MAP[display_scale]

    @staticmethod
    def _safe_decimal(val: str) -> Decimal:
        try:
            d = Decimal(val)
        except InvalidOperation:
            raise ValueError("INVALID_DECIMAL_VALUE")
        if d.is_nan() or d.is_infinite():
            raise ValueError("INVALID_DECIMAL_VALUE")
        return d

    @staticmethod
    def _format_display(value: Decimal, unit: str, scale_div: Decimal) -> str:
        if unit in ("PERCENT", "RATIO"):
            return f"{value:.4f}"
        scaled = value / scale_div
        return f"{scaled:,.2f}"

    @staticmethod
    def _make_pagination(total_rows: int, page: int, page_size: int) -> PaginationDTO:
        total_pages = max(1, ceil(total_rows / page_size))
        return PaginationDTO(
            page=page,
            page_size=page_size,
            total_rows=total_rows,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    @staticmethod
    def _validate_evidence_coordinates(ev: CandidateEvidence, doc_ver: DocumentVersion | None) -> bool:
        """Validate format-based evidence coordinates."""
        mime = (doc_ver.detected_mime_type if doc_ver else "application/pdf").lower()

        if "pdf" in mime:
            if ev.page_number is None or ev.page_number <= 0:
                return False
            bbox = ev.bounding_box or {}
            required_keys = ("x0", "y0", "x1", "y1")
            return all(k in bbox and isinstance(bbox[k], (int, float)) for k in required_keys)
        elif "spreadsheet" in mime or "excel" in mime or "xlsx" in mime:
            if ev.sheet_name and ev.cell_coordinate:
                return True
            if ev.row_index is not None and ev.column_index is not None:
                return ev.row_index > 0 and ev.column_index > 0
            return False
        elif "csv" in mime or "text" in mime:
            if ev.row_index is not None and ev.column_index is not None:
                return ev.row_index > 0 and ev.column_index > 0
            return False

        # Fallback for generic format with page or coordinates
        return (ev.page_number is not None and ev.page_number > 0) or bool(ev.bounding_box)

    # ──────────────────────────── execute_comparison ────────────────────────────

    @classmethod
    async def execute_comparison(
        cls,
        db: AsyncSession,
        organization_id: UUID,
        requested_by_user_id: UUID,
        payload: ComparisonRequestDTO,
    ) -> ComparisonResponseDTO:
        # Enforce tenant RLS context
        await db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(organization_id)},
        )

        # Thresholds
        if (
            len(payload.institution_ids) > 10
            or len(payload.semantic_measures) > 15
            or len(payload.reporting_period_ids) > 20
        ):
            raise ValueError("COMPARISON_LIMIT_EXCEEDED")
        if payload.top_n is not None and payload.top_n > 50:
            raise ValueError("COMPARISON_LIMIT_EXCEEDED")

        # ── Resolve & Validate Semantic Measures ──
        semantic_defs: dict[str, SemanticMeasureDefinition] = {}
        for sel in payload.semantic_measures:
            defn = SemanticMeasureRegistry.get(sel.semantic_measure_code)
            semantic_defs[defn.semantic_measure_code] = defn

        # ── Fetch Institutions & Periods ──
        inst_res = await db.execute(
            select(Institution).where(
                Institution.id.in_(payload.institution_ids),
                Institution.organization_id == organization_id,
            )
        )
        institutions = {inst.id: inst for inst in inst_res.scalars().all()}
        if len(institutions) != len(payload.institution_ids):
            raise ValueError("INSTITUTION_NOT_FOUND")

        period_res = await db.execute(
            select(ReportingPeriod).where(
                ReportingPeriod.id.in_(payload.reporting_period_ids),
                ReportingPeriod.organization_id == organization_id,
            )
        )
        periods = {p.id: p for p in period_res.scalars().all()}
        if len(periods) != len(payload.reporting_period_ids):
            raise ValueError("PERIOD_NOT_FOUND")

        # Collect reported metrics & derived formula codes needed
        needed_reported_metrics = set()
        needed_derived_formulas = set()

        for defn in semantic_defs.values():
            if (
                payload.value_source_policy
                in (
                    "SOURCE_REPORTED_ONLY",
                    "PREFER_SOURCE_REPORTED",
                    "BOTH_SEPARATE_SERIES",
                )
                and defn.reported_metric_code
            ):
                needed_reported_metrics.add(defn.reported_metric_code)
            if (
                payload.value_source_policy
                in (
                    "SYSTEM_DERIVED_ONLY",
                    "PREFER_SYSTEM_DERIVED",
                    "BOTH_SEPARATE_SERIES",
                )
                and defn.derived_formula_code
            ):
                needed_derived_formulas.add(defn.derived_formula_code)
            if payload.value_source_policy == "PREFER_SOURCE_REPORTED" and defn.derived_formula_code:
                needed_derived_formulas.add(defn.derived_formula_code)
            if payload.value_source_policy == "PREFER_SYSTEM_DERIVED" and defn.reported_metric_code:
                needed_reported_metrics.add(defn.reported_metric_code)

        # ── Query Source-Reported Facts ──
        facts_by_key: dict[tuple[UUID, UUID, str], FinancialFact] = {}
        fact_evidence_map: dict[UUID, UUID] = {}

        if needed_reported_metrics:
            fact_res = await db.execute(
                select(FinancialFact).where(
                    FinancialFact.organization_id == organization_id,
                    FinancialFact.institution_id.in_(payload.institution_ids),
                    FinancialFact.reporting_period_id.in_(payload.reporting_period_ids),
                    FinancialFact.metric_code.in_(list(needed_reported_metrics)),
                    FinancialFact.valid_to.is_(None),
                    FinancialFact.review_status == "HUMAN_VERIFIED",
                    FinancialFact.value_origin == "SOURCE_REPORTED",
                    FinancialFact.reporting_basis == payload.reporting_basis,
                )
            )
            for fact in fact_res.scalars().all():
                if fact.normalized_value is None:
                    continue
                if fact.unit not in ("PERCENT", "RATIO") and fact.currency != payload.currency:
                    raise ValueError("CURRENCY_MISMATCH")

                # Validate CandidateEvidence & format coordinates
                ev_res = await db.execute(
                    select(CandidateEvidence, DocumentVersion)
                    .join(
                        DocumentVersion,
                        CandidateEvidence.source_document_version_id == DocumentVersion.id,
                    )
                    .where(
                        CandidateEvidence.organization_id == organization_id,
                        CandidateEvidence.candidate_id == fact.source_candidate_id,
                    )
                    .order_by(
                        CandidateEvidence.page_number,
                        CandidateEvidence.row_index,
                        CandidateEvidence.column_index,
                        CandidateEvidence.created_at,
                        CandidateEvidence.id,
                    )
                )
                ev_list = ev_res.all()
                if not ev_list:
                    if payload.evidence_policy == "STRICT":
                        raise ValueError("EVIDENCE_INCOMPLETE")
                    continue

                # Coordinate verification for deterministic evidence
                valid_ev_id: UUID | None = None
                for cand_ev, doc_ver in ev_list:
                    if cls._validate_evidence_coordinates(cand_ev, doc_ver):
                        valid_ev_id = cand_ev.id
                        break

                if not valid_ev_id:
                    if payload.evidence_policy == "STRICT":
                        raise ValueError("EVIDENCE_FORMAT_COORDINATES_INVALID")
                    continue

                fact_evidence_map[fact.id] = valid_ev_id
                facts_by_key[(fact.institution_id, fact.reporting_period_id, fact.metric_code)] = fact

        # ── Query System-Derived Calculations ──
        calcs_by_key: dict[tuple[UUID, UUID, str], Calculation] = {}
        reconciliations_by_calc_id: dict[UUID, CalculationReconciliation] = {}

        if needed_derived_formulas:
            calc_res = await db.execute(
                select(Calculation, CalculationAttempt)
                .join(
                    CalculationAttempt,
                    Calculation.calculation_attempt_id == CalculationAttempt.id,
                )
                .where(
                    Calculation.organization_id == organization_id,
                    Calculation.institution_id.in_(payload.institution_ids),
                    Calculation.reporting_period_id.in_(payload.reporting_period_ids),
                    Calculation.formula_code.in_(list(needed_derived_formulas)),
                    Calculation.status == "COMPLETED",
                    CalculationAttempt.status == "COMPLETED",
                )
            )
            for calc, attempt in calc_res.all():
                # Lineage & Checksum validation
                if calc.organization_id != attempt.organization_id:
                    continue
                if calc.idempotency_hash != attempt.execution_idempotency_hash:
                    continue
                if calc.result_value_unrounded is None:
                    continue
                if not calc.result_unit or not calc.result_scale:
                    continue

                try:
                    FormulaRegistry.verify_checksum(
                        calc.formula_code,
                        calc.formula_version,
                        calc.formula_spec_checksum,
                        calc.implementation_checksum,
                    )
                except ValueError:
                    continue

                # CalculationInput validation
                inputs_res = await db.execute(
                    select(CalculationInput).where(
                        CalculationInput.calculation_id == calc.id,
                        CalculationInput.organization_id == organization_id,
                    )
                )
                calc_inputs = inputs_res.scalars().all()
                if not calc_inputs:
                    continue

                # CalculationEvidence validation
                ev_cnt_res = await db.execute(
                    select(CalculationEvidence).where(
                        CalculationEvidence.calculation_id == calc.id,
                        CalculationEvidence.organization_id == organization_id,
                    )
                )
                if not ev_cnt_res.scalars().all():
                    continue

                # Query CalculationReconciliation if present
                rec_res = await db.execute(
                    select(CalculationReconciliation).where(
                        CalculationReconciliation.calculation_id == calc.id,
                        CalculationReconciliation.organization_id == organization_id,
                    )
                )
                rec_obj = rec_res.scalar_one_or_none()
                if rec_obj:
                    reconciliations_by_calc_id[calc.id] = rec_obj

                calcs_by_key[(calc.institution_id, calc.reporting_period_id, calc.formula_code)] = calc

        scale_div = cls._scale_divisor(payload.display_scale)

        # ── Measure & Cell Assembly ──
        measures_map: dict[str, MeasureItemDTO] = {}
        all_dataset_rows: list[DatasetRowDTO] = []
        evidence_ref_ids: list[UUID] = []
        calc_ref_ids: list[UUID] = []
        dataset_warnings: list[dict[str, str]] = []

        populated_cells = 0
        missing_source_cells = 0
        excluded_ineligible_cells = 0
        excluded_mismatch_cells = 0
        warning_cells = 0

        src_reported_count = 0
        sys_derived_count = 0
        reconciliation_warning_count = 0

        # Construct target measure keys based on policy
        target_measures: list[
            tuple[
                str,
                SemanticMeasureDefinition,
                Literal["SOURCE_REPORTED", "SYSTEM_DERIVED"],
            ]
        ] = []

        for sem_code, sem_defn in semantic_defs.items():
            pol = payload.value_source_policy
            if pol == "BOTH_SEPARATE_SERIES":
                if sem_defn.reported_metric_code:
                    target_measures.append((f"{sem_code}:SOURCE_REPORTED", sem_defn, "SOURCE_REPORTED"))
                if sem_defn.derived_formula_code:
                    target_measures.append((f"{sem_code}:SYSTEM_DERIVED", sem_defn, "SYSTEM_DERIVED"))
            elif pol == "SOURCE_REPORTED_ONLY":
                if sem_defn.reported_metric_code:
                    target_measures.append((sem_code, sem_defn, "SOURCE_REPORTED"))
            elif pol == "SYSTEM_DERIVED_ONLY":
                if sem_defn.derived_formula_code:
                    target_measures.append((sem_code, sem_defn, "SYSTEM_DERIVED"))
            elif pol == "PREFER_SOURCE_REPORTED":
                target_measures.append((sem_code, sem_defn, "SOURCE_REPORTED"))
            elif pol == "PREFER_SYSTEM_DERIVED":
                target_measures.append((sem_code, sem_defn, "SYSTEM_DERIVED"))

        expected_cells = len(payload.institution_ids) * len(payload.reporting_period_ids) * len(target_measures)

        sorted_inst_ids = sorted(
            payload.institution_ids,
            key=lambda x: (institutions[x].display_name, str(x)),
        )
        sorted_period_ids = sorted(
            payload.reporting_period_ids,
            key=lambda x: (
                periods[x].start_date,
                periods[x].end_date,
                periods[x].period_type,
                str(x),
            ),
        )

        for inst_id in sorted_inst_ids:
            inst_obj = institutions[inst_id]
            for period_id in sorted_period_ids:
                period_obj = periods[period_id]
                row_cells: dict[str, DatasetRowCellDTO] = {}

                for m_key, sem_defn, default_origin in target_measures:
                    sem_code = sem_defn.semantic_measure_code
                    matched_fact = (
                        facts_by_key.get((inst_id, period_id, sem_defn.reported_metric_code))
                        if sem_defn.reported_metric_code
                        else None
                    )
                    matched_calc = (
                        calcs_by_key.get((inst_id, period_id, sem_defn.derived_formula_code))
                        if sem_defn.derived_formula_code
                        else None
                    )

                    selected_value: Decimal | None = None
                    value_origin: Literal["SOURCE_REPORTED", "SYSTEM_DERIVED"] = default_origin
                    fact_id: UUID | None = None
                    calc_id: UUID | None = None
                    evidence_id: UUID | None = None
                    warning_flag = False
                    warning_code: str | None = None
                    rec_status: (
                        Literal[
                            "RECONCILED",
                            "WITHIN_TOLERANCE",
                            "OUTSIDE_TOLERANCE",
                            "NO_SOURCE_REPORTED_COMPARISON",
                            "NOT_APPLICABLE",
                        ]
                        | None
                    ) = None

                    pol = payload.value_source_policy

                    if pol == "SOURCE_REPORTED_ONLY":
                        if matched_fact and matched_fact.normalized_value is not None:
                            selected_value = matched_fact.normalized_value
                            value_origin = "SOURCE_REPORTED"
                            fact_id = matched_fact.id
                            evidence_id = fact_evidence_map.get(matched_fact.id)

                    elif pol == "SYSTEM_DERIVED_ONLY":
                        if matched_calc and matched_calc.result_value_unrounded is not None:
                            selected_value = matched_calc.result_value_unrounded
                            value_origin = "SYSTEM_DERIVED"
                            calc_id = matched_calc.id

                    elif pol == "PREFER_SOURCE_REPORTED":
                        if matched_fact and matched_fact.normalized_value is not None:
                            selected_value = matched_fact.normalized_value
                            value_origin = "SOURCE_REPORTED"
                            fact_id = matched_fact.id
                            evidence_id = fact_evidence_map.get(matched_fact.id)
                        elif matched_calc and matched_calc.result_value_unrounded is not None:
                            selected_value = matched_calc.result_value_unrounded
                            value_origin = "SYSTEM_DERIVED"
                            calc_id = matched_calc.id

                    elif pol == "PREFER_SYSTEM_DERIVED":
                        if matched_calc and matched_calc.result_value_unrounded is not None:
                            selected_value = matched_calc.result_value_unrounded
                            value_origin = "SYSTEM_DERIVED"
                            calc_id = matched_calc.id
                        elif matched_fact and matched_fact.normalized_value is not None:
                            selected_value = matched_fact.normalized_value
                            value_origin = "SOURCE_REPORTED"
                            fact_id = matched_fact.id
                            evidence_id = fact_evidence_map.get(matched_fact.id)

                    elif pol == "BOTH_SEPARATE_SERIES":
                        if default_origin == "SOURCE_REPORTED":
                            if matched_fact and matched_fact.normalized_value is not None:
                                selected_value = matched_fact.normalized_value
                                value_origin = "SOURCE_REPORTED"
                                fact_id = matched_fact.id
                                evidence_id = fact_evidence_map.get(matched_fact.id)
                        else:
                            if matched_calc and matched_calc.result_value_unrounded is not None:
                                selected_value = matched_calc.result_value_unrounded
                                value_origin = "SYSTEM_DERIVED"
                                calc_id = matched_calc.id

                    # ── Derived Reconciliation Mapping ──
                    if calc_id and payload.include_reconciliation:
                        rec_obj = reconciliations_by_calc_id.get(calc_id)
                        if rec_obj:
                            raw_st = rec_obj.reconciliation_status
                            if raw_st in (
                                "RECONCILED",
                                "WITHIN_TOLERANCE",
                                "OUTSIDE_TOLERANCE",
                                "NO_SOURCE_REPORTED_COMPARISON",
                                "NOT_APPLICABLE",
                            ):
                                rec_status = raw_st  # type: ignore[assignment]
                            if rec_status == "OUTSIDE_TOLERANCE":
                                warning_flag = True
                                warning_code = "OUTSIDE_TOLERANCE"
                                reconciliation_warning_count += 1

                    if selected_value is not None:
                        unit = sem_defn.result_unit
                        disp_val = cls._format_display(selected_value, unit, scale_div)

                        if m_key not in measures_map:
                            measures_map[m_key] = MeasureItemDTO(
                                measure_code=m_key,
                                semantic_measure_code=sem_code,
                                label=sem_defn.display_name,
                                unit=unit,
                                currency=payload.currency if unit == "CURRENCY" else None,
                                scale=payload.display_scale,
                                value_origin=value_origin,
                                formula_code=sem_defn.derived_formula_code
                                if value_origin == "SYSTEM_DERIVED"
                                else None,
                            )

                        if evidence_id:
                            evidence_ref_ids.append(evidence_id)
                        if calc_id:
                            calc_ref_ids.append(calc_id)

                        populated_cells += 1
                        if warning_flag:
                            warning_cells += 1
                        if value_origin == "SOURCE_REPORTED":
                            src_reported_count += 1
                        else:
                            sys_derived_count += 1

                        row_cells[m_key] = DatasetRowCellDTO(
                            measure_code=m_key,
                            semantic_measure_code=sem_code,
                            canonical_value=str(selected_value),
                            display_value=disp_val,
                            value_origin=value_origin,
                            fact_id=fact_id,
                            calculation_id=calc_id,
                            evidence_id=evidence_id,
                            reconciliation_status=rec_status,
                            warning_flag=warning_flag,
                            warning_code=warning_code,
                        )
                    else:
                        missing_source_cells += 1
                        if payload.common_period_policy == "STRICT_COMMON_PERIOD":
                            raise ValueError("INCOMPLETE_COMMON_PERIOD")
                        if payload.common_period_policy == "ALLOW_PARTIAL_WITH_WARNINGS":
                            dataset_warnings.append(
                                {
                                    "code": "MISSING_DATA_POINT",
                                    "message": f"Data missing for {inst_obj.display_name} ({period_obj.label})",
                                    "institution": inst_obj.display_name,
                                    "period": period_obj.label,
                                    "measure": sem_defn.display_name,
                                }
                            )

                if row_cells:
                    row_key = f"{inst_id}:{period_id}"
                    all_dataset_rows.append(
                        DatasetRowDTO(
                            row_id=row_key,
                            institution_id=inst_id,
                            institution_name=inst_obj.display_name,
                            reporting_period_id=period_id,
                            period_label=period_obj.label,
                            reporting_basis=payload.reporting_basis,
                            cells=row_cells,
                        )
                    )

        # ── Deterministic Sorting ──
        sort_measure_key = payload.sort_measure_code or (next(iter(measures_map.keys())) if measures_map else None)

        def _sort_key(r: DatasetRowDTO) -> tuple[Decimal, str, str]:
            if sort_measure_key and sort_measure_key in r.cells:
                cell = r.cells[sort_measure_key]
                val = cls._safe_decimal(cell.canonical_value)
                if payload.sort_direction == "desc":
                    val = -val
            else:
                val = Decimal(0)
            return (val, r.institution_name, r.row_id)

        all_dataset_rows.sort(key=_sort_key)

        # ── Top-N Scope Handling ──
        if payload.top_n is not None:
            if payload.top_n_scope == "DATASET_ROWS_GLOBAL":
                all_dataset_rows = all_dataset_rows[: payload.top_n]
            elif payload.top_n_scope == "INSTITUTIONS_PER_PERIOD":
                # Filter top N institutions per period group
                period_counts: dict[UUID, int] = {}
                filtered_rows: list[DatasetRowDTO] = []
                for r in all_dataset_rows:
                    cnt = period_counts.get(r.reporting_period_id, 0)
                    if cnt < payload.top_n:
                        filtered_rows.append(r)
                        period_counts[r.reporting_period_id] = cnt + 1
                all_dataset_rows = filtered_rows

        total_rows = len(all_dataset_rows)

        # ── Server-side Pagination ──
        start_idx = (payload.page - 1) * payload.page_size
        end_idx = start_idx + payload.page_size
        paginated_rows = all_dataset_rows[start_idx:end_idx]

        pagination = cls._make_pagination(total_rows, payload.page, payload.page_size)

        # ── Data Quality Summary Invariant Check ──
        sum_cells = populated_cells + missing_source_cells + excluded_ineligible_cells + excluded_mismatch_cells
        if expected_cells != sum_cells:
            raise ValueError(f"DATA_QUALITY_INVARIANT_VIOLATED: expected ({expected_cells}) != sum ({sum_cells})")

        if expected_cells > 0:
            comp_pct = (Decimal(str(populated_cells)) / Decimal(str(expected_cells))) * Decimal(100)
            completeness_str = str(comp_pct.quantize(Decimal("0.01")))
        else:
            completeness_str = "0.00"

        data_quality = DataQualitySummaryDTO(
            expected_cells=expected_cells,
            populated_cells=populated_cells,
            missing_source_cells=missing_source_cells,
            excluded_ineligible_cells=excluded_ineligible_cells,
            excluded_mismatch_cells=excluded_mismatch_cells,
            warning_cells=warning_cells,
            source_reported_count=src_reported_count,
            system_derived_count=sys_derived_count,
            reconciliation_warning_count=reconciliation_warning_count,
            completeness_percentage=completeness_str,
        )

        run_id = uuid4()
        dataset_id = uuid4()
        now_dt = datetime.now(UTC)

        query_snap = QuerySnapshotDTO(
            institution_ids=payload.institution_ids,
            semantic_measures=[
                {"code": s.semantic_measure_code, "preferred_origin": s.preferred_origin}
                for s in payload.semantic_measures
            ],
            reporting_period_ids=payload.reporting_period_ids,
            reporting_basis=payload.reporting_basis,
            currency=payload.currency,
            display_scale=payload.display_scale,
            value_source_policy=payload.value_source_policy,
            sort_measure_code=payload.sort_measure_code,
            sort_origin=payload.sort_origin,
            sort_direction=payload.sort_direction,
            top_n_scope=payload.top_n_scope,
            comparison_mode=payload.comparison_mode,
            common_period_policy=payload.common_period_policy,
            evidence_policy=payload.evidence_policy,
            top_n=payload.top_n,
            page=payload.page,
            page_size=payload.page_size,
        )

        result_dataset = ResultDatasetDTO(
            result_dataset_id=dataset_id,
            schema_version="3.0.0",
            generated_at=now_dt,
            query_snapshot=query_snap,
            value_source_policy=payload.value_source_policy,
            dimensions={
                "institutions_count": len(payload.institution_ids),
                "periods_count": len(payload.reporting_period_ids),
                "measures_count": len(measures_map),
            },
            measures=list(measures_map.values()),
            rows=paginated_rows,
            data_quality_summary=data_quality,
            warnings=dataset_warnings,
            evidence_references=list(set(evidence_ref_ids)),
            calculation_references=list(set(calc_ref_ids)),
            pagination=pagination,
        )

        # ── TableSpec (Paginated Rows) ──
        table_cols = [
            TableColumnDTO(
                key="institution_name",
                title="Institution",
                data_type="string",
                alignment="left",
                unit_label="Text",
            ),
            TableColumnDTO(
                key="period_label",
                title="Period",
                data_type="string",
                alignment="left",
                unit_label="Text",
            ),
        ]
        for m in measures_map.values():
            table_cols.append(
                TableColumnDTO(
                    key=m.measure_code,
                    title=m.label,
                    data_type="decimal" if m.unit not in ("PERCENT", "RATIO") else "percent",
                    alignment="right",
                    unit_label=f"{m.currency or ''} ({m.scale})" if m.unit not in ("PERCENT", "RATIO") else "%",
                )
            )

        table_rows: list[TableRowDTO] = []
        for d_row in paginated_rows:
            t_cells: dict[str, TableCellDTO] = {}
            for m_key, cell_dto in d_row.cells.items():
                t_cells[m_key] = TableCellDTO(
                    raw_value=cell_dto.canonical_value,
                    display_text=cell_dto.display_value,
                    value_origin=cell_dto.value_origin,
                    reconciliation_status=cell_dto.reconciliation_status,
                    warning_flag=cell_dto.warning_flag,
                    warning_code=cell_dto.warning_code,
                    evidence_id=cell_dto.evidence_id,
                )
            table_rows.append(
                TableRowDTO(
                    row_id=d_row.row_id,
                    institution_name=d_row.institution_name,
                    period_label=d_row.period_label,
                    cells=t_cells,
                )
            )

        table_spec = TableSpecDTO(
            result_dataset_id=dataset_id,
            schema_version="3.0.0",
            columns=table_cols,
            rows=table_rows,
            pagination=pagination,
        )

        # ── ChartSpecs (Paginated View Alignment) ──
        chart_specs: list[ChartSpecDTO] = []
        unit_groups: dict[str, list[str]] = {}
        for m_key, m_item in measures_map.items():
            unit_groups.setdefault(m_item.unit, []).append(m_key)

        for c_type in payload.chart_types:
            for unit_key, m_keys_in_group in unit_groups.items():
                c_series: list[ChartSeriesDTO] = []
                chart_warnings: list[str] = []

                for m_key in m_keys_in_group:
                    m_item = measures_map[m_key]
                    pts: list[ChartSeriesItemDTO] = []
                    for d_row in paginated_rows:
                        c_cell = d_row.cells.get(m_key)
                        if c_cell:
                            pts.append(
                                ChartSeriesItemDTO(
                                    x=f"{d_row.institution_name} ({d_row.period_label})",
                                    y=c_cell.canonical_value,
                                    display_value=c_cell.display_value,
                                    label=m_item.label,
                                    evidence_id=c_cell.evidence_id,
                                    warning_flag=c_cell.warning_flag,
                                    warning_code=c_cell.warning_code,
                                )
                            )
                            if c_cell.warning_flag and c_cell.warning_code:
                                chart_warnings.append(c_cell.warning_code)
                    c_series.append(
                        ChartSeriesDTO(
                            series_name=m_item.label,
                            semantic_measure_code=m_item.semantic_measure_code,
                            measure_code=m_key,
                            unit=m_item.unit,
                            currency=m_item.currency,
                            data_points=pts,
                        )
                    )

                y_label = unit_key if unit_key in ("PERCENT", "RATIO") else payload.display_scale
                chart_specs.append(
                    ChartSpecDTO(
                        result_dataset_id=dataset_id,
                        chart_type=c_type,
                        title=", ".join(measures_map[k].label for k in m_keys_in_group),
                        subtitle=f"Basis: {payload.reporting_basis} | Scale: {payload.display_scale}",
                        x_axis_label="Institution / Period",
                        y_axis_label=y_label,
                        unit=unit_key,
                        currency=payload.currency if unit_key not in ("PERCENT", "RATIO") else None,
                        series=c_series,
                        warning_annotations=list(set(chart_warnings)),
                    )
                )

        # ── Persist Full Dataset Snapshot ──
        comp_run_obj = ComparisonRun(
            id=run_id,
            organization_id=organization_id,
            requested_by_user_id=requested_by_user_id,
            comparison_mode=payload.comparison_mode,
            value_source_policy=payload.value_source_policy,
            query_snapshot=query_snap.model_dump(mode="json"),
            created_at=now_dt,
        )
        db.add(comp_run_obj)
        await db.flush()

        ds_model_obj = ResultDatasetModel(
            id=dataset_id,
            organization_id=organization_id,
            comparison_run_id=run_id,
            schema_version="3.0.0",
            query_snapshot=query_snap.model_dump(mode="json"),
            dimensions_snapshot=result_dataset.dimensions,
            measures_snapshot=[m.model_dump(mode="json") for m in result_dataset.measures],
            rows_snapshot=[r.model_dump(mode="json") for r in all_dataset_rows],
            table_spec_snapshot=table_spec.model_dump(mode="json"),
            chart_specs_snapshot=[cs.model_dump(mode="json") for cs in chart_specs],
            data_quality_summary=data_quality.model_dump(mode="json"),
            warnings_snapshot=dataset_warnings,
            created_at=now_dt,
        )
        db.add(ds_model_obj)

        await AuditService.record_event(
            db=db,
            organization_id=organization_id,
            event_type="COMPARISON_COMPLETED",
            target_type="COMPARISON_RUN",
            target_id=run_id,
            actor_id=requested_by_user_id,
            payload={"comparison_mode": payload.comparison_mode, "total_rows": total_rows},
        )
        await db.commit()

        return ComparisonResponseDTO(
            comparison_id=run_id,
            result_dataset=result_dataset,
            table_spec=table_spec,
            chart_specs=chart_specs,
        )

    # ──────────────────────────── get_filter_metadata ────────────────────────────

    @classmethod
    async def get_filter_metadata(cls, db: AsyncSession, organization_id: UUID) -> ComparisonFiltersDTO:
        await db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(organization_id)},
        )

        inst_res = await db.execute(select(Institution).where(Institution.organization_id == organization_id))
        inst_list = [{"id": str(i.id), "name": i.display_name} for i in inst_res.scalars().all()]

        period_res = await db.execute(
            select(ReportingPeriod)
            .where(ReportingPeriod.organization_id == organization_id)
            .order_by(ReportingPeriod.start_date, ReportingPeriod.end_date)
        )
        period_list = [{"id": str(p.id), "name": p.label} for p in period_res.scalars().all()]

        sem_measures = [
            {"code": d.semantic_measure_code, "name": d.display_name, "unit": d.result_unit}
            for d in SemanticMeasureRegistry.list_all()
        ]

        has_data = len(inst_list) > 0 and len(period_list) > 0

        return ComparisonFiltersDTO(
            supported_institutions=inst_list,
            supported_reporting_periods=period_list,
            supported_semantic_measures=sem_measures,
            supported_reporting_bases=["SOLO", "CONSOLIDATED"],
            supported_currencies=["TRY", "USD", "EUR"],
            supported_scales=["ONE", "THOUSAND", "MILLION", "BILLION"],
            supported_source_policies=[
                "SOURCE_REPORTED_ONLY",
                "SYSTEM_DERIVED_ONLY",
                "PREFER_SOURCE_REPORTED",
                "PREFER_SYSTEM_DERIVED",
                "BOTH_SEPARATE_SERIES",
            ],
            supported_chart_types=["horizontal_bar", "vertical_bar", "grouped_bar", "line"],
            supported_top_n_scopes=["INSTITUTIONS_PER_PERIOD", "DATASET_ROWS_GLOBAL"],
            supported_common_period_policies=["STRICT_COMMON_PERIOD", "ALLOW_PARTIAL_WITH_WARNINGS"],
            supported_evidence_policies=["STRICT", "PARTIAL"],
            is_data_backed=has_data,
        )

    # ──────────────────────────── get_evidence_detail ────────────────────────────

    @classmethod
    async def get_evidence_detail(cls, db: AsyncSession, organization_id: UUID, evidence_id: UUID) -> EvidenceDetailDTO:
        await db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(organization_id)},
        )

        ev_res = await db.execute(
            select(CandidateEvidence).where(
                CandidateEvidence.id == evidence_id,
                CandidateEvidence.organization_id == organization_id,
            )
        )
        cand_ev = ev_res.scalar_one_or_none()
        if not cand_ev:
            raise ValueError("EVIDENCE_NOT_FOUND")

        cand_res = await db.execute(
            select(FinancialFactCandidate).where(
                FinancialFactCandidate.id == cand_ev.candidate_id,
                FinancialFactCandidate.organization_id == organization_id,
            )
        )
        candidate = cand_res.scalar_one_or_none()

        doc_ver_res = await db.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == cand_ev.source_document_version_id,
                DocumentVersion.organization_id == organization_id,
            )
        )
        doc_ver = doc_ver_res.scalar_one_or_none()

        doc_title: str | None = None
        verified_mime: str | None = None
        mime_is_verified = False

        if doc_ver:
            doc_res = await db.execute(
                select(Document).where(
                    Document.id == doc_ver.document_id,
                    Document.organization_id == organization_id,
                )
            )
            doc = doc_res.scalar_one_or_none()
            if doc:
                doc_title = doc.display_name
            if doc_ver.detected_mime_type:
                verified_mime = doc_ver.detected_mime_type
                mime_is_verified = True

        # Classification policy check & snippet masking
        raw_snippet = cand_ev.raw_snippet or ""
        snippet: str | None = raw_snippet[:2000] if raw_snippet else None
        is_masked = False
        classification = "CONFIDENTIAL"

        if snippet and ("TCKN" in snippet or "SECRET" in snippet):
            snippet = "[MASKED PERSONAL DATA]"
            is_masked = True
            classification = "STRICTLY_CONFIDENTIAL"

        extraction_method: str | None = getattr(candidate, "extraction_method", None)
        confidence_score: str | None = (
            str(candidate.confidence_score) if candidate and candidate.confidence_score else None
        )
        review_status: str | None = getattr(candidate, "review_status", None)

        return EvidenceDetailDTO(
            evidence_id=cand_ev.id,
            document_title=doc_title,
            document_version_id=cand_ev.source_document_version_id,
            mime_type=verified_mime,
            mime_verified=mime_is_verified,
            page_number=cand_ev.page_number,
            sheet_name=cand_ev.sheet_name,
            cell_coordinate=cand_ev.cell_coordinate,
            row_index=cand_ev.row_index,
            column_index=cand_ev.column_index,
            bounding_box=cand_ev.bounding_box,
            sanitized_snippet=snippet,
            extraction_method=extraction_method,
            confidence_score=confidence_score,
            review_status=review_status,
            source_authority=None,
            classification=classification,
            is_masked=is_masked,
        )
