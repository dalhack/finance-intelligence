from uuid import uuid4
import pytest
from app.orchestration.exceptions import UnsupportedNumericClaimException
from app.orchestration.quality_gate import NumericClaimVerifier

ORG_ID_A = "e9b3034d-6fed-4d99-8543-edf6daa3a866"
ORG_ID_B = "11111111-2222-3333-4444-555555555555"

SAMPLE_DATASET = {
    "organization_id": ORG_ID_A,
    "facts": [
        {
            "fact_id": str(uuid4()),
            "organization_id": ORG_ID_A,
            "metric": "TOTAL_ASSETS",
            "value": 2450000000000.0,
            "currency": "TRY",
            "unit": "CURRENCY",
            "reporting_basis": "SOLO",
        },
        {
            "fact_id": str(uuid4()),
            "organization_id": ORG_ID_A,
            "metric": "TOTAL_ASSETS",
            "value": 1980000000000.0,
            "currency": "TRY",
            "unit": "CURRENCY",
            "reporting_basis": "SOLO",
        },
    ],
}


def test_existing_direct_fact_verification_remains_accepted():
    dataset = {"cells": [{"display_value": "1,500,000"}]}
    NumericClaimVerifier.verify_narrative_numeric_claims("Total assets reached 1,500,000 TRY.", dataset)


def test_verified_subtraction_accepted():
    narrative = "Fark ₺470.000.000.000 (470 milyar) olarak gerçekleşti."
    NumericClaimVerifier.verify_narrative_numeric_claims(narrative, SAMPLE_DATASET)


def test_verified_addition_accepted():
    narrative = "Birleşik toplam ₺4.430.000.000.000 (4430 milyar) oldu."
    NumericClaimVerifier.verify_narrative_numeric_claims(narrative, SAMPLE_DATASET)


def test_verified_ratio_accepted():
    narrative = "Oran %80,82 olarak hesaplanmıştır."
    NumericClaimVerifier.verify_narrative_numeric_claims(narrative, SAMPLE_DATASET)


def test_verified_percentage_change_accepted():
    narrative = "Büyüklük farkı %23,74 seviyesindedir."
    NumericClaimVerifier.verify_narrative_numeric_claims(narrative, SAMPLE_DATASET)


def test_wrong_operand_rejected():
    narrative = "Fark ₺999.000.000.000 olarak yanlış hesaplandı."
    with pytest.raises(UnsupportedNumericClaimException):
        NumericClaimVerifier.verify_narrative_numeric_claims(narrative, SAMPLE_DATASET)


def test_cross_tenant_evidence_rejected():
    dataset = {
        "organization_id": ORG_ID_A,
        "facts": [
            {
                "fact_id": str(uuid4()),
                "organization_id": ORG_ID_A,
                "value": 200000000.0,
                "currency": "TRY",
                "unit": "CURRENCY",
                "reporting_basis": "SOLO",
            },
            {
                "fact_id": str(uuid4()),
                "organization_id": ORG_ID_B,  # Mismatched Tenant
                "value": 100000000.0,
                "currency": "TRY",
                "unit": "CURRENCY",
                "reporting_basis": "SOLO",
            },
        ],
    }
    narrative = "Fark 100.000.000 TRY oldu."
    with pytest.raises(UnsupportedNumericClaimException):
        NumericClaimVerifier.verify_narrative_numeric_claims(narrative, dataset)


def test_currency_unit_basis_mismatch_rejected():
    dataset = {
        "organization_id": ORG_ID_A,
        "facts": [
            {
                "fact_id": str(uuid4()),
                "value": 200000000.0,
                "currency": "USD",  # USD
                "unit": "CURRENCY",
                "reporting_basis": "SOLO",
            },
            {
                "fact_id": str(uuid4()),
                "value": 100000000.0,
                "currency": "EUR",  # EUR
                "unit": "CURRENCY",
                "reporting_basis": "SOLO",
            },
        ],
    }
    narrative = "Fark 100.000.000 oldu."
    with pytest.raises(UnsupportedNumericClaimException):
        NumericClaimVerifier.verify_narrative_numeric_claims(narrative, dataset)


def test_zero_denominator_rejected():
    dataset = {
        "organization_id": ORG_ID_A,
        "facts": [
            {"fact_id": str(uuid4()), "value": 100000.0, "currency": "TRY", "unit": "CURRENCY", "reporting_basis": "SOLO"},
            {"fact_id": str(uuid4()), "value": 0.0, "currency": "TRY", "unit": "CURRENCY", "reporting_basis": "SOLO"},
        ],
    }
    narrative = "Oran %500.000 olarak kaydedildi."
    with pytest.raises(UnsupportedNumericClaimException):
        NumericClaimVerifier.verify_narrative_numeric_claims(narrative, dataset)


def test_free_text_math_without_evidence_rejected():
    narrative = "Uydurma sayı 888.888.888 tespit edildi."
    with pytest.raises(UnsupportedNumericClaimException):
        NumericClaimVerifier.verify_narrative_numeric_claims(narrative, SAMPLE_DATASET)


def test_rounding_cannot_bypass_canonical_recomputation():
    narrative = "Gelişigüzel yuvarlanmış uydurma değer 777.777 kabul edilemez."
    with pytest.raises(UnsupportedNumericClaimException):
        NumericClaimVerifier.verify_narrative_numeric_claims(narrative, SAMPLE_DATASET)
