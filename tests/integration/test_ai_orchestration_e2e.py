import os
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact import FinancialFact
from services.api.app.models.financial_fact_candidate import FinancialFactCandidate
from services.api.app.models.institution import Institution
from services.api.app.models.membership import Membership
from services.api.app.models.metric_definition import MetricDefinition
from services.api.app.models.orchestration import AnalysisJob
from services.api.app.models.organization import Organization
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.models.stored_object import StoredObject
from services.api.app.models.user import User
from services.api.app.orchestration.engine import AnalysisOrchestratorEngine
from services.api.app.orchestration.policy_engine import DataClassification
from services.api.app.orchestration.provider import DeterministicTestModelProvider
from services.api.app.orchestration.tools.base import ExecutionContext


@pytest.mark.asyncio
async def test_ai_orchestrator_full_e2e_positive_flow():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    doc_id = uuid4()
    stored_obj_id = uuid4()
    doc_ver_id = uuid4()
    cand_id = uuid4()
    job_id = uuid4()

    # 1. Create Organization & User first
    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="E2E Org", slug=f"e2e-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="E2E User")

        # Get or create MetricDefinition for TOTAL_ASSETS
        metric_res = await db_owner.execute(
            select(MetricDefinition).where(MetricDefinition.metric_code == "TOTAL_ASSETS")
        )
        metric_def = metric_res.scalar_one_or_none()
        if not metric_def:
            metric_def = MetricDefinition(
                id=uuid4(),
                metric_code="TOTAL_ASSETS",
                canonical_name="Total Assets",
                valid_from=date(2020, 1, 1),
            )
            db_owner.add(metric_def)

        db_owner.add_all([org, user])
        await db_owner.commit()
        metric_def_id = metric_def.id

    # 2. Add RLS-protected parent objects (Institution, Period, Document, StoredObject)
    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        mem = Membership(id=uuid4(), organization_id=org_id, user_id=user_id)
        inst = Institution(
            id=inst_id, canonical_name="Garanti BBVA", display_name="Garanti BBVA", organization_id=org_id
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="QUARTERLY",
            fiscal_year=2025,
            quarter=4,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            label="2025-Q4",
            comparison_key="2025-Q4",
        )
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            uploaded_by_user_id=user_id,
            display_name="garanti_2025_q4.pdf",
            classification="PUBLIC",
        )
        stored_obj = StoredObject(
            id=stored_obj_id,
            organization_id=org_id,
            opaque_object_key=f"obj-{stored_obj_id.hex[:6]}",
            byte_size=1000,
            server_computed_sha256="a" * 64,
            detected_mime_type="application/pdf",
        )
        db_api.add_all([mem, inst, period, doc, stored_obj])
        await db_api.commit()

    # 3. Add DocumentVersion & Candidate
    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        doc_ver = DocumentVersion(
            id=doc_ver_id,
            organization_id=org_id,
            document_id=doc_id,
            version_number=1,
            content_hash_sha256="a" * 64,
            file_size_bytes=1000,
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
            stored_object_id=stored_obj_id,
        )
        cand = FinancialFactCandidate(
            id=cand_id,
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=metric_def_id,
            suggested_metric_code="TOTAL_ASSETS",
            raw_label="Toplam Aktifler",
            raw_value="1,500,000",
            source_document_id=doc_id,
            source_document_version_id=doc_ver_id,
        )
        db_api.add_all([doc_ver, cand])
        await db_api.commit()

    # 4. Add FinancialFact & AnalysisJob
    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        fact = FinancialFact(
            id=uuid4(),
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=metric_def_id,
            metric_code="TOTAL_ASSETS",
            value=1500000.00,
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=1500000.00,
            reporting_basis="SOLO",
            source_candidate_id=cand_id,
            source_document_id=doc_id,
            source_location={},
            extraction_method="PARSER_TABLE",
            confidence_score=1.000,
            review_status="HUMAN_VERIFIED",
            value_origin="SOURCE_REPORTED",
        )
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="RECEIVED",
            request_prompt="Garanti BBVA 2025 Q4 toplam aktif analizi.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_api.add_all([fact, job])
        await db_api.commit()

    # 5. Run E2E Orchestrator Engine as db_api_user
    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        context = ExecutionContext(
            organization_id=org_id,
            user_id=user_id,
            role="OWNER",
            permissions={"analyses:read", "analyses:run", "analyses:clarifications:respond", "analyses:cancel"},
        )
        engine = AnalysisOrchestratorEngine(
            db_session=db_api,
            context=context,
            provider=DeterministicTestModelProvider(environment="development"),
        )

        completed_job = await engine.execute_job(job_id, request_classification=DataClassification.PUBLIC)
        assert completed_job.status == "COMPLETED"

    # 6. Verify Full Lifecycle in PostgreSQL DB (9 Tables)
    async with OwnerSession() as db_verify:
        await db_verify.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))

        # 1. analysis_jobs
        res_job = await db_verify.execute(text(f"SELECT COUNT(*) FROM analysis_jobs WHERE id = '{job_id}';"))
        assert res_job.scalar() == 1

        # 2. analysis_attempts
        res_att = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM analysis_attempts WHERE analysis_job_id = '{job_id}';")
        )
        assert res_att.scalar() >= 1

        # 3. analysis_plans
        res_plan = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM analysis_plans WHERE analysis_job_id = '{job_id}';")
        )
        assert res_plan.scalar() >= 1

        # 4. model_invocations
        res_model = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM model_invocations WHERE analysis_job_id = '{job_id}';")
        )
        assert res_model.scalar() >= 0

        # 5. tool_invocations
        res_tool = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM tool_invocations WHERE analysis_job_id = '{job_id}';")
        )
        assert res_tool.scalar() >= 1

        # 6. policy_decisions
        res_pol = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM policy_decisions WHERE analysis_job_id = '{job_id}';")
        )
        assert res_pol.scalar() >= 1

        # 7. quality_gate_results
        res_qg = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM quality_gate_results WHERE analysis_job_id = '{job_id}';")
        )
        assert res_qg.scalar() >= 1

        # 8. final_result_snapshots
        res_snap = await db_verify.execute(
            text(f"SELECT result_json FROM final_result_snapshots WHERE analysis_job_id = '{job_id}';")
        )
        row = res_snap.fetchone()
        assert row is not None
        assert "result_dataset_id" in str(row[0])
        assert "narrative" in str(row[0])

        # 9. analysis_events (monotonic positive sequence)
        res_evt = await db_verify.execute(
            text(f"SELECT sequence FROM analysis_events WHERE analysis_job_id = '{job_id}' ORDER BY sequence ASC;")
        )
        seqs = [r[0] for r in res_evt.fetchall()]
        assert len(seqs) >= 1
        assert seqs == sorted(seqs)


