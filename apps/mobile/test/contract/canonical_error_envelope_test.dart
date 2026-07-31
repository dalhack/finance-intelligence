import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/app_exception.dart';
import 'package:finance_intelligence/core/network/error_envelope_parser.dart';

void main() {
  group('Canonical ErrorEnvelope Parsing', () {
    test('Parses canonical ErrorEnvelope into typed AppException', () {
      final json = {
        'error': {
          'code': 'CURRENCY_MISMATCH',
          'message': 'Currency TRY does not match USD',
          'requestId': 'req-99182',
          'retryable': false,
          'details': [
            {'field': 'currency', 'issue': 'Mismatch'}
          ],
        }
      };

      final exc = ErrorEnvelopeParser.parse(
        responseBody: json,
        statusCode: 400,
        fallbackRequestId: 'fallback-123',
      );

      expect(exc, isA<DataQualityException>());
      expect(exc.code, equals('CURRENCY_MISMATCH'));
      expect(exc.requestId, equals('req-99182'));
      expect(exc.retryable, isFalse);
    });

    test(
        'Redacts unparsed HTML / plain-text 500 server error while preserving requestId',
        () {
      const htmlBody =
          '<html><body>500 Internal Server Error Traceback...</body></html>';

      final exc = ErrorEnvelopeParser.parse(
        responseBody: htmlBody,
        statusCode: 500,
        fallbackRequestId: 'req-500-test',
      );

      expect(exc, isA<ServerException>());
      expect(exc.code, equals('INTERNAL_SERVER_ERROR'));
      expect(
          exc.message,
          equals(
              'Sunucuda beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.'));
      expect(exc.requestId, equals('req-500-test'));
    });

    test('Parses unsupported schema version into UnsupportedContractException',
        () {
      final json = {
        'error': {
          'code': 'DATASET_SCHEMA_VERSION_UNSUPPORTED',
          'message': 'Schema version 4.0.0 is not supported',
          'requestId': 'req-ver-1',
          'retryable': false,
        }
      };

      final exc = ErrorEnvelopeParser.parse(
        responseBody: json,
        statusCode: 400,
        fallbackRequestId: 'fallback-ver',
      );

      expect(exc, isA<UnsupportedContractException>());
      expect(exc.code, equals('DATASET_SCHEMA_VERSION_UNSUPPORTED'));
    });

    test('Parses HTTP 409 Conflict RESULT_NOT_READY envelope cleanly', () {
      final json = {
        'error': {
          'code': 'RESULT_NOT_READY',
          'message':
              'Analysis result is not ready. Current job status is IN_PROGRESS.',
          'requestId': 'req-not-ready',
          'retryable': true,
        }
      };

      final exc = ErrorEnvelopeParser.parse(
        responseBody: json,
        statusCode: 409,
        fallbackRequestId: 'fallback-409',
      );

      expect(exc.code, equals('RESULT_NOT_READY'));
      expect(exc.retryable, isTrue);
    });
  });
}
