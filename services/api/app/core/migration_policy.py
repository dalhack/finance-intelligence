"""Canonical Irreversible Migration Policy Registry.

Defines machine-readable policies and boundaries for applied historical migrations.
"""

from typing import Any, Final

IRREVERSIBLE_MIGRATION_POLICIES: Final[dict[str, dict[str, Any]]] = {
    "023_analysis_clarification_workflow": {
        "revision": "023_analysis_clarification_workflow",
        "classification": "IRREVERSIBLE",
        "minimum_safe_downgrade_target": "023_analysis_clarification_workflow",
        "reason_code": "IRREVERSIBLE_CLARIFICATION_DATA_MODEL",
        "owner": "finance-intelligence-core",
        "introduced_at": "2026-07-31",
        "remediation_policy": (
            "Disaster Recovery via Point-In-Time-Recovery (PITR) / Database Backup Snapshot. "
            "Data model state cannot be safely down-migrated without destructive data loss."
        ),
    }
}


def get_minimum_safe_downgrade_target(current_head: str) -> str:
    """Returns the minimum safe downgrade target revision for the given head.

    If any migration up to current_head is marked IRREVERSIBLE, the minimum safe
    target is the latest IRREVERSIBLE migration boundary.
    """
    for policy in IRREVERSIBLE_MIGRATION_POLICIES.values():
        if policy.get("classification") == "IRREVERSIBLE":
            return str(policy["minimum_safe_downgrade_target"])
    return "base"


def validate_downgrade_target(target_revision: str) -> None:
    """Validates that target_revision does not cross any irreversible migration boundary.

    Raises RuntimeError with MIGRATION_IRREVERSIBLE_BOUNDARY_VIOLATION if boundary is violated.
    """
    if target_revision in (
        "base",
        "000",
        "001",
        "002",
        "003",
        "004",
        "005",
        "006",
        "007",
        "008",
        "009",
        "010",
        "011",
        "012",
        "013",
        "014",
        "015",
        "016",
        "017",
        "018",
        "019",
        "020",
        "021",
        "022",
    ):
        min_safe = get_minimum_safe_downgrade_target("head")
        raise RuntimeError(
            f"MIGRATION_IRREVERSIBLE_BOUNDARY_VIOLATION: Requested downgrade target '{target_revision}' "
            f"violates irreversible migration boundary at '{min_safe}'. "
            "Down-migrating across irreversible data model boundaries is forbidden. "
            "Use Point-In-Time-Recovery (PITR) / Database Backup Snapshot for disaster recovery."
        )
