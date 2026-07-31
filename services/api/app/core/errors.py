from typing import Any

from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: list[dict[str, Any]] | None = None,
    ):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or []


class InvalidCredentialsException(BaseAPIException):
    def __init__(self, message: str = "Invalid or expired authentication credentials."):
        super().__init__(code="INVALID_CREDENTIALS", message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class DevelopmentAuthDisabledException(BaseAPIException):
    def __init__(self):
        super().__init__(
            code="DEVELOPMENT_AUTH_DISABLED",
            message="Development authentication is strictly disabled in production mode.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class MembershipRequiredException(BaseAPIException):
    def __init__(self, message: str = "Active organization membership is required to access target resource."):
        super().__init__(code="MEMBERSHIP_REQUIRED", message=message, status_code=status.HTTP_403_FORBIDDEN)


class NotImplementedEndpointException(BaseAPIException):
    def __init__(self, feature: str = "Feature"):
        super().__init__(
            code="NOT_IMPLEMENTED",
            message=f"{feature} is scheduled for a future release phase and is not currently active.",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )
