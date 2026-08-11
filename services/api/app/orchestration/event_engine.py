import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.models.orchestration import AnalysisEvent
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


class CrossTenantEventAccessException(Exception):
    """Exception raised when an event replay is attempted across tenant boundaries."""


class EventSequenceGapException(Exception):
    """Exception raised when an invalid or non-sequential event sequence is detected."""


class EventPayloadTooLargeException(Exception):
    """Exception raised when an event payload exceeds the 32KB safety limit."""


class AnalysisEventEngine:
    MAX_PAYLOAD_BYTES = 32768  # 32 KB

    def __init__(self, db: AsyncSession, organization_id: UUID):
        self.db = db
        self.organization_id = organization_id

    async def emit_event(
        self,
        analysis_job_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        analysis_attempt_id: UUID | None = None,
        schema_version: str = "1.0.0",
    ) -> AnalysisEvent:
        # Enforce RLS context
        await self.db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(self.organization_id)},
        )

        # Validate payload size
        payload_bytes = len(json.dumps(payload).encode("utf-8"))
        if payload_bytes > self.MAX_PAYLOAD_BYTES:
            raise EventPayloadTooLargeException(
                f"Event payload size {payload_bytes} bytes exceeds maximum limit {self.MAX_PAYLOAD_BYTES} bytes."
            )

        # Compute next monotonic sequence number for job
        seq_stmt = (
            select(AnalysisEvent.sequence)
            .where(
                AnalysisEvent.organization_id == self.organization_id,
                AnalysisEvent.analysis_job_id == analysis_job_id,
            )
            .order_by(AnalysisEvent.sequence.desc())
            .limit(1)
        )

        last_seq = (await self.db.execute(seq_stmt)).scalar_one_or_none() or 0
        next_seq = last_seq + 1

        now = datetime.now(UTC)
        event = AnalysisEvent(
            id=uuid4(),
            organization_id=self.organization_id,
            analysis_job_id=analysis_job_id,
            analysis_attempt_id=analysis_attempt_id,
            sequence=next_seq,
            event_type=event_type,
            schema_version=schema_version,
            payload_json=payload,
            created_at=now,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def replay_events(
        self,
        analysis_job_id: UUID,
        last_event_id: str | None = None,
        last_sequence: int = 0,
    ) -> list[AnalysisEvent]:
        """Replay stored events for an analysis job starting after last_sequence."""
        await self.db.execute(
            text("SELECT set_config('app.current_organization_id', :org_id, true);"),
            {"org_id": str(self.organization_id)},
        )

        stmt = (
            select(AnalysisEvent)
            .where(
                AnalysisEvent.organization_id == self.organization_id,
                AnalysisEvent.analysis_job_id == analysis_job_id,
                AnalysisEvent.sequence > last_sequence,
            )
            .order_by(AnalysisEvent.sequence.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
