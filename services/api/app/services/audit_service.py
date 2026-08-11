import hashlib
from typing import Any
from uuid import UUID

from app.models.audit_event import AuditEvent
from sqlalchemy.ext.asyncio import AsyncSession

SENSITIVE_KEYS = {
    "filename",
    "display_name",
    "raw_filename",
    "raw_value",
    "content",
    "cell_value",
    "opaque_object_key",
    "temporary_object_key",
    "token",
    "secret",
    "password",
    "authorization",
    "value",
    "normalized_value",
    "result_value",
    "snapshot_value",
    "normalized_value_snapshot",
}


def sanitize_payload_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned_dict = {}
        for k, v in obj.items():
            if str(k).lower() not in SENSITIVE_KEYS:
                cleaned_dict[str(k)] = sanitize_payload_recursive(v)
        return cleaned_dict
    elif isinstance(obj, (list, set, tuple)):
        return [sanitize_payload_recursive(item) for item in obj]

    else:
        return str(obj) if isinstance(obj, UUID) else obj


class AuditService:
    @staticmethod
    async def record_event(
        db: AsyncSession,
        organization_id: UUID,
        event_type: str,
        target_type: str,
        target_id: UUID,
        actor_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        clean_payload: dict[str, Any] = {"target_type": target_type, "target_id": str(target_id)}
        if payload:
            sanitized = sanitize_payload_recursive(payload)
            if isinstance(sanitized, dict):
                clean_payload.update(sanitized)

        u_hash = hashlib.sha256(str(actor_id or "system").encode()).hexdigest()
        o_hash = hashlib.sha256(str(organization_id).encode()).hexdigest()
        curr_hash = hashlib.sha256(f"{event_type}:{u_hash}:{o_hash}".encode()).hexdigest()

        event = AuditEvent(
            organization_id=organization_id,
            user_hash=u_hash,
            org_hash=o_hash,
            event_type=event_type,
            payload_summary=clean_payload,
            previous_hash="0" * 64,
            current_hash=curr_hash,
        )
        db.add(event)
        await db.flush()
        return event
