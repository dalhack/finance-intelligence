import uuid
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ConfigDict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class ExecutionContext(BaseModel):
    authenticated_user_id: UUID
    active_organization_id: UUID
    membership_id: UUID
    roles: list[str]
    permissions: list[str]
    request_id: str
    correlation_id: str
    authentication_method: str
    environment: str

    model_config = ConfigDict(frozen=True, extra="forbid")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.execution_context = None

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response
