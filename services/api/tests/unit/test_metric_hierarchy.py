"""The seeded catalog must form a usable tree, and the reader must be told what each code means."""

import importlib.util
from pathlib import Path

from app.services.llm_fact_extraction_service import build_extraction_tool

MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "035_metric_hierarchy_and_statement_lines.py"


def _seed():
    spec = importlib.util.spec_from_file_location("metric_hierarchy_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_parent_is_a_metric_that_exists():
    """A parent pointing at nothing would break a breakdown query at read time."""
    seed = _seed()
    known = {row[0] for row in seed.NEW_METRICS} | {row[0] for row in seed.EXISTING_PLACEMENT}

    parents = {row[3] for row in seed.NEW_METRICS if row[3]} | {row[2] for row in seed.EXISTING_PLACEMENT if row[2]}

    assert parents <= known, f"parents with no metric: {sorted(parents - known)}"


def test_no_metric_is_its_own_parent():
    seed = _seed()
    for code, _name, _section, parent, *_ in seed.NEW_METRICS:
        assert parent != code


def test_the_hierarchy_has_no_cycles():
    seed = _seed()
    parent_of = {row[0]: row[3] for row in seed.NEW_METRICS}
    parent_of.update({row[0]: row[2] for row in seed.EXISTING_PLACEMENT})

    for code in parent_of:
        seen = set()
        cursor = code
        while cursor is not None:
            assert cursor not in seen, f"cycle reached from {code}"
            seen.add(cursor)
            cursor = parent_of.get(cursor)


def test_codes_are_unique_and_do_not_collide_with_existing_ones():
    seed = _seed()
    new_codes = [row[0] for row in seed.NEW_METRICS]
    existing_codes = [row[0] for row in seed.EXISTING_PLACEMENT]

    assert len(new_codes) == len(set(new_codes))
    assert not set(new_codes) & set(existing_codes)


def test_the_lines_a_filing_lost_now_have_a_home():
    """Net interest income and paid-in capital were read correctly and dropped."""
    codes = {row[0] for row in _seed().NEW_METRICS}
    assert "NET_INTEREST_INCOME" in codes
    assert "PAID_IN_CAPITAL" in codes


def test_liability_children_roll_up_to_total_liabilities():
    seed = _seed()
    children = {row[0] for row in seed.NEW_METRICS if row[3] == "TOTAL_LIABILITIES"}
    assert "FUNDS_BORROWED" in children
    assert "SECURITIES_ISSUED" in children
    # Deposits already existed and must be re-parented, not duplicated.
    assert ("TOTAL_DEPOSITS", "BALANCE_SHEET_LIABILITIES", "TOTAL_LIABILITIES", 110) in seed.EXISTING_PLACEMENT


def test_the_tool_tells_the_model_what_each_code_means():
    tool = build_extraction_tool(
        ["PAID_IN_CAPITAL", "TOTAL_ASSETS"],
        {"PAID_IN_CAPITAL": "Ödenmiş Sermaye", "TOTAL_ASSETS": "Toplam Aktifler"},
    )
    description = tool["description"]

    assert "PAID_IN_CAPITAL = Ödenmiş Sermaye" in description
    assert "TOTAL_ASSETS = Toplam Aktifler" in description


def test_the_tool_still_works_without_a_legend():
    tool = build_extraction_tool(["TOTAL_ASSETS"])
    assert "stands for this statement line" not in tool["description"]
    assert tool["input_schema"]["properties"]["figures"]["items"]["properties"]["metric_code"]["enum"] == [
        "TOTAL_ASSETS"
    ]


def test_a_code_without_a_name_is_omitted_from_the_legend_not_guessed():
    tool = build_extraction_tool(["TOTAL_ASSETS", "MYSTERY"], {"TOTAL_ASSETS": "Toplam Aktifler"})
    assert "MYSTERY =" not in tool["description"]
    assert "TOTAL_ASSETS = Toplam Aktifler" in tool["description"]
