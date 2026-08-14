"""Storage adapter selection. LocalStorageAdapter self-guards against
non-development environments; GCS is the staging/production backend."""

from app.core.config import settings


def get_storage_adapter():
    if settings.STORAGE_BACKEND.lower() == "gcs":
        from app.storage.gcs_adapter import GCSStorageAdapter

        return GCSStorageAdapter()
    from app.storage.local_adapter import LocalStorageAdapter

    return LocalStorageAdapter()
