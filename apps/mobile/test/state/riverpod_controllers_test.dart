import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/repositories/document_repository.dart';
import 'package:finance_intelligence/presentation/state/async_value_state.dart';
import 'package:finance_intelligence/presentation/state/document_list_controller.dart';

class ControllerMockDocumentRepo implements DocumentRepository {
  List<DocumentItem> itemsToReturn = [
    const DocumentItem(
        documentId: 'doc-1',
        organizationId: 'org-1',
        displayName: 'Report 2024.pdf')
  ];

  @override
  Future<List<DocumentItem>> getDocuments() async => itemsToReturn;

  @override
  Future<UploadSession> uploadSingleMultipart({
    required dynamic file,
    void Function(int p1, int p2)? onProgress,
    dynamic cancelToken,
  }) async =>
      const UploadSession(
        uploadSessionId: 'sess-1',
        organizationId: 'org-1',
        documentId: 'doc-1',
        documentVersionId: 'ver-1',
        status: 'FINALIZED',
        expectedSizeBytes: 100,
      );

  @override
  Future<UploadSession> createUploadSession({required dynamic file}) async =>
      throw UnimplementedError();

  @override
  Future<void> uploadFileStreamed(
      {required String uploadSessionId,
      required dynamic file,
      void Function(int p1, int p2)? onProgress,
      dynamic cancelToken}) async {}

  @override
  Future<IngestionJob> finalizeUpload(
          {required String uploadSessionId}) async =>
      throw UnimplementedError();
}

void main() {
  group('Riverpod Notifiers & Async State Correctness', () {
    test(
        'DocumentListController transitions from loading to success with generation token',
        () async {
      final repo = ControllerMockDocumentRepo();
      final controller = DocumentListController(repo);

      expect(controller.currentUiState.status, equals(AsyncStatus.initial));

      final future = controller.loadDocuments();
      expect(controller.currentUiState.status, equals(AsyncStatus.loading));

      await future;
      expect(controller.currentUiState.status, equals(AsyncStatus.success));
      expect(controller.currentUiState.data, hasLength(1));
      expect(controller.currentUiState.data!.first.displayName,
          equals('Report 2024.pdf'));
    });

    test(
        'DocumentListController transitions to empty when document list is empty',
        () async {
      final repo = ControllerMockDocumentRepo();
      repo.itemsToReturn = [];
      final controller = DocumentListController(repo);

      await controller.loadDocuments();
      expect(controller.currentUiState.status, equals(AsyncStatus.empty));
    });
  });
}
