import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/app_exception.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/data/repositories/document_repository.dart';
import 'package:finance_intelligence/presentation/state/upload_controller.dart';

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

/// Repository double that records whether the upload lifecycle reached the
/// finalize step — the step that actually creates the document row.
class RecordingDocumentRepository implements DocumentRepository {
  final String sessionId;
  String? finalizedSessionId;

  RecordingDocumentRepository({this.sessionId = 'sess-123'});

  @override
  Future<UploadSession> uploadSingleMultipart({
    required File file,
    void Function(int sentBytes, int totalBytes)? onProgress,
    CancelToken? cancelToken,
  }) async {
    onProgress?.call(10, 10);
    return UploadSession(
      uploadSessionId: sessionId,
      organizationId: 'org-1',
      documentId: '',
      documentVersionId: '',
      status: 'UPLOADED',
      expectedSizeBytes: 10,
    );
  }

  @override
  Future<List<DocumentItem>> getDocuments() async => throw UnimplementedError();

  @override
  Future<UploadSession> createUploadSession({required File file}) async =>
      throw UnimplementedError();

  @override
  Future<void> uploadFileStreamed({
    required String uploadSessionId,
    required File file,
    void Function(int sentBytes, int totalBytes)? onProgress,
    CancelToken? cancelToken,
  }) async =>
      throw UnimplementedError();

  @override
  Future<IngestionJob> finalizeUpload({required String uploadSessionId}) async {
    finalizedSessionId = uploadSessionId;
    return const IngestionJob(
      jobId: 'job-123',
      documentId: 'doc-1',
      organizationId: 'org-1',
      documentVersionId: 'ver-1',
      status: 'QUEUED',
    );
  }
}

void main() {
  group('Upload visibility contract', () {
    test('parses the session id returned by UploadInitiateResponse', () {
      final session = UploadSession.fromJson(const {
        'session_id': 'sess-abc',
        'organization_id': 'org-1',
        'status': 'UPLOADED',
      });
      expect(session.uploadSessionId, 'sess-abc');
    });

    test('multipart upload finalizes so the document becomes listable',
        () async {
      final repo = RecordingDocumentRepository();
      final controller = UploadLifecycleController(repo);
      final file = File('${Directory.systemTemp.path}/visibility_probe.pdf')
        ..writeAsBytesSync(List<int>.filled(10, 0));
      addTearDown(() {
        if (file.existsSync()) file.deleteSync();
      });

      await controller.startUploadAndFinalize(file);

      expect(repo.finalizedSessionId, 'sess-123',
          reason: 'without finalize the file is stored but no document row '
              'is created, so it never appears in the list');
      expect(controller.state.status, UploadStatus.queued);
      expect(controller.state.job?.status, 'QUEUED');
    });

    test('missing session id fails loudly instead of silently succeeding',
        () async {
      final repo = RecordingDocumentRepository(sessionId: '');
      final controller = UploadLifecycleController(repo);
      final file = File('${Directory.systemTemp.path}/visibility_probe2.pdf')
        ..writeAsBytesSync(List<int>.filled(10, 0));
      addTearDown(() {
        if (file.existsSync()) file.deleteSync();
      });

      await controller.startUploadAndFinalize(file);

      expect(controller.state.status, UploadStatus.failed);
      expect(controller.state.exception?.code, 'UPLOAD_SESSION_ID_MISSING');
      expect(repo.finalizedSessionId, isNull);
    });
  });

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
