import 'dart:io';
import 'package:dio/dio.dart';
import '../../core/models/app_exception.dart';
import '../../core/models/wire_models.dart';
import '../api/api_client.dart';

abstract class DocumentRepository {
  Future<List<DocumentItem>> getDocuments();
  Future<UploadSession> createUploadSession({required File file});
  Future<void> uploadFileStreamed({
    required String uploadSessionId,
    required File file,
    void Function(int sentBytes, int totalBytes)? onProgress,
    CancelToken? cancelToken,
  });
  Future<IngestionJob> finalizeUpload({required String uploadSessionId});
}

class RemoteDocumentRepository implements DocumentRepository {
  final FinanceIntelligenceApiClient apiClient;
  final Set<String> _finalizedSessions = {};

  RemoteDocumentRepository({required this.apiClient});

  static const maxFileSizeBytes = 50 * 1024 * 1024; // 50MB limit
  static const allowedExtensions = ['pdf', 'xlsx', 'csv'];

  @override
  Future<List<DocumentItem>> getDocuments() async {
    return await apiClient.getDocuments();
  }

  @override
  Future<UploadSession> createUploadSession({required File file}) async {
    final path = file.path;
    final ext = path.split('.').last.toLowerCase();
    if (!allowedExtensions.contains(ext)) {
      throw const ValidationException(
        code: 'INVALID_FILE_EXTENSION',
        message:
            'Desteklenmeyen dosya uzantısı. Yalnızca PDF, XLSX ve CSV yüklenebilir.',
        requestId: 'client_validation',
      );
    }

    final len = await file.length();
    if (len > maxFileSizeBytes) {
      throw const ValidationException(
        code: 'FILE_SIZE_EXCEEDED',
        message: 'Dosya boyutu 50MB sınırını aşamaz.',
        requestId: 'client_validation',
      );
    }

    final filename = path.split('/').last;
    return await apiClient.createUploadSession(
      filename: filename,
      expectedSizeBytes: len,
    );
  }

  @override
  Future<void> uploadFileStreamed({
    required String uploadSessionId,
    required File file,
    void Function(int sentBytes, int totalBytes)? onProgress,
    CancelToken? cancelToken,
  }) async {
    await apiClient.uploadFileStreamed(
      uploadSessionId: uploadSessionId,
      file: file,
      onSendProgress: onProgress,
      cancelToken: cancelToken,
    );
  }

  @override
  Future<IngestionJob> finalizeUpload({required String uploadSessionId}) async {
    if (_finalizedSessions.contains(uploadSessionId)) {
      throw const ConflictException(
        code: 'DUPLICATE_FINALIZE_PROHIBITED',
        message: 'Bu yükleme oturumu zaten sonlandırıldı.',
        requestId: 'client_validation',
      );
    }
    _finalizedSessions.add(uploadSessionId);
    return await apiClient.finalizeUploadSession(
        uploadSessionId: uploadSessionId);
  }
}
