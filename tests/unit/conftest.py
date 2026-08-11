import os
import sys
from pathlib import Path

# Ensure services/api is at position 0 in sys.path so app modules are canonically loaded
API_DIR = Path(__file__).resolve().parent.parent / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# STAGE B: Unit Dead-Port Guard
# Unconditionally pin all canonical unit database environment variables to dead-port 127.0.0.1:1
# to fail closed instantly if any un-mocked database session escapes during unit testing.

DEADPORT_SENTINEL_URL = "postgresql+asyncpg://unit_guard:unit_guard@127.0.0.1:1/unit_guard_forbidden"

DEADPORT_ENV_KEYS = [
    "TEST_API_DATABASE_URL",
    "TEST_WORKER_DATABASE_URL",
    "TEST_BOOTSTRAP_DATABASE_URL",
    "TEST_MAINTENANCE_DATABASE_URL",
    "TEST_OWNER_DATABASE_URL",
    "API_DATABASE_URL",
    "WORKER_DATABASE_URL",
    "BOOTSTRAP_DATABASE_URL",
    "MAINTENANCE_DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "DATABASE_URL",
]

for key in DEADPORT_ENV_KEYS:
    os.environ[key] = DEADPORT_SENTINEL_URL
