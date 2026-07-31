import hashlib
import json
import os

import pytest

GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden"))


@pytest.mark.unit
def test_golden_fixtures_manifest_integrity():
    manifest_path = os.path.join(GOLDEN_DIR, "manifest.json")
    assert os.path.exists(manifest_path), "Golden fixtures manifest.json does not exist."

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("dataset") == "SYNTHETIC_TEST_DATA"
    fixtures = manifest.get("fixtures", {})
    assert len(fixtures) > 0, "Manifest contains zero fixture entries."

    dir_files = set(os.listdir(GOLDEN_DIR)) - {"manifest.json", ".DS_Store"}

    for fname, meta in fixtures.items():
        assert fname in dir_files, f"Golden fixture {fname} in manifest is missing from directory."
        fpath = os.path.join(GOLDEN_DIR, fname)
        assert meta.get("classification") == "SYNTHETIC_TEST_DATA"

        with open(fpath, "rb") as f:
            content = f.read()
            h = hashlib.sha256(content).hexdigest()

        assert h == meta.get("sha256"), f"SHA-256 mismatch for golden fixture {fname}."
        expected_size = meta.get("size_bytes") or meta.get("file_size_bytes")
        assert len(content) == expected_size, f"File size mismatch for golden fixture {fname}."

    manifest_files = set(fixtures.keys())
    unexpected = dir_files - manifest_files
    assert not unexpected, f"Unexpected unlisted files found in golden directory: {unexpected}"
