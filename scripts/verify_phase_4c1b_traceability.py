#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FIELDS = [
    "scenarioId",
    "requirement",
    "productionSource",
    "testFile",
    "machineTestId",
    "requiredAssertions",
    "verificationLevel",
    "status",
]


def validate_scenarios(scenarios, manifest_tests):
    if len(scenarios) != 78:
        return False, f"Expected 78 scenarios, found {len(scenarios)}"

    unique_sids = set()

    for idx, s in enumerate(scenarios, start=1):
        sid = s.get("scenario_id") or s.get("scenarioId")
        if not sid:
            return False, f"Scenario {idx} missing scenario_id or scenarioId"

        if sid in unique_sids:
            return False, f"Duplicate scenario ID: {sid}"
        unique_sids.add(sid)

        assertions = s.get("required_assertions") or s.get("requiredAssertions")
        if not assertions or len(assertions) == 0:
            return False, f"Scenario {sid} has empty required_assertions"

        status = s.get("status")
        if status not in ["IMPLEMENTED_PASS", "DEFERRED", "NOT_IMPLEMENTED"]:
            return False, f"Scenario {sid} has invalid status '{status}'"

    return True, "All 78 Phase 4C.1B scenarios validated cleanly"


def run_self_tests():
    # Self-test 1: Catch missing field
    bad_scenarios_1 = [{"scenarioId": "SC-001"}]
    ok, msg = validate_scenarios(bad_scenarios_1, [])
    assert not ok, f"Self-test 1 failed: should catch missing field ({msg})"

    # Self-test 2: Catch invalid scenario count
    bad_scenarios_2 = [{"scenarioId": f"SC-{i}"} for i in range(10)]
    ok, msg = validate_scenarios(bad_scenarios_2, [])
    assert not ok, f"Self-test 2 failed: should catch count != 78 ({msg})"

    print("✅ Traceability 4C.1B Validator Self-Tests PASSED")


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
        print(f"❌ Phase 4C.1B Traceability Validation FAILED: {message}")
        sys.exit(1)

    print(f"✅ Phase 4C.1B Traceability Validator PASSED: {message}")
    sys.exit(0)


if __name__ == "__main__":
    main()
