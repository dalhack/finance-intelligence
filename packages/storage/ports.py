from abc import ABC, abstractmethod
from typing import BinaryIO


class ObjectStoragePort(ABC):
    @abstractmethod
    async def put_object(self, tenant_id: str, object_key: str, data_stream: BinaryIO) -> str:
        """Stores a binary object under a tenant scope and returns the canonical storage key."""

    @abstractmethod
    async def get_object(self, tenant_id: str, object_key: str) -> BinaryIO:
        """Retrieves a binary object stream for a given tenant."""

    @abstractmethod
    async def delete_object(self, tenant_id: str, object_key: str) -> bool:
        """Deletes a stored object."""

    @abstractmethod
    async def object_exists(self, tenant_id: str, object_key: str) -> bool:
        """Checks if a stored object exists."""
