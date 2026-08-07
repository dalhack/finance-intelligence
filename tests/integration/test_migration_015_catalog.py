import os
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.models.calculation import Calculation
from services.api.app.models.calculation_attempt import CalculationAttempt
from services.api.app.models.calculation_input import CalculationInput
from services.api.app.models.calculation_request import CalculationRequest
from services.api.app.models.document import Document
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.financial_fact import FinancialFact
from services.api.app.models.financial_fact_candidate import FinancialFactCandidate
from services.api.app.models.institution import Institution
from services.api.app.models.organization import Organization
from services.api.app.models.reporting_period import ReportingPeriod
from services.api.app.models.stored_object import StoredObject
from services.api.app.models.user import User


@pytest.mark.asyncio
async def test_migration_015_catalog_and_tenant_immutability():
    """Verify Migration 015 catalog properties and tenant context immutability."""
    owner_engine = create_async_engine(os.environ["TEST_OWNER_DATABASE_URL"])
    api_engine = create_async_engine(os.environ["TEST_API_DATABASE_URL"])

    OwnerSession = async_sessionmaker(owner_engine, class_=AsyncSession, expire_on_commit=False)
    ApiSession = async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)

    async with OwnerSession() as db_owner_session, ApiSession() as db_api_session:
        # 1. Verify Alembic Version
        res = await db_owner_session.execute(text("SELECT version_num FROM alembic_version;"))
        row = res.fetchone()
        assert row is not None
        assert row[0] in [
            "023_analysis_clarification_workflow",
            "024_maintenance_scheduler_and_operational_resilience",
            "025_distributed_provider_circuit_breaker",
            "026_public_schema_acl_hardening",
            "027_auth_context_lookup_security_plane",
            "028_remove_organization_only_actor_lookup",
            "029_analysis_authorization_policy",
            "030_reconcile_application_role_catalog",
            "031_analysis_job_claim_authority",
        ]

        # 2. Verify Security Definer Function catalog properties
        func_res = await db_owner_session.execute(
            text("""
            SELECT p.proname, p.prosecdef, p.proconfig, r.rolname
            FROM pg_proc p
            JOIN pg_roles r ON p.proowner = r.oid
            WHERE p.proname = 'fn_prevent_terminal_child_lineage_mutation';
            """)
        )
        func_row = func_res.fetchone()
        assert func_row is not None
        _proname, prosecdef, proconfig, owner_name = func_row
        assert prosecdef is True
        assert owner_name == "db_owner"
        assert proconfig is not None
        assert "search_path=public, pg_catalog, pg_temp" in proconfig

        # Verify Function Body contains NO set_config
        body_res = await db_owner_session.execute(
            text("SELECT prosrc FROM pg_proc WHERE proname = 'fn_prevent_terminal_child_lineage_mutation';")
        )
        prosrc = body_res.scalar()
        assert "set_config" not in prosrc
        assert "SET LOCAL" not in prosrc

        # 3. Verify col_index column is ABSENT from candidate_evidence
        col_res = await db_owner_session.execute(
            text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'candidate_evidence' AND column_name = 'col_index';
            """)
        )
        assert col_res.fetchone() is None

        # 4. Verify DB CHECK constraints on calculation_attempts
        chk_res = await db_owner_session.execute(
            text("""
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'public.calculation_attempts'::regclass AND contype = 'c';
            """)
        )
        constraints = [r[0] for r in chk_res.fetchall()]
        assert "chk_attempts_status_valid" in constraints
        assert "chk_attempts_completed_invariants" in constraints
        assert "chk_attempts_failed_invariants" in constraints

        # 5. Tenant Context Immutability Test
        org_a = uuid4()
        _org_b = uuid4()
        calc_id = uuid4()
        inp_id = uuid4()
        req_id = uuid4()
        att_id = uuid4()

        # Seed organization & user via db_owner_session
        user_id = uuid4()
        org_obj = Organization(id=org_a, name="Org A", slug=f"org-{org_a.hex[:6]}")
        user_obj = User(id=user_id, external_subject=f"sub_{uuid4().hex[:6]}", display_name="User A")
        db_owner_session.add_all([org_obj, user_obj])
        await db_owner_session.commit()

        # API Session sets Tenant A context
        await db_api_session.execute(
            text("SELECT set_config('app.current_organization_id', :org_a, true);"), {"org_a": str(org_a)}
        )

        inst_id = uuid4()
        period_id = uuid4()
        doc_id = uuid4()
        doc_ver_id = uuid4()
        obj_id = uuid4()
        cand_id = uuid4()
        fact_id = uuid4()

        inst = Institution(
            id=inst_id, organization_id=org_a, canonical_name=f"bank_{org_a.hex[:6]}", display_name="Bank A"
        )
        period = ReportingPeriod(
            id=period_id,
            organization_id=org_a,
            period_type="YEAR",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            label="2024 FY",
            comparison_key="2024",
        )
        stored_obj = StoredObject(
            id=obj_id,
            organization_id=org_a,
            opaque_object_key=f"pdf_key_{uuid4().hex[:6]}.pdf",
            server_computed_sha256="hash123",
            byte_size=100,
            detected_mime_type="application/pdf",
            storage_provider="LOCAL",
        )
        doc = Document(id=doc_id, organization_id=org_a, uploaded_by_user_id=user_id, display_name="report.pdf")
        doc_ver = DocumentVersion(
            id=doc_ver_id,
            organization_id=org_a,
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

        cand = FinancialFactCandidate(
            id=cand_id,
            organization_id=org_a,
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
            organization_id=org_a,
            institution_id=inst_id,
            reporting_period_id=period_id,
            metric_definition_id=UUID("a0000000-0000-0000-0000-000000000002"),
            metric_code="TOTAL_LOANS",
            value=Decimal("800.0"),
            normalized_value=Decimal("800.0"),
            source_candidate_id=cand_id,
            source_document_id=doc_id,
        )
        db_api_session.add(fact)
        await db_api_session.flush()

        calc_req = CalculationRequest(
            id=req_id,
            organization_id=org_a,
            request_fingerprint=f"fp_{uuid4().hex}",
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            formula_version="1.0.0",
            institution_id=inst_id,
            reporting_period_id=period_id,
            requested_by_user_id=uuid4(),
        )
        calc_att = CalculationAttempt(
            id=att_id,
            organization_id=org_a,
            calculation_request_id=req_id,
            attempt_number=1,
            execution_idempotency_hash=f"{'a' * 64}",
            formula_spec_checksum=f"{'b' * 64}",
            implementation_checksum=f"{'c' * 64}",
            completed_at=func.now(),
            status="COMPLETED",
        )
        calc = Calculation(
            id=calc_id,
            organization_id=org_a,
            calculation_request_id=req_id,
            calculation_attempt_id=att_id,
            institution_id=inst_id,
            reporting_period_id=period_id,
            formula_code="LOAN_TO_DEPOSIT_RATIO",
            formula_version="1.0.0",
            status="COMPLETED",
            result_value_unrounded=80.0,
            result_value_display=80.0,
            result_unit="PERCENT",
            result_scale="ONE",
            value_representation="PERCENT_DISPLAY",
            working_precision=38,
            rounding_policy="ROUND_HALF_UP",
            idempotency_hash=f"{'a' * 64}",
            formula_spec_checksum=f"{'b' * 64}",
            implementation_checksum=f"{'c' * 64}",
            requested_by_user_id=uuid4(),
        )
        inp = CalculationInput(
            id=inp_id,
            organization_id=org_a,
            calculation_id=calc_id,
            financial_fact_id=fact_id,
            input_role="NUMERATOR",
            metric_code="TOTAL_LOANS",
            normalized_value_snapshot=800.0,
            currency_snapshot="TRY",
            unit_snapshot="CURRENCY",
            scale_snapshot="ONE",
            reporting_basis_snapshot="SOLO",
            reporting_period_id_snapshot=period_id,
        )
        db_api_session.add(calc_req)
        await db_api_session.flush()

        db_api_session.add(calc_att)
        await db_api_session.flush()

        db_api_session.add_all([calc, inp])
        await db_api_session.commit()

        # Re-set Tenant A context for mutation test
        await db_api_session.execute(
            text("SELECT set_config('app.current_organization_id', :org_a, true);"), {"org_a": str(org_a)}
        )
        ctx_before = (
            await db_api_session.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        ).scalar()
        assert ctx_before == str(org_a)

        # Savepoint block for forbidden lineage mutation
        try:
            async with db_api_session.begin_nested():
                await db_api_session.execute(
                    text("UPDATE calculation_inputs SET metric_code = 'MUTATED' WHERE id = :inp_id"),
                    {"inp_id": str(inp_id)},
                )
                await db_api_session.commit()
        except Exception as err:  # noqa: BLE001
            assert "IMMUTABLE_LINEAGE" in str(err)

        # Assert tenant context remains unchanged (Tenant A)
        ctx_after = (
            await db_api_session.execute(text("SELECT current_setting('app.current_organization_id', true);"))
        ).scalar()
        assert ctx_after == str(org_a)

    await owner_engine.dispose()
    await api_engine.dispose()
