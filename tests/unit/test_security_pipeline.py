import os

import pytest
from app.core.security_pipeline import (
    SECURITY_HEADER_SAMPLE_BYTES,
    SecurityPipelineException,
    sanitize_filename,
    security_validation_read_size,
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


@pytest.mark.unit
def test_structure_validated_formats_require_the_whole_object():
    """PDF/XLSX indexes live at the end of the file, so a bounded prefix is
    never enough; validating from a sample rejects every file above the sample
    size with a false MALFORMED_DOCUMENT."""
    large_size = 5 * 1024 * 1024

    assert security_validation_read_size("Solo VAKBN 31.03.2026 TR.pdf", large_size) == large_size
    assert security_validation_read_size("bilanco.xlsx", large_size) == large_size
    # Header-only formats stay bounded.
    assert security_validation_read_size("veriler.csv", large_size) == SECURITY_HEADER_SAMPLE_BYTES
    # Never request a zero-length read for an empty object.
    assert security_validation_read_size("bos.pdf", 0) == 1


@pytest.mark.unit
def test_truncated_pdf_prefix_is_reported_as_malformed():
    """Regression guard: a valid PDF truncated to the old sample size parses as
    corrupt, which is exactly the failure users saw on finalize."""
    pdf_path = os.path.join(GOLDEN_DIR, "sample_financial.pdf")
    with open(pdf_path, "rb") as f:
        content = f.read()

    validate_file_security(content, "sample_financial.pdf", "application/pdf")

    truncated = content[: len(content) // 2]
    with pytest.raises(SecurityPipelineException) as exc:
        validate_file_security(truncated, "sample_financial.pdf", "application/pdf")
    assert exc.value.code == "MALFORMED_DOCUMENT"


@pytest.mark.unit
def test_permission_only_encrypted_pdf_is_accepted():
    """Bank and regulator filings ship with permission-only encryption and an
    empty user password. They open and extract normally, so rejecting them on
    `is_encrypted` alone blocks the product's primary document source."""
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt(user_password="", owner_password="restricted-owner-pw")
    buffer = BytesIO()
    writer.write(buffer)

    result = validate_file_security(buffer.getvalue(), "solo_filing.pdf", "application/pdf")
    assert result["detected_mime"] == "application/pdf"


@pytest.mark.unit
def test_pdf_requiring_a_real_password_is_still_rejected():
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt(user_password="needs-a-password", owner_password="owner-pw")
    buffer = BytesIO()
    writer.write(buffer)

    with pytest.raises(SecurityPipelineException) as exc:
        validate_file_security(buffer.getvalue(), "locked.pdf", "application/pdf")
    assert exc.value.code == "ENCRYPTED_DOCUMENT"
