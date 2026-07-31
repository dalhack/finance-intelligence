import logging
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from services.api.app.core.config import settings
from services.api.app.core.errors import BaseAPIException

logger = logging.getLogger("finance_intelligence")


async def custom_api_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    if not isinstance(exc, BaseAPIException):
        return await unhandled_exception_handler(request, exc)

    error_body: dict[str, Any] = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "requestId": request_id,
            "retryable": False,
            "details": exc.details,
        }
    }
    return JSONResponse(status_code=exc.status_code, content=error_body)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    if not isinstance(exc, RequestValidationError):
        return await unhandled_exception_handler(request, exc)

    details = [{"field": str(e.get("loc", [])), "issue": e.get("msg", "Validation error")} for e in exc.errors()]
    error_body: dict[str, Any] = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request payload failed schema validation.",
            "requestId": request_id,
            "retryable": False,
            "details": details,
        }
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_body)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled exception: {exc!s}", exc_info=settings.DEBUG)

    # Redact unexpected internal errors to prevent leaking SQL/technical stack traces
    error_body: dict[str, Any] = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred.",
            "requestId": request_id,
            "retryable": False,
            "details": [],
        }
    }
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_body)
