"""A question names its period in prose; the resolver has to recognise it."""

from dataclasses import dataclass

import pytest
from app.orchestration.period_expression import (
    PeriodKey,
    parse_period_keys,
    period_record_keys,
    text_matches_period,
)


@dataclass
class StoredPeriod:
    fiscal_year: int = 2026
    quarter: int | None = 1
    label: str = "2026/Q1"
    comparison_key: str = "2026-Q1"


@pytest.mark.parametrize(
    "text",
    [
        "2026/Q1",
        "2026 Q1",
        "2026-Q1",
        "Q1 2026",
        "1Ç2026",
        "1Ç26",
        "2026 birinci çeyrek",
        "2026 ilk çeyrek",
        "2026 1. çeyrek",
        "2026 yılının ilk çeyreği",
        "birinci çeyrek 2026",
        "31.03.2026",
        "2026-03-31",
        "Mart 2026",
        "2026 Mart",
    ],
)
def test_the_ways_a_person_writes_the_first_quarter_of_2026(text):
    assert text_matches_period(text, StoredPeriod()), text


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2025 dördüncü çeyrek", PeriodKey(2025, 4)),
        ("2024 üçüncü çeyrek", PeriodKey(2024, 3)),
        ("30.06.2025", PeriodKey(2025, 2)),
        ("Aralık 2025", PeriodKey(2025, 4)),
        ("2Ç25", PeriodKey(2025, 2)),
    ],
)
def test_other_quarters_resolve_to_their_own_key(text, expected):
    assert expected in parse_period_keys(text)


def test_a_different_quarter_does_not_match():
    assert not text_matches_period("2026 ikinci çeyrek", StoredPeriod())
    assert not text_matches_period("2025 birinci çeyrek", StoredPeriod())


def test_a_bare_year_matches_any_quarter_of_that_year():
    """Asking about 2026 should reach 2026 data rather than be refused."""
    assert text_matches_period("2026 bilançosu", StoredPeriod())
    assert not text_matches_period("2025 bilançosu", StoredPeriod())


def test_a_bare_year_is_not_asserted_when_a_quarter_was_named():
    keys = parse_period_keys("2026 birinci çeyrek")
    assert PeriodKey(2026, 1) in keys
    assert PeriodKey(2026, None) not in keys


def test_text_without_a_period_matches_nothing():
    assert parse_period_keys("toplam aktifleri göster") == set()
    assert not text_matches_period("toplam aktifleri göster", StoredPeriod())
    assert not text_matches_period("", StoredPeriod())


def test_a_stored_period_is_read_from_its_own_columns():
    """The label may be unusual; the columns still identify the period."""
    period = StoredPeriod(label="Ocak-Mart dönemi", comparison_key="internal-7")
    assert PeriodKey(2026, 1) in period_record_keys(period)
    assert text_matches_period("2026 birinci çeyrek", period)


def test_an_annual_period_matches_a_year_reference():
    annual = StoredPeriod(quarter=None, label="2025/FY", comparison_key="2025-FY")
    assert text_matches_period("2025 yılı", annual)
    assert not text_matches_period("2024 yılı", annual)


def test_two_digit_years_do_not_swallow_unrelated_numbers():
    assert parse_period_keys("3 çeyreklik büyüme") == set()


def test_a_prompt_naming_both_institution_and_period_still_resolves():
    prompt = "VAKBN için 2026 birinci çeyrek solo ödenmiş sermaye değerini tablo olarak göster."
    assert text_matches_period(prompt, StoredPeriod())
