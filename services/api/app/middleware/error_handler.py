import logging
from typing import Any

from app.core.config import settings
from app.core.errors import BaseAPIException
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("finance_intelligence")

HTTP_STATUS_CODE_MAP = {
    400: ("BAD_REQUEST", "İstek parametreleri veya biçimi geçersiz.", False),
    401: ("UNAUTHENTICATED", "Geçerli kimlik doğrulaması gerekli.", False),
    403: ("FORBIDDEN", "Bu kaynağa erişim yetkiniz bulunmamaktadır.", False),
    404: ("NOT_FOUND", "İstenen kaynak bulunamadı.", False),
    405: ("METHOD_NOT_ALLOWED", "İstenen HTTP yöntemi bu uç nokta için desteklenmiyor.", False),
    409: ("CONFLICT", "İstek mevcut kaynak durumuyla çakışıyor.", False),
    413: ("FILE_TOO_LARGE", "Yüklenen dosya boyutu izin verilen sınırı aşıyor.", False),
    415: ("UNSUPPORTED_FILE_TYPE", "Yüklenen dosya türü desteklenmiyor.", False),
    422: ("UNPROCESSABLE_ENTITY", "İstek verileri işlenemedi.", False),
    429: ("RATE_LIMIT_EXCEEDED", "İstek sınırı aşıldı. Lütfen daha sonra tekrar deneyin.", True),
}


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)

    default_code, default_msg, retryable = HTTP_STATUS_CODE_MAP.get(
        status_code,
        ("HTTP_ERROR", "İstek işlenirken bir HTTP hatası oluştu.", False),
    )

    detail = getattr(exc, "detail", None)
    safe_message = default_msg
    if isinstance(detail, str) and detail:
        lower_detail = detail.lower()
        if not any(kw in lower_detail for kw in ["token", "secret", "traceback", "sql", "password", "authorization"]):
            safe_message = detail

    error_body: dict[str, Any] = {
        "error": {
            "code": default_code,
            "message": safe_message,
            "requestId": request_id,
            "retryable": retryable,
            "details": [],
        }
    }

    headers = getattr(exc, "headers", None)
    return JSONResponse(status_code=status_code, content=error_body, headers=headers)


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
