import ast
from pathlib import Path

INTEGRATION_TESTS_DIR = Path(__file__).resolve().parent.parent / "integration"


class SkipCallVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.violations: list[str] = []

    def visit_Attribute(self, node: ast.Attribute):
        # Match pytest.skip, pytest.mark.skip, pytest.mark.skipif, unittest.skip
        attr_name = node.attr
        if attr_name in ("skip", "skipif"):
            # Check if value is pytest or pytest.mark or unittest
            self.violations.append(f"{self.filename}:{node.lineno}: AST violation found '{attr_name}' attribute call.")
        self.generic_visit(node)


def test_zero_skip_in_integration_tests():
    """Automated AST scanner asserting zero pytest.skip / pytest.mark.skipif / skip calls across all integration test files."""
    test_files = list(INTEGRATION_TESTS_DIR.glob("*.py"))
    assert len(test_files) > 0, "No integration test files found to scan!"

    all_violations: list[str] = []
    for test_file in test_files:
        if test_file.name == "conftest.py":
            continue
        content = test_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(test_file))
        visitor = SkipCallVisitor(test_file.name)
        visitor.visit(tree)
        all_violations.extend(visitor.violations)

    assert len(all_violations) == 0, (
        f"ZERO-SKIP GATE VIOLATION: Found skip calls in integration tests: {all_violations}"
    )
