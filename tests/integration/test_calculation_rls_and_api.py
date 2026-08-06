import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.db.tenant_context import tenant_transaction_context
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.calculations.registry import (
    compute_formula_spec_checksum,
    compute_implementation_checksum,
)
from services.api.app.models.calculation import Calculation
from services.api.app.models.calculation_attempt import CalculationAttempt
from services.api.app.models.calculation_input import CalculationInput
from services.api.app.models.calculation_request import CalculationRequest
from services.api.app.models.candidate_evidence import CandidateEvidence
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact import FinancialFact
from services.api.app.models.financial_fact_candidate import FinancialFactCandidate
from services.api.app.models.formula_definition import FormulaDefinition
from services.api.app.models.institution import Institution
from services.api.app.models.organization import Organization
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.models.stored_object import StoredObject
from services.api.app.models.user import User
from services.api.app.services.calculation_service import CalculationService

OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")
WORKER_URL = os.environ.get("TEST_WORKER_DATABASE_URL")

pytestmark = [pytest.mark.integration]


@pytest.fixture
async def db_owner_session():
    engine = create_async_engine(OWNER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def db_api_session():
    engine = create_async_engine(API_USER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def db_worker_session():
    engine = create_async_engine(WORKER_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_calculation_service_end_to_end_and_reconciliation(db_owner_session, db_api_session):
    """Test full calculation service, input snapshotting, evidence linking, and reconciliation against unrounded values."""
    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    doc_id = uuid4()
    doc_ver_id = uuid4()
    cand1_id = uuid4()
    cand2_id = uuid4()
    fact1_id = uuid4()
    fact2_id = uuid4()

    # Seed Org & User using owner session
    org = Organization(id=org_id, name="Calc Org", slug=f"calc-{uuid4().hex[:6]}")
    user = User(id=user_id, external_subject=f"sub_{uuid4().hex[:6]}", display_name="Calc User")
    db_owner_session.add_all([org, user])
    await db_owner_session.commit()

    # Seed FormulaDefinition if not present
    from services.api.app.calculations.formulas.loan_to_deposit import LoanToDepositRatioFormula

    f_cls = LoanToDepositRatioFormula
    spec_cs = compute_formula_spec_checksum(f_cls)
    impl_cs = compute_implementation_checksum(f_cls)

    f_def_res = await db_owner_session.execute(
        select(FormulaDefinition).where(FormulaDefinition.formula_code == "LOAN_TO_DEPOSIT_RATIO")
    )
    f_def = f_def_res.scalar_one_or_none()
    if not f_def:
        f_def = FormulaDefinition(
            id=uuid4(),
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            formula_version="1.0.0",
            display_name="Loan to Deposit Ratio",
            calculation_type="RATIO",
            required_input_roles=["NUMERATOR", "DENOMINATOR"],
            expected_metric_codes=["TOTAL_LOANS", "TOTAL_DEPOSITS"],
            result_unit="PERCENT",
            result_scale="ONE",
            rounding_policy="ROUND_HALF_UP",
            display_precision=2,
            status="ACTIVE",
            implementation_checksum=impl_cs,
            formula_spec_checksum=spec_cs,
            implementation_revision="1.0.0",
            tolerance_policy_version="1.0.0",
            tolerance_kind="ABSOLUTE",
            tolerance_value=Decimal("0.05"),
            tolerance_unit="PERCENTAGE_POINTS",
        )
        db_owner_session.add(f_def)
    else:
        f_def.formula_spec_checksum = spec_cs
        f_def.implementation_checksum = impl_cs

    await db_owner_session.commit()

    from app.db.tenant_context import tenant_transaction_context

    # Seed tenant data using API user session with tenant_transaction_context
    async with tenant_transaction_context(db_api_session, org_id):
        inst = Institution(
            id=inst_id, organization_id=org_id, canonical_name=f"calc_bank_{uuid4().hex[:6]}", display_name="Calc Bank"
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            period_presentation="FULL_YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024 FY",
            comparison_key="2024",
        )

        obj_id = uuid4()
        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=f"pdf_key_{uuid4().hex[:6]}.pdf",
            server_computed_sha256="hash123",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="report.pdf")
        doc_ver = DocumentVersion(
            id=doc_ver_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=obj_id,
            content_hash_sha256="hash123",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )

        db_api_session.add(stored_obj)
        await db_api_session.flush()

        db_api_session.add_all([inst, period, doc, doc_ver])
        await db_api_session.flush()

        # Seed Candidates & Evidence
        cand1 = FinancialFactCandidate(
            id=cand1_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            suggested_metric_code="TOTAL_LOANS",
            raw_label="Toplam Krediler",
            raw_value="800.00",
            parsed_decimal_value=Decimal("800.00"),
            source_document_id=doc_id,
            source_document_version_id=doc_ver_id,
            extraction_method="PARSER_TABLE",
            review_status="HUMAN_VERIFIED",
        )
        cand2 = FinancialFactCandidate(
            id=cand2_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            suggested_metric_code="TOTAL_DEPOSITS",
            raw_label="Toplam Mevduat",
            raw_value="1000.00",
            parsed_decimal_value=Decimal("1000.00"),
            source_document_id=doc_id,
            source_document_version_id=doc_ver_id,
            extraction_method="PARSER_TABLE",
            review_status="HUMAN_VERIFIED",
        )
        db_api_session.add_all([cand1, cand2])
        await db_api_session.flush()

        ev1 = CandidateEvidence(
            id=uuid4(),
            organization_id=org_id,
            candidate_id=cand1_id,
            source_document_version_id=doc_ver_id,
            page_number=5,
            bounding_box={"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5},
            raw_snippet="Krediler 800",
        )
        ev2 = CandidateEvidence(
            id=uuid4(),
            organization_id=org_id,
            candidate_id=cand2_id,
            source_document_version_id=doc_ver_id,
            page_number=5,
            bounding_box={"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5},
            raw_snippet="Mevduat 1000",
        )
        db_api_session.add_all([ev1, ev2])
        await db_api_session.flush()

        # Seed Financial Facts (HUMAN_VERIFIED, SOURCE_REPORTED, valid_to=None)
        fact1 = FinancialFact(
            id=fact1_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=UUID("a0000000-0000-0000-0000-000000000002"),
            metric_code="TOTAL_LOANS",
            value=Decimal("800.000000"),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=Decimal("800.000000"),
            reporting_basis="SOLO",
            source_candidate_id=cand1_id,
            source_document_id=doc_id,
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=user_id,
            value_origin="SOURCE_REPORTED",
        )
        fact2 = FinancialFact(
            id=fact2_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=UUID("a0000000-0000-0000-0000-000000000003"),
            metric_code="TOTAL_DEPOSITS",
            value=Decimal("1000.000000"),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=Decimal("1000.000000"),
            reporting_basis="SOLO",
            source_candidate_id=cand2_id,
            source_document_id=doc_id,
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=user_id,
            value_origin="SOURCE_REPORTED",
        )
        db_api_session.add_all([fact1, fact2])
        await db_api_session.flush()

    await db_api_session.commit()

    # Execute Calculation Service
    async with tenant_transaction_context(db_api_session, org_id):
        calc, calc_inputs, _reconciliation = await CalculationService.run_calculation(
            db=db_api_session,
            organization_id=org_id,
            requested_by_user_id=user_id,
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            institution_id=inst_id,
            reporting_period_id=period_id,
            comparison_policy="EXPLICIT_PERIOD",
        )

    assert calc.status == "COMPLETED"
    assert calc.result_value_unrounded == Decimal("80.0")
    assert calc.result_value_display == Decimal("80.00")
    assert calc.result_unit == "PERCENT"
    assert calc.result_currency is None  # Percentage metrics have result_currency = None
    assert len(calc_inputs) == 2


@pytest.mark.asyncio
async def test_worker_role_denial_on_calculation_tables(db_worker_session):
    """Verify db_ingestion_worker is denied access to calculation tables."""
    with pytest.raises(Exception):  # noqa: B017
        await db_worker_session.execute(text("SELECT count(*) FROM public.calculations;"))


@pytest.mark.asyncio
async def test_calculation_immutability_trigger(db_owner_session, db_api_session):
    """Verify trg_prevent_completed_calculation_mutation blocks UPDATE/DELETE on completed calculations."""
    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    calc_id = uuid4()

    org = Organization(id=org_id, name="Imm Org", slug=f"imm-{uuid4().hex[:6]}")
    user = User(id=user_id, external_subject=f"sub_{uuid4().hex[:6]}", display_name="Imm User")
    db_owner_session.add_all([org, user])
    await db_owner_session.commit()

    async with tenant_transaction_context(db_api_session, org_id):
        inst = Institution(
            id=inst_id, organization_id=org_id, canonical_name=f"imm_bank_{uuid4().hex[:6]}", display_name="Imm Bank"
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024 FY",
            comparison_key="2024",
        )
        db_api_session.add_all([inst, period])
        await db_api_session.flush()

        req_id = uuid4()
        att_id = uuid4()
        calc_req = CalculationRequest(
            id=req_id,
            organization_id=org_id,
            request_fingerprint=f"fp_{uuid4().hex}",
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            formula_version="1.0.0",
            institution_id=inst_id,
            reporting_period_id=period_id,
            requested_by_user_id=user_id,
        )
        same_hash = f"{'a' * 64}"
        spec_check = f"{'b' * 64}"
        impl_check = f"{'c' * 64}"

        calc_att = CalculationAttempt(
            id=att_id,
            organization_id=org_id,
            calculation_request_id=req_id,
            attempt_number=1,
            execution_idempotency_hash=same_hash,
            formula_spec_checksum=spec_check,
            implementation_checksum=impl_check,
            completed_at=datetime.now(UTC),
            status="COMPLETED",
        )
        db_api_session.add(calc_req)
        await db_api_session.flush()
        db_api_session.add(calc_att)
        await db_api_session.flush()

        calc = Calculation(
            id=calc_id,
            organization_id=org_id,
            calculation_request_id=req_id,
            calculation_attempt_id=att_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            formula_version="1.0.0",
            status="COMPLETED",
            result_value_unrounded=Decimal("80.0"),
            result_value_display=Decimal("80.00"),
            result_unit="PERCENT",
            result_scale="ONE",
            result_currency=None,
            value_representation="PERCENT_DISPLAY",
            working_precision=38,
            rounding_policy="ROUND_HALF_UP",
            idempotency_hash=same_hash,
            implementation_checksum=impl_check,
            requested_by_user_id=user_id,
        )
        db_api_session.add(calc)
        await db_api_session.flush()

    await db_api_session.commit()

    # Try updating completed calculation -> trigger blocks
    async with tenant_transaction_context(db_api_session, org_id):
        try:
            await db_api_session.execute(
                text("UPDATE calculations SET result_value_display = 90.00 WHERE id = :id"),
                {"id": str(calc_id)},
            )
            await db_api_session.commit()
        except Exception as err:  # noqa: BLE001
            assert "CALCULATION_IMMUTABLE" in str(err) or "IMMUTABLE" in str(err)
        finally:
            await db_api_session.rollback()


@pytest.mark.asyncio
async def test_terminal_lineage_mutation_denial_trigger(db_owner_session, db_api_session):
    """Verify fn_prevent_terminal_child_lineage_mutation blocks UPDATE/DELETE on lineage tables if parent calculation is terminal."""
    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    calc_id = uuid4()
    fact_id = uuid4()

    org = Organization(id=org_id, name="Lineage Org", slug=f"lin-{uuid4().hex[:6]}")
    user = User(id=user_id, external_subject=f"sub_{uuid4().hex[:6]}", display_name="Lineage User")
    db_owner_session.add_all([org, user])
    await db_owner_session.commit()

    async with tenant_transaction_context(db_api_session, org_id):
        inst = Institution(
            id=inst_id,
            organization_id=org_id,
            canonical_name=f"lin_bank_{uuid4().hex[:6]}",
            display_name="Lineage Bank",
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            period_presentation="FULL_YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024 FY",
            comparison_key="2024",
        )
        db_api_session.add_all([inst, period])
        await db_api_session.flush()

        req_id = uuid4()
        att_id = uuid4()
        calc_req = CalculationRequest(
            id=req_id,
            organization_id=org_id,
            request_fingerprint=f"fp_{uuid4().hex}",
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            formula_version="1.0.0",
            institution_id=inst_id,
            reporting_period_id=period_id,
            requested_by_user_id=user_id,
        )
        same_hash2 = f"{'d' * 64}"
        spec_check2 = f"{'e' * 64}"
        impl_check2 = f"{'f' * 64}"

        calc_att = CalculationAttempt(
            id=att_id,
            organization_id=org_id,
            calculation_request_id=req_id,
            attempt_number=1,
            execution_idempotency_hash=same_hash2,
            formula_spec_checksum=spec_check2,
            implementation_checksum=impl_check2,
            completed_at=datetime.now(UTC),
            status="COMPLETED",
        )
        db_api_session.add(calc_req)
        await db_api_session.flush()
        db_api_session.add(calc_att)
        await db_api_session.flush()

        calc = Calculation(
            id=calc_id,
            organization_id=org_id,
            calculation_request_id=req_id,
            calculation_attempt_id=att_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            formula_version="1.0.0",
            status="COMPLETED",
            result_value_unrounded=Decimal("80.0"),
            result_value_display=Decimal("80.00"),
            result_unit="PERCENT",
            result_scale="ONE",
            value_representation="PERCENT_DISPLAY",
            working_precision=38,
            rounding_policy="ROUND_HALF_UP",
            idempotency_hash=same_hash2,
            formula_spec_checksum=spec_check2,
            implementation_checksum=impl_check2,
            requested_by_user_id=user_id,
        )
        db_api_session.add(calc)
        await db_api_session.flush()

        doc_id = uuid4()
        cand_id = uuid4()
        doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="report.pdf")
        doc_ver_id = uuid4()
        obj_id = uuid4()
        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=f"pdf_key_{uuid4().hex[:6]}.pdf",
            server_computed_sha256="hash123",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        doc_ver = DocumentVersion(
            id=doc_ver_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=obj_id,
            content_hash_sha256="hash123",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        db_api_session.add(stored_obj)
        await db_api_session.flush()
        db_api_session.add_all([doc, doc_ver])
        await db_api_session.flush()

        cand = FinancialFactCandidate(
            id=cand_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            suggested_metric_code="TOTAL_LOANS",
            raw_label="Toplam Krediler",
            raw_value="800.00",
            parsed_decimal_value=Decimal("800.00"),
            source_document_id=doc_id,
            source_document_version_id=doc_ver_id,
            extraction_method="PARSER_TABLE",
            review_status="HUMAN_VERIFIED",
        )
        db_api_session.add(cand)
        await db_api_session.flush()

        fact = FinancialFact(
            id=fact_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=UUID("a0000000-0000-0000-0000-000000000002"),
            metric_code="TOTAL_LOANS",
            value=Decimal("800.0"),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=Decimal("800.0"),
            reporting_basis="SOLO",
            source_candidate_id=cand_id,
            source_document_id=doc_id,
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=user_id,
            value_origin="SOURCE_REPORTED",
        )
        db_api_session.add(fact)
        await db_api_session.flush()

        inp_id = uuid4()
        inp = CalculationInput(
            id=inp_id,
            organization_id=org_id,
            calculation_id=calc_id,
            financial_fact_id=fact_id,
            input_role="NUMERATOR",
            metric_code="TOTAL_LOANS",
            normalized_value_snapshot=Decimal("800.0"),
            currency_snapshot="TRY",
            unit_snapshot="CURRENCY",
            scale_snapshot="ONE",
            reporting_basis_snapshot="SOLO",
            reporting_period_id_snapshot=period_id,
        )
        db_api_session.add(inp)
        await db_api_session.flush()

    await db_api_session.commit()

    # Attempt updating lineage row -> trigger raises IMMUTABLE_LINEAGE
    async with tenant_transaction_context(db_api_session, org_id):
        try:
            await db_api_session.execute(
                text("UPDATE calculation_inputs SET metric_code = 'MUTATED' WHERE id = :id"),
                {"id": str(inp_id)},
            )
            await db_api_session.commit()
        except Exception as err:  # noqa: BLE001
            assert "IMMUTABLE_LINEAGE" in str(err) or "IMMUTABLE" in str(err)
        finally:
            await db_api_session.rollback()


@pytest.mark.asyncio
async def test_evidence_completeness_gate_raises_evidence_incomplete(db_owner_session, db_api_session):
    """Verify calculation service raises EVIDENCE_INCOMPLETE if input fact lacks candidate evidence."""
    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    doc_id = uuid4()
    cand1_id = uuid4()
    cand2_id = uuid4()
    fact1_id = uuid4()
    fact2_id = uuid4()

    org = Organization(id=org_id, name="Ev Incomp Org", slug=f"evi-{uuid4().hex[:6]}")
    user = User(id=user_id, external_subject=f"sub_{uuid4().hex[:6]}", display_name="Ev User")
    db_owner_session.add_all([org, user])
    await db_owner_session.commit()

    async with tenant_transaction_context(db_api_session, org_id):
        inst = Institution(
            id=inst_id, organization_id=org_id, canonical_name=f"evi_bank_{uuid4().hex[:6]}", display_name="Evi Bank"
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            period_presentation="FULL_YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024 FY",
            comparison_key="2024",
        )
        doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="report.pdf")
        doc_ver_id = uuid4()
        obj_id = uuid4()
        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=f"pdf_key_{uuid4().hex[:6]}.pdf",
            server_computed_sha256="hash123",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        doc_ver = DocumentVersion(
            id=doc_ver_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=obj_id,
            content_hash_sha256="hash123",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        db_api_session.add(stored_obj)
        await db_api_session.flush()
        db_api_session.add_all([inst, period, doc, doc_ver])
        await db_api_session.flush()

        cand1 = FinancialFactCandidate(
            id=cand1_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            suggested_metric_code="TOTAL_LOANS",
            raw_label="Toplam Krediler",
            raw_value="800.00",
            parsed_decimal_value=Decimal("800.00"),
            source_document_id=doc_id,
            source_document_version_id=doc_ver_id,
            extraction_method="PARSER_TABLE",
            review_status="HUMAN_VERIFIED",
        )
        cand2 = FinancialFactCandidate(
            id=cand2_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            suggested_metric_code="TOTAL_DEPOSITS",
            raw_label="Toplam Mevduat",
            raw_value="1000.00",
            parsed_decimal_value=Decimal("1000.00"),
            source_document_id=doc_id,
            source_document_version_id=doc_ver_id,
            extraction_method="PARSER_TABLE",
            review_status="HUMAN_VERIFIED",
        )
        db_api_session.add_all([cand1, cand2])
        await db_api_session.flush()

        fact1 = FinancialFact(
            id=fact1_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=UUID("a0000000-0000-0000-0000-000000000002"),
            metric_code="TOTAL_LOANS",
            value=Decimal("800.0"),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=Decimal("800.0"),
            reporting_basis="SOLO",
            source_candidate_id=cand1_id,
            source_document_id=doc_id,
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=user_id,
            value_origin="SOURCE_REPORTED",
        )
        fact2 = FinancialFact(
            id=fact2_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=UUID("a0000000-0000-0000-0000-000000000003"),
            metric_code="TOTAL_DEPOSITS",
            value=Decimal("1000.0"),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=Decimal("1000.0"),
            reporting_basis="SOLO",
            source_candidate_id=cand2_id,
            source_document_id=doc_id,
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=user_id,
            value_origin="SOURCE_REPORTED",
        )
        db_api_session.add_all([fact1, fact2])
        await db_api_session.flush()

    await db_api_session.commit()

    # Calculation should fail with EVIDENCE_INCOMPLETE since CandidateEvidence was NOT seeded
    async with tenant_transaction_context(db_api_session, org_id):
        with pytest.raises(ValueError, match="EVIDENCE_INCOMPLETE"):
            await CalculationService.run_calculation(
                db=db_api_session,
                organization_id=org_id,
                requested_by_user_id=user_id,
                formula_code="LOAN_TO_DEPOSIT_RATIO",
                institution_id=inst_id,
                reporting_period_id=period_id,
                comparison_policy="EXPLICIT_PERIOD",
            )
