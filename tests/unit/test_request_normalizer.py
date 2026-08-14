from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.models.institution import Institution
from app.models.reporting_period import ReportingPeriod
from app.orchestration.provider import ModelResponse, TokenUsage
from app.orchestration.request_normalizer import AnalysisRequestNormalizer
from app.schemas.clarification import ClarificationCode


@pytest.mark.unit
@pytest.mark.asyncio
async def test_valid_unambiguous_request_normalizes():
    org_id = uuid4()
    inst1 = MagicMock(spec=Institution)
    inst1.id = uuid4()
    inst1.canonical_name = "Garanti BBVA"
    inst1.display_name = "Türkiye Garanti Bankası A.Ş."
    inst1.regulatory_identifier = "GARAN"
    inst1.aliases = ["garanti", "garan"]

    inst2 = MagicMock(spec=Institution)
    inst2.id = uuid4()
    inst2.canonical_name = "Akbank"
    inst2.display_name = "Akbank T.A.Ş."
    inst2.regulatory_identifier = "AKBNK"
    inst2.aliases = ["akbank", "akbnk"]

    period1 = MagicMock(spec=ReportingPeriod)
    period1.id = uuid4()
    period1.label = "2025 Q4"
    period1.comparison_key = "2025-Q4"

    mock_db = MagicMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "institutions" in stmt_str:
            res.scalars.return_value.all.return_value = [inst1, inst2]
        elif "reporting_periods" in stmt_str:
            res.scalars.return_value.all.return_value = [period1]
        else:
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute

    mock_provider = MagicMock()

    async def mock_invoke(req):
        return ModelResponse(
            invocation_id="inv-001",
            content_text='{"intent": "CROSS_INSTITUTION_COMPARISON", "requested_institutions": ["Garanti BBVA", "Akbank"], "requested_periods": ["2025-Q4"], "requested_semantic_measures": ["TOTAL_ASSETS"]}',
            tool_calls=[],
            stop_reason="end_turn",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, cached_prompt_tokens=0),
        )

    mock_provider.invoke_model = mock_invoke

    normalizer = AnalysisRequestNormalizer(provider=mock_provider)
    outcome = await normalizer.normalize_request(
        prompt="Garanti ve Akbank 2025 Q4 aktif karşılaştırması yap.",
        organization_id=org_id,
        db_session=mock_db,
    )

    assert outcome.status == "SUCCESS"
    assert outcome.normalized_request is not None
    assert outcome.normalized_request.intent == "CROSS_INSTITUTION_COMPARISON"
    assert len(outcome.matched_institution_ids) == 2
    assert str(inst1.id) in outcome.matched_institution_ids
    assert str(inst2.id) in outcome.matched_institution_ids
    assert len(outcome.matched_period_ids) == 1
    assert str(period1.id) in outcome.matched_period_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_institution_matches_by_name_code_or_ticker():
    org_id = uuid4()
    inst1 = MagicMock(spec=Institution)
    inst1.id = uuid4()
    inst1.canonical_name = "Garanti BBVA"
    inst1.display_name = "Türkiye Garanti Bankası A.Ş."
    inst1.regulatory_identifier = "GARAN"
    inst1.aliases = ["garan.is", "garan"]

    period1 = MagicMock(spec=ReportingPeriod)
    period1.id = uuid4()
    period1.label = "2025 Q4"
    period1.comparison_key = "2025-Q4"

    mock_db = MagicMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "institutions" in stmt_str:
            res.scalars.return_value.all.return_value = [inst1]
        elif "reporting_periods" in stmt_str:
            res.scalars.return_value.all.return_value = [period1]
        return res

    mock_db.execute = mock_execute

    mock_provider = MagicMock()

    async def mock_invoke(req):
        return ModelResponse(
            invocation_id="inv-002",
            content_text='{"intent": "SINGLE_PERIOD_ANALYSIS", "requested_institutions": ["GARAN.IS"], "requested_periods": ["2025-Q4"], "requested_semantic_measures": ["TOTAL_ASSETS"]}',
            tool_calls=[],
            stop_reason="end_turn",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, cached_prompt_tokens=0),
        )

    mock_provider.invoke_model = mock_invoke

    normalizer = AnalysisRequestNormalizer(provider=mock_provider)
    outcome = await normalizer.normalize_request(
        prompt="GARAN.IS 2025 Q4 aktif analizi.",
        organization_id=org_id,
        db_session=mock_db,
    )

    assert outcome.status == "SUCCESS"
    assert outcome.matched_institution_ids == [str(inst1.id)]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_period_matches_by_period_code():
    org_id = uuid4()
    inst1 = MagicMock(spec=Institution)
    inst1.id = uuid4()
    inst1.canonical_name = "Garanti BBVA"
    inst1.display_name = "Garanti Bankası"
    inst1.regulatory_identifier = "GARAN"
    inst1.aliases = []

    period1 = MagicMock(spec=ReportingPeriod)
    period1.id = uuid4()
    period1.label = "2025 Q4"
    period1.comparison_key = "2025-Q4"

    mock_db = MagicMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "institutions" in stmt_str:
            res.scalars.return_value.all.return_value = [inst1]
        elif "reporting_periods" in stmt_str:
            res.scalars.return_value.all.return_value = [period1]
        return res

    mock_db.execute = mock_execute

    mock_provider = MagicMock()

    async def mock_invoke(req):
        return ModelResponse(
            invocation_id="inv-003",
            content_text='{"intent": "SINGLE_PERIOD_ANALYSIS", "requested_institutions": ["Garanti BBVA"], "requested_periods": ["2025-Q4"], "requested_semantic_measures": ["TOTAL_ASSETS"]}',
            tool_calls=[],
            stop_reason="end_turn",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, cached_prompt_tokens=0),
        )

    mock_provider.invoke_model = mock_invoke

    normalizer = AnalysisRequestNormalizer(provider=mock_provider)
    outcome = await normalizer.normalize_request(
        prompt="Garanti 2025-Q4 raporu.",
        organization_id=org_id,
        db_session=mock_db,
    )

    assert outcome.status == "SUCCESS"
    assert outcome.matched_period_ids == [str(period1.id)]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_malformed_model_output_fails_closed():
    org_id = uuid4()
    mock_db = MagicMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute

    mock_provider = MagicMock()

    async def mock_invoke(req):
        return ModelResponse(
            invocation_id="inv-004",
            content_text="NOT_VALID_JSON_STRING",
            tool_calls=[],
            stop_reason="end_turn",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, cached_prompt_tokens=0),
        )

    mock_provider.invoke_model = mock_invoke

    normalizer = AnalysisRequestNormalizer(provider=mock_provider)
    outcome = await normalizer.normalize_request(
        prompt="Geçersiz metin istemi.",
        organization_id=org_id,
        db_session=mock_db,
    )

    assert outcome.status == "NEEDS_CLARIFICATION"
    assert outcome.clarification_code in (
        ClarificationCode.INSTITUTION_REQUIRED.value,
        ClarificationCode.UNSUPPORTED_REQUEST_SCOPE.value,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_entity_returns_needs_clarification():
    org_id = uuid4()
    mock_db = MagicMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute

    mock_provider = MagicMock()

    async def mock_invoke(req):
        return ModelResponse(
            invocation_id="inv-005",
            content_text='{"intent": "SINGLE_PERIOD_ANALYSIS", "requested_institutions": [], "requested_periods": [], "requested_semantic_measures": []}',
            tool_calls=[],
            stop_reason="end_turn",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, cached_prompt_tokens=0),
        )

    mock_provider.invoke_model = mock_invoke

    normalizer = AnalysisRequestNormalizer(provider=mock_provider)
    outcome = await normalizer.normalize_request(
        prompt="Bilinmeyen kurum ve dönem.",
        organization_id=org_id,
        db_session=mock_db,
    )

    assert outcome.status == "NEEDS_CLARIFICATION"
    assert outcome.clarification_code is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_model_failure_has_no_hardcoded_fallback():
    org_id = uuid4()
    mock_db = MagicMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute

    mock_provider = MagicMock()

    async def mock_invoke(req):
        raise RuntimeError("SIMULATED_MODEL_TIMEOUT")

    mock_provider.invoke_model = mock_invoke

    normalizer = AnalysisRequestNormalizer(provider=mock_provider)
    outcome = await normalizer.normalize_request(
        prompt="Model zaman aşımı testi.",
        organization_id=org_id,
        db_session=mock_db,
    )

    assert outcome.status == "NEEDS_CLARIFICATION"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cross_tenant_candidate_is_not_exposed():
    tenant_a_org_id = uuid4()
    tenant_b_inst = MagicMock(spec=Institution)
    tenant_b_inst.id = uuid4()
    tenant_b_inst.name = "Foreign Tenant Bank"
    tenant_b_inst.code = "FOREIGN"
    tenant_b_inst.organization_id = uuid4()  # Different org ID

    mock_db = MagicMock()

    # RLS query for Tenant A returns ONLY Tenant A institutions (empty)
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute

    mock_provider = MagicMock()

    async def mock_invoke(req):
        return ModelResponse(
            invocation_id="inv-007",
            content_text='{"intent": "SINGLE_PERIOD_ANALYSIS", "requested_institutions": ["Foreign Tenant Bank"], "requested_periods": ["2025-Q4"], "requested_semantic_measures": ["TOTAL_ASSETS"]}',
            tool_calls=[],
            stop_reason="end_turn",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, cached_prompt_tokens=0),
        )

    mock_provider.invoke_model = mock_invoke

    normalizer = AnalysisRequestNormalizer(provider=mock_provider)
    outcome = await normalizer.normalize_request(
        prompt="Foreign Tenant Bank analizi yap.",
        organization_id=tenant_a_org_id,
        db_session=mock_db,
    )

    # Must NOT return Tenant B's institution ID
    assert outcome.status == "NEEDS_CLARIFICATION"
    assert outcome.matched_institution_ids is None or len(outcome.matched_institution_ids) == 0
