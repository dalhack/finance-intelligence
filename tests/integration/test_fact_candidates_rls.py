import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from services.api.app.db.session import ApiSessionLocal, WorkerSessionLocal
from services.api.app.models.candidate_evidence import CandidateEvidence
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact import FinancialFact
from services.api.app.models.financial_fact_candidate import FinancialFactCandidate
from services.api.app.models.institution import Institution
from services.api.app.models.metric_definition import MetricDefinition
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.models.stored_object import StoredObject
from services.api.app.services.fact_candidate_service import FactCandidateService
from services.api.app.services.financial_fact_service import FinancialFactService

OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    "postgresql://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_test",
).replace("+asyncpg", "")


@pytest.mark.asyncio
async def test_fact_candidate_creation_and_rls_isolation():
    """Verify candidate creation, RLS multi-tenant isolation, and worker least-privilege permissions."""
    org_a = uuid4()
    org_b = uuid4()
    user_a = uuid4()
    doc_id_a = uuid4()
    version_id_a = uuid4()
    obj_id_a = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_a),
        f"Org A {org_a}",
        f"org-a-{org_a}",
    )
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_b),
        f"Org B {org_b}",
        f"org-b-{org_b}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_a),
        f"sub-{user_a}",
        f"User {user_a}",
    )
    await conn_owner.close()

    async with ApiSessionLocal() as session_a:
        await session_a.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_a)}
        )
        stored_obj = StoredObject(
            id=obj_id_a,
            organization_id=org_a,
            opaque_object_key=f"{uuid4().hex}.pdf",
            server_computed_sha256="dummy_hash_facts",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        session_a.add(stored_obj)
        await session_a.flush()
        doc = Document(id=doc_id_a, organization_id=org_a, uploaded_by_user_id=user_a, display_name="q4_report.pdf")
        session_a.add(doc)
        await session_a.flush()

        doc_ver = DocumentVersion(
            id=version_id_a,
            organization_id=org_a,
            document_id=doc_id_a,
            version_number=1,
            stored_object_id=obj_id_a,
            content_hash_sha256="dummy_hash_facts",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        session_a.add(doc_ver)

        inst = Institution(organization_id=org_a, canonical_name="Garanti Bankasi", display_name="Garanti")
        session_a.add(inst)
        period = ReportingPeriod(
            organization_id=org_a,
            period_type="QUARTER",
            fiscal_year=2025,
            quarter=4,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            label="2025/Q4",
            comparison_key="2025-Q4",
        )
        session_a.add(period)
        await session_a.commit()

        inst_id = inst.id
        period_id = period.id

    async with WorkerSessionLocal() as w_session:
        await w_session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_a)}
        )
        cand = await FactCandidateService.create_candidate(
            db=w_session,
            organization_id=org_a,
            institution_id=inst_id,
            reporting_period_id=period_id,
            raw_label="Toplam Aktifler",
            raw_value="1.234.567,89",
            source_document_id=doc_id_a,
            source_document_version_id=version_id_a,
            raw_currency="TRY",
            raw_unit="CURRENCY",
            raw_scale="ONE",
            detected_reporting_basis="SOLO",
            source_location={"x0": 10, "y0": 10, "x1": 50, "y1": 50},
        )
        await w_session.commit()
        cand_id = cand.id

    # Verify RLS Isolation: Org B cannot see Org A's candidate
    async with ApiSessionLocal() as session_b:
        await session_b.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_b)}
        )
        res_b = await session_b.execute(
            text("SELECT count(*) FROM financial_fact_candidates WHERE id = :cid;"), {"cid": str(cand_id)}
        )
        assert res_b.scalar() == 0, "RLS VIOLATION: Org B must not see Org A's candidate!"

    # Approve Candidate under Org A by User A -> Creates immutable FinancialFact
    async with ApiSessionLocal() as session_a:
        await session_a.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_a)}
        )
        approved_cand, fact = await FinancialFactService.approve_candidate(
            db=session_a,
            organization_id=org_a,
            candidate_id=cand_id,
            reviewer_user_id=user_a,
            notes="Verified against audited report",
        )
        assert approved_cand.review_status == "APPROVED"
        assert fact.metric_code == "TOTAL_ASSETS"
        assert fact.normalized_value == Decimal("1234567.89")
        assert fact.review_status == "HUMAN_VERIFIED"
        first_fact_id = fact.id

    # Conflict Test: Standard approve on candidate with different value MUST fail with FACT_VALUE_CONFLICT
    async with WorkerSessionLocal() as w_session:
        await w_session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_a)}
        )
        revised_cand = await FactCandidateService.create_candidate(
            db=w_session,
            organization_id=org_a,
            institution_id=inst_id,
            reporting_period_id=period_id,
            raw_label="Toplam Aktifler",
            raw_value="1.250.000,00",
            source_document_id=doc_id_a,
            source_document_version_id=version_id_a,
            raw_currency="TRY",
            raw_unit="CURRENCY",
            raw_scale="ONE",
            detected_reporting_basis="SOLO",
            source_location={"x0": 10, "y0": 10, "x1": 50, "y1": 50},
        )
        await w_session.commit()
        revised_cand_id = revised_cand.id

    async with ApiSessionLocal() as session_a:
        await session_a.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_a)}
        )
        with pytest.raises(ValueError, match="FACT_VALUE_CONFLICT"):
            await FinancialFactService.approve_candidate(
                db=session_a,
                organization_id=org_a,
                candidate_id=revised_cand_id,
                reviewer_user_id=user_a,
            )

    # Explicit Revision Approval Test: approve_candidate_as_revision succeeds and supersedes first_fact_id
    async with ApiSessionLocal() as session_a:
        await session_a.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_a)}
        )
        revised_cand_app, new_fact = await FinancialFactService.approve_candidate_as_revision(
            db=session_a,
            organization_id=org_a,
            candidate_id=revised_cand_id,
            expected_existing_fact_id=first_fact_id,
            reviewer_user_id=user_a,
            notes="Explicit revision approved",
        )
        assert revised_cand_app.review_status == "APPROVED"
        assert new_fact.supersedes_fact_id == first_fact_id
        assert new_fact.normalized_value == Decimal("1250000.00")
        await session_a.commit()

        # Verify old fact valid_to is closed
        async with ApiSessionLocal() as session_check:
            await session_check.execute(
                text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_a)}
            )
            old_fact_res = await session_check.execute(
                text("SELECT valid_to FROM financial_facts WHERE id = :fid;"), {"fid": str(first_fact_id)}
            )
            valid_to_val = old_fact_res.scalar()
            assert valid_to_val is not None, "Expected old fact valid_to to be set upon supersession!"


