from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_no_developer_absolute_paths_in_tracked_code():
    """Scanner asserting zero developer absolute paths (/Users/, .gemini/) in tracked python/dart/yaml/json files."""
    forbidden_substrings = [
        "/Users/korhanturgut",
        "antigravity-ide",
    ]

    scanned_extensions = {".py", ".dart", ".yml", ".yaml", ".json", ".sh"}
    scanned_files = [
        p
        for p in REPO_ROOT.rglob("*")
        if p.is_file()
        and p.suffix in scanned_extensions
        and ".venv" not in p.parts
        and ".git" not in p.parts
        and "build" not in p.parts
        and ".pytest_cache" not in p.parts
        and ".dart_tool" not in p.parts
        and "ephemeral" not in p.parts
        and "flutter_export_environment.sh" not in p.name
        and not p.name.startswith("pytest-unit-report")
    ]

    offending_files = []
    for file_path in scanned_files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for forbidden in forbidden_substrings:
            if forbidden in content:
                # Exclude this scanner test file itself from self-matching the literal string
                if file_path.name == "test_absolute_path_scanner.py":
                    continue
                offending_files.append((file_path.relative_to(REPO_ROOT), forbidden))

    assert not offending_files, f"CRITICAL: Found developer absolute paths in tracked files: {offending_files}"
