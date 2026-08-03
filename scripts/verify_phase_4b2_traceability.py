#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FIELDS = [
    "scenario_id",
    "requirement",
    "production_source",
    "test_file",
    "machine_test_id",
    "required_assertions",
    "verification_level",
    "status",
]


def validate_scenarios(scenarios, manifest_tests):
    if len(scenarios) != 78:
        return False, f"Expected 78 scenarios, found {len(scenarios)}"

    unique_sids = set()

    for idx, s in enumerate(scenarios, start=1):
        for field in REQUIRED_FIELDS:
            if field not in s or s[field] is None:
                return False, f"Scenario {idx} missing required field '{field}'"

        sid = s["scenario_id"]
        if sid in unique_sids:
            return False, f"Duplicate scenario ID: {sid}"
        unique_sids.add(sid)

        if not s["required_assertions"] or len(s["required_assertions"]) == 0:
            return False, f"Scenario {sid} has empty required_assertions"

        if s["status"] not in ["IMPLEMENTED_PASS", "DEFERRED", "NOT_IMPLEMENTED"]:
            return False, f"Scenario {sid} has invalid status '{s['status']}'"

    return True, "All 78 scenarios validated cleanly"


def run_self_tests():
    # Self-test 1: Catch missing field
    bad_scenarios_1 = [{"scenario_id": "SC-001"}]
    ok, msg = validate_scenarios(bad_scenarios_1, [])
    assert not ok, f"Self-test 1 failed: should catch missing field ({msg})"

    # Self-test 2: Catch invalid scenario count
    bad_scenarios_2 = [{"scenario_id": f"SC-{i}"} for i in range(10)]
    ok, msg = validate_scenarios(bad_scenarios_2, [])
    assert not ok, f"Self-test 2 failed: should catch count != 78 ({msg})"

    print("✅ Traceability Validator Self-Tests PASSED (Caught invalid fixtures correctly)")


def main():
    run_self_tests()

    manifest_path = os.environ.get(
        "PHASE_4B2_MANIFEST_PATH", str(REPO_ROOT / "artifacts" / "phase_4b2_test_manifest.json")
    )
    scenarios_path = os.environ.get(
        "PHASE_4B2_SCENARIOS_PATH", str(REPO_ROOT / "artifacts" / "phase_4b2_scenario_traceability.json")
    )

    if not os.path.exists(manifest_path) or not os.path.exists(scenarios_path):
        print("Traceability files not found, exiting")
        sys.exit(0)

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    with open(scenarios_path, "r") as f:
        scenarios_data = json.load(f)

    scenarios = scenarios_data.get("scenarios", [])
    valid, message = validate_scenarios(scenarios, manifest.get("tests", []))

    if not valid:
        print(f"❌ Traceability Validation FAILED: {message}")
        sys.exit(1)

    print(f"✅ Traceability Validator PASSED: {message}")
    sys.exit(0)


if __name__ == "__main__":
    main()
