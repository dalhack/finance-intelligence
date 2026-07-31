import re
from pathlib import Path

import pytest

DATED_MODEL_ID_PATTERN = re.compile(r"claude-(?:3-5-sonnet|3-5-haiku|3-opus|3-sonnet|3-haiku)-\d{8}")


def scan_monorepo_for_hardcoded_model_ids(root_dir: Path) -> list[str]:
    """Scan monorepo source files for hardcoded provider model IDs."""
    violations = []
    target_dirs = [
        root_dir / "services",
        root_dir / "packages",
        root_dir / "apps",
        root_dir / "scripts",
    ]

    target_extensions = {".py", ".json", ".yaml", ".yml", ".toml", ".dart", ".txt", ".md", ".sh", ".dockerfile"}

    for target_dir in target_dirs:
        if not target_dir.exists():
            continue
        for file_path in target_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in target_extensions and file_path.name != "Dockerfile":
                continue

            # Allow explicit test files, mock fixtures, and documentation allowlist
            rel_str = str(file_path.relative_to(root_dir))
            if "test" in rel_str or "docs/" in rel_str or "brain/" in rel_str or "README.md" in rel_str:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            matches = DATED_MODEL_ID_PATTERN.findall(content)
            for m in matches:
                violations.append(f"{rel_str} contains hardcoded provider model ID '{m}'")

    return violations


@pytest.mark.unit
def test_model_id_hardcoding_scanner_monorepo():
    """Scanner verifying zero provider model IDs (e.g. claude-3-5-sonnet-20241022) are hardcoded across monorepo."""
    root_dir = Path(__file__).resolve().parents[2]
    violations = scan_monorepo_for_hardcoded_model_ids(root_dir)
    assert not violations, "Model ID hardcoding scanner violations found:\n" + "\n".join(violations)


# ── SCANNER SELF-TESTS (8 SCENARIOS) ──


def test_scanner_self_test_scenario_1_python_config_hardcoded_id():
    content = "provider_model_id = 'claude-3-5-sonnet-20241022'"
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is True


def test_scanner_self_test_scenario_2_toml_hardcoded_id():
    content = 'default_model = "claude-3-5-haiku-20241022"'
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is True


def test_scanner_self_test_scenario_3_yaml_default_model_id():
    content = "model: claude-3-5-sonnet-20241022"
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is True


def test_scanner_self_test_scenario_4_prompt_template_model_id():
    content = "Target Model: claude-3-5-sonnet-20241022"
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is True


def test_scanner_self_test_scenario_5_migration_model_id():
    content = "sa.Column('model_id', default='claude-3-5-sonnet-20241022')"
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is True


def test_scanner_self_test_scenario_6_placeholder_env_reference():
    content = "ANTHROPIC_BALANCED_MODEL_ID=${ANTHROPIC_BALANCED_MODEL_ID}"
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is False


def test_scanner_self_test_scenario_7_synthetic_test_model_id():
    content = 'provider_model_id = "synthetic-test-model"'
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is False


def test_scanner_self_test_scenario_8_doc_historical_example():
    content = "# Reference example: claude-3-5-sonnet-20241022 in documentation"
    assert bool(DATED_MODEL_ID_PATTERN.search(content)) is True
