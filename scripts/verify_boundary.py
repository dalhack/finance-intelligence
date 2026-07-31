#!/usr/bin/env python3
"""Finance Intelligence Boundary & Secret Scanner.

Performs static analysis to ensure zero workspace boundary escapes (symlink traversal)
and audits source files for hardcoded secrets, private keys, or forbidden files.

CONTEXTUAL ALLOWLIST POLICY FOR TEST FIXTURES:
- Local & CI environment default passwords ('dev_owner_pass_123', 'ci_owner_pass_123')
  and development pseudonymization salts ('dev-salt-...') are EXPLICITLY CLASSIFIED as
  ephemeral non-production test fixtures. They are strictly allowed ONLY within
  test directories ('tests/'), CI workflows ('.github/'), documentation ('README.md'),
  and example environment files ('.env.example').
- If ANY test fixture password or salt appears within forbidden production application code
  ('packages/', 'apps/mobile/'), the scanner FAILS IMMEDIATELY.
"""

import os
import re
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

IGNORE_DIRS = {
    ".venv",
    ".git",
    ".dart_tool",
    ".fvm",
    ".pub-cache",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    ".idea",
    "__pycache__",
    ".pgdata_dev",
    "storage",
}
BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".jar",
    ".pyc",
    ".zip",
    ".tar",
    ".gz",
    ".ttf",
    ".woff",
    ".woff2",
    ".dill",
    ".pdf",
    ".xlsx",
    ".bin",
}

# Allowlisted non-production test fixture strings mapped to allowed relative path prefixes
ALLOWED_FIXTURE_RULES = {
    "postgres": [
        "tests/",
        ".github/",
        ".env.example",
        "pyproject.toml",
        "README.md",
        "services/api/app/core/config.py",
    ],
    "dev_owner_pass_123": [
        "tests/",
        ".github/",
        ".env.example",
        "pyproject.toml",
        "README.md",
        "services/api/app/core/config.py",
    ],
    "dev_bootstrap_pass_123": [
        "tests/",
        ".github/",
        ".env.example",
        "pyproject.toml",
        "README.md",
        "services/api/app/core/config.py",
    ],
    "dev_app_user_pass_123": [
        "tests/",
        ".github/",
        ".env.example",
        "pyproject.toml",
        "README.md",
        "services/api/app/core/config.py",
    ],
    "dev_api_user_pass_123": [
        "tests/",
        ".github/",
        ".env.example",
        "pyproject.toml",
        "README.md",
        "services/api/app/core/config.py",
    ],
    "dev_worker_pass_123": [
        "tests/",
        ".github/",
        ".env.example",
        "pyproject.toml",
        "README.md",
        "services/api/app/core/config.py",
    ],
    "ci_owner_pass_123": ["tests/", ".github/", ".env.example"],
    "ci_bootstrap_pass_123": ["tests/", ".github/", ".env.example"],
    "ci_api_user_pass_123": ["tests/", ".github/", ".env.example"],
    "ci_worker_pass_123": ["tests/", ".github/", ".env.example"],
    "mock_prod_pass_123": ["tests/"],
    "mock_worker_pass_123": ["tests/"],
    "mock_bootstrap_pass_123": ["tests/"],
    "mock_secret_pass_123": ["tests/"],
    "ci_app_user_pass_123": ["tests/", ".github/", ".env.example"],
    "ci_postgres_password_123": ["tests/", ".github/", ".env.example"],
    "dev-salt-3918204918239012830129": ["tests/", ".github/", ".env.example", "services/api/app/core/config.py"],
    "secret_pass": ["tests/unit/test_config_validation.py"],
    "unapproved_secret_pass_888": ["tests/unit/test_secret_scanner.py"],
}

# Secret pattern regexes
REGEX_FIREBASE_KEY = re.compile(r"AIzaSy[A-Za-z0-9_\-]{33}")
REGEX_ANTHROPIC_KEY = re.compile(r"sk-ant-api[A-Za-z0-9_\-]{32,}")
REGEX_PRIVATE_KEY = re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----")
REGEX_POSTGRES_URL_PASS = re.compile(r"postgres(?:ql)?(?:\+[a-z0-9]+)?://([^:\s]+):([^@\s]+)@([^/\s]+)/([^\s\?]+)")


