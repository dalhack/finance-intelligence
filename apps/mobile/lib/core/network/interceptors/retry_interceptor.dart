import 'dart:async';
import 'dart:math';
import 'package:dio/dio.dart';

class RetryInterceptor extends Interceptor {
  final Dio dio;
  final int maxRetries;

  RetryInterceptor({
    required this.dio,
    this.maxRetries = 2,
  });

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final method = err.requestOptions.method.toUpperCase();
    final statusCode = err.response?.statusCode;
    final isRetryableMethod = method == 'GET' ||
        method == 'HEAD' ||
        err.requestOptions.headers.containsKey('X-Idempotency-Key');
    final isRetryableStatus = statusCode == 429 ||
        (statusCode != null && statusCode >= 502 && statusCode <= 504);

    final currentAttempt =
        (err.requestOptions.extra['retry_attempt'] as int? ?? 0);

    if (isRetryableMethod && isRetryableStatus && currentAttempt < maxRetries) {
      if (err.type == DioExceptionType.cancel) {
        return handler.next(err);
      }

      final nextAttempt = currentAttempt + 1;
      err.requestOptions.extra['retry_attempt'] = nextAttempt;

      final backoffMs =
          (pow(2, nextAttempt) * 200 + Random().nextInt(100)).toInt();
      await Future.delayed(Duration(milliseconds: backoffMs));

      if (err.requestOptions.cancelToken?.isCancelled == true) {
        return handler.next(err);
      }

      try {
        final response = await dio.fetch(err.requestOptions);
        return handler.resolve(response);
      } catch (retryErr) {
        if (retryErr is DioException) {
          return handler.next(retryErr);
        }
        return handler.next(err);
      }
    }

    return handler.next(err);
  }
}
