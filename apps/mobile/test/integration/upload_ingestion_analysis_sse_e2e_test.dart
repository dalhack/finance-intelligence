@Tags(['local_backend_integration'])
library;

import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:finance_intelligence/core/config/app_config.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/core/network/dio_client_factory.dart';
import 'package:finance_intelligence/core/security/dev_security_adapters.dart';
import 'package:finance_intelligence/data/api/analysis_sse_client.dart';
import 'package:finance_intelligence/data/api/api_client.dart';

void main() {
  group(
      'Executable Real Local E2E Upload -> Ingestion -> Analysis -> SSE Integration Test Node',
      () {
    const backendBaseUrl = 'http://127.0.0.1:8000';
    const allowedHosts = ['127.0.0.1', 'localhost', '::1'];

    late Dio dio;
    late FinanceIntelligenceApiClient apiClient;
    late AnalysisSseClient sseClient;
    late File tempFile;
    bool isBackendOnline = false;

    setUpAll(() async {
      final uri = Uri.parse(backendBaseUrl);
      if (!allowedHosts.contains(uri.host)) {
        throw StateError(
          'FAIL_CLOSED: Non-loopback backend host "${uri.host}" is prohibited for local E2E integration tests.',
        );
      }

      final config = AppConfig.development;
      final identityProv = DevelopmentIdentityTokenProvider(config: config);
      final attestationProv =
          DevelopmentAttestationTokenProvider(config: config);

      dio = DioClientFactory.createDio(
        config: config,
        identityTokenProvider: identityProv,
        appAttestationTokenProvider: attestationProv,
      );
      dio.options.baseUrl = '$backendBaseUrl/api/v1';

      apiClient = FinanceIntelligenceApiClient(dio: dio);
      sseClient = AnalysisSseClient(dio: dio);

      // Check backend health
      try {
        final healthDio = Dio(BaseOptions(
          baseUrl: backendBaseUrl,
          connectTimeout: const Duration(seconds: 2),
        ));
        final res = await healthDio.get('/health');
        if (res.statusCode == 200) {
          isBackendOnline = true;
        }
      } catch (_) {
        isBackendOnline = false;
      }

      // Create safe temporary test file
      final dir = Directory.systemTemp.createTempSync('e2e_test_');
      tempFile = File('${dir.path}/test_report_2025_q4.pdf');
      await tempFile.writeAsString(
        '%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
        '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
        '3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources <<>> /Contents 4 0 R >>\nendobj\n'
        '4 0 obj\n<< /Length 50 >>\nstream\nBT /F1 12 Tf 72 712 Td (Garanti 2025 Q4 Test Report) Tj ET\nendstream\nendobj\n'
        'xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000062 00000 n \n0000000125 00000 n \n0000000208 00000 n \n'
        'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n308\n%%EOF\n',
      );
    });

    tearDownAll(() async {
      if (await tempFile.exists()) {
        await tempFile.delete();
      }
    });

    test(
        'Full Real Local E2E Upload -> Finalize -> Ingestion -> Analysis -> SSE Pipeline',
        () async {
      if (!isBackendOnline) {
        fail(
          'FAIL_CLOSED: Local FastAPI backend on $backendBaseUrl is OFFLINE. '
          'Real HTTP contract test requires a live running backend process.',
        );
      }

      // 1. Create Upload Session
      final session = await apiClient.createUploadSession(
        filename: tempFile.path.split('/').last,
        expectedSizeBytes: await tempFile.length(),
      );
      expect(session.uploadSessionId, isNotEmpty);

      // 2. Stream Upload Bytes
      await apiClient.uploadFileStreamed(
        uploadSessionId: session.uploadSessionId,
        file: tempFile,
      );

      // 3. Finalize Upload
      final finalizeRes = await apiClient.finalizeUploadSession(
        uploadSessionId: session.uploadSessionId,
      );
      expect(finalizeRes.jobId, isNotEmpty);
      final documentId = finalizeRes.documentId;
      expect(documentId, isNotEmpty);

      // 4. Poll Ingestion Job Status until terminal success
      IngestionJob jobStatus;
      int pollAttempts = 0;
      do {
        await Future.delayed(const Duration(milliseconds: 500));
        jobStatus =
            await apiClient.getIngestionJobStatus(jobId: finalizeRes.jobId);
        pollAttempts++;
      } while (!jobStatus.isTerminal && pollAttempts < 20);

      expect(jobStatus.status, equals('PROCESSED_SUCCESS'));

      // 5. Create Analysis Job using authoritative document_id
      final analysisJob = await apiClient.createAnalysis(
        prompt: 'Garanti 2025 Q4 Toplam Aktif ve Özkaynak analizi yapınız.',
        idempotencyKey: 'idem-e2e-${DateTime.now().millisecondsSinceEpoch}',
      );
      expect(analysisJob.id, isNotEmpty);

      // Enforce domain separation assertion: ingestion_job_id != analysis_id
      expect(analysisJob.id, isNot(equals(finalizeRes.jobId)));

      // 6. Connect SSE Stream with exact analysis_id
      final events = <AnalysisDomainEventModel>[];
      final completer = Completer<void>();

      final sub =
          sseClient.streamEvents(analysisId: analysisJob.id).listen((ev) {
        events.add(ev);
        if (ev.eventType == 'analysis.completed' ||
            ev.eventType == 'analysis.failed') {
          if (!completer.isCompleted) completer.complete();
        }
      });

      await completer.future.timeout(const Duration(seconds: 30),
          onTimeout: () {
        sub.cancel();
      });

      await sub.cancel();

      expect(events, isNotEmpty);
      final terminalEvent = events.lastWhere(
        (e) =>
            e.eventType == 'analysis.completed' ||
            e.eventType == 'analysis.failed',
      );
      expect(terminalEvent.eventType, equals('analysis.completed'));
    });
  });
}