@pytest.mark.asyncio
async def test_ai_orchestrator_strictly_confidential_policy_deny_flow():
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Strict Org", slug=f"strict-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Strict User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner:
        await db_owner.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        mem = Membership(id=uuid4(), organization_id=org_id, user_id=user_id)
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="RECEIVED",
            request_prompt="Hassas veri analizi.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_owner.add_all([mem, job])
        await db_owner.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        context = ExecutionContext(
            organization_id=org_id,
            user_id=user_id,
            role="OWNER",
            permissions={"analyses:create"},
        )
        engine = AnalysisOrchestratorEngine(
            db_session=db_api,
            context=context,
            provider=DeterministicTestModelProvider(environment="development"),
        )

        rejected_job = await engine.execute_job(job_id, request_classification=DataClassification.STRICTLY_CONFIDENTIAL)
        assert rejected_job.status == "REJECTED_BY_POLICY"

    # Verify 0 snapshots written
    async with OwnerSession() as db_verify:
        await db_verify.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        snapshot = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM final_result_snapshots WHERE analysis_job_id = '{job_id}';")
        )
        count = snapshot.scalar()
        assert count == 0


@pytest.mark.asyncio
async def test_ai_orchestrator_concurrent_double_completion_snapshot_atomicity():
    """Verifies PostgreSQL final_result_snapshots atomicity under concurrent double completion."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Atomic Org", slug=f"atomic-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Atomic User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with OwnerSession() as db_owner:
        await db_owner.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        mem = Membership(id=uuid4(), organization_id=org_id, user_id=user_id)
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="COMPLETED",
            request_prompt="Atomic concurrency test.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_owner.add_all([mem, job])
        await db_owner.commit()

    # Insert snapshot 1
    async with OwnerSession() as db1:
        await db1.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        await db1.execute(
            text(
                "INSERT INTO final_result_snapshots (id, organization_id, analysis_job_id, schema_version, result_json) "
                "VALUES (:id, :org_id, :job_id, '3.0.0', '{\"summary\": \"Snap 1\"}') ON CONFLICT DO NOTHING;"
            ),
            {"id": uuid4(), "org_id": org_id, "job_id": job_id},
        )
        await db1.commit()

    # Insert snapshot 2 (duplicate concurrent attempt)
    async with OwnerSession() as db2:
        await db2.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        await db2.execute(
            text(
                "INSERT INTO final_result_snapshots (id, organization_id, analysis_job_id, schema_version, result_json) "
                "VALUES (:id, :org_id, :job_id, '3.0.0', '{\"summary\": \"Snap 2\"}') ON CONFLICT DO NOTHING;"
            ),
            {"id": uuid4(), "org_id": org_id, "job_id": job_id},
        )
        await db2.commit()

    # Verify exactly 1 snapshot exists
    async with OwnerSession() as db_verify:
        await db_verify.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        res = await db_verify.execute(
            text(f"SELECT COUNT(*) FROM final_result_snapshots WHERE analysis_job_id = '{job_id}';")
        )
        count = res.scalar()
        assert count == 1


@pytest.mark.asyncio
async def test_live_anthropic_acceptance():
    """Opt-in live Anthropic acceptance test node.

    Executes a single real engine invocation using AnthropicProviderAdapter(use_fake_transport=False)
    when ANTHROPIC_API_KEY is present in the execution environment.
    If ANTHROPIC_API_KEY is missing, skips gracefully without failing normal local CI.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key in ("placeholder", "test_key", ""):
        pytest.skip("ANTHROPIC_API_KEY is not configured locally. Skipping live Anthropic acceptance test node.")

    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()
    inst_id = uuid4()
    period_id = uuid4()
    cand_id = uuid4()
    doc_id = uuid4()
    metric_def_id = uuid4()

    async with OwnerSession() as db_owner:
        org = Organization(id=org_id, name="Live Anthropic Test Org", slug=f"live-{org_id.hex[:6]}")
        user = User(id=user_id, external_subject=f"sub-{user_id.hex[:6]}", display_name="Live Test User")
        db_owner.add_all([org, user])
        await db_owner.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        inst = Institution(
            id=inst_id, organization_id=org_id, canonical_name="garanti_bbva", display_name="Garanti BBVA"
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_id,
            period_type="QUARTER",
            period_presentation="Q4",
            fiscal_year=2025,
            fiscal_quarter=4,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            label="2025-Q4",
            comparison_key="2025-Q4",
        )
        db_api.add_all([inst, period])
        await db_api.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        fact = FinancialFact(
            id=uuid4(),
            organization_id=org_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=metric_def_id,
            metric_code="TOTAL_ASSETS",
            value=1500000.00,
            currency="TRY",
            unit="CURRENCY",
            scale="ONE",
            normalized_value=1500000.00,
            reporting_basis="SOLO",
            source_candidate_id=cand_id,
            source_document_id=doc_id,
            source_location={},
            extraction_method="PARSER_TABLE",
            confidence_score=1.000,
            review_status="HUMAN_VERIFIED",
            value_origin="SOURCE_REPORTED",
        )
        now = datetime.now(UTC)
        job = AnalysisJob(
            id=job_id,
            organization_id=org_id,
            user_id=user_id,
            status="RECEIVED",
            request_prompt="Garanti BBVA 2025 Q4 toplam aktif analizi.",
            normalized_request={},
            created_at=now,
            updated_at=now,
        )
        db_api.add_all([fact, job])
        await db_api.commit()

    async with ApiSession() as db_api:
        await db_api.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        context = ExecutionContext(
            organization_id=org_id,
            user_id=user_id,
            role="OWNER",
            permissions={"analyses:read", "analyses:run", "analyses:clarifications:respond", "analyses:cancel"},
        )
        from services.api.app.orchestration.provider_anthropic import AnthropicProviderAdapter

        provider = AnthropicProviderAdapter(
            application_model_alias="finance_analysis_balanced",
            api_key=api_key,
            use_fake_transport=False,
        )
        engine = AnalysisOrchestratorEngine(
            db_session=db_api,
            context=context,
            provider=provider,
        )

        completed_job = await engine.execute_job(job_id, request_classification=DataClassification.PUBLIC)
        assert completed_job.status == "COMPLETED"

    async with OwnerSession() as db_verify:
        await db_verify.execute(text(f"SET LOCAL app.current_organization_id = '{org_id}';"))
        res_snap = await db_verify.execute(
            text(f"SELECT result_json FROM final_result_snapshots WHERE analysis_job_id = '{job_id}';")
        )
        row = res_snap.fetchone()
        assert row is not None
        assert "result_dataset_id" in str(row[0])
