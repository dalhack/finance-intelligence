"""Google Cloud Storage adapter implementing ObjectStoragePort plus the
temporary-write surface used by the upload streaming endpoints.

Upload sessions stream chunks to a local temporary file (Cloud Run's /tmp);
finalize_temporary_write pushes the completed file to the bucket under
`{tenant_id}/{object_key}`. Read paths stream from GCS."""

import asyncio
import io
import os
import tempfile
from typing import BinaryIO

from app.core.config import settings
from app.storage.local_adapter import PathTraversalException

from packages.storage.ports import ObjectStoragePort


class GCSStorageAdapter(ObjectStoragePort):
    def __init__(self, bucket_name: str | None = None):
        from google.cloud import storage  # type: ignore[attr-defined]

        name = bucket_name or settings.STORAGE_BUCKET
        if not name:
            raise ValueError("STORAGE_BUCKET must be configured when STORAGE_BACKEND=gcs.")
        self._client = storage.Client()
        self._bucket = self._client.bucket(name)

    @staticmethod
    def _safe_blob_name(tenant_id: str, object_key: str) -> str:
        if ".." in tenant_id or ".." in object_key or tenant_id.startswith("/"):
            raise PathTraversalException(
                f"Path traversal sequence rejected: tenant_id='{tenant_id}', key='{object_key}'"
            )
        safe_tenant = os.path.basename(tenant_id)
        safe_key = os.path.basename(object_key)
        return f"{safe_tenant}/{safe_key}"

    # --- Temporary write surface (mirrors LocalStorageAdapter) ---

    def begin_temporary_write(self, tenant_id: str, object_key: str) -> str:
        self._safe_blob_name(tenant_id, object_key)  # validate early
        fd, temp_path = tempfile.mkstemp(prefix="fi-upload-", suffix=".part")
        os.close(fd)
        return temp_path

    def write_chunk(self, temp_path: str, chunk: bytes) -> None:
        with open(temp_path, "ab") as f:
            f.write(chunk)

    def finalize_temporary_write(self, temp_path: str, tenant_id: str, object_key: str) -> str:
        blob_name = self._safe_blob_name(tenant_id, object_key)
        blob = self._bucket.blob(blob_name)
        blob.upload_from_filename(temp_path)
        os.remove(temp_path)
        return blob_name

    def abort_temporary_write(self, temp_path: str) -> None:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass

    # --- Read/verify surface ---

    async def compute_hash_and_size(self, tenant_id: str, object_key: str) -> tuple[str, int]:
        import hashlib

        blob_name = self._safe_blob_name(tenant_id, object_key)

        def _run() -> tuple[str, int]:
            sha256 = hashlib.sha256()
            size = 0
            blob = self._bucket.blob(blob_name)
            with blob.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    sha256.update(chunk)
                    size += len(chunk)
            return sha256.hexdigest(), size

        return await asyncio.to_thread(_run)

    async def read_sample_bytes(self, tenant_id: str, object_key: str, max_bytes: int = 65536) -> bytes:
        blob_name = self._safe_blob_name(tenant_id, object_key)

        def _run() -> bytes:
            blob = self._bucket.blob(blob_name)
            return blob.download_as_bytes(start=0, end=max_bytes - 1)

        return await asyncio.to_thread(_run)

    # --- ObjectStoragePort ---

    async def put_object(self, tenant_id: str, object_key: str, data_stream: BinaryIO) -> str:
        blob_name = self._safe_blob_name(tenant_id, object_key)

        def _run() -> str:
            blob = self._bucket.blob(blob_name)
            blob.upload_from_file(data_stream)
            return blob_name

        return await asyncio.to_thread(_run)

    async def get_object(self, tenant_id: str, object_key: str) -> BinaryIO:
        blob_name = self._safe_blob_name(tenant_id, object_key)

        def _run() -> BinaryIO:
            blob = self._bucket.blob(blob_name)
            return io.BytesIO(blob.download_as_bytes())

        return await asyncio.to_thread(_run)

    async def delete_object(self, tenant_id: str, object_key: str) -> bool:
        blob_name = self._safe_blob_name(tenant_id, object_key)

        def _run() -> bool:
            blob = self._bucket.blob(blob_name)
            try:
                blob.delete()
                return True
            except Exception:  # noqa: BLE001
                return False

        return await asyncio.to_thread(_run)

    async def object_exists(self, tenant_id: str, object_key: str) -> bool:
        blob_name = self._safe_blob_name(tenant_id, object_key)

        def _run() -> bool:
            return self._bucket.blob(blob_name).exists()

        return await asyncio.to_thread(_run)
