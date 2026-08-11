import io
import logging
import re
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.models.stored_object import StoredObject

from services.worker.app.main import WORKER_ID, run_worker_loop


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_run_worker_loop_log_redaction_all_worker_modules(monkeypatch):
    """Verify executing real run_worker_loop logs ZERO raw IDs, tokens, paths, URLs, passwords, or tracebacks."""
    log_stream = io.StringIO()
    stream_handler = logging.StreamHandler(log_stream)

    # Attach stream handler to root and finance_intelligence_worker loggers
    worker_logger = logging.getLogger("finance_intelligence_worker")
    worker_logger.addHandler(stream_handler)
    worker_logger.setLevel(logging.INFO)

    sensitive_job_id = uuid4()
    sensitive_org_id = uuid4()
    sensitive_doc_ver_id = uuid4()
    sensitive_claim_token = uuid4()
    sensitive_object_key = "secret_tenant_123/sensitive_financial_document.csv"

    mock_job = MagicMock(spec=IngestionJob)
    mock_job.id = sensitive_job_id
    mock_job.organization_id = sensitive_org_id
    mock_job.document_version_id = sensitive_doc_ver_id
    mock_job.status = "PARSING"
    mock_job.current_attempt = 1
    mock_job.max_attempts = 3
    mock_job.locked_by = WORKER_ID
    mock_job.claim_token = sensitive_claim_token

    mock_version = MagicMock(spec=DocumentVersion)
    mock_version.id = sensitive_doc_ver_id
    mock_version.stored_object_id = uuid4()
    mock_version.ingestion_status = "QUEUED"
    mock_version.extraction_status = "PENDING"

    mock_stored_obj = MagicMock(spec=StoredObject)
    mock_stored_obj.detected_mime_type = "text/csv"
    mock_stored_obj.opaque_object_key = sensitive_object_key

    monkeypatch.setenv("INGESTION_HMAC_SECRET", "test_hmac_secret_32_bytes_long_1234")

    # Mock DB query responses
    async def mock_execute(query, *args, **kwargs):
        q_str = str(query)
        if "claim_ingestion_job" in q_str:
            row = MagicMock()
            row.job_id = sensitive_job_id
            row.organization_id = sensitive_org_id
            row.document_version_id = sensitive_doc_ver_id
            row.claim_token = sensitive_claim_token
            res = MagicMock()
            res.fetchone.return_value = row
            return res
        elif "ingestion_jobs" in q_str:
            if "SELECT" in q_str and "LIMIT 1" in q_str:
                row = MagicMock()
                row.__getitem__ = lambda self, idx: sensitive_job_id if idx == 0 else None
                res = MagicMock()
                res.fetchone.return_value = row
                return res
            res = MagicMock()
            res.scalar_one_or_none.return_value = mock_job
            return res

        elif "document_versions" in q_str:
            res = MagicMock()
            res.scalar_one_or_none.return_value = mock_version
            return res
        elif "stored_objects" in q_str:
            res = MagicMock()
            res.scalar_one.return_value = mock_stored_obj
            return res
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    mock_db = MagicMock()
    mock_db.execute = mock_execute
    mock_db.flush = AsyncMock(return_value=None)
    mock_db.commit = AsyncMock(return_value=None)
    mock_db.rollback = AsyncMock(return_value=None)

    # Mock WorkerSessionLocal to yield mock_db
    class MockWorkerSessionContextManager:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("services.worker.app.main.WorkerSessionLocal", lambda: MockWorkerSessionContextManager())
    monkeypatch.setattr("app.db.session.WorkerSessionLocal", lambda: MockWorkerSessionContextManager())
    monkeypatch.setattr("app.db.session.ApiSessionLocal", lambda: MockWorkerSessionContextManager())
    monkeypatch.setattr(
        "services.worker.app.main.analysis_worker.session_factory", lambda: MockWorkerSessionContextManager()
    )

    # Mock LocalStorageAdapter
    mock_adapter = MagicMock()
    mock_adapter.get_object = AsyncMock(return_value=io.BytesIO(b"col1,col2\nval1,val2"))
    monkeypatch.setattr("services.worker.app.ingestion_worker.LocalStorageAdapter", lambda: mock_adapter)

    # Execute actual worker loop with run_once=True
    processed = await run_worker_loop(run_once=True)
    assert processed == 1

    log_output = log_stream.getvalue()
    worker_logger.removeHandler(stream_handler)

    # 1. Assert ZERO occurrences of sensitive raw UUIDs or tokens
    assert str(sensitive_job_id) not in log_output
    assert str(sensitive_org_id) not in log_output
    assert str(sensitive_claim_token) not in log_output
    assert WORKER_ID not in log_output
    assert sensitive_object_key not in log_output

    # 2. Assert ZERO occurrences of credentials, URLs, or tracebacks
    assert "postgresql" not in log_output.lower()
    assert "pass" not in log_output.lower()
    assert "Traceback (most recent call last)" not in log_output

    # 3. Assert raw UUID regex pattern yields ZERO matches in logs
    uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
    matches = uuid_pattern.findall(log_output)
    assert len(matches) == 0, f"Raw UUIDs found in worker loop logs: {matches}"
