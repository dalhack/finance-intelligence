import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/config/app_config.dart';
import 'package:finance_intelligence/core/security/dev_security_adapters.dart';

void main() {
  group('AppConfig & Security Validation', () {
    test('Production config rejects localhost or dev auth', () {
      const invalidLocalhostConfig = AppConfig(
        apiBaseUrl: 'http://localhost:8000/api/v1',
        environment: 'production',
        enableDevAuth: false,
      );
      expect(() => invalidLocalhostConfig.validateConfig(), throwsStateError);

      const invalidDevAuthConfig = AppConfig(
        apiBaseUrl: 'https://api.finance-intelligence.internal/v1',
        environment: 'production',
        enableDevAuth: true,
      );
      expect(() => invalidDevAuthConfig.validateConfig(), throwsStateError);

      const validProdConfig = AppConfig(
        apiBaseUrl: 'https://api.finance-intelligence.internal/v1',
        environment: 'production',
        enableDevAuth: false,
      );
      expect(() => validProdConfig.validateConfig(), returnsNormally);
    });

    test('DevelopmentSecurityAdapters fail-closed in production', () {
      const prodConfig = AppConfig(
        apiBaseUrl: 'https://api.finance-intelligence.internal/v1',
        environment: 'production',
        enableDevAuth: false,
      );

      expect(() => DevelopmentIdentityTokenProvider(config: prodConfig),
          throwsStateError);
      expect(() => DevelopmentAttestationTokenProvider(config: prodConfig),
          throwsStateError);
    });
  });
}
