import 'package:dio/dio.dart';

class SafeLoggingInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    // Redact tokens and headers
    final sanitizedHeaders = Map<String, dynamic>.from(options.headers);
    if (sanitizedHeaders.containsKey('Authorization')) {
      sanitizedHeaders['Authorization'] = '[REDACTED TOKEN]';
    }
    if (sanitizedHeaders.containsKey('X-App-Check')) {
      sanitizedHeaders['X-App-Check'] = '[REDACTED TOKEN]';
    }

    // Do not log request body or file bytes
    handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    // Do not log response body or financial values
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    // Do not log stack traces or raw response bodies
    handler.next(err);
  }
}
