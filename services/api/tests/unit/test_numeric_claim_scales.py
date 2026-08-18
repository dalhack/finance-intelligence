"""The gate must refuse invented numbers without refusing honest presentations."""

import pytest
from app.orchestration.exceptions import UnsupportedNumericClaimException
from app.orchestration.quality_gate import NumericClaimVerifier

DATASET = {
    "organization_id": "org-1",
    "facts": [{"organization_id": "org-1", "value": "5550109551000", "metric": "TOTAL_ASSETS"}],
}


@pytest.mark.parametrize(
    "narrative",
    [
        "Toplam aktifler 5550109551000 TL olarak raporlandı.",
        "Toplam aktifler 5.550.109,55 milyon TL olarak raporlandı.",
        "Toplam aktifler 5.550,11 milyar TL seviyesindedir.",
    ],
)
def test_the_same_figure_written_at_any_scale_passes(narrative):
    NumericClaimVerifier.verify_narrative_numeric_claims(narrative, DATASET)


def test_a_number_that_is_not_the_figure_still_fails():
    with pytest.raises(UnsupportedNumericClaimException):
        NumericClaimVerifier.verify_narrative_numeric_claims(
            "Toplam aktifler 7.777.777 milyon TL olarak raporlandı.", DATASET
        )
