import json
from pathlib import Path
from uuid import uuid4

import pytest
from app.db.session import get_db_session
from app.dependencies import get_execution_context
from app.main import app
from app.middleware.execution_context import ExecutionContext
from fastapi import status
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.asyncio
async def test_openapi_contract_drift_request_body_parity():
    spec_path = REPO_ROOT / "contracts" / "openapi_spec.json"
    assert spec_path.exists(), "contracts/openapi_spec.json missing"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    # 1. Verify AnalysisCreateRequest schema parity
    schemas = spec.get("components", {}).get("schemas", {})
    assert "AnalysisCreateRequest" in schemas, "AnalysisCreateRequest missing from OpenAPI schemas"
    create_schema = schemas["AnalysisCreateRequest"]

    props = create_schema.get("properties", {})
    assert "prompt" in props, "prompt field missing in AnalysisCreateRequest"
    assert "idempotency_key" in props, "idempotency_key field missing in AnalysisCreateRequest"
    assert "selected_document_ids" in props, "selected_document_ids field missing in AnalysisCreateRequest"
    assert create_schema.get("required") == ["prompt"], "required fields in AnalysisCreateRequest must be ['prompt']"
    assert create_schema.get("additionalProperties") is False, "extra fields must be forbidden (additionalProperties: false)"

    # 2. Verify POST /api/v1/documents/uploads multipart endpoint
    paths = spec.get("paths", {})
    assert "/api/v1/documents/uploads" in paths, "/api/v1/documents/uploads route missing from OpenAPI"
    uploads_op = paths["/api/v1/documents/uploads"].get("post", {})
    content = uploads_op.get("requestBody", {}).get("content", {})
    assert "multipart/form-data" in content, "multipart/form-data media type missing from POST /documents/uploads"
    multipart_schema_ref = content["multipart/form-data"].get("schema", {})
    
    if "$ref" in multipart_schema_ref:
        ref_name = multipart_schema_ref["$ref"].split("/")[-1]
        multipart_props = schemas.get(ref_name, {}).get("properties", {})
    else:
        multipart_props = multipart_schema_ref.get("properties", {})
    
    assert "file" in multipart_props, "file field missing in POST /documents/uploads request body"
    assert "display_name" in multipart_props, "display_name field missing in POST /documents/uploads request body"


@pytest.fixture
def mock_exec_context():
    org_id = uuid4()
    user_id = uuid4()
    ctx = ExecutionContext(
        authenticated_user_id=user_id,
        active_organization_id=org_id,
        membership_id=uuid4(),
        roles=["ANALYST"],
        permissions=["analyses:run", "documents:upload"],
        request_id="req-test",
        correlation_id="corr-test",
        authentication_method="development",
        environment="test",
    )
    return ctx


@pytest.mark.asyncio
async def test_analysis_create_extra_fields_forbidden(mock_exec_context, mocker):
    mock_db = mocker.AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db
    app.dependency_overrides[get_execution_context] = lambda: mock_exec_context

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            response = await ac.post(
                "/api/v1/analyses",
                json={
                    "prompt": "Analyze cash flow",
                    "invalid_extra_field": "disallowed",
                },
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analysis_create_selected_document_ids_unauthorized_fails_closed(mock_exec_context, mocker):
    foreign_doc_id = str(uuid4())
    mock_db = mocker.AsyncMock()
    mock_scalars = mocker.MagicMock()
    mock_scalars.all.return_value = []
    mock_res = mocker.MagicMock()
    mock_res.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db_session] = lambda: mock_db
    app.dependency_overrides[get_execution_context] = lambda: mock_exec_context

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            response = await ac.post(
                "/api/v1/analyses",
                json={
                    "prompt": "Analyze revenue",
                    "selected_document_ids": [foreign_doc_id],
                },
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "error" in response.json()
            assert "unauthorized, or deleted" in response.json()["error"]["message"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analysis_create_idempotency_deduplication(mock_exec_context, mocker):
    idempotency_key = f"idem-key-{uuid4()}"
    payload = {
        "prompt": "Analyze liquidity ratio",
        "idempotency_key": idempotency_key,
    }

    from datetime import UTC, datetime

    from app.models.orchestration import AnalysisJob
    existing_job = AnalysisJob(
        id=uuid4(),
        organization_id=mock_exec_context.active_organization_id,
        user_id=mock_exec_context.authenticated_user_id,
        status="RECEIVED",
        request_prompt="Analyze liquidity ratio",
        normalized_request={},
        idempotency_key=idempotency_key,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db = mocker.AsyncMock()
    mock_res = mocker.MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_job
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db_session] = lambda: mock_db
    app.dependency_overrides[get_execution_context] = lambda: mock_exec_context

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            res1 = await ac.post("/api/v1/analyses", json=payload)
            assert res1.status_code == status.HTTP_201_CREATED
            job1 = res1.json()

            res2 = await ac.post("/api/v1/analyses", json=payload)
            assert res2.status_code == status.HTTP_201_CREATED
            job2 = res2.json()

            assert job1["id"] == str(existing_job.id)
            assert job2["id"] == str(existing_job.id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_http_exception_error_envelope_formatting():
    from app.middleware.error_handler import http_exception_handler
    from fastapi import HTTPException
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/documents",
        "headers": [],
    }
    req = Request(scope)
    req.state.request_id = "req-test-401"

    exc = HTTPException(
        status_code=401,
        detail="Authentication credentials were not provided.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    res = await http_exception_handler(req, exc)
    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"

    import json
    data = json.loads(res.body.decode("utf-8"))
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHENTICATED"
    assert data["error"]["requestId"] == "req-test-401"
    assert data["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_backend_http_exception_raw_secret_detail_redaction():
    from app.middleware.error_handler import http_exception_handler
    from fastapi import HTTPException
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/documents/uploads",
        "headers": [],
    }
    req = Request(scope)
    req.state.request_id = "req-test-secret"

    exc = HTTPException(
        status_code=400,
        detail="Invalid token provided: secret_key_12345 in SQL traceback",
    )
    res = await http_exception_handler(req, exc)
    import json
    data = json.loads(res.body.decode("utf-8"))
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"
    assert "secret_key_12345" not in data["error"]["message"]
    assert "sql" not in data["error"]["message"].lower()
