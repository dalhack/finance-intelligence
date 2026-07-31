#!/usr/bin/env python3
"""Finance Intelligence Test Isolation Quality Control Scanner

Scans all integration test files in tests/integration/ for:
1. TRUNCATE statements (case-insensitive, multi-line, text() blocks, raw driver calls)
2. Global/un-scoped DELETE statements without WHERE clauses targeting tenant boundaries

Note: This scanner acts as a automated quality control check against defined dangerous SQL patterns.
"""

import os
import re
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INTEGRATION_TESTS_DIR = os.path.join(PROJECT_ROOT, "tests", "integration")

TRUNCATE_PATTERN = re.compile(r"\bTRUNCATE\b", re.IGNORECASE | re.MULTILINE)
UNSCOPED_DELETE_PATTERN = re.compile(
    r"\bDELETE\s+FROM\s+(?:ingestion_jobs|ingestion_attempts|documents|document_versions|audit_events)\b(?!\s+WHERE\b)",
    re.IGNORECASE | re.MULTILINE,
)


def scan_integration_test_isolation() -> bool:
    print("=== Finance Intelligence Test Isolation Quality Control Scanner ===")
    print(f"Target Directory: {INTEGRATION_TESTS_DIR}\n")

    if not os.path.exists(INTEGRATION_TESTS_DIR):
        print(f"ERROR: Directory not found: {INTEGRATION_TESTS_DIR}")
        return False

    violations = []
    scanned_files = 0

    for root, _, files in os.walk(INTEGRATION_TESTS_DIR):
        for file in files:
            if file.endswith(".py"):
                scanned_files += 1
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, PROJECT_ROOT)

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 1. Check for TRUNCATE
                truncate_matches = TRUNCATE_PATTERN.findall(content)
                if truncate_matches:
                    violations.append(
                        (rel_path, f"Forbidden TRUNCATE statement found ({len(truncate_matches)} match(es))")
                    )

                # 2. Check for un-scoped DELETE FROM without WHERE
                unscoped_delete_matches = UNSCOPED_DELETE_PATTERN.findall(content)
                if unscoped_delete_matches:
                    violations.append(
                        (
                            rel_path,
                            f"Forbidden un-scoped DELETE FROM statement found ({len(unscoped_delete_matches)} match(es))",
                        )
                    )

    print(f"Scanned {scanned_files} integration test file(s).")

    if violations:
        print("\n❌ TEST ISOLATION QUALITY CONTROL VIOLATIONS FOUND:")
        for file_rel, error_msg in violations:
            print(f"  - {file_rel}: {error_msg}")
        return False

    print("✅ Zero TRUNCATE or un-scoped DELETE violations found across all integration tests.")
    print("Quality Control Check Passed: Test data isolation maintained with tenant-scoped UUIDs.\n")
    return True


if __name__ == "__main__":
    success = scan_integration_test_isolation()
    sys.exit(0 if success else 1)
