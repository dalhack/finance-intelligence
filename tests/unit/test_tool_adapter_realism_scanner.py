import inspect

from app.orchestration.tools.registry import (
    ToolRegistry,
)


def test_tool_adapters_do_not_contain_mock_or_synthetic_placeholders():
    for name in [
        "search_internal_documents",
        "query_financial_facts",
        "calculate_financial_metrics",
        "compare_institutions",
        "get_source_evidence",
        "save_analysis",
    ]:
        tool = ToolRegistry.get_tool(name)
        source_code = inspect.getsource(tool.execute)

        assert "NOT_IMPLEMENTED" not in source_code
        assert "placeholder" not in source_code.lower()
        # Verify that tools issue real SQLAlchemy or service queries
        assert "db_session" in source_code or "select" in source_code or "Service" in source_code
