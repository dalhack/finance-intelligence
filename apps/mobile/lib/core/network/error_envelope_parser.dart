import '../models/app_exception.dart';

class ErrorEnvelopeParser {
  static AppException parse({
    required dynamic responseBody,
    required int? statusCode,
    required String fallbackRequestId,
  }) {
    if (responseBody is Map<String, dynamic> &&
        responseBody.containsKey('error')) {
      final errMap = responseBody['error'];
      if (errMap is Map<String, dynamic>) {
        final code = errMap['code']?.toString() ?? 'UNKNOWN_ERROR';
        final message =
            errMap['message']?.toString() ?? 'Beklenmeyen bir hata oluştu.';
        final requestId = errMap['requestId']?.toString() ?? fallbackRequestId;
        final retryable = errMap['retryable'] as bool? ?? false;
        final details = (errMap['details'] as List<dynamic>?) ?? const [];

        return _mapCodeToException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      }
    }

    // Redact HTML or unparsed 500 error body
    if (statusCode != null && statusCode >= 500) {
      return ServerException(
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Sunucuda beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.',
        requestId: fallbackRequestId,
        retryable: false,
        details: const [],
        statusCode: statusCode,
      );
    }

    if (statusCode == 401) {
      return AuthenticationException(
        code: 'UNAUTHENTICATED',
        message: 'Oturum süreniz doldu. Lütfen tekrar giriş yapın.',
        requestId: fallbackRequestId,
      );
    }

    if (statusCode == 403) {
      return AuthorizationException(
        code: 'FORBIDDEN',
        message: 'Bu işlemi gerçekleştirme yetkiniz bulunmamaktadır.',
        requestId: fallbackRequestId,
      );
    }

    if (statusCode == 404) {
      return NotFoundException(
        code: 'NOT_FOUND',
        message: 'İstenen kaynak bulunamadı.',
        requestId: fallbackRequestId,
      );
    }

    return UnknownException(
      code: 'UNEXPECTED_RESPONSE',
      message: 'Sunucudan beklenmeyen bir yanıt alındı.',
      requestId: fallbackRequestId,
      statusCode: statusCode,
    );
  }

  static AppException _mapCodeToException({
    required String code,
    required String message,
    required String requestId,
    required bool retryable,
    required List<dynamic> details,
    required int? statusCode,
  }) {
    switch (code) {
      case 'VALIDATION_ERROR':
        return ValidationException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      case 'UNAUTHENTICATED':
      case 'EXPIRED_TOKEN':
      case 'INVALID_TOKEN':
        return AuthenticationException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      case 'ATTESTATION_FAILED':
      case 'INVALID_APP_CHECK':
        return AttestationException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      case 'FORBIDDEN':
      case 'PERMISSION_DENIED':
        return AuthorizationException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      case 'NOT_FOUND':
      case 'INSTITUTION_NOT_FOUND':
      case 'PERIOD_NOT_FOUND':
      case 'EVIDENCE_NOT_FOUND':
      case 'COMPARISON_NOT_FOUND':
        return NotFoundException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      case 'RATE_LIMIT_EXCEEDED':
        return RateLimitException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: true,
          details: details,
          statusCode: statusCode,
        );
      case 'DATA_QUALITY_INVARIANT_VIOLATED':
      case 'CURRENCY_MISMATCH':
      case 'REPORTING_BASIS_MISMATCH':
      case 'UNIT_MISMATCH':
      case 'SCALE_NORMALIZATION_ERROR':
        return DataQualityException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      case 'DATASET_SCHEMA_VERSION_UNSUPPORTED':
      case 'UNSUPPORTED_JOB_STATUS':
        return UnsupportedContractException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      case 'INTERNAL_SERVER_ERROR':
      case 'COMPARISON_INTERNAL_ERROR':
      case 'EVIDENCE_INTERNAL_ERROR':
        return ServerException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
      default:
        return UnknownException(
          code: code,
          message: message,
          requestId: requestId,
          retryable: retryable,
          details: details,
          statusCode: statusCode,
        );
    }
  }
}
