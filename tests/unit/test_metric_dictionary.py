from app.models.metric_definition import MetricDefinition

EXPECTED_METRICS = [
    "TOTAL_ASSETS",
    "TOTAL_LOANS",
    "TOTAL_DEPOSITS",
    "TOTAL_EQUITY",
    "NET_INCOME",
    "NON_PERFORMING_LOANS",
    "CAPITAL_ADEQUACY_RATIO",
    "RETURN_ON_ASSETS",
    "RETURN_ON_EQUITY",
    "NET_INTEREST_MARGIN",
    "LOAN_TO_DEPOSIT_RATIO",
]


def test_mvp_metric_dictionary_codes():
    assert len(EXPECTED_METRICS) == 11
    # Verify metric definition model fields exist
    md = MetricDefinition(
        metric_code="TOTAL_ASSETS",
        canonical_name="Toplam Aktifler",
        value_type="CURRENCY",
        default_unit="TRY",
    )
    assert md.metric_code == "TOTAL_ASSETS"
    assert md.canonical_name == "Toplam Aktifler"