@pytest.mark.asyncio
async def test_evidence_completeness_and_unknown_basis_guards():
    """Verify evidence completeness failure and UNKNOWN reporting basis approval rejection."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org Guard {org_id}",
        f"org-guard-{org_id}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        stored_obj = StoredObject(
            id=uuid4(),
            organization_id=org_id,
            opaque_object_key=f"{uuid4().hex}.pdf",
            server_computed_sha256="dummy_hash_guard",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        session.add(stored_obj)
        await session.flush()
        doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="guard_test.pdf")
        session.add(doc)
        await session.flush()
        doc_ver = DocumentVersion(
            id=version_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=stored_obj.id,
            content_hash_sha256="dummy_hash_guard",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        session.add(doc_ver)

        inst = Institution(organization_id=org_id, canonical_name="Akbank", display_name="Akbank")
        session.add(inst)
        period = ReportingPeriod(
            organization_id=org_id,
            period_type="YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024/FY",
            comparison_key="2024-FY",
        )
        session.add(period)
        await session.flush()
        inst_id, period_id = inst.id, period.id

        m_res = await session.execute(select(MetricDefinition).limit(1))
        m_def = m_res.scalar_one_or_none()
        if not m_def:
            m_def = MetricDefinition(
                metric_code="NET_PROFIT",
                canonical_name="Net Profit",
                value_type="CURRENCY",
            )
            session.add(m_def)
            await session.flush()

        cand = FinancialFactCandidate(
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=m_def.id,
            suggested_metric_code="NET_PROFIT",
            raw_label="Net Kar",
            raw_value="500000",
            parsed_decimal_value=Decimal(500000),
            raw_currency="TRY",
            raw_unit="CURRENCY",
            raw_scale="ONE",
            normalized_currency="TRY",
            normalized_unit="CURRENCY",
            normalized_scale="ONE",
            normalized_value=Decimal(500000),
            detected_reporting_basis="UNKNOWN",
            source_document_id=doc_id,
            source_document_version_id=version_id,
        )
        session.add(cand)

        await session.commit()
        cand_no_ev_id = cand.id

    # 1. Approval without Evidence MUST fail with EVIDENCE_INCOMPLETE
    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        with pytest.raises(ValueError, match="EVIDENCE_INCOMPLETE"):
            await FinancialFactService.approve_candidate(
                db=session,
                organization_id=org_id,
                candidate_id=cand_no_ev_id,
                reviewer_user_id=user_id,
            )

        # Now add Evidence record
        ev = CandidateEvidence(
            organization_id=org_id,
            candidate_id=cand_no_ev_id,
            source_document_version_id=version_id,
            page_number=1,
            bounding_box={"x0": 10, "y0": 10, "x1": 50, "y1": 50},
            raw_snippet="Net Kar 500.000 TRY",
        )
        session.add(ev)
        await session.commit()

    # 2. Approval with UNKNOWN basis and no explicit selection MUST fail with REPORTING_BASIS_REQUIRED
    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        with pytest.raises(ValueError, match="REPORTING_BASIS_REQUIRED"):
            await FinancialFactService.approve_candidate(
                db=session,
                organization_id=org_id,
                candidate_id=cand_no_ev_id,
                reviewer_user_id=user_id,
            )

        # Passing explicit target_reporting_basis="SOLO" resolves it
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        approved_cand, fact = await FinancialFactService.approve_candidate(
            db=session,
            organization_id=org_id,
            candidate_id=cand_no_ev_id,
            reviewer_user_id=user_id,
            target_reporting_basis="SOLO",
        )
        assert approved_cand.review_status == "APPROVED"
        assert fact.reporting_basis == "SOLO"


@pytest.mark.asyncio
async def test_database_immutability_trigger_enforcement():
    """Verify PostgreSQL trigger trg_prevent_fact_mutation blocks unauthorized updates to core fact columns."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org Imm {org_id}",
        f"org-imm-{org_id}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.close()

    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )

        stored_obj = StoredObject(
            id=uuid4(),
            organization_id=org_id,
            opaque_object_key=f"{uuid4().hex}.pdf",
            server_computed_sha256="dummy_hash_imm",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        session.add(stored_obj)
        await session.flush()
        doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="imm_test.pdf")
        session.add(doc)
        await session.flush()
        doc_ver = DocumentVersion(
            id=version_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=stored_obj.id,
            content_hash_sha256="dummy_hash_imm",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        session.add(doc_ver)

        inst = Institution(organization_id=org_id, canonical_name="Isbank", display_name="Isbank")
        session.add(inst)
        period = ReportingPeriod(
            organization_id=org_id,
            period_type="YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024/FY",
            comparison_key="2024-FY",
        )
        session.add(period)
        await session.flush()
        inst_id, period_id = inst.id, period.id

        cand = await FactCandidateService.create_candidate(
            db=session,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            raw_label="Toplam Aktifler",
            raw_value="999.000,00",
            source_document_id=doc_id,
            source_document_version_id=version_id,
            detected_reporting_basis="SOLO",
            source_location={"x0": 10, "y0": 10, "x1": 50, "y1": 50},
        )
        await session.flush()

        _, fact = await FinancialFactService.approve_candidate(
            db=session,
            organization_id=org_id,
            candidate_id=cand.id,
            reviewer_user_id=user_id,
        )
        fact_id = fact.id
        await session.commit()

    # Attempt direct SQL UPDATE on normalized_value -> MUST trigger PostgreSQL exception
    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        with pytest.raises(Exception, match="CRITICAL_IMMUTABILITY_VIOLATION"):
            await session.execute(
                text("UPDATE financial_facts SET normalized_value = 111111.00 WHERE id = :fid;"),
                {"fid": str(fact_id)},
            )
            await session.commit()


@pytest.mark.asyncio
async def test_revision_natural_key_mismatch_and_target_guards():
    """Verify revision fails with REVISION_NATURAL_KEY_MISMATCH when natural key attributes differ."""
    org_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org Rev {org_id}",
        f"org-rev-{org_id}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.execute(
        "INSERT INTO metric_definitions (id, metric_code, canonical_name, value_type, default_unit) VALUES ($1, 'NET_INCOME', 'Net Kar', 'DECIMAL', 'CURRENCY') ON CONFLICT DO NOTHING;",
        str(uuid4()),
    )
    await conn_owner.execute(
        "INSERT INTO memberships (id, organization_id, user_id) VALUES ($1, $2, $3);",
        str(uuid4()),
        str(org_id),
        str(user_id),
    )
    await conn_owner.close()

    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        stored_obj = StoredObject(
            id=uuid4(),
            organization_id=org_id,
            opaque_object_key=f"{uuid4().hex}.pdf",
            server_computed_sha256="dummy_hash_rev",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        session.add(stored_obj)
        await session.flush()
        doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="rev_test.pdf")
        session.add(doc)
        await session.flush()
        doc_ver = DocumentVersion(
            id=version_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=stored_obj.id,
            content_hash_sha256="dummy_hash_rev",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        session.add(doc_ver)

        inst1 = Institution(organization_id=org_id, canonical_name="Garanti Bank", display_name="Garanti Bank")
        inst2 = Institution(organization_id=org_id, canonical_name="Akbank", display_name="Akbank")
        session.add_all([inst1, inst2])

        period = ReportingPeriod(
            organization_id=org_id,
            period_type="YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024/FY",
            comparison_key="2024-FY",
        )
        session.add(period)
        await session.flush()

        # Candidate 1: Inst 1
        cand1 = await FactCandidateService.create_candidate(
            db=session,
            organization_id=org_id,
            institution_id=inst1.id,
            reporting_period_id=period.id,
            raw_label="Toplam Aktifler",
            raw_value="100.000,00",
            source_document_id=doc_id,
            source_document_version_id=version_id,
            detected_reporting_basis="SOLO",
            source_location={"x0": 10, "y0": 10, "x1": 50, "y1": 50},
        )
        await session.flush()
        _, fact1 = await FinancialFactService.approve_candidate(
            db=session, organization_id=org_id, candidate_id=cand1.id, reviewer_user_id=user_id
        )

        # Re-bind session tenant context after commit
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )

        # Candidate 2: Inst 2 (different natural key!)
        cand2 = await FactCandidateService.create_candidate(
            db=session,
            organization_id=org_id,
            institution_id=inst2.id,
            reporting_period_id=period.id,
            raw_label="Toplam Aktifler",
            raw_value="200.000,00",
            source_document_id=doc_id,
            source_document_version_id=version_id,
            detected_reporting_basis="SOLO",
            source_location={"x0": 10, "y0": 10, "x1": 50, "y1": 50},
        )
        await session.flush()

        # Attempt to revise fact1 using cand2 (which has inst2) -> MUST fail REVISION_NATURAL_KEY_MISMATCH
        with pytest.raises(ValueError, match="REVISION_NATURAL_KEY_MISMATCH"):
            await FinancialFactService.approve_candidate_as_revision(
                db=session,
                organization_id=org_id,
                candidate_id=cand2.id,
                expected_existing_fact_id=fact1.id,
                reviewer_user_id=user_id,
            )