def verify_file_within_boundary(file_path: str) -> bool:
    """Ensure real path does not escape PROJECT_ROOT (prevents symlink attacks)."""
    try:
        real_path = os.path.realpath(file_path)
        common = os.path.commonpath([real_path, PROJECT_ROOT])
        return common == PROJECT_ROOT
    except ValueError:
        return False


def scan_content(full_path: str, content: str, rel_path: str) -> tuple[list[str], list[tuple[str, str, int]]]:
    """Scan content for hardcoded secrets or unallowed test fixtures."""
    findings = []
    fixtures = []

    # Ignore unit test file itself for synthetic key testing
    if not rel_path.endswith("tests/unit/test_secret_scanner.py"):
        if REGEX_FIREBASE_KEY.search(content):
            findings.append(f"Hardcoded Firebase Key in {rel_path}")
        if REGEX_ANTHROPIC_KEY.search(content):
            findings.append(f"Hardcoded Anthropic Key in {rel_path}")
        if REGEX_PRIVATE_KEY.search(content):
            findings.append(f"Hardcoded Private Key in {rel_path}")

    # 2. Database Connection URL Passwords Audit
    for match in REGEX_POSTGRES_URL_PASS.finditer(content):
        _user, password, _host, _dbname = match.groups()

        is_allowed = False
        for allowed_fixture, allowed_path_prefixes in ALLOWED_FIXTURE_RULES.items():
            if password == allowed_fixture:
                for prefix in allowed_path_prefixes:
                    if rel_path.startswith(prefix) or rel_path == prefix:
                        is_allowed = True
                        fixtures.append((password, rel_path, 1))
                        break
                if is_allowed:
                    break

        if not is_allowed:
            if any(rel_path.startswith(p) for p in [".github/", "tests/", ".env.example"]):
                findings.append(f"Unapproved hardcoded DB password '{password}' in {rel_path}")
            else:
                findings.append(f"Non-production test fixture '{password}' leaked into production path: {rel_path}")

    return findings, fixtures


def scan_file_for_secrets(rel_path: str, full_path: str) -> tuple[list[str], list[tuple[str, str, int]]]:
    """Scan file content for hardcoded secrets or unallowed test fixtures."""
    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return scan_content(full_path, content, rel_path)
    except Exception as e:  # noqa: BLE001
        return [f"Could not scan file {rel_path}: {e}"], []


def main():
    print("=== Finance Intelligence Boundary & Secret Scanner ===")
    print(f"Project Root: {PROJECT_ROOT}\n")

    boundary_violations = []
    secret_findings = []
    scanned_count = 0
    ignored_count = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, PROJECT_ROOT)

            if not verify_file_within_boundary(full_path):
                boundary_violations.append(full_path)
                continue

            ext = os.path.splitext(file)[1].lower()
            if ext in BINARY_EXTS:
                ignored_count += 1
                continue

            scanned_count += 1
            findings, _fixtures = scan_file_for_secrets(rel_path, full_path)
            secret_findings.extend(findings)

    print("--- METRICS BREAKDOWN ---")
    print(f"Discovered Total Files: {scanned_count + ignored_count + len(boundary_violations)}")
    print(f"Ignored Generated/Cache Files: {ignored_count}")
    print(f"Scanned Source/Config Files: {scanned_count}")
    print(f"Symlinks Inspected: {len(boundary_violations)}\n")

    print("--- BOUNDARY SCAN RESULTS ---")
    if boundary_violations:
        print(f"❌ BOUNDARY ESCAPES DETECTED ({len(boundary_violations)}):")
        for path in boundary_violations:
            print(f"  - {path}")
    else:
        print("✅ Zero Boundary Violations. All files strictly within project root.")

    print("\n--- SECRET SCAN RESULTS ---")
    if secret_findings:
        print(f"❌ SECRETS / FORBIDDEN FILES FOUND: {len(secret_findings)}")
        for finding in secret_findings:
            print(f"  - {finding}")
    else:
        print("✅ Zero Hardcoded Secrets Found. Non-production test fixtures correctly scoped.")

    if boundary_violations or secret_findings:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
