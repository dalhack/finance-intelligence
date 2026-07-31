import os
from uuid import UUID, uuid4

from services.worker.app.command_envelope import IngestionCommandEnvelope

TEST_HMAC_SECRET = os.environ.get("INGESTION_HMAC_SECRET", "test_hmac_secret_32_bytes_long_1234")


def make_signed_envelope(
    job_id: UUID | None = None,
    command_id: UUID | None = None,
    command_type: str = "PROCESS_INGESTION_JOB",
    schema_version: str = "2.0.0",
    key_id: str = "key-v1",
    secret: str = TEST_HMAC_SECRET,
) -> IngestionCommandEnvelope:
    """Helper for constructing valid signed v2.0.0 command envelopes in test suites."""
    target_job = job_id or uuid4()
    target_cmd = command_id or uuid4()

    env = IngestionCommandEnvelope(
        job_id=target_job,
        command_id=target_cmd,
        command_type=command_type,
        schema_version=schema_version,
        key_id=key_id,
    )
    return env.with_signature(secret)
