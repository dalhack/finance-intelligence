import pytest

from services.worker.app.ingestion_worker import KNOWN_SAFE_ERROR_CODES


@pytest.mark.unit
def test_worker_error_codes_allowlist():
    assert "RESOURCE_LIMIT_EXCEEDED" in KNOWN_SAFE_ERROR_CODES
    assert "ENCRYPTED_DOCUMENT" in KNOWN_SAFE_ERROR_CODES
    assert "MALFORMED_DOCUMENT" in KNOWN_SAFE_ERROR_CODES
    assert "ENCODING_UNCERTAIN" in KNOWN_SAFE_ERROR_CODES
