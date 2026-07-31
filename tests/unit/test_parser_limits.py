import io
import os
import zipfile

import pytest

from services.api.app.core.config import settings
from services.api.app.parsers.csv_parser import CsvParser
from services.api.app.parsers.pdf_parser import PdfParser
from services.api.app.parsers.xlsx_parser import XlsxParser

GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden"))


@pytest.mark.unit
def test_csv_parser_null_byte_rejection():
    parser = CsvParser()
    out = parser.parse(b"col1,col2\nval1,\x00val2", "null_byte.csv")
    assert out.status == "REJECTED"
    assert any(w.warning_code == "NULL_BYTE_DETECTED" for w in out.warnings)


@pytest.mark.unit
def test_csv_parser_encoding_uncertain_rejection():
    parser = CsvParser()
    out = parser.parse(b"\x80\x81\x82\x83\x84\x85\x86\x87", "invalid.csv")
    assert out.status == "AWAITING_REVIEW"
    assert any(w.warning_code == "ENCODING_UNCERTAIN" for w in out.warnings)


@pytest.mark.unit
def test_csv_parser_row_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_CSV_ROWS", 2)
    parser = CsvParser()
    csv_data = b"col1,col2\nval1,val2\nval3,val4\nval5,val6\nval7,val8"
    out = parser.parse(csv_data, "rows.csv")
    assert out.status == "COMPLETED_WITH_WARNINGS"
    assert any(w.warning_code == "RESOURCE_LIMIT_EXCEEDED" and "row count" in w.warning_message for w in out.warnings)


@pytest.mark.unit
def test_csv_parser_column_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_CSV_COLS", 2)
    parser = CsvParser()
    csv_data = b"c1,c2,c3,c4,c5\nv1,v2,v3,v4,v5"
    out = parser.parse(csv_data, "cols.csv")
    assert out.status == "COMPLETED_WITH_WARNINGS"
    assert any(
        w.warning_code == "RESOURCE_LIMIT_EXCEEDED" and "column count" in w.warning_message for w in out.warnings
    )


@pytest.mark.unit
def test_csv_parser_cell_length_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_CELL_LEN", 5)
    parser = CsvParser()
    csv_data = b"col1,col2\nval1,extremely_long_cell_value_123456789"
    out = parser.parse(csv_data, "cell_len.csv")
    assert out.status == "COMPLETED_WITH_WARNINGS"
    assert any(w.warning_code == "CSV_CELL_TRUNCATED" for w in out.warnings)
    cell_chunks = [c for c in out.chunks if c["chunk_type"] == "CELL"]
    assert len(cell_chunks) > 0
    assert cell_chunks[-1]["content"] == "extre"
    assert cell_chunks[-1]["source_lineage"].get("truncated") is True


@pytest.mark.unit
def test_xlsx_parser_sheet_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_XLSX_SHEETS", 0)
    xlsx_path = os.path.join(GOLDEN_DIR, "sample_ledger.xlsx")
    with open(xlsx_path, "rb") as f:
        xlsx_bytes = f.read()
    parser = XlsxParser()
    out = parser.parse(xlsx_bytes, "sample_ledger.xlsx")
    assert out.status == "COMPLETED_WITH_WARNINGS"
    assert any(w.warning_code == "RESOURCE_LIMIT_EXCEEDED" and "sheet count" in w.warning_message for w in out.warnings)


@pytest.mark.unit
def test_xlsx_parser_row_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_XLSX_ROWS", 1)
    xlsx_path = os.path.join(GOLDEN_DIR, "sample_ledger.xlsx")
    with open(xlsx_path, "rb") as f:
        xlsx_bytes = f.read()
    parser = XlsxParser()
    out = parser.parse(xlsx_bytes, "sample_ledger.xlsx")
    assert out.status == "COMPLETED_WITH_WARNINGS"
    assert any(w.warning_code == "RESOURCE_LIMIT_EXCEEDED" and "row count" in w.warning_message for w in out.warnings)


