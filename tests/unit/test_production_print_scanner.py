import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_DIRS = [PROJECT_ROOT / "services", PROJECT_ROOT / "packages"]


def find_print_calls_in_file(file_path: Path) -> list[str]:
    """Parse python file using AST and return list of print() call locations."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as err:  # noqa: BLE001
        return [f"AST parse error in {file_path}: {err}"]

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "print":
                rel_path = file_path.relative_to(PROJECT_ROOT)
                violations.append(f"{rel_path}:{node.lineno}: print() call detected")
    return violations


@pytest.mark.unit
def test_zero_production_print_statements():
    """Automated AST scanner asserting ZERO print() calls across services/ and packages/."""
    all_violations: list[str] = []
    for target_dir in TARGET_DIRS:
        if not target_dir.exists():
            continue
        for py_file in target_dir.rglob("*.py"):
            # Exclude virtual environments or cache dirs if any exist
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            violations = find_print_calls_in_file(py_file)
            all_violations.extend(violations)

    assert len(all_violations) == 0, "Production print() statements detected:\n" + "\n".join(all_violations)
