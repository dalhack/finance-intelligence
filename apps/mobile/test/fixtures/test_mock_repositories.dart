import 'dart:io';
import 'package:dio/dio.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/repositories/document_repository.dart';
import 'package:finance_intelligence/data/repositories/fact_review_repository.dart';

class TestMockDocumentRepository implements DocumentRepository {
  @override
  Future<List<DocumentItem>> getDocuments() async => const [];

  @override
  Future<UploadSession> uploadSingleMultipart({
    required File file,
    void Function(int sentBytes, int totalBytes)? onProgress,
    CancelToken? cancelToken,
  }) async =>
      const UploadSession(
        uploadSessionId: 'sess-test-1',
        organizationId: 'org-test-1',
        documentId: 'doc-test-1',
        documentVersionId: 'ver-test-1',
        status: 'FINALIZED',
        expectedSizeBytes: 1024,
      );

  @override
  Future<UploadSession> createUploadSession({required File file}) async =>
      throw UnimplementedError();

  @override
  Future<void> uploadFileStreamed({
    required String uploadSessionId,
    required File file,
    void Function(int sentBytes, int totalBytes)? onProgress,
    CancelToken? cancelToken,
  }) async {}

  @override
  Future<IngestionJob> finalizeUpload(
          {required String uploadSessionId}) async =>
      throw UnimplementedError();
}

class TestMockFactReviewRepository implements FactReviewRepository {
  @override
  Future<List<Map<String, dynamic>>> getCandidateQueue() async => const [];

  @override
  Future<void> approveCandidate(
      {required String candidateId,
      String? notes,
      String? targetReportingBasis}) async {}

  @override
  Future<void> rejectCandidate(
      {required String candidateId, required String reason}) async {}

  @override
  Future<void> approveCandidateRevision({
    required String candidateId,
    required String expectedExistingFactId,
    String? notes,
    String? targetReportingBasis,
  }) async {}
}
