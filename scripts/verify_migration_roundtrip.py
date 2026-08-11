"""Verification Script for Safe Alembic Migration Round-Trip & Boundary Enforcement.

Enforces irreversible migration boundary rules from app.core.migration_policy
and executes the safe roundtrip (head 026 -> safe boundary 023 -> head 026).
"""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.core.migration_policy import (
    get_minimum_safe_downgrade_target,
    validate_downgrade_target,
)


def run_alembic(target_url: str, action: str, target: str) -> subprocess.CompletedProcess[str]:
    ini_path = REPO_ROOT / "services" / "api" / "alembic.ini"
    env = os.environ.copy()
    env["DATABASE_URL"] = target_url
    env["ALEMBIC_TARGET_URL"] = target_url

    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ini_path),
        "-x",
        f"sqlalchemy.url={target_url}",
        action,
        target,
    ]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)


def verify_roundtrip(target_url: str) -> None:
    print(f"Starting Safe Migration Roundtrip Verification on {target_url}...")

    # Step 1: Upgrade to head (026)
    print("Step 1: Upgrading to Alembic head (026)...")
    res1 = run_alembic(target_url, "upgrade", "head")
    assert res1.returncode == 0, f"Alembic upgrade head failed: {res1.stderr}"

    # Step 2: Determine safe downgrade boundary from canonical policy
    safe_target = get_minimum_safe_downgrade_target("head")
    print(f"Step 2: Canonical safe downgrade target identified: '{safe_target}'")

    # Step 3: Pre-execution boundary validation check for unsafe target (e.g. 022)
    print("Step 3: Testing pre-execution boundary rejection for unsafe target '022'...")
    try:
        validate_downgrade_target("022")
        raise AssertionError("SECURITY_FAILURE: Pre-execution boundary check failed to reject '022'!")
    except RuntimeError as exc:
        assert "MIGRATION_IRREVERSIBLE_BOUNDARY_VIOLATION" in str(exc)
        print("  ✓ Pre-execution boundary rejection verified successfully!")

    # Step 4: Validate safe downgrade target
    validate_downgrade_target(safe_target)

    # Step 5: Execute safe downgrade to boundary (023)
    print(f"Step 5: Downgrading to safe boundary '{safe_target}'...")
    res2 = run_alembic(target_url, "downgrade", safe_target)
    assert res2.returncode == 0, f"Alembic safe downgrade to {safe_target} failed: {res2.stderr}"

    # Step 6: Re-upgrade to head (026)
    print("Step 6: Re-upgrading to head (026)...")
    res3 = run_alembic(target_url, "upgrade", "head")
    assert res3.returncode == 0, f"Alembic re-upgrade to head failed: {res3.stderr}"

    print("SAFE MIGRATION ROUNDTRIP (026 -> 023 -> 026) COMPLETED SUCCESSFULLY 100%!")


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_ROUNDTRIP_DATABASE_URL")
    if not url:
        url = "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"
    verify_roundtrip(url)
