import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/models/app_exception.dart';
import '../../core/models/wire_models.dart';
import '../../data/repositories/document_repository.dart';

enum UploadStatus {
  idle,
  selecting,
  uploading,
  uploaded,
  finalizing,
  queued,
  failed,
  cancelled,
}

class UploadState {
  final UploadStatus status;
  final int sentBytes;
  final int totalBytes;
  final UploadSession? session;
  final IngestionJob? job;
  final AppException? exception;

  const UploadState({
    required this.status,
    this.sentBytes = 0,
    this.totalBytes = 0,
    this.session,
    this.job,
    this.exception,
  });

  double get progressFraction => totalBytes > 0 ? sentBytes / totalBytes : 0.0;

  UploadState copyWith({
    UploadStatus? status,
    int? sentBytes,
    int? totalBytes,
    UploadSession? session,
    IngestionJob? job,
    AppException? exception,
  }) {
    return UploadState(
      status: status ?? this.status,
      sentBytes: sentBytes ?? this.sentBytes,
      totalBytes: totalBytes ?? this.totalBytes,
      session: session ?? this.session,
      job: job ?? this.job,
      exception: exception ?? this.exception,
    );
  }
}

class UploadLifecycleController extends StateNotifier<UploadState> {
  final DocumentRepository _repository;
  CancelToken? _cancelToken;
  bool _isDisposed = false;

  UploadLifecycleController(this._repository)
      : super(const UploadState(status: UploadStatus.idle));

  @override
  void dispose() {
    _isDisposed = true;
    _cancelToken?.cancel('Controller disposed');
    super.dispose();
  }

  void cancelUpload() {
    if (state.status == UploadStatus.uploading) {
      _cancelToken?.cancel('User cancelled upload');
      state = state.copyWith(status: UploadStatus.cancelled);
    }
  }

  Future<void> startUploadAndFinalize(File file) async {
    if (state.status == UploadStatus.uploading ||
        state.status == UploadStatus.finalizing) {
      return; // Prevent duplicate submit
    }

    state = state.copyWith(status: UploadStatus.selecting);

    try {
      _cancelToken = CancelToken();
      final totalLen = await file.length();

      state = state.copyWith(
        status: UploadStatus.uploading,
        sentBytes: 0,
        totalBytes: totalLen,
      );

      final session = await _repository.uploadSingleMultipart(
        file: file,
        onProgress: (sent, total) {
          if (!_isDisposed && state.status == UploadStatus.uploading) {
            state = state.copyWith(
                sentBytes: sent, totalBytes: total > 0 ? total : totalLen);
          }
        },
        cancelToken: _cancelToken,
      );

      if (_isDisposed) return;
      state = state.copyWith(
        status: UploadStatus.uploaded,
        session: session,
        sentBytes: totalLen,
        totalBytes: totalLen,
      );

      // The document row, its version and the ingestion job are only created
      // when the upload session is finalized. Without this step the file
      // reaches storage but never appears in the document list.
      if (session.uploadSessionId.isEmpty) {
        throw const ValidationException(
          code: 'UPLOAD_SESSION_ID_MISSING',
          message:
              'Yükleme tamamlanamadı: sunucu bir oturum kimliği döndürmedi.',
          requestId: 'client_validation',
        );
      }

      state = state.copyWith(status: UploadStatus.finalizing);
      final job = await _repository.finalizeUpload(
        uploadSessionId: session.uploadSessionId,
      );

      if (_isDisposed) return;
      state = state.copyWith(status: UploadStatus.queued, job: job);
    } on AppException catch (e) {
      if (_isDisposed) return;
      state = state.copyWith(status: UploadStatus.failed, exception: e);
    } catch (e) {
      if (_isDisposed) return;
      if (e is DioException && e.type == DioExceptionType.cancel) {
        state = state.copyWith(status: UploadStatus.cancelled);
        return;
      }
      state = state.copyWith(
        status: UploadStatus.failed,
        exception: UnknownException(
          code: 'UPLOAD_FAILED',
          message: 'Belge yüklenirken bir sorun oluştu. Lütfen tekrar deneyin.',
          requestId: 'unknown',
        ),
      );
    }
  }
}
