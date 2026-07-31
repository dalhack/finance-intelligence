from datetime import date

from services.api.app.api.v1.facts import (
    ApproveCandidateRequestDTO,
    InstitutionCreateDTO,
    RejectCandidateRequestDTO,
    ReportingPeriodCreateDTO,
)


def test_institution_create_dto():
    dto = InstitutionCreateDTO(
        canonical_name="Garanti BBVA",
        display_name="Garanti Bankası",
        institution_type="BANK",
    )
    assert dto.canonical_name == "Garanti BBVA"
    assert dto.country_code == "TR"


def test_reporting_period_create_dto():
    dto = ReportingPeriodCreateDTO(
        period_type="QUARTER",
        fiscal_year=2025,
        quarter=4,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        label="2025/Q4",
    )
    assert dto.fiscal_year == 2025
    assert dto.quarter == 4


def test_approve_reject_dtos():
    approve_dto = ApproveCandidateRequestDTO(notes="Confirmed from annual report")
    assert approve_dto.notes == "Confirmed from annual report"

    reject_dto = RejectCandidateRequestDTO(reason_code="PARSING_ERROR", notes="Row misalignment")
    assert reject_dto.reason_code == "PARSING_ERROR"
