import enum
from typing import Any, Protocol


class JobLifecycleState(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_REVIEW = "awaiting_review"


class IdempotencyStore(Protocol):
    async def is_processed(self, idempotency_key: str) -> bool: ...
    async def mark_processed(self, idempotency_key: str) -> None: ...


class JobHandler(Protocol):
    async def handle_task(self, task_payload: dict[str, Any], idempotency_key: str) -> JobLifecycleState: ...


class SampleUnimplementedWorkerHandler:
    async def handle_task(self, task_payload: dict[str, Any], idempotency_key: str) -> JobLifecycleState:
        """
        Sample Unimplemented Task Handler.
        Does NOT produce fake completed job results or execute PDF/OCR/LLM processing.
        """
        raise NotImplementedError("Worker job handlers are scheduled for future release phases.")
