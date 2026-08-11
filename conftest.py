import sys
from pathlib import Path

# Ensure repo root and services/api are in sys.path for canonical module resolution across all test suites
REPO_ROOT = Path(__file__).resolve().parent
API_DIR = REPO_ROOT / "services" / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(1, str(REPO_ROOT))
