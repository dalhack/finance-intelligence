import 'package:dio/dio.dart';
import '../../security/app_attestation_token_provider.dart';

class AppCheckInterceptor extends Interceptor {
  final AppAttestationTokenProvider appAttestationTokenProvider;

  AppCheckInterceptor({required this.appAttestationTokenProvider});

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    try {
      final attestationToken =
          await appAttestationTokenProvider.getAttestationToken();
      if (attestationToken != null && attestationToken.isNotEmpty) {
        options.headers['X-App-Check'] = attestationToken;
      }
      handler.next(options);
    } catch (e) {
      handler.next(options);
    }
  }
}
