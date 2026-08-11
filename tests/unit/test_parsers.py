import os

import pytest
from app.parsers.csv_parser import CsvParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.xlsx_parser import XlsxParser

GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden"))


@pytest.mark.unit
def test_pdf_parser_on_synthetic_pdf():
    pdf_path = os.path.join(GOLDEN_DIR, "sample_financial.pdf")
    with open(pdf_path, "rb") as f:
        content = f.read()

    parser = PdfParser()
    out = parser.parse(content, "sample_financial.pdf")
    assert out.parser_name == "PdfParser"
    assert out.status in ["EXTRACTED", "AWAITING_REVIEW"]


@pytest.mark.unit
def test_xlsx_parser_on_synthetic_xlsx():
    xlsx_path = os.path.join(GOLDEN_DIR, "sample_ledger.xlsx")
    with open(xlsx_path, "rb") as f:
        content = f.read()

    parser = XlsxParser()
    out = parser.parse(content, "sample_ledger.xlsx")
    assert out.parser_name == "XlsxParser"
    assert out.status in ["EXTRACTED", "COMPLETED_WITH_WARNINGS"]
    assert len(out.chunks) > 0

    # Verify formula text is preserved unevaluated
    formula_chunks = [c for c in out.chunks if c["source_lineage"].get("is_formula") is True]
    assert len(formula_chunks) > 0
    assert formula_chunks[0]["source_lineage"]["formula_text"].startswith("=")


@pytest.mark.unit
def test_csv_parser_formula_injection_and_raw_preservation():
    csv_path = os.path.join(GOLDEN_DIR, "sample_formula_injection.csv")
    with open(csv_path, "rb") as f:
        content = f.read()

    parser = CsvParser()
    out = parser.parse(content, "sample_formula_injection.csv")
    assert out.parser_name == "CsvParser"
    assert out.status == "COMPLETED_WITH_WARNINGS"

    # Verify formula injection warning is logged
    warnings = [w for w in out.warnings if w.warning_code == "CSV_FORMULA_INJECTION_RISK"]
    assert len(warnings) > 0

    # Verify RAW CELL VALUE IS NEVER MUTATED IN DATABASE
    raw_cells = [c["content"] for c in out.chunks if c["source_lineage"].get("formula_injection_risk") is True]
    assert len(raw_cells) > 0
    assert any(cell.startswith("=") for cell in raw_cells)


@pytest.mark.unit
def test_csv_parser_turkish_characters():
    csv_path = os.path.join(GOLDEN_DIR, "sample_turkish.csv")
    with open(csv_path, "rb") as f:
        content = f.read()

    parser = CsvParser()
    out = parser.parse(content, "sample_turkish.csv")
    assert out.status == "COMPLETED"

    assert any("İstanbul" in c["content"] for c in out.chunks)
