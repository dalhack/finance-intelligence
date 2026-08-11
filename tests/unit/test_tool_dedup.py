from app.orchestration.tool_dedup import ToolDeduplicationManager


def test_tool_arguments_checksum_determinism():
    args1 = {"a": 1, "b": [1, 2, 3], "c": {"x": "y"}}
    args2 = {"c": {"x": "y"}, "b": [1, 2, 3], "a": 1}

    checksum1 = ToolDeduplicationManager.compute_arguments_checksum(args1)
    checksum2 = ToolDeduplicationManager.compute_arguments_checksum(args2)

    assert checksum1 == checksum2
    assert len(checksum1) == 64
