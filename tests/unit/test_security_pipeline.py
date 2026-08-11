import os

import pytest
from app.core.security_pipeline import (
    SecurityPipelineException,
    sanitize_filename,
    validate_file_security,
)

GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden"))


@pytest.mark.unit
def test_sanitize_filename():
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("report_2025 (1).pdf") == "report_2025__1_.pdf"


@pytest.mark.unit
def test_unsupported_file_type_rejected():
    with pytest.raises(SecurityPipelineException) as exc:
        validate_file_security(b"executable_content", "script.sh", "application/x-sh")
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.unit
def test_malformed_pdf_rejected():
    pdf_path = os.path.join(GOLDEN_DIR, "sample_malformed.pdf")
    with open(pdf_path, "rb") as f:
        content = f.read()

    with pytest.raises(SecurityPipelineException) as exc:
        validate_file_security(content, "sample_malformed.pdf", "application/pdf")
    assert exc.value.code in ["INVALID_FILE_SIGNATURE", "MALFORMED_DOCUMENT"]


@pytest.mark.unit
def test_encrypted_pdf_rejected():
    pdf_path = os.path.join(GOLDEN_DIR, "sample_encrypted.pdf")
    with open(pdf_path, "rb") as f:
        content = f.read()

    with pytest.raises(SecurityPipelineException) as exc:
        validate_file_security(content, "sample_encrypted.pdf", "application/pdf")
    assert exc.value.code == "ENCRYPTED_DOCUMENT"
