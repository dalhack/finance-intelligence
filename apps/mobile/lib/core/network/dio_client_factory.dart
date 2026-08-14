import 'package:dio/dio.dart';
import '../config/app_config.dart';
import '../security/app_attestation_token_provider.dart';
import '../security/identity_token_provider.dart';
import 'interceptors/app_check_interceptor.dart';
import 'interceptors/auth_interceptor.dart';
import 'interceptors/logging_interceptor.dart';
import 'interceptors/organization_interceptor.dart';
import 'interceptors/retry_interceptor.dart';

class DioClientFactory {
  static Dio createDio({
    required AppConfig config,
    required IdentityTokenProvider identityTokenProvider,
    required AppAttestationTokenProvider appAttestationTokenProvider,
  }) {
    config.validateConfig();

    final dio = Dio(
      BaseOptions(
        baseUrl: config.apiBaseUrl,
        connectTimeout: const Duration(seconds: 10),
        sendTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      ),
    );

    // Deterministic Interceptor Chain
    dio.interceptors.addAll([
      AuthInterceptor(identityTokenProvider: identityTokenProvider),
      OrganizationInterceptor(),
      AppCheckInterceptor(
          appAttestationTokenProvider: appAttestationTokenProvider),
      RetryInterceptor(dio: dio),
      SafeLoggingInterceptor(),
    ]);

    return dio;
  }
}
