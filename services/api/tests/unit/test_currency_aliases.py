"""A filing writes TL; the fact store and every comparison speak ISO 4217."""

import pytest
from app.services.normalization_service import NormalizationService


@pytest.mark.parametrize("written", ["TL", "tl", " TL ", "₺", "TRL", "TRY"])
def test_the_lira_always_lands_as_try(written):
    assert NormalizationService.normalize_currency(written) == "TRY"


@pytest.mark.parametrize("written,expected", [("$", "USD"), ("€", "EUR"), ("£", "GBP")])
def test_common_symbols_resolve(written, expected):
    assert NormalizationService.normalize_currency(written) == expected


def test_an_unknown_currency_is_still_refused():
    with pytest.raises(ValueError, match="UNSUPPORTED_CURRENCY"):
        NormalizationService.normalize_currency("XYZ")
