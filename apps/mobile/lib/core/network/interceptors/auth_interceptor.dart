import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';
import '../../security/identity_token_provider.dart';

class AuthInterceptor extends Interceptor {
  final IdentityTokenProvider identityTokenProvider;
  final Uuid _uuid = const Uuid();
  bool _isRefreshing = false;
  Future<String>? _refreshFuture;

  AuthInterceptor({required this.identityTokenProvider});

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    try {
      options.headers['X-Request-ID'] ??= _uuid.v4();
      options.headers['X-Client-Contract-Version'] = '3.0.0';

      final token = await identityTokenProvider.getIdToken();
      if (token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    } catch (e) {
      handler.reject(
        DioException(
          requestOptions: options,
          error: e,
          type: DioExceptionType.cancel,
        ),
      );
    }
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final statusCode = err.response?.statusCode;
    final isAlreadyRetried =
        err.requestOptions.extra['is_token_retried'] == true;

    if (statusCode == 401 && !isAlreadyRetried) {
      err.requestOptions.extra['is_token_retried'] = true;
      try {
        final newToken = await _getRefreshedTokenSingleFlight();
        final options = err.requestOptions;
        options.headers['Authorization'] = 'Bearer $newToken';

        final dio = Dio(); // Clean retry client instance
        final response = await dio.fetch(options);
        return handler.resolve(response);
      } catch (refreshErr) {
        return handler.next(err);
      }
    }
    return handler.next(err);
  }

  Future<String> _getRefreshedTokenSingleFlight() async {
    if (_isRefreshing && _refreshFuture != null) {
      return _refreshFuture!;
    }
    _isRefreshing = true;
    _refreshFuture = identityTokenProvider.getIdToken(forceRefresh: true);

    try {
      final token = await _refreshFuture!;
      return token;
    } finally {
      _isRefreshing = false;
      _refreshFuture = null;
    }
  }
}
