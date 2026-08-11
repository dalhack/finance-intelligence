import io
import logging
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.core.logging import PseudonymizingFormatter, redact_sensitive_text
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.models.stored_object import StoredObject
from app.parsers.registry import parser_registry

from services.worker.app.ingestion_worker import ClaimedJob, IngestionWorker, WorkerOutcomeStatus


@pytest.mark.unit
def test_pseudonymizing_formatter_basic():
    formatter = PseudonymizingFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Processing document for tenant",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "Processing document for tenant" in formatted


@pytest.mark.unit
def test_redact_sensitive_text_urls():
    raw = "Connecting to postgresql+asyncpg://db_owner:mock_secret_pass_123@localhost:5432/finance_db"
    redacted = redact_sensitive_text(raw)
    assert "mock_secret_pass_123" not in redacted
    assert "[REDACTED_URL]" in redacted


@pytest.mark.unit
def test_redact_sensitive_text_sql():
    raw = "Executed SELECT * FROM users WHERE id = 1"
    redacted = redact_sensitive_text(raw)
    assert "[REDACTED_SQL]" in redacted


@pytest.mark.unit
def test_redact_sensitive_uuids():
    raw = "Failed for org_id=123e4567-e89b-12d3-a456-426614174000"
    redacted = redact_sensitive_text(raw)
    assert "123e4567-e89b-12d3-a456-426614174000" not in redacted
    assert "[REDACTED_UUID]" in redacted


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_worker_exception_log_capture_redaction(monkeypatch):
    """Verify real worker exception log output contains ZERO raw tracebacks or sensitive values."""
    log_stream = io.StringIO()
    stream_handler = logging.StreamHandler(log_stream)
    stream_handler.setFormatter(PseudonymizingFormatter())

    worker_logger = logging.getLogger("finance_intelligence_worker")
    worker_logger.addHandler(stream_handler)
    worker_logger.setLevel(logging.ERROR)

    sensitive_uuid = "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
    sensitive_path = "/Users/secret_user/finance-intelligence/storage/tenant_123/file.csv"
    sensitive_sql = "SELECT secret_credit_card FROM financial_records"
    sensitive_url = "postgresql+asyncpg://admin:dev_worker_pass_123@10.0.0.1:5432/db"

    mock_parser = MagicMock()
    mock_parser.parse.side_effect = RuntimeError(
        f"Corrupt parsing at {sensitive_path} for org {sensitive_uuid} using {sensitive_sql} connected to {sensitive_url}"
    )
    monkeypatch.setattr(parser_registry, "get_parser", lambda mime: mock_parser)

    mock_job = MagicMock(spec=IngestionJob)
    mock_job.status = "PARSING"
    mock_job.current_attempt = 1
    mock_job.max_attempts = 3
    mock_job.organization_id = uuid4()
    mock_job.document_version_id = uuid4()
    mock_job.id = uuid4()

    mock_version = MagicMock(spec=DocumentVersion)
    mock_version.id = mock_job.document_version_id
    mock_version.stored_object_id = uuid4()
    mock_version.ingestion_status = "QUEUED"
    mock_version.extraction_status = "PENDING"

    mock_stored_obj = MagicMock(spec=StoredObject)
    mock_stored_obj.detected_mime_type = "text/csv"
    mock_stored_obj.opaque_object_key = "test_obj.csv"

    from unittest.mock import AsyncMock

    async def mock_execute(query, *args, **kwargs):
        q_str = str(query)
        if "ingestion_jobs" in q_str:
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

    # Mock storage adapter get_object
    mock_adapter = MagicMock()
    mock_adapter.get_object = AsyncMock(return_value=io.BytesIO(b"col1,col2\nval1,val2"))
    monkeypatch.setattr("services.worker.app.ingestion_worker.LocalStorageAdapter", lambda: mock_adapter)

    claimed_job = ClaimedJob(
        job_id=mock_job.id,
        organization_id=mock_job.organization_id,
        document_version_id=mock_job.document_version_id,
        worker_id="worker-log-test",
        claim_token=uuid4(),
    )

    mock_job.locked_by = claimed_job.worker_id
    mock_job.claim_token = claimed_job.claim_token

    worker = IngestionWorker(mock_db)
    outcome = await worker._process_claimed_job(claimed_job)
    assert outcome.outcome_status == WorkerOutcomeStatus.PROCESSED_FAILED

    log_output = log_stream.getvalue()

    # Assert ZERO occurrence of sensitive values in captured log output
    assert sensitive_uuid not in log_output
    assert sensitive_path not in log_output
    assert sensitive_sql not in log_output
    assert sensitive_url not in log_output
    assert "dev_worker_pass_123" not in log_output

    assert "Traceback (most recent call last)" not in log_output

    worker_logger.removeHandler(stream_handler)
