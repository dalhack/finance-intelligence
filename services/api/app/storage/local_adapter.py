import hashlib
import os
from io import BytesIO
from typing import BinaryIO

from packages.storage.ports import ObjectStoragePort
from services.api.app.core.config import settings
from services.api.app.core.errors import BaseAPIException


class PathTraversalException(BaseAPIException):
    def __init__(self, details: str = "Invalid file path detected."):
        super().__init__(
            status_code=400,
            code="PATH_TRAVERSAL_DETECTED",
            message="Security violation: Path traversal or symlink escape detected.",
            details=[{"detail": details}],
        )


class ProductionStorageDisabledException(BaseAPIException):
    def __init__(self):
        super().__init__(
            status_code=500,
            code="LOCAL_STORAGE_DISABLED_IN_PRODUCTION",
            message="LocalStorageAdapter is strictly disabled in production environments.",
        )


class LocalStorageAdapter(ObjectStoragePort):
    def __init__(self, base_dir: str | None = None):
        if not settings.is_development:
            raise ProductionStorageDisabledException()

        root = base_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "storage", "local_buckets")
        )
        self.storage_root = os.path.realpath(os.path.abspath(root))
        os.makedirs(self.storage_root, exist_ok=True)

    def _resolve_safe_path(self, tenant_id: str, object_key: str) -> str:
        # Reject explicit path traversal sequences
        if ".." in tenant_id or ".." in object_key or tenant_id.startswith("/") or object_key.startswith("/"):
            raise PathTraversalException(
                f"Path traversal sequence rejected: tenant_id='{tenant_id}', key='{object_key}'"
            )

        safe_tenant = os.path.basename(tenant_id)
        safe_key = os.path.basename(object_key)

        tenant_dir = os.path.realpath(os.path.abspath(os.path.join(self.storage_root, safe_tenant)))
        full_path = os.path.realpath(os.path.abspath(os.path.join(tenant_dir, safe_key)))

        try:
            common = os.path.commonpath([full_path, self.storage_root])
            if common != self.storage_root:
                raise PathTraversalException(f"Path escape attempt rejected: {full_path}")
        except ValueError:
            raise PathTraversalException(f"Path containment check failed for: {full_path}")

        if os.path.islink(full_path) or os.path.islink(tenant_dir):
            raise PathTraversalException(f"Symlink target rejected: {full_path}")

        return full_path

    def begin_temporary_write(self, tenant_id: str, object_key: str) -> str:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        tmp_path = target_path + ".tmp"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return tmp_path

    def write_chunk(self, temp_path: str, chunk: bytes) -> None:
        with open(temp_path, "ab") as f:
            f.write(chunk)

    def finalize_temporary_write(self, temp_path: str, tenant_id: str, object_key: str) -> str:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        if not os.path.exists(temp_path):
            raise FileNotFoundError(f"Temporary upload file {temp_path} does not exist.")
        os.replace(temp_path, target_path)
        return target_path

    def abort_temporary_write(self, temp_path: str) -> None:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    async def compute_hash_and_size(self, tenant_id: str, object_key: str) -> tuple[str, int]:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Stored object {object_key} not found for tenant {tenant_id}")

        sha256 = hashlib.sha256()
        total_size = 0
        with open(target_path, "rb") as f:  # noqa: ASYNC230
            while chunk := f.read(65536):
                total_size += len(chunk)
                sha256.update(chunk)
        return sha256.hexdigest(), total_size

    async def read_sample_bytes(self, tenant_id: str, object_key: str, max_bytes: int = 65536) -> bytes:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Stored object {object_key} not found for tenant {tenant_id}")

        with open(target_path, "rb") as f:  # noqa: ASYNC230
            return f.read(max_bytes)

    async def put_object(self, tenant_id: str, object_key: str, data_stream: BinaryIO) -> str:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        tmp_path = target_path + ".tmp"
        data_stream.seek(0)
        with open(tmp_path, "wb") as f:  # noqa: ASYNC230
            while chunk := data_stream.read(65536):
                f.write(chunk)

        os.replace(tmp_path, target_path)
        return object_key

    async def get_object(self, tenant_id: str, object_key: str) -> BinaryIO:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Stored object {object_key} not found for tenant {tenant_id}")

        with open(target_path, "rb") as f:  # noqa: ASYNC230
            content = f.read()
        return BytesIO(content)

    async def delete_object(self, tenant_id: str, object_key: str) -> bool:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        if os.path.exists(target_path):
            os.remove(target_path)
            return True
        return False

    async def object_exists(self, tenant_id: str, object_key: str) -> bool:
        target_path = self._resolve_safe_path(tenant_id, object_key)
        return os.path.exists(target_path) and not os.path.islink(target_path)
