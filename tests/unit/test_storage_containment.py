import pytest

from services.api.app.storage.local_adapter import LocalStorageAdapter, PathTraversalException


@pytest.mark.unit
def test_storage_containment_path_traversal_rejected():
    adapter = LocalStorageAdapter()
    with pytest.raises(PathTraversalException):
        adapter._resolve_safe_path("tenant-123", "../../../etc/passwd")
