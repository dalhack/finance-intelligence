from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.core.errors import BaseAPIException
from services.api.app.models.document_version import DocumentVersion
from services.api.app.models.stored_object import StoredObject


class ReferenceService:
    @staticmethod
    async def create_or_acquire(
        db: AsyncSession,
        organization_id: UUID,
        sha256_hash: str,
        opaque_key: str,
        byte_size: int,
        detected_mime: str,
    ) -> tuple[StoredObject, bool]:
        # Atomic ON CONFLICT upsert restricting set_ to reference_count ONLY
        stmt = (
            insert(StoredObject)
            .values(
                id=uuid4(),
                organization_id=organization_id,
                opaque_object_key=opaque_key,
                storage_provider="local",
                storage_bucket_alias="default",
                byte_size=byte_size,
                server_computed_sha256=sha256_hash,
                detected_mime_type=detected_mime,
                integrity_status="VALIDATED",
                retention_status="ACTIVE",
                deletion_status="ACTIVE",
                reference_count=1,
            )
            .on_conflict_do_update(
                index_elements=["organization_id", "server_computed_sha256"],
                set_={"reference_count": StoredObject.reference_count + 1},
            )
        )
        await db.execute(stmt)

        # Lock and fetch canonical stored object for tenant
        res = await db.execute(
            select(StoredObject)
            .where(
                StoredObject.organization_id == organization_id,
                StoredObject.server_computed_sha256 == sha256_hash,
            )
            .with_for_update()
        )
        stored_object = res.scalar_one()

        is_deduplicated = stored_object.opaque_object_key != opaque_key
        return stored_object, is_deduplicated

    @staticmethod
    async def acquire_existing(
        db: AsyncSession,
        organization_id: UUID,
        stored_object_id: UUID,
    ) -> StoredObject:
        res = await db.execute(
            select(StoredObject)
            .where(
                StoredObject.id == stored_object_id,
                StoredObject.organization_id == organization_id,
            )
            .with_for_update()
        )
        obj = res.scalar_one_or_none()
        if not obj:
            raise BaseAPIException(status_code=404, code="STORED_OBJECT_NOT_FOUND", message="Stored object not found.")

        obj.reference_count += 1
        await db.flush()
        return obj

    @staticmethod
    async def release_reference(
        db: AsyncSession,
        organization_id: UUID,
        stored_object_id: UUID,
    ) -> int:
        res = await db.execute(
            select(StoredObject)
            .where(
                StoredObject.id == stored_object_id,
                StoredObject.organization_id == organization_id,
            )
            .with_for_update()
        )
        obj = res.scalar_one_or_none()
        if not obj:
            raise BaseAPIException(status_code=404, code="STORED_OBJECT_NOT_FOUND", message="Stored object not found.")

        if obj.reference_count <= 0:
            raise BaseAPIException(
                status_code=400,
                code="INVALID_REFERENCE_COUNT",
                message="Reference count cannot be decremented below zero.",
            )

        obj.reference_count -= 1
        await db.flush()
        return obj.reference_count

    @staticmethod
    async def reconcile(
        db: AsyncSession,
        organization_id: UUID,
        stored_object_id: UUID,
    ) -> dict:
        count_res = await db.execute(
            select(func.count(DocumentVersion.id)).where(
                DocumentVersion.stored_object_id == stored_object_id,
                DocumentVersion.organization_id == organization_id,
            )
        )
        active_count = count_res.scalar() or 0

        res = await db.execute(
            select(StoredObject)
            .where(
                StoredObject.id == stored_object_id,
                StoredObject.organization_id == organization_id,
            )
            .with_for_update()
        )
        obj = res.scalar_one_or_none()
        if not obj:
            raise BaseAPIException(status_code=404, code="STORED_OBJECT_NOT_FOUND", message="Stored object not found.")

        obj.reference_count = active_count
        await db.flush()
        return {
            "stored_object_id": stored_object_id,
            "active_versions": active_count,
            "reconciled_reference_count": active_count,
        }

    @staticmethod
    async def is_eligible_for_deletion(
        db: AsyncSession,
        organization_id: UUID,
        stored_object_id: UUID,
    ) -> bool:
        res = await db.execute(
            select(StoredObject).where(
                StoredObject.id == stored_object_id,
                StoredObject.organization_id == organization_id,
            )
        )
        obj = res.scalar_one_or_none()
        return bool(obj and obj.reference_count == 0 and obj.retention_status == "EXPIRED")
