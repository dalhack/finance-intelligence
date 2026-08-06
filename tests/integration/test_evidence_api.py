import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.candidate_evidence import CandidateEvidence
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact_candidate import FinancialFactCandidate
from services.api.app.models.institution import Institution
from services.api.app.models.organization import Organization
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.models.stored_object import StoredObject
from services.api.app.models.user import User
from services.api.app.services.comparison_service import ComparisonService


@pytest.mark.asyncio
async def test_evidence_drawer_detail_and_cross_tenant_isolation():
    """Verify evidence drawer detail API returns sanitized data and enforces tenant isolation."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_a = uuid4()
    org_b = uuid4()
    user_a = uuid4()
    ev_id = uuid4()
    obj_id = uuid4()

    async with OwnerSession() as db_owner:
        org1 = Organization(id=org_a, name="Org A Ev", slug=f"ev-a-{org_a.hex[:6]}")
        org2 = Organization(id=org_b, name="Org B Ev", slug=f"ev-b-{org_b.hex[:6]}")
        usr = User(id=user_a, external_subject=f"sub_{user_a.hex[:6]}", display_name="User A")
        db_owner.add_all([org1, org2, usr])
        await db_owner.commit()

    async with ApiSession() as db_api:
        from app.db.tenant_context import tenant_transaction_context

        async with tenant_transaction_context(db_api, org_a):
            doc_id = uuid4()
            ver_id = uuid4()
            cand_id = uuid4()
            inst_id = uuid4()
            period_id = uuid4()

            st_obj = StoredObject(
                id=obj_id,
                organization_id=org_a,
                opaque_object_key=f"{uuid4().hex}.pdf",
                server_computed_sha256="dummy_hash_ev",
                byte_size=100,
                detected_mime_type="application/pdf",
                storage_provider="LOCAL",
            )
            inst = Institution(
                id=inst_id,
                organization_id=org_a,
                canonical_name=f"ev_bank_{inst_id.hex[:6]}",
                display_name="Ev Bank",
            )
            period = ReportingPeriod(
                id=period_id,
                organization_id=org_a,
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
                organization_id=org_a,
                uploaded_by_user_id=user_a,
                display_name="report.pdf",
            )
            db_api.add_all([st_obj, inst, period, doc])
            await db_api.flush()

            ver = DocumentVersion(
                id=ver_id,
                organization_id=org_a,
                document_id=doc_id,
                stored_object_id=obj_id,
                version_number=1,
                content_hash_sha256="dummy_hash_ev",
                file_size_bytes=100,
                declared_mime_type="application/pdf",
                detected_mime_type="application/pdf",
            )
            db_api.add(ver)
            await db_api.flush()

            cand = FinancialFactCandidate(
                id=cand_id,
                organization_id=org_a,
                institution_id=inst_id,
                reporting_period_id=period_id,
                raw_label="Total Assets",
                raw_value="1000",
                source_document_id=doc_id,
                source_document_version_id=ver_id,
            )
            db_api.add(cand)
            await db_api.flush()

            ev = CandidateEvidence(
                id=ev_id,
                organization_id=org_a,
                candidate_id=cand_id,
                source_document_version_id=ver_id,
                page_number=3,
                sheet_name=None,
                cell_coordinate=None,
                bounding_box={"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 50.0},
                raw_snippet="Total Assets 1000 TRY",
            )
            db_api.add(ev)
            await db_api.flush()

            # Tenant A retrieves evidence
            detail = await ComparisonService.get_evidence_detail(db=db_api, organization_id=org_a, evidence_id=ev_id)
            assert detail.evidence_id == ev_id
            assert detail.page_number == 3
            assert detail.mime_type == "application/pdf"
            assert detail.mime_verified is True
        assert detail.document_title == "report.pdf"
        assert detail.sanitized_snippet == "Total Assets 1000 TRY"

        # Tenant B cross-tenant lookup must raise EVIDENCE_NOT_FOUND (404 isolation)
        with pytest.raises(ValueError, match="EVIDENCE_NOT_FOUND"):
            await ComparisonService.get_evidence_detail(db=db_api, organization_id=org_b, evidence_id=ev_id)

    await owner_engine.dispose()
    await api_engine.dispose()
