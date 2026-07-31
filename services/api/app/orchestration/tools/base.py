from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from services.api.app.orchestration.exceptions import ToolInputInvalidException

FORBIDDEN_MODEL_INPUT_KEYS = {
    "organization_id",
    "tenant_id",
    "user_id",
    "role",
    "permission",
}


@dataclass(frozen=True)
class ExecutionContext:
    organization_id: UUID
    user_id: UUID
    role: str
    permissions: set[str]


class BoundedTool(Protocol):
    @property
    def tool_name(self) -> str: ...

    @property
    def input_schema(self) -> dict[str, Any]: ...

    async def execute(
        self,
        context: ExecutionContext,
        arguments: dict[str, Any],
        db_session: Any,
    ) -> dict[str, Any]: ...


def validate_tool_arguments(arguments: dict[str, Any]) -> None:
    for key in arguments:
        if key.lower() in FORBIDDEN_MODEL_INPUT_KEYS:
            raise ToolInputInvalidException(
                f"Model is strictly prohibited from injecting '{key}' in tool arguments. ExecutionContext is injected server-side."
            )
