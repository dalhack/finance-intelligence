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

  static const canonicalApiBaseUrl = 'https://finapi.korhanturgut.com/api/v1';

  /// Build-time environment selector. Supplied with
  /// `--dart-define=APP_ENV=development|staging|production`.
  /// Defaults to production so that a build without an explicit define can
  /// never silently fall back to a local, unauthenticated environment.
  static const appEnv =
      String.fromEnvironment('APP_ENV', defaultValue: 'production');

  static const development = AppConfig(
    apiBaseUrl: 'http://localhost:8000/api/v1',
    environment: 'development',
    requestTimeoutMs: 30000,
    enableDevAuth: true,
    enableAppCheck: false,
  );

  /// Physical-device and staging builds: canonical HTTPS API, real Firebase
  /// identity, App Check in audit mode (server ENFORCE_APP_CHECK=false).
  static const staging = AppConfig(
    apiBaseUrl: canonicalApiBaseUrl,
    environment: 'staging',
    requestTimeoutMs: 30000,
    enableDevAuth: false,
    enableAppCheck: false,
  );

  static const production = AppConfig(
    apiBaseUrl: canonicalApiBaseUrl,
    environment: 'production',
    requestTimeoutMs: 30000,
    enableDevAuth: false,
    enableAppCheck: true,
  );

  /// Resolves the active configuration from [appEnv]. Unknown values fail
  /// closed instead of degrading to a permissive environment.
  static AppConfig resolve({String environment = appEnv}) {
    switch (environment) {
      case 'development':
        return development;
      case 'staging':
        return staging;
      case 'production':
        return production;
      default:
        throw StateError(
          'CRITICAL CONFIG ERROR: Unknown APP_ENV. '
          'Expected development, staging or production.',
        );
    }
  }

  bool get isRemoteEnvironment =>
      environment == 'production' || environment == 'staging';

  void validateConfig() {
    if (isRemoteEnvironment) {
      if (enableDevAuth) {
        throw StateError(
          'CRITICAL SECURITY ERROR: Development authentication is strictly prohibited outside development.',
        );
      }
      if (apiBaseUrl.contains('localhost') ||
          apiBaseUrl.contains('127.0.0.1')) {
        throw StateError(
          'CRITICAL SECURITY ERROR: Localhost API endpoints are prohibited outside development.',
        );
      }
      if (!apiBaseUrl.startsWith('https://')) {
        throw StateError(
          'CRITICAL SECURITY ERROR: Cleartext API endpoints are prohibited outside development.',
        );
      }
    }
  }
}
