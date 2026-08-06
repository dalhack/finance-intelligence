import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import '../../core/models/wire_models.dart';

class AnalysisSseClient {
  final Dio _dio;

  AnalysisSseClient({required Dio dio}) : _dio = dio;

  Stream<AnalysisDomainEventModel> streamEvents({
    required String analysisId,
    String? lastEventId,
    CancelToken? cancelToken,
  }) async* {
    final response = await _dio.get<ResponseBody>(
      '/analyses/$analysisId/events',
      options: Options(
        responseType: ResponseType.stream,
        headers: {
          if (lastEventId != null && lastEventId.isNotEmpty)
            'Last-Event-ID': lastEventId,
        },
      ),
      cancelToken: cancelToken,
    );

    final stream = response.data?.stream;
    if (stream == null) return;

    String buffer = '';
    String currentType = '';
    String currentId = '';
    String currentData = '';

    await for (final chunk
        in stream.cast<List<int>>().transform(utf8.decoder)) {
      buffer += chunk;
      final lines = buffer.split('\n');
      buffer = lines.removeLast(); // Keep incomplete trailing line in buffer

      for (final line in lines) {
        final trimmed = line.trim();
        if (trimmed.isEmpty) {
          // Event boundary reached
          if (currentType.isNotEmpty && currentData.isNotEmpty) {
            try {
              final parsedJson =
                  json.decode(currentData) as Map<String, dynamic>;
              yield AnalysisDomainEventModel.fromSseLine(
                type: currentType,
                id: currentId,
                data: parsedJson,
              );
            } catch (_) {
              // Ignore malformed JSON or unsupported event FormatExceptions gracefully
            }
          }
          currentType = '';
          currentId = '';
          currentData = '';
          continue;
        }

        if (trimmed.startsWith('event:')) {
          currentType = trimmed.substring(6).trim();
        } else if (trimmed.startsWith('id:')) {
          currentId = trimmed.substring(3).trim();
        } else if (trimmed.startsWith('data:')) {
          final dataVal = trimmed.substring(5).trim();
          currentData =
              currentData.isEmpty ? dataVal : '$currentData\n$dataVal';
        }
      }
    }
  }
}