@pytest.mark.asyncio
async def test_active_fact_partial_unique_index_engine_enforcement():
    """Verify PostgreSQL database engine blocks two active facts with identical natural key via uq_financial_facts_active_natural_key."""
    org_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    metric_id = uuid4()
    doc_id = uuid4()
    user_id = uuid4()

    conn_owner = await asyncpg.connect(OWNER_URL)
    await conn_owner.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);",
        str(org_id),
        f"Org Index {org_id}",
        f"org-idx-{org_id}",
    )
    await conn_owner.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        str(user_id),
        f"sub-{user_id}",
        f"User {user_id}",
    )
    await conn_owner.execute(
        "INSERT INTO memberships (id, organization_id, user_id) VALUES ($1, $2, $3);",
        str(uuid4()),
        str(org_id),
        str(user_id),
    )
    await conn_owner.execute(
        "INSERT INTO metric_definitions (id, metric_code, canonical_name, value_type, default_unit) VALUES ($1, 'TEST_METRIC', 'Test Metric', 'DECIMAL', 'CURRENCY') ON CONFLICT DO NOTHING;",
        str(metric_id),
    )
    await conn_owner.close()

    async with ApiSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"), {"org_id": str(org_id)}
        )
        inst = Institution(id=inst_id, organization_id=org_id, canonical_name="Ziraat", display_name="Ziraat")
        session.add(inst)
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024/FY",
            comparison_key="2024-FY",
        )
        session.add(period)
        stored_obj = StoredObject(
            id=uuid4(),
            organization_id=org_id,
            opaque_object_key=f"{uuid4().hex}.pdf",
            server_computed_sha256="dummy_hash_idx",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        session.add(stored_obj)
        await session.flush()
        doc = Document(id=doc_id, organization_id=org_id, uploaded_by_user_id=user_id, display_name="test.pdf")
        session.add(doc)
        await session.flush()

        doc_ver = DocumentVersion(
            id=uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            stored_object_id=stored_obj.id,
            content_hash_sha256="dummy_hash_idx",
            file_size_bytes=100,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
        )
        session.add(doc_ver)
        await session.flush()

        cand = await FactCandidateService.create_candidate(
            db=session,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            raw_label="Toplam Aktifler",
            raw_value="100.000,00",
            source_document_id=doc_id,
            source_document_version_id=doc_ver.id,
            detected_reporting_basis="SOLO",
            source_location={"x0": 10, "y0": 10, "x1": 50, "y1": 50},
        )
        await session.flush()

        # Insert first active fact
        fact1 = FinancialFact(
            id=uuid4(),
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=cand.metric_definition_id,
            metric_code="TOTAL_ASSETS",
            value=Decimal(100),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=Decimal(100),
            reporting_basis="SOLO",
            source_candidate_id=cand.id,
            source_document_id=doc_id,
            extraction_method="MANUAL",
            confidence_score=Decimal("1.0"),
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=user_id,
        )
        session.add(fact1)
        await session.flush()

        # Attempt second active fact with identical natural key -> MUST fail with IntegrityError
        fact2 = FinancialFact(
            id=uuid4(),
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=cand.metric_definition_id,
            metric_code="TOTAL_ASSETS",
            value=Decimal(200),
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=Decimal(200),
            reporting_basis="SOLO",
            source_candidate_id=cand.id,
            source_document_id=doc_id,
            extraction_method="MANUAL",
            confidence_score=Decimal("1.0"),
            review_status="HUMAN_VERIFIED",
            verified_by_user_id=user_id,
        )
        session.add(fact2)
        with pytest.raises(IntegrityError):
            await session.flush()
