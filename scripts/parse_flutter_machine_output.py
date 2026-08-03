import json
import sys
from pathlib import Path


def parse_flutter_machine(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"CRITICAL: Machine test log {file_path} missing!", file=sys.stderr)
        sys.exit(1)

    tests_done = {}

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
                event_type = data.get("type") or data.get("event")
                if event_type == "testDone":
                    test_id = data.get("testID") or data.get("testId")
                    result = data.get("result")
                    hidden = data.get("hidden", False)
                    skipped_flag = data.get("skipped", False)

                    if not hidden and test_id is not None:
                        tests_done[test_id] = {
                            "result": result,
                            "skipped": skipped_flag,
                        }
            except Exception:
                pass

    passed = 0
    failed = 0
    skipped = 0

    for test_info in tests_done.values():
        if test_info["skipped"]:
            skipped += 1
        elif test_info["result"] == "success":
            passed += 1
        else:
            failed += 1

    total = len(tests_done)
    print(f"Flutter Machine Results: total={total}, passed={passed}, skipped={skipped}, failed={failed}")

    if total == 0:
        print("CRITICAL: Zero Flutter tests executed!", file=sys.stderr)
        sys.exit(1)
    if skipped > 0:
        print(f"CRITICAL CI FAILURE: {skipped} skipped Flutter tests detected!", file=sys.stderr)
        sys.exit(1)
    if failed > 0:
        print(f"CRITICAL CI FAILURE: {failed} failed Flutter tests detected!", file=sys.stderr)
        sys.exit(1)

    print("ALL FLUTTER MACHINE TESTS PASSED WITH ZERO SKIPS!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_flutter_machine_output.py <path_to_jsonl>", file=sys.stderr)
        sys.exit(1)
    parse_flutter_machine(sys.argv[1])
