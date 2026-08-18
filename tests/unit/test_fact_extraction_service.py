from datetime import date

import pytest
from app.services.fact_extraction_service import FactExtractionService


@pytest.mark.unit
def test_document_context_is_inferred_from_filing_name():
    ctx = FactExtractionService.parse_document_context("Solo_VAKBN_31.03.2026__TR.pdf")
    assert ctx.institution_code == "VAKBN"
    assert ctx.period_end == date(2026, 3, 31)
    assert ctx.reporting_basis == "SOLO"


@pytest.mark.unit
def test_consolidated_and_iso_dates_are_recognised():
    ctx = FactExtractionService.parse_document_context("Konsolide_GARAN_2025-12-31_TR.pdf")
    assert ctx.institution_code == "GARAN"
    assert ctx.period_end == date(2025, 12, 31)
    assert ctx.reporting_basis == "CONSOLIDATED"


@pytest.mark.unit
def test_unparseable_name_yields_no_context_instead_of_guessing():
    ctx = FactExtractionService.parse_document_context("rapor.pdf")
    assert ctx.period_end is None
    assert ctx.reporting_basis == "UNKNOWN"


@pytest.mark.unit
def test_table_rows_pair_labels_with_their_first_numeric_cell():
    content = (
        "Toplam Aktifler | 1.234.567 | 1.100.000\n"
        "Açıklama satırı | metin | başka metin\n"
        "Toplam Krediler |  | 987.654\n"
        "| 42"
    )
    rows = FactExtractionService.iter_table_rows(content)
    assert ("Toplam Aktifler", "1.234.567") in rows
    assert ("Toplam Krediler", "987.654") in rows
    # Rows without a numeric cell or without a label are not candidates.
    assert all(label.strip() for label, _ in rows)
    assert len(rows) == 2


@pytest.mark.unit
def test_candidate_ceiling_is_defined():
    """A filing repeats captions across dozens of note tables; the ceiling keeps
    a single document from flooding the review queue."""
    from app.services.fact_extraction_service import MAX_CANDIDATES_PER_VERSION

    assert 0 < MAX_CANDIDATES_PER_VERSION <= 500
