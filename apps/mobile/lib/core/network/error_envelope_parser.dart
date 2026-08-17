import '../models/app_exception.dart';

class ErrorEnvelopeParser {
  static AppException parse({
    required dynamic responseBody,
    required int? statusCode,
    required String fallbackRequestId,
  }) {
    if (responseBody is Map<String, dynamic>) {
      if (responseBody.containsKey('error')) {
        final errMap = responseBody['error'];
        if (errMap is Map<String, dynamic>) {
          final code = errMap['code']?.toString() ?? 'UNKNOWN_ERROR';
          final message =
              errMap['message']?.toString() ?? 'Beklenmeyen bir hata oluştu.';
          final requestId =
              errMap['requestId']?.toString() ?? fallbackRequestId;
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
      } else if (responseBody.containsKey('detail')) {
        final rawDetail = responseBody['detail'];
        String safeDetail = _extractSafeDetail(rawDetail);

        if (statusCode == 401) {
          return AuthenticationException(
            code: 'UNAUTHENTICATED',
            message: safeDetail.isNotEmpty
                ? safeDetail
                : 'Oturum süreniz doldu. Lütfen tekrar giriş yapın.',
            requestId: fallbackRequestId,
            statusCode: statusCode,
          );
        }
        if (statusCode == 403) {
          return AuthorizationException(
            code: 'FORBIDDEN',
            message: safeDetail.isNotEmpty
                ? safeDetail
                : 'Bu işlemi gerçekleştirme yetkiniz bulunmamaktadır.',
            requestId: fallbackRequestId,
            statusCode: statusCode,
          );
        }
        if (statusCode == 404) {
          return NotFoundException(
            code: 'NOT_FOUND',
            message: safeDetail.isNotEmpty
                ? safeDetail
                : 'İstenen kaynak bulunamadı.',
            requestId: fallbackRequestId,
            statusCode: statusCode,
          );
        }
        if (statusCode == 413) {
          return ValidationException(
            code: 'FILE_TOO_LARGE',
            message: 'Yüklenen dosya boyutu izin verilen sınırı aşıyor.',
            requestId: fallbackRequestId,
            statusCode: statusCode,
          );
        }
        if (statusCode == 415) {
          return ValidationException(
            code: 'UNSUPPORTED_FILE_TYPE',
            message:
                'Yüklenen dosya türü desteklenmiyor. Yalnızca PDF, XLSX ve CSV yüklenebilir.',
            requestId: fallbackRequestId,
            statusCode: statusCode,
          );
        }
        if (statusCode == 400 || statusCode == 422) {
          return ValidationException(
            code: statusCode == 400 ? 'BAD_REQUEST' : 'UNPROCESSABLE_ENTITY',
            message: safeDetail.isNotEmpty
                ? safeDetail
                : 'Gönderilen istek parametreleri geçersiz.',
            requestId: fallbackRequestId,
            statusCode: statusCode,
          );
        }
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

    if (statusCode == 400) {
      return ValidationException(
        code: 'BAD_REQUEST',
        message: 'İstek parametreleri veya biçimi geçersiz.',
        requestId: fallbackRequestId,
        statusCode: statusCode,
      );
    }

    if (statusCode == 401) {
      return AuthenticationException(
        code: 'UNAUTHENTICATED',
        message: 'Oturum süreniz doldu. Lütfen tekrar giriş yapın.',
        requestId: fallbackRequestId,
        statusCode: statusCode,
      );
    }

    if (statusCode == 403) {
      return AuthorizationException(
        code: 'FORBIDDEN',
        message: 'Bu işlemi gerçekleştirme yetkiniz bulunmamaktadır.',
        requestId: fallbackRequestId,
        statusCode: statusCode,
      );
    }

    if (statusCode == 404) {
      return NotFoundException(
        code: 'NOT_FOUND',
        message: 'İstenen kaynak bulunamadı.',
        requestId: fallbackRequestId,
        statusCode: statusCode,
      );
    }

    if (statusCode == 413) {
      return ValidationException(
        code: 'FILE_TOO_LARGE',
        message: 'Yüklenen dosya boyutu izin verilen sınırı aşıyor.',
        requestId: fallbackRequestId,
        statusCode: statusCode,
      );
    }

    if (statusCode == 415) {
      return ValidationException(
        code: 'UNSUPPORTED_FILE_TYPE',
        message: 'Yüklenen dosya türü desteklenmiyor.',
        requestId: fallbackRequestId,
        statusCode: statusCode,
      );
    }

    if (statusCode == 422) {
      return ValidationException(
        code: 'UNPROCESSABLE_ENTITY',
        message: 'Gönderilen istek verileri sunucu şemasıyla uyumsuz.',
        requestId: fallbackRequestId,
        statusCode: statusCode,
      );
    }

    if (statusCode == 429) {
      return RateLimitException(
        code: 'RATE_LIMIT_EXCEEDED',
        message: 'Çok fazla istek gönderildi. Lütfen bir süre bekleyin.',
        requestId: fallbackRequestId,
        retryable: true,
        statusCode: statusCode,
      );
    }

    return UnknownException(
      code: 'UNEXPECTED_RESPONSE',
      message: 'Sunucudan beklenmeyen bir yanıt alındı.',
      requestId: fallbackRequestId,
      statusCode: statusCode,
    );
  }

  static String _extractSafeDetail(dynamic rawDetail) {
    if (rawDetail is String && rawDetail.isNotEmpty) {
      final lower = rawDetail.toLowerCase();
      if (!anySecretKeyword(lower)) {
        return rawDetail;
      }
    }
    return '';
  }

  static bool anySecretKeyword(String val) {
    return val.contains('token') ||
        val.contains('secret') ||
        val.contains('traceback') ||
        val.contains('sql') ||
        val.contains('password') ||
        val.contains('authorization');
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
