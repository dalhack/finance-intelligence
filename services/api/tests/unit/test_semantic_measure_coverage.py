"""Every catalog line must be measurable, or a understood question still fails."""

import importlib.util
from pathlib import Path

from app.calculations.semantic_measure_registry import SemanticMeasureRegistry

MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "035_metric_hierarchy_and_statement_lines.py"
)


def _seeded_codes() -> set[str]:
    spec = importlib.util.spec_from_file_location("metric_seed", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {row[0] for row in module.NEW_METRICS} | {row[0] for row in module.EXISTING_PLACEMENT}


def test_every_seeded_metric_is_a_known_semantic_measure():
    missing = sorted(code for code in _seeded_codes() if code not in SemanticMeasureRegistry._DEFINITIONS)
    assert not missing, f"catalog lines with no semantic measure: {missing}"


def test_paid_in_capital_resolves_to_its_own_reported_metric():
    definition = SemanticMeasureRegistry.get("PAID_IN_CAPITAL")
    assert definition.reported_metric_code == "PAID_IN_CAPITAL"
    assert definition.result_unit == "CURRENCY"


def test_generated_lines_do_not_overwrite_hand_written_definitions():
    """Total assets was defined by hand; regeneration must not replace it."""
    assert SemanticMeasureRegistry.get("TOTAL_ASSETS").display_name == "Total Assets"