@pytest.mark.unit
def test_xlsx_parser_column_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_XLSX_COLS", 1)
    xlsx_path = os.path.join(GOLDEN_DIR, "sample_ledger.xlsx")
    with open(xlsx_path, "rb") as f:
        xlsx_bytes = f.read()
    parser = XlsxParser()
    out = parser.parse(xlsx_bytes, "sample_ledger.xlsx")
    assert out.status == "COMPLETED_WITH_WARNINGS"
    assert any(
        w.warning_code == "RESOURCE_LIMIT_EXCEEDED" and "column count" in w.warning_message for w in out.warnings
    )


@pytest.mark.unit
def test_xlsx_zip_entry_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ZIP_ENTRIES", 2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("f1.txt", "content1")
        zf.writestr("f2.txt", "content2")
        zf.writestr("f3.txt", "content3")
    parser = XlsxParser()
    out = parser.parse(buf.getvalue(), "bomb.xlsx")
    assert out.status == "REJECTED"
    assert any(w.warning_code == "ZIP_BOMB_LIMIT_EXCEEDED" and "ZIP entries" in w.warning_message for w in out.warnings)


@pytest.mark.unit
def test_xlsx_zip_single_entry_uncompressed_byte_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES", 100)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("huge.txt", "A" * 500)
    parser = XlsxParser()
    out = parser.parse(buf.getvalue(), "huge_entry.xlsx")
    assert out.status == "REJECTED"
    assert any(
        w.warning_code == "ZIP_BOMB_LIMIT_EXCEEDED" and "uncompressed size" in w.warning_message for w in out.warnings
    )


@pytest.mark.unit
def test_xlsx_zip_total_uncompressed_byte_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES", 300)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("f1.txt", "A" * 200)
        zf.writestr("f2.txt", "B" * 200)
    parser = XlsxParser()
    out = parser.parse(buf.getvalue(), "total_huge.xlsx")
    assert out.status == "REJECTED"
    assert any(
        w.warning_code == "ZIP_BOMB_LIMIT_EXCEEDED" and "total uncompressed" in w.warning_message for w in out.warnings
    )


@pytest.mark.unit
def test_xlsx_zip_compression_ratio_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ZIP_COMPRESSION_RATIO", 2.0)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("high_comp.txt", "0" * 10000)
    parser = XlsxParser()
    out = parser.parse(buf.getvalue(), "high_comp.xlsx")
    assert out.status == "REJECTED"
    assert any(
        w.warning_code == "ZIP_BOMB_LIMIT_EXCEEDED" and "compression ratio" in w.warning_message for w in out.warnings
    )


@pytest.mark.unit
def test_pdf_parser_page_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PDF_PAGES", 0)
    pdf_path = os.path.join(GOLDEN_DIR, "sample_financial.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    parser = PdfParser()
    out = parser.parse(pdf_bytes, "sample_financial.pdf")
    assert out.status == "AWAITING_REVIEW"
    assert any(w.warning_code == "RESOURCE_LIMIT_EXCEEDED" for w in out.warnings)


@pytest.mark.unit
def test_pdf_parser_text_char_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PDF_TEXT_CHARS", 1)
    pdf_path = os.path.join(GOLDEN_DIR, "sample_financial.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    parser = PdfParser()
    out = parser.parse(pdf_bytes, "sample_financial.pdf")
    assert out.status == "AWAITING_REVIEW"
    assert any(w.warning_code in ("RESOURCE_LIMIT_EXCEEDED", "OCR_REQUIRED_BUT_UNAVAILABLE") for w in out.warnings)


@pytest.mark.unit
def test_xlsx_parser_corrupt_container():
    parser = XlsxParser()
    out = parser.parse(b"NOT_A_ZIP_CONTAINER", "corrupt.xlsx")
    assert out.status == "FAILED"
    assert any(w.warning_code == "MALFORMED_DOCUMENT" for w in out.warnings)
