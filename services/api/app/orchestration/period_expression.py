"""Understands the ways a reporting period gets written in a question.

A tenant's periods are stored canonically — label `2026/Q1`, comparison key
`2026-Q1`. A person asking a question does not write either of those. They
write "2026 birinci çeyrek", "2026 1. çeyrek", "1Ç26", "Mart 2026 dönemi" or
"31.03.2026", and matching those against the canonical text by substring finds
nothing, so a perfectly answerable question is bounced back for clarification.

This module reduces both sides to the same structural key — a fiscal year and,
when the wording names one, a quarter — so the question and the stored period
can be compared on what they mean rather than on how they were typed.
"""

import re
from dataclasses import dataclass


# A period reference is a year with an optional quarter. A year on its own
# means the full year, which is how a filing labels its annual figures.
@dataclass(frozen=True)
class PeriodKey:
    fiscal_year: int
    quarter: int | None

    def matches(self, other: "PeriodKey") -> bool:
        """True when the two references can denote the same period.

        A reference that names no quarter is deliberately permissive: "2026"
        should find the 2026 periods rather than nothing at all.
        """
        if self.fiscal_year != other.fiscal_year:
            return False
        return self.quarter is None or other.quarter is None or self.quarter == other.quarter


_ORDINAL_WORDS = {
    "ilk": 1,
    "birinci": 1,
    "1": 1,
    "i": 1,
    "ikinci": 2,
    "2": 2,
    "ii": 2,
    "üçüncü": 3,
    "ucuncu": 3,
    "3": 3,
    "iii": 3,
    "dördüncü": 4,
    "dorduncu": 4,
    "son": 4,
    "4": 4,
    "iv": 4,
}

_MONTH_TO_QUARTER = {
    "ocak": 1,
    "şubat": 1,
    "subat": 1,
    "mart": 1,
    "nisan": 2,
    "mayıs": 2,
    "mayis": 2,
    "haziran": 2,
    "temmuz": 3,
    "ağustos": 3,
    "agustos": 3,
    "eylül": 3,
    "eylul": 3,
    "ekim": 4,
    "kasım": 4,
    "kasim": 4,
    "aralık": 4,
    "aralik": 4,
}

_YEAR = r"(19|20)\d{2}"

# "2026/Q1", "2026-Q1", "2026 Q1", "FY2026"
_YEAR_THEN_QUARTER = re.compile(rf"\b({_YEAR})\s*[/\-_ ]?\s*[qç]\s*([1-4])\b", re.IGNORECASE)
# "Q1 2026", "1Ç26", "1Ç2026"
_QUARTER_THEN_YEAR = re.compile(rf"\b[qç]?\s*([1-4])\s*[qç]\s*({_YEAR}|\d{{2}})\b", re.IGNORECASE)
_QUARTER_LABEL_THEN_YEAR = re.compile(rf"\b[qç]\s*([1-4])\s*[/\-_ ]?\s*({_YEAR})\b", re.IGNORECASE)
# "2026 birinci çeyrek", "2026 1. çeyrek", "2026 yılının ilk çeyreği"
_YEAR_THEN_WORD_QUARTER = re.compile(
    rf"\b({_YEAR})\b[^0-9]{{0,24}}?\b([1-4]|ilk|birinci|ikinci|üçüncü|ucuncu|dördüncü|dorduncu|son)\b\.?\s*çeyre",
    re.IGNORECASE,
)
# "birinci çeyrek 2026", "ilk çeyrek 2026"
_WORD_QUARTER_THEN_YEAR = re.compile(
    rf"\b([1-4]|ilk|birinci|ikinci|üçüncü|ucuncu|dördüncü|dorduncu|son)\b\.?\s*çeyre\w*\s*(?:\w+\s+){{0,2}}?\b({_YEAR})\b",
    re.IGNORECASE,
)
# "31.03.2026", "2026-03-31"
_DMY = re.compile(rf"\b(\d{{1,2}})[./\-](\d{{1,2}})[./\-]({_YEAR})\b")
_YMD = re.compile(rf"\b({_YEAR})[./\-](\d{{1,2}})[./\-](\d{{1,2}})\b")
# "Mart 2026", "2026 Mart"
_MONTH_THEN_YEAR = re.compile(rf"\b({'|'.join(_MONTH_TO_QUARTER)})\s+({_YEAR})\b", re.IGNORECASE)
_YEAR_THEN_MONTH = re.compile(rf"\b({_YEAR})\s+({'|'.join(_MONTH_TO_QUARTER)})\b", re.IGNORECASE)
_BARE_YEAR = re.compile(rf"\b({_YEAR})\b")


