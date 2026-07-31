import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
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
async def test_comparison_service_execution_and_persistence():
    """Verify ComparisonService executes queries, constructs ResultDataset, TableSpec, ChartSpecs, and persists run snapshot."""
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    doc_id = uuid4()
    ver_id = uuid4()
    cand_id = uuid4()
    ev_id = uuid4()
    obj_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Comp Org", slug=f"comp-{org_id.hex[:6]}")
        usr = User(id=user_id, external_subject=f"sub_{user_id.hex[:6]}", display_name="Comp User")

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

    async with ApiSession() as db_api:
        await db_api.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(org_id)},
        )

        st_obj = StoredObject(
            id=obj_id,
            organization_id=org_id,
            opaque_object_key=f"{uuid4().hex}.pdf",
            server_computed_sha256="dummy_hash_comp",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        inst = Institution(
            id=inst_id,
            organization_id=org_id,
            canonical_name=f"bank_{inst_id.hex[:6]}",
            display_name="Bank A",
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            period_presentation="FULL_YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024-Q1",
            comparison_key="2024-Q1",
        )
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            uploaded_by_user_id=user_id,
            display_name="report.pdf",
        )
        db_api.add_all([st_obj, inst, period, doc])
        await db_api.flush()

        ver = DocumentVersion(
            id=ver_id,
            organization_id=org_id,
            document_id=doc_id,
            stored_object_id=obj_id,
            version_number=1,
            content_hash_sha256="dummy_hash_comp",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        db_api.add(ver)
        await db_api.flush()

        cand = FinancialFactCandidate(
            id=cand_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            raw_label="Total Assets",
            raw_value="1500000",
            source_document_id=doc_id,
            source_document_version_id=ver_id,
        )
        db_api.add(cand)
        await db_api.flush()

        ev = CandidateEvidence(
            id=ev_id,
            organization_id=org_id,
            candidate_id=cand_id,
            source_document_version_id=ver_id,
            page_number=1,
            bounding_box={"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 50.0},
            raw_snippet="Total Assets: 1,500,000 TRY",
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
            value=Decimal("1500000.0000"),
            normalized_value=Decimal("1500000.0000"),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            reporting_basis="SOLO",
            value_origin="SOURCE_REPORTED",
            review_status="HUMAN_VERIFIED",
            source_candidate_id=cand_id,
            source_document_id=doc_id,
        )
        db_api.add(fact)
        await db_api.commit()

        req = ComparisonRequestDTO(
            institution_ids=[inst_id],
            semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
            reporting_period_ids=[period_id],
            reporting_basis="SOLO",
            currency="TRY",
            display_scale="MILLION",
            value_source_policy="SOURCE_REPORTED_ONLY",
            comparison_mode="CROSS_INSTITUTION",
            chart_types=["vertical_bar", "line"],
        )

        res = await ComparisonService.execute_comparison(
            db=db_api,
            organization_id=org_id,
            requested_by_user_id=user_id,
            payload=req,
        )

        assert res.comparison_id is not None
        assert res.result_dataset.query_snapshot.currency == "TRY"
        assert len(res.result_dataset.rows) == 1
        assert res.result_dataset.data_quality_summary.source_reported_count == 1
        assert res.table_spec.pagination.total_rows == 1
        assert len(res.chart_specs) == 2

        # Verify filter metadata
        filters = await ComparisonService.get_filter_metadata(db=db_api, organization_id=org_id)
        assert len(filters.supported_institutions) >= 1
        assert len(filters.supported_semantic_measures) >= 1
        assert "SOLO" in filters.supported_reporting_bases
        assert "CONSOLIDATED" in filters.supported_reporting_bases

    await api_engine.dispose()
    await owner_engine.dispose()


@pytest.mark.asyncio
async def test_comparison_limit_exceeded_rejection():
    """Verify ComparisonService rejects requests exceeding limit thresholds."""
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()

    async with ApiSession() as db_api:
        req = ComparisonRequestDTO.model_construct(
            institution_ids=[uuid4() for _ in range(11)],
            semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
            reporting_period_ids=[uuid4()],
            reporting_basis="SOLO",
            currency="TRY",
            display_scale="MILLION",
            value_source_policy="PREFER_SOURCE_REPORTED",
            comparison_mode="CROSS_INSTITUTION",
            chart_types=["vertical_bar"],
            top_n=None,
            page=1,
            page_size=20,
        )
        with pytest.raises(ValueError, match="COMPARISON_LIMIT_EXCEEDED"):
            await ComparisonService.execute_comparison(
                db=db_api,
                organization_id=org_id,
                requested_by_user_id=user_id,
                payload=req,
            )

    await api_engine.dispose()
