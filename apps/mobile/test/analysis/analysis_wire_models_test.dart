import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';

void main() {
  group('Analysis Wire Models Tests', () {
    test('AnalysisCreateRequestModel serializes prompt and idempotencyKey', () {
      const req = AnalysisCreateRequestModel(
        userQuery: 'Garanti 2025 Q4 Toplam Aktif analizi',
        idempotencyKey: 'idem-12345',
      );
      final jsonMap = req.toJson();
      assert(jsonMap['prompt'] == 'Garanti 2025 Q4 Toplam Aktif analizi');
      assert(jsonMap['idempotency_key'] == 'idem-12345');
      assert(!jsonMap.containsKey('organization_id'));
      assert(!jsonMap.containsKey('tenant_id'));
      assert(!jsonMap.containsKey('user_id'));
    });

    test('AnalysisDomainEventModel parses valid SSE event line', () {
      final event = AnalysisDomainEventModel.fromSseLine(
        type: 'analysis.completed',
        id: '15',
        data: {
          'analysis_job_id': 'job-abc-123',
          'status': 'COMPLETED',
        },
      );
      expect(event.eventType, equals('analysis.completed'));
      expect(event.sequence, equals(15));
      expect(event.analysisId, equals('job-abc-123'));
    });

    test(
        'AnalysisDomainEventModel throws FormatException for unsupported event type',
        () {
      expect(
        () => AnalysisDomainEventModel.fromSseLine(
          type: 'unsupported.random_event',
          id: '1',
          data: {},
        ),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
