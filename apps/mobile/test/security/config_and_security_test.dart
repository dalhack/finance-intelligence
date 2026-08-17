import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/config/app_config.dart';
import 'package:finance_intelligence/core/models/app_exception.dart';
import 'package:finance_intelligence/core/security/dev_security_adapters.dart';
import 'package:finance_intelligence/data/api/api_client.dart';

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

  group('APP_ENV environment selection', () {
    test('resolves each known environment explicitly', () {
      expect(AppConfig.resolve(environment: 'development').environment,
          'development');
      expect(AppConfig.resolve(environment: 'staging').environment, 'staging');
      expect(AppConfig.resolve(environment: 'production').environment,
          'production');
    });

    test('unknown or empty environment fails closed', () {
      expect(() => AppConfig.resolve(environment: 'qa'), throwsStateError);
      expect(() => AppConfig.resolve(environment: ''), throwsStateError);
    });

    test('localhost is reachable only through explicit development', () {
      expect(AppConfig.resolve(environment: 'development').apiBaseUrl,
          contains('localhost'));
      for (final env in ['staging', 'production']) {
        final config = AppConfig.resolve(environment: env);
        expect(config.apiBaseUrl, AppConfig.canonicalApiBaseUrl);
        expect(config.apiBaseUrl, startsWith('https://'));
        expect(config.apiBaseUrl, isNot(contains('localhost')));
      }
    });

    test('staging uses real identity and passes validation', () {
      const staging = AppConfig.staging;
      expect(staging.enableDevAuth, isFalse);
      expect(() => staging.validateConfig(), returnsNormally);
    });

    test('remote environments reject cleartext endpoints', () {
      const cleartextStaging = AppConfig(
        apiBaseUrl: 'http://finapi.korhanturgut.com/api/v1',
        environment: 'staging',
        enableDevAuth: false,
      );
      expect(() => cleartextStaging.validateConfig(), throwsStateError);
    });
  });

  group('Transport error classification', () {
    AppException? map(DioExceptionType type, {bool hasResponse = false}) =>
        FinanceIntelligenceApiClient.mapTransportException(
            type, hasResponse, 'req-1');

    test('connection failures surface a retryable NetworkException', () {
      for (final type in [
        DioExceptionType.connectionError,
        DioExceptionType.badCertificate,
      ]) {
        final error = map(type);
        expect(error, isA<NetworkException>());
        expect(error!.code, 'NETWORK_UNAVAILABLE');
        expect(error.retryable, isTrue);
      }
    });

    test('timeouts surface a TimeoutException', () {
      for (final type in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.sendTimeout,
        DioExceptionType.receiveTimeout,
      ]) {
        final error = map(type);
        expect(error, isA<TimeoutException>());
        expect(error!.code, 'NETWORK_TIMEOUT');
      }
    });

    test('responses are left to the envelope parser', () {
      expect(map(DioExceptionType.badResponse, hasResponse: true), isNull);
      expect(map(DioExceptionType.unknown, hasResponse: true), isNull);
      expect(map(DioExceptionType.cancel), isNull);
    });

    test('unknown transport failure without response is a network error', () {
      expect(map(DioExceptionType.unknown), isA<NetworkException>());
    });

    test('messages leak no url, token, header or driver detail', () {
      for (final type in DioExceptionType.values) {
        final error = map(type);
        if (error == null) continue;
        final message = error.message.toLowerCase();
        for (final forbidden in [
          'http',
          'localhost',
          'finapi',
          'bearer',
          'token',
          'authorization',
          'dioexception',
          'socketexception',
        ]) {
          expect(message, isNot(contains(forbidden)),
              reason: '$type message must not expose "$forbidden"');
        }
      }
    });
  });
}
