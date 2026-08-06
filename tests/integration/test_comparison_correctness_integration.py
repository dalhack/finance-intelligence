import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.db.tenant_context import tenant_transaction_context
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.candidate_evidence import CandidateEvidence
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact import FinancialFact
from services.api.app.models.financial_fact_candidate import FinancialFactCandidate
from services.api.app.models.institution import Institution
from services.api.app.models.metric_definition import MetricDefinition
from services.api.app.models.organization import Organization
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.models.stored_object import StoredObject
from services.api.app.models.user import User
from services.api.app.schemas.comparison import ComparisonRequestDTO, SemanticMeasureSelectorDTO
from services.api.app.services.comparison_service import ComparisonService


@pytest.mark.asyncio
async def test_both_separate_series_policy_and_measure_keys():
    """Verify BOTH_SEPARATE_SERIES produces separate measure keys (<code:SOURCE_REPORTED> and <code:SYSTEM_DERIVED>)."""
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Both Org", slug=f"both-{org_id.hex[:6]}")
        usr = User(id=user_id, external_subject=f"sub_{user_id.hex[:6]}", display_name="User Both")
        res = await db_owner.execute(select(MetricDefinition).where(MetricDefinition.metric_code == "TOTAL_ASSETS"))
        m_def = res.scalar_one_or_none()
        if not m_def:
            m_def = MetricDefinition(
                id=uuid4(),
                metric_code="TOTAL_ASSETS",
                canonical_name="Total Assets",
                value_type="CURRENCY",
                default_unit="TRY",
            )
            db_owner.add(m_def)
        db_owner.add_all([org, usr])
        await db_owner.commit()
        metric_def_id = m_def.id

    async with ApiSession() as db_api, tenant_transaction_context(db_api, org_id):
        st_obj = StoredObject(
            id=uuid4(),
            organization_id=org_id,
            opaque_object_key=f"{uuid4().hex}.pdf",
            server_computed_sha256="hash_both",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        inst = Institution(id=inst_id, organization_id=org_id, canonical_name="bank_b", display_name="Bank B")
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            period_presentation="FULL_YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024-FY",
            comparison_key="2024-FY",
        )
        doc = Document(id=uuid4(), organization_id=org_id, uploaded_by_user_id=user_id, display_name="doc.pdf")
        db_api.add_all([st_obj, inst, period, doc])
        await db_api.flush()

        ver = DocumentVersion(
            id=uuid4(),
            organization_id=org_id,
            document_id=doc.id,
            stored_object_id=st_obj.id,
            version_number=1,
            content_hash_sha256="hash_both",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        db_api.add(ver)
        await db_api.flush()

        cand = FinancialFactCandidate(
            id=uuid4(),
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            raw_label="Total Assets",
            raw_value="2000",
            source_document_id=doc.id,
            source_document_version_id=ver.id,
        )
        db_api.add(cand)
        await db_api.flush()

        ev = CandidateEvidence(
            id=uuid4(),
            organization_id=org_id,
            candidate_id=cand.id,
            source_document_version_id=ver.id,
            page_number=1,
            bounding_box={"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 50.0},
            raw_snippet="Total Assets: 2000",
        )
        db_api.add(ev)
        await db_api.flush()

        fact = FinancialFact(
            id=uuid4(),
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=metric_def_id,
            metric_code="TOTAL_ASSETS",
            value=Decimal("2000.0000"),
            normalized_value=Decimal("2000.0000"),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            reporting_basis="SOLO",
            value_origin="SOURCE_REPORTED",
            review_status="HUMAN_VERIFIED",
            source_candidate_id=cand.id,
            source_document_id=doc.id,
        )
        db_api.add(fact)
        await db_api.commit()

        req = ComparisonRequestDTO(
            institution_ids=[inst_id],
            semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
            reporting_period_ids=[period_id],
            reporting_basis="SOLO",
            currency="TRY",
            display_scale="ONE",
            value_source_policy="BOTH_SEPARATE_SERIES",
            comparison_mode="CROSS_INSTITUTION",
        )

        res = await ComparisonService.execute_comparison(
            db=db_api,
            organization_id=org_id,
            requested_by_user_id=user_id,
            payload=req,
        )

        assert res.comparison_id is not None
        row = res.result_dataset.rows[0]
        assert "TOTAL_ASSETS:SOURCE_REPORTED" in row.cells
        cell = row.cells["TOTAL_ASSETS:SOURCE_REPORTED"]
        assert cell.value_origin == "SOURCE_REPORTED"
        assert cell.canonical_value == "2000.0000"

    await api_engine.dispose()
    await owner_engine.dispose()


@pytest.mark.asyncio
async def test_strict_common_period_policy_rejection():
    """Verify STRICT_COMMON_PERIOD policy raises INCOMPLETE_COMMON_PERIOD when data is missing."""
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Strict Org", slug=f"strict-{org_id.hex[:6]}")
        db_owner.add(org)
        await db_owner.commit()

    async with ApiSession() as db_api, tenant_transaction_context(db_api, org_id):
        inst = Institution(id=inst_id, organization_id=org_id, canonical_name="bank_s", display_name="Bank S")
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            period_presentation="FULL_YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024-FY",
            comparison_key="2024-FY",
        )
        db_api.add_all([inst, period])
        await db_api.commit()

        req = ComparisonRequestDTO(
            institution_ids=[inst_id],
            semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
            reporting_period_ids=[period_id],
            reporting_basis="SOLO",
            currency="TRY",
            display_scale="MILLION",
            value_source_policy="SOURCE_REPORTED_ONLY",
            common_period_policy="STRICT_COMMON_PERIOD",
        )

        with pytest.raises(ValueError, match="INCOMPLETE_COMMON_PERIOD"):
            await ComparisonService.execute_comparison(
                db=db_api,
                organization_id=org_id,
                requested_by_user_id=uuid4(),
                payload=req,
            )

    await api_engine.dispose()
    await owner_engine.dispose()


@pytest.mark.asyncio
async def test_missing_institution_or_period_rejection():
    """Verify requesting non-existent or cross-tenant institution/period raises INSTITUTION_NOT_FOUND or PERIOD_NOT_FOUND."""
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Missing Org", slug=f"miss-{org_id.hex[:6]}")
        db_owner.add(org)
        await db_owner.commit()

    async with ApiSession() as db_api, tenant_transaction_context(db_api, org_id):
        req = ComparisonRequestDTO(
            institution_ids=[uuid4()],
            semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
            reporting_period_ids=[uuid4()],
            reporting_basis="SOLO",
        )

        with pytest.raises(ValueError, match="INSTITUTION_NOT_FOUND"):
            await ComparisonService.execute_comparison(
                db=db_api,
                organization_id=org_id,
                requested_by_user_id=uuid4(),
                payload=req,
            )

    await api_engine.dispose()
    await owner_engine.dispose()
