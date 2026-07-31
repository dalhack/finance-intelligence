import pytest

from services.api.app.core.security_pipeline import SecurityPipelineException, validate_file_security


@pytest.mark.unit
def test_mime_reconciliation_pdf_mismatch():
    xlsx_bytes = b"PK\x03\x04\x14\x00\x00\x00"
    with pytest.raises(SecurityPipelineException) as exc_info:
        validate_file_security(xlsx_bytes, "sample.pdf", "application/pdf")
    assert exc_info.value.code in ["MIME_MISMATCH", "MALFORMED_DOCUMENT"]


@pytest.mark.unit
def test_mime_reconciliation_double_extension_rejected():
    with pytest.raises(SecurityPipelineException) as exc_info:
        validate_file_security(b"%PDF-1.4", "malicious.exe.pdf", "application/pdf")
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.unit
def test_mime_reconciliation_csv_binary_null_byte_rejected():
    with pytest.raises(SecurityPipelineException) as exc_info:
        validate_file_security(b"header1,header2\x00binary", "sample.csv", "text/csv")
    assert exc_info.value.code == "MIME_MISMATCH"
