import 'dart:io';
import 'package:dio/dio.dart';
import '../../core/models/app_exception.dart';
import '../../core/models/wire_models.dart';
import '../../core/network/error_envelope_parser.dart';

class FinanceIntelligenceApiClient {
  final Dio _dio;

  FinanceIntelligenceApiClient({required Dio dio}) : _dio = dio;

  Future<dynamic> createDevSession() async {
    return _safeCall(() async {
      final res = await _dio.post('/dev-session');
      return res.data;
    });
  }

  Future<List<DocumentItem>> getDocuments() async {
    return _safeCall(() async {
      final res = await _dio.get('/documents');
      final list = (res.data as List<dynamic>?) ?? [];
      return list
          .map((item) => DocumentItem.fromJson(item as Map<String, dynamic>))
          .toList();
    });
  }

  Future<UploadSession> uploadDocumentMultipart({
    required File file,
    required String displayName,
    String classification = 'CONFIDENTIAL',
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    return _safeCall(() async {
      final fileName = displayName.isNotEmpty ? displayName : file.path.split('/').last;
      final formData = FormData.fromMap({
        'display_name': fileName,
        'classification': classification,
        'file': await MultipartFile.fromFile(
          file.path,
          filename: fileName,
        ),
      });

      final res = await _dio.post(
        '/documents/uploads',
        data: formData,
        onSendProgress: onSendProgress,
        cancelToken: cancelToken,
      );
      return UploadSession.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<UploadSession> createUploadSession({
    required String filename,
    required int expectedSizeBytes,
  }) async {
    return _safeCall(() async {
      final res = await _dio.post(
        '/documents/uploads',
        data: {
          'filename': filename,
          'expected_size_bytes': expectedSizeBytes,
        },
      );
      return UploadSession.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<void> uploadFileStreamed({
    required String uploadSessionId,
    required File file,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    return _safeCall(() async {
      final len = await file.length();
      final stream = file.openRead();

      final formData = FormData.fromMap({
        'file': MultipartFile.fromStream(
          () => stream,
          len,
          filename: file.path.split('/').last,
        ),
      });

      await _dio.post(
        '/documents/uploads/$uploadSessionId/stream',
        data: formData,
        onSendProgress: onSendProgress,
        cancelToken: cancelToken,
      );
    });
  }

  Future<IngestionJob> finalizeUploadSession({
    required String uploadSessionId,
  }) async {
    return _safeCall(() async {
      final res =
          await _dio.post('/documents/uploads/$uploadSessionId/finalize');
      return IngestionJob.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<IngestionJob> getIngestionJobStatus({
    required String jobId,
  }) async {
    return _safeCall(() async {
      final res = await _dio.get('/documents/ingestion-jobs/$jobId');
      return IngestionJob.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<Map<String, dynamic>> executeComparison({
    required ComparisonRequest request,
  }) async {
    return _safeCall(() async {
      final res = await _dio.post(
        '/comparisons',
        data: request.toJson(),
      );
      return res.data as Map<String, dynamic>;
    });
  }

  Future<Map<String, dynamic>> getPersistedComparison({
    required String comparisonId,
    int page = 1,
    int pageSize = 20,
  }) async {
    return _safeCall(() async {
      final res = await _dio.get(
        '/comparisons/$comparisonId',
        queryParameters: {
          'page': page,
          'page_size': pageSize,
        },
      );
      return res.data as Map<String, dynamic>;
    });
  }

  Future<Map<String, dynamic>> getComparisonFiltersMetadata() async {
    return _safeCall(() async {
      final res = await _dio.get('/comparisons/metadata/filters');
      return res.data as Map<String, dynamic>;
    });
  }

  Future<EvidenceDetail> getEvidenceDetail({
    required String evidenceId,
  }) async {
    return _safeCall(() async {
      final res = await _dio.get('/evidence/$evidenceId');
      return EvidenceDetail.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<List<Map<String, dynamic>>> getCandidateFacts() async {
    return _safeCall(() async {
      final res = await _dio.get('/facts/candidates');
      return (res.data as List<dynamic>)
          .map((e) => e as Map<String, dynamic>)
          .toList();
    });
  }

  Future<Map<String, dynamic>> approveCandidate({
    required String candidateId,
    String? notes,
    String? targetReportingBasis,
  }) async {
    return _safeCall(() async {
      final res = await _dio.post(
        '/facts/candidates/$candidateId/approve',
        data: {
          if (notes != null) 'notes': notes,
          if (targetReportingBasis != null)
            'target_reporting_basis': targetReportingBasis,
        },
      );
      return res.data as Map<String, dynamic>;
    });
  }

  Future<Map<String, dynamic>> rejectCandidate({
    required String candidateId,
    required String reason,
  }) async {
    return _safeCall(() async {
      final res = await _dio.post(
        '/facts/candidates/$candidateId/reject',
        data: {'reason': reason},
      );
      return res.data as Map<String, dynamic>;
    });
  }

  Future<Map<String, dynamic>> approveCandidateRevision({
    required String candidateId,
    required String expectedExistingFactId,
    String? notes,
    String? targetReportingBasis,
  }) async {
    return _safeCall(() async {
      final res = await _dio.post(
        '/facts/candidates/$candidateId/approve-revision',
        data: {
          'expected_existing_fact_id': expectedExistingFactId,
          if (notes != null) 'notes': notes,
          if (targetReportingBasis != null)
            'target_reporting_basis': targetReportingBasis,
        },
      );
      return res.data as Map<String, dynamic>;
    });
  }

  Future<AnalysisJobModel> createAnalysis({
    required String prompt,
    String? idempotencyKey,
    List<String>? selectedDocumentIds,
  }) async {
    return _safeCall(() async {
      final reqModel = AnalysisCreateRequestModel(
        userQuery: prompt,
        idempotencyKey: idempotencyKey,
        selectedDocumentIds: selectedDocumentIds,
      );
      final res = await _dio.post(
        '/analyses',
        data: reqModel.toJson(),
      );
      return AnalysisJobModel.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<AnalysisJobModel> getAnalysis({required String analysisId}) async {
    return _safeCall(() async {
      final res = await _dio.get('/analyses/$analysisId');
      return AnalysisJobModel.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<List<AnalysisJobModel>> listAnalyses({
    int limit = 20,
    int offset = 0,
  }) async {
    return _safeCall(() async {
      final res = await _dio.get(
        '/analyses',
        queryParameters: {'limit': limit, 'offset': offset},
      );
      final list = (res.data as List<dynamic>?) ?? [];
      return list
          .map(
              (item) => AnalysisJobModel.fromJson(item as Map<String, dynamic>))
          .toList();
    });
  }

  Future<AnalysisJobModel> cancelAnalysis({required String analysisId}) async {
    return _safeCall(() async {
      final res = await _dio.post('/analyses/$analysisId/cancel');
      return AnalysisJobModel.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<Map<String, dynamic>> getCompletedResult({
    required String analysisId,
  }) async {
    return _safeCall(() async {
      final res = await _dio.get('/analyses/$analysisId/result');
      return res.data as Map<String, dynamic>;
    });
  }

  Future<Map<String, dynamic>> getAnalysisClarification({
    required String analysisId,
  }) async {
    return _safeCall(() async {
      final res = await _dio.get('/analyses/$analysisId/clarification');
      return res.data as Map<String, dynamic>;
    });
  }

  Future<AnalysisJobModel> respondToClarification({
    required String analysisId,
    required Map<String, dynamic> requestData,
  }) async {
    return _safeCall(() async {
      final res = await _dio.post(
        '/analyses/$analysisId/clarification/respond',
        data: requestData,
      );
      return AnalysisJobModel.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<AnalysisJobModel> cancelClarification({
    required String analysisId,
    required Map<String, dynamic> requestData,
  }) async {
    return _safeCall(() async {
      final res = await _dio.post(
        '/analyses/$analysisId/clarification/cancel',
        data: requestData,
      );
      return AnalysisJobModel.fromJson(res.data as Map<String, dynamic>);
    });
  }

  Future<T> _safeCall<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on DioException catch (e) {
      final fallbackId =
          e.requestOptions.headers['X-Request-ID']?.toString() ?? 'unknown';
      throw ErrorEnvelopeParser.parse(
        responseBody: e.response?.data,
        statusCode: e.response?.statusCode,
        fallbackRequestId: fallbackId,
      );
    } catch (e) {
      if (e is AppException) rethrow;
      throw UnknownException(
        code: 'UNEXPECTED_CLIENT_ERROR',
        message: e.toString(),
        requestId: 'unknown',
      );
    }
  }
}