def _expand_two_digit_year(raw: str) -> int:
    year = int(raw)
    return year if year > 99 else 2000 + year


def parse_period_keys(text: str) -> set[PeriodKey]:
    """Every period a piece of text can be read as naming.

    More than one is returned when the wording is genuinely ambiguous; the
    caller treats any overlap as a match, which is the behaviour a question
    like "2026 birinci çeyrek bilançosu" needs.
    """
    if not text:
        return set()

    keys: set[PeriodKey] = set()
    lowered = text.casefold()

    for match in _YEAR_THEN_QUARTER.finditer(lowered):
        keys.add(PeriodKey(int(match.group(1)), int(match.group(3))))
    for match in _QUARTER_LABEL_THEN_YEAR.finditer(lowered):
        keys.add(PeriodKey(int(match.group(2)), int(match.group(1))))
    for match in _QUARTER_THEN_YEAR.finditer(lowered):
        keys.add(PeriodKey(_expand_two_digit_year(match.group(2)), int(match.group(1))))
    for match in _YEAR_THEN_WORD_QUARTER.finditer(lowered):
        quarter = _ORDINAL_WORDS.get(match.group(3))
        if quarter:
            keys.add(PeriodKey(int(match.group(1)), quarter))
    for match in _WORD_QUARTER_THEN_YEAR.finditer(lowered):
        quarter = _ORDINAL_WORDS.get(match.group(1))
        if quarter:
            keys.add(PeriodKey(int(match.group(2)), quarter))

    for match in _YMD.finditer(lowered):
        month = int(match.group(3))
        if 1 <= month <= 12:
            keys.add(PeriodKey(int(match.group(1)), (month - 1) // 3 + 1))
    for match in _DMY.finditer(lowered):
        month = int(match.group(2))
        if 1 <= month <= 12:
            keys.add(PeriodKey(int(match.group(3)), (month - 1) // 3 + 1))

    for match in _MONTH_THEN_YEAR.finditer(lowered):
        keys.add(PeriodKey(int(match.group(2)), _MONTH_TO_QUARTER[match.group(1)]))
    for match in _YEAR_THEN_MONTH.finditer(lowered):
        keys.add(PeriodKey(int(match.group(1)), _MONTH_TO_QUARTER[match.group(3)]))

    # A bare year only counts when nothing more specific was found, so that
    # "2026 birinci çeyrek" does not also assert the whole of 2026.
    if not keys:
        for match in _BARE_YEAR.finditer(lowered):
            keys.add(PeriodKey(int(match.group(1)), None))

    return keys


def period_record_keys(period: object) -> set[PeriodKey]:
    """The structural keys of a stored reporting period.

    Its own columns are authoritative; its label and comparison key are read
    too, so a period stored with an unusual label still resolves.
    """
    keys: set[PeriodKey] = set()

    fiscal_year = getattr(period, "fiscal_year", None)
    if isinstance(fiscal_year, int):
        quarter = getattr(period, "quarter", None)
        keys.add(PeriodKey(fiscal_year, quarter if isinstance(quarter, int) else None))

    for attribute in ("label", "comparison_key"):
        value = getattr(period, attribute, None)
        if isinstance(value, str):
            keys |= parse_period_keys(value)

    return keys


def text_matches_period(text: str, period: object) -> bool:
    """True when the wording can be read as naming this stored period."""
    asked = parse_period_keys(text)
    if not asked:
        return False
    stored = period_record_keys(period)
    return any(a.matches(s) for a in asked for s in stored)
