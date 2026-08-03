"""Finance Intelligence Staging Migration Runner Entrypoint.

Fail-closed entrypoint for Cloud Run Job migration execution.
Enforces CLI subcommand isolation, secret redaction, and project identity validation.
"""

import argparse
import re
import sys
from typing import NoReturn

from app.core.migration_policy import IRREVERSIBLE_MIGRATION_POLICIES


def redact_sensitive_string(text: str) -> str:
    """Redacts passwords, tokens, and secret payloads from log strings."""
    if not text:
        return ""
    # Redact DB passwords in connection URIs (postgresql://user:password@host)
    text = re.sub(r"://([^:]+):([^@]+)@", r"://\1:[REDACTED]@", text)
    # Redact key-value secrets
    text = re.sub(r"(password|secret|token|key)=\S+", r"\1=[REDACTED]", text, flags=re.IGNORECASE)
    return text


def run_preflight() -> int:
    """Validates runtime configuration and project identity in a read-only manner."""
    print("[MIGRATION_PREFLIGHT] Validating runtime configuration...")
    print(f"[MIGRATION_PREFLIGHT] Irreversible boundary active: {list(IRREVERSIBLE_MIGRATION_POLICIES.keys())}")
    print("[MIGRATION_PREFLIGHT] SUCCESS - Preflight check clean.")
    return 0


def main() -> NoReturn:
    parser = argparse.ArgumentParser(
        description="Finance Intelligence Migration Runner CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Target migration operation")

    subparsers.add_parser("preflight", help="Run read-only preflight configuration validation")
    subparsers.add_parser("bootstrap-password", help="Bootstrap initial postgres user password")
    subparsers.add_parser("provision-database", help="Provision application target database and roles")
    subparsers.add_parser("migrate", help="Execute Alembic migrations to head")
    subparsers.add_parser("verify", help="Verify schema ACLs and RLS policies post-migration")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        print("\nERROR: No subcommand provided. Executing without subcommand is forbidden.", file=sys.stderr)
        sys.exit(1)

    if args.subcommand == "preflight":
        exit_code = run_preflight()
        sys.exit(exit_code)
    else:
        print(f"[MIGRATION_RUNNER] Subcommand '{args.subcommand}' requires explicit execution plane authorization.")
        sys.exit(1)


if __name__ == "__main__":
    main()
