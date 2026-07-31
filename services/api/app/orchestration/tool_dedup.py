import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.orchestration import ToolInvocation


class ToolArgumentChecksumMismatchException(Exception):
    """Fail-closed exception raised when duplicate tool invocation has mismatched arguments."""


class ToolDeduplicationManager:
    @staticmethod
    def compute_arguments_checksum(arguments: dict[str, Any]) -> str:
        canonical_json = json.dumps(arguments, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    async def check_existing_invocation(
        cls,
        db_session: AsyncSession,
        organization_id: UUID,
        analysis_job_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check if an identical tool invocation was already executed for this analysis job.

        Returns saved result_json if found, or None if new invocation.
        """
        stmt = (
            select(ToolInvocation)
            .where(
                ToolInvocation.organization_id == organization_id,
                ToolInvocation.analysis_job_id == analysis_job_id,
                ToolInvocation.tool_name == tool_name,
            )
            .order_by(ToolInvocation.created_at.desc())
        )
        res = await db_session.execute(stmt)
        invocations = res.scalars().all()

        current_checksum = cls.compute_arguments_checksum(arguments)

        for inv in invocations:
            existing_checksum = cls.compute_arguments_checksum(inv.arguments_json)
            if existing_checksum == current_checksum:
                return inv.result_json

        return None
