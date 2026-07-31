import glob
import json
import os

import pytest

CONTRACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "packages", "contracts")


@pytest.mark.contract
def test_all_json_schemas_valid():
    schema_files = glob.glob(os.path.join(CONTRACTS_DIR, "*.json"))
    assert len(schema_files) >= 6, f"Expected at least 6 contract schemas, found {len(schema_files)}"

    for s_path in schema_files:
        with open(s_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data.get("type") == "object"
            assert data.get("additionalProperties") is False, (
                f"Schema {os.path.basename(s_path)} missing additionalProperties: false constraint"
            )
