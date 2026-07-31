import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/app_exception.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/data/repositories/document_repository.dart';

class MockFinanceApiClient extends FinanceIntelligenceApiClient {
  MockFinanceApiClient() : super(dio: Dio());

  int uploadCallCount = 0;
  bool isFinalized = false;

  @override
  Future<UploadSession> createUploadSession({
    required String filename,
    required int expectedSizeBytes,
  }) async {
    return UploadSession(
      uploadSessionId: 'sess-123',
      organizationId: 'org-1',
      documentId: 'doc-1',
      documentVersionId: 'ver-1',
      status: 'CREATED',
      expectedSizeBytes: expectedSizeBytes,
    );
  }

  @override
  Future<void> uploadFileStreamed({
    required String uploadSessionId,
    required File file,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    uploadCallCount++;
  }

  @override
  Future<IngestionJob> finalizeUploadSession({
    required String uploadSessionId,
  }) async {
    isFinalized = true;
    return const IngestionJob(
      jobId: 'job-123',
      organizationId: 'org-1',
      documentVersionId: 'ver-1',
      status: 'PENDING',
    );
  }
}

void main() {
  group('Streamed Upload & Finalize Rules', () {
    test('Rejects invalid file extensions before network call', () async {
      final mockApi = MockFinanceApiClient();
      final repo = RemoteDocumentRepository(apiClient: mockApi);
      final fakeFile = File('test.txt');

      expect(
        () => repo.createUploadSession(file: fakeFile),
        throwsA(isA<ValidationException>()
            .having((e) => e.code, 'code', 'INVALID_FILE_EXTENSION')),
      );
    });

    test('Prevents duplicate finalize for the same upload session', () async {
      final mockApi = MockFinanceApiClient();
      final repo = RemoteDocumentRepository(apiClient: mockApi);

      await repo.finalizeUpload(uploadSessionId: 'sess-abc');

      expect(
        () => repo.finalizeUpload(uploadSessionId: 'sess-abc'),
        throwsA(isA<ConflictException>()
            .having((e) => e.code, 'code', 'DUPLICATE_FINALIZE_PROHIBITED')),
      );
    });
  });
}
