#!/usr/bin/env python3
"""Finance Intelligence Tenant Context Scoping Scanner.

Scans all Python source, test, and script files in the codebase to assert
ZERO occurrences of set_config('app.current_organization_id', ..., false)
or any non-transactional is_local=false tenant context bindings.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_DIRS = ["services", "packages", "tests", "scripts"]


def scan_tenant_context_scoping() -> list[str]:
    violations = []
    for target in TARGET_DIRS:
        target_path = os.path.join(PROJECT_ROOT, target)
        if not os.path.exists(target_path):
            continue

        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, PROJECT_ROOT)

                    if (
                        rel_path.startswith("scripts/verify_tenant_context_scoping.py")
                        or "test_tenant_context_scanner.py" in rel_path
                    ):
                        continue

                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    for idx, line in enumerate(lines, start=1):
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue
                        if "set_config" in line and "app.current_organization_id" in line:
                            clean_line = line.strip().lower()
                            if "false" in clean_line:
                                violations.append(f"{rel_path}:{idx}: {line.strip()}")

    return violations


def main() -> None:
    print("=== Finance Intelligence Tenant Context Scoping Scanner ===")
    violations = scan_tenant_context_scoping()

    if violations:
        print(f"❌ SECURITY VIOLATION: Found {len(violations)} non-transactional set_config(..., false) occurrences:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("✅ Zero set_config(..., false) violations found. All tenant context calls are strictly transaction-scoped.")
    sys.exit(0)


if __name__ == "__main__":
    main()
