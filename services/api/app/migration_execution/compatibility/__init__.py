"""Migration Execution Compatibility Package."""

from app.migration_execution.compatibility.revision_024 import (
    COMPATIBILITY_REVISION,
    EXPECTED_REVISION_024_SHA256,
    MIGRATION_ADVISORY_LOCK_ID,
    SOURCE_REVISION,
    Migration024CompatibilityError,
    execute_compatibility_bridge,
    verify_compatibility_preconditions,
    verify_postconditions,
)

__all__ = [
    "COMPATIBILITY_REVISION",
    "EXPECTED_REVISION_024_SHA256",
    "MIGRATION_ADVISORY_LOCK_ID",
    "SOURCE_REVISION",
    "Migration024CompatibilityError",
    "execute_compatibility_bridge",
    "verify_compatibility_preconditions",
    "verify_postconditions",
]
