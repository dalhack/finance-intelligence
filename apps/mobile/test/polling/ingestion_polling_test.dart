import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/data/repositories/ingestion_repository.dart';

class MockPollingApiClient extends FinanceIntelligenceApiClient {
  MockPollingApiClient() : super(dio: Dio());

  int fetchCount = 0;
  String currentStatus = 'PENDING';

  @override
  Future<IngestionJob> getIngestionJobStatus({required String jobId}) async {
    fetchCount++;
    if (fetchCount >= 3) {
      currentStatus = 'PROCESSED_SUCCESS';
    }
    return IngestionJob(
      jobId: jobId,
      organizationId: 'org-1',
      documentVersionId: 'ver-1',
      status: currentStatus,
    );
  }
}

void main() {
  group('Ingestion Job Polling Lifecycle', () {
    test('Polls until terminal status PROCESSED_SUCCESS and stops', () async {
      final mockApi = MockPollingApiClient();
      final repo = RemoteIngestionRepository(apiClient: mockApi);

      final stream = repo.pollIngestionJob(
        jobId: 'job-poller-1',
        initialInterval: const Duration(milliseconds: 10),
        maxInterval: const Duration(milliseconds: 50),
      );

      final results = await stream.toList();

      expect(results, isNotEmpty);
      expect(results.last.status, equals('PROCESSED_SUCCESS'));
      expect(results.last.isTerminal, isTrue);
    });

    test('Fails closed on unsupported job status', () {
      expect(
        () => IngestionJob.fromJson({
          'id': '1',
          'organization_id': '2',
          'document_version_id': '3',
          'status': 'UNKNOWN_MAGIC_STATUS'
        }),
        throwsA(isA<FormatException>().having(
            (e) => e.message, 'message', contains('UNSUPPORTED_JOB_STATUS'))),
      );
    });
  });
}
