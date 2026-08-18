"""A question names its metric in prose; guessing the wrong one is worse than none."""

from app.orchestration.metric_resolution import resolve_metric_codes

CATALOG = [
    ("TOTAL_ASSETS", "Toplam Aktifler"),
    ("TOTAL_LOANS", "Toplam Krediler"),
    ("TOTAL_DEPOSITS", "Toplam Mevduat"),
    ("TOTAL_EQUITY", "Toplam Özkaynaklar"),
    ("PAID_IN_CAPITAL", "Ödenmiş Sermaye"),
    ("NET_INCOME", "Net Dönem Kârı"),
    ("INTEREST_INCOME", "Faiz Gelirleri"),
    ("NET_INTEREST_INCOME", "Net Faiz Geliri veya Gideri"),
]


def test_resolves_the_line_the_question_names():
    codes = resolve_metric_codes("VAKBN 2026 birinci çeyrek ödenmiş sermaye ne kadar?", CATALOG)
    assert codes == ["PAID_IN_CAPITAL"]


def test_resolves_through_a_turkish_suffix():
    assert "TOTAL_EQUITY" in resolve_metric_codes("bankanın toplam özkaynakları nedir", CATALOG)


def test_resolves_a_bare_code():
    assert resolve_metric_codes("TOTAL_ASSETS değerini göster", CATALOG) == ["TOTAL_ASSETS"]


def test_prefers_the_longer_name_when_one_contains_another():
    codes = resolve_metric_codes("net faiz geliri veya gideri kalemini göster", CATALOG)
    assert codes[0] == "NET_INTEREST_INCOME"


def test_resolves_several_lines_from_one_question():
    codes = resolve_metric_codes("toplam aktifler ve toplam mevduat tablosu", CATALOG)
    assert set(codes) == {"TOTAL_ASSETS", "TOTAL_DEPOSITS"}


def test_a_question_naming_no_line_resolves_to_nothing():
    """Returning a default here is what answered the wrong question."""
    assert resolve_metric_codes("bu bankanın durumu nasıl", CATALOG) == []
    assert resolve_metric_codes("", CATALOG) == []
    assert resolve_metric_codes("toplam aktifler", []) == []
