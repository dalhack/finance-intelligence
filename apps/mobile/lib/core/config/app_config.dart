class AppConfig {
  final String apiBaseUrl;
  final String environment;
  final int requestTimeoutMs;
  final bool enableDevAuth;
  final bool enableAppCheck;

  const AppConfig({
    required this.apiBaseUrl,
    required this.environment,
    this.requestTimeoutMs = 30000,
    required this.enableDevAuth,
    this.enableAppCheck = true,
  });

  static const development = AppConfig(
    apiBaseUrl: 'http://localhost:8000/api/v1',
    environment: 'development',
    requestTimeoutMs: 30000,
    enableDevAuth: true,
    enableAppCheck: false,
  );

  static const production = AppConfig(
    // TODO: switch back to https://finapi.korhanturgut.com/api/v1 once the
    // Cloud Run domain-mapping certificate is issued (rate-limited 2026-08-13).
    apiBaseUrl: 'https://finance-api-523958262212.us-central1.run.app/api/v1',
    environment: 'production',
    requestTimeoutMs: 30000,
    enableDevAuth: false,
    enableAppCheck: true,
  );

  void validateConfig() {
    if (environment == 'production') {
      if (enableDevAuth) {
        throw StateError(
          'CRITICAL SECURITY ERROR: Development authentication is strictly prohibited in production.',
        );
      }
      if (apiBaseUrl.contains('localhost') ||
          apiBaseUrl.contains('127.0.0.1')) {
        throw StateError(
          'CRITICAL SECURITY ERROR: Localhost API endpoints are prohibited in production.',
        );
      }
    }
  }
}
