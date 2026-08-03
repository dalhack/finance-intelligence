abstract class AppException implements Exception {
  final String code;
  final String message;
  final String requestId;
  final bool retryable;
  final List<dynamic> details;
  final int? statusCode;

  const AppException({
    required this.code,
    required this.message,
    required this.requestId,
    this.retryable = false,
    this.details = const [],
    this.statusCode,
  });

  @override
  String toString() =>
      '$runtimeType(code: $code, message: $message, requestId: $requestId, retryable: $retryable)';
}

class ValidationException extends AppException {
  const ValidationException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 422,
  });
}

class AuthenticationException extends AppException {
  const AuthenticationException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 401,
  });
}

class AttestationException extends AppException {
  const AttestationException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 401,
  });
}

class AuthorizationException extends AppException {
  const AuthorizationException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 403,
  });
}

class NotFoundException extends AppException {
  const NotFoundException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 404,
  });
}

class ConflictException extends AppException {
  const ConflictException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 409,
  });
}

class RateLimitException extends AppException {
  const RateLimitException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = true,
    super.details,
    super.statusCode = 429,
  });
}

class DataQualityException extends AppException {
  const DataQualityException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 400,
  });
}

class NetworkException extends AppException {
  const NetworkException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = true,
    super.details,
    super.statusCode,
  });
}

class TimeoutException extends AppException {
  const TimeoutException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = true,
    super.details,
    super.statusCode = 408,
  });
}

class ServerException extends AppException {
  const ServerException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 500,
  });
}

class UnsupportedContractException extends AppException {
  const UnsupportedContractException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode = 400,
  });
}

class UnknownException extends AppException {
  const UnknownException({
    required super.code,
    required super.message,
    required super.requestId,
    super.retryable = false,
    super.details,
    super.statusCode,
  });
}
