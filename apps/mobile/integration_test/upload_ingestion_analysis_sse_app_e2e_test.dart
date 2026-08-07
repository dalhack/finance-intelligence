import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:finance_intelligence/app/app.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/features/analysis/controllers/analysis_controller.dart';
import 'package:finance_intelligence/presentation/providers/providers.dart';
import 'package:finance_intelligence/presentation/state/async_value_state.dart';
import 'package:finance_intelligence/presentation/state/upload_controller.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Real Application Entry Path E2E Test Node (Yol A)', () {
    const backendBaseUrl = String.fromEnvironment('FI_E2E_API_BASE_URL', defaultValue: 'http://127.0.0.1:8000');
    const e2eAuthId = String.fromEnvironment('FI_E2E_AUTHORIZATION_ID', defaultValue: '');
    const e2eOrgId = String.fromEnvironment('FI_E2E_ORGANIZATION_ID', defaultValue: '');
    const e2eActorId = String.fromEnvironment('FI_E2E_ACTOR_ID', defaultValue: '');
    const e2eInstId = String.fromEnvironment('FI_E2E_INSTITUTION_ID', defaultValue: '');
    const e2ePeriodId = String.fromEnvironment('FI_E2E_REPORTING_PERIOD_ID', defaultValue: '');
    const e2eFixtureFilePath = String.fromEnvironment('FI_E2E_FIXTURE_FILE_PATH', defaultValue: '');

    const allowedHosts = ['127.0.0.1', 'localhost', '::1'];

    late File tempFile;
    bool isBackendOnline = false;

    setUpAll(() async {
      final uri = Uri.parse(backendBaseUrl);
      if (!allowedHosts.contains(uri.host)) {
        throw StateError(
          'FAIL_CLOSED: Non-loopback backend host "${uri.host}" is prohibited for application E2E integration tests.',
        );
      }

      // If e2eAuthId is provided via harness, validate that all required defines are non-empty
      if (e2eAuthId.isNotEmpty) {
        if (e2eOrgId.isEmpty || e2eActorId.isEmpty || e2eInstId.isEmpty || e2ePeriodId.isEmpty) {
          throw StateError(
            'FAIL_CLOSED: Missing required FI_E2E_* dart defines when FI_E2E_AUTHORIZATION_ID is set.',
          );
        }
      }

      // Check backend health
      try {
        final client = HttpClient();
        client.connectionTimeout = const Duration(seconds: 2);
        final request =
            await client.getUrl(Uri.parse('$backendBaseUrl/health'));
        final response = await request.close();
        if (response.statusCode == 200) {
          isBackendOnline = true;
        }
      } catch (_) {
        isBackendOnline = false;
      }

      if (e2eFixtureFilePath.isNotEmpty && await File(e2eFixtureFilePath).exists()) {
        tempFile = File(e2eFixtureFilePath);
      } else {
        final dir = Directory.systemTemp.createTempSync('app_e2e_test_');
        tempFile = File('${dir.path}/test_financial_report_2025.pdf');
        await tempFile.writeAsString(
          '%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
          '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
          '3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources <<>> /Contents 4 0 R >>\nendobj\n'
          '4 0 obj\n<< /Length 55 >>\nstream\nBT /F1 12 Tf 72 712 Td (Garanti 2025 Q4 Financial Report) Tj ET\nendstream\nendobj\n'
          'xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000062 00000 n \n0000000125 00000 n \n0000000208 00000 n \n'
          'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n313\n%%EOF\n',
        );
      }
    });

    tearDownAll(() async {
      if (await tempFile.exists()) {
        await tempFile.delete();
      }
    });

    testWidgets(
        'Full Real Application Path: Upload -> Ingestion Poll -> Document Ready -> User Submit Analysis -> SSE Terminal State',
        (WidgetTester tester) async {
      if (!isBackendOnline) {
        fail(
          'FAIL_CLOSED: Local FastAPI backend on $backendBaseUrl is OFFLINE. '
          'Real application E2E test requires a running backend process.',
        );
      }

      // 1. Pump Application Widget Tree with Production Riverpod Graph
      await tester.pumpWidget(
        const ProviderScope(
          child: FinanceIntelligenceApp(),
        ),
      );
      await tester.pumpAndSettle();

      // 2. Drive Upload Lifecycle Controller with real temporary file
      final container = ProviderScope.containerOf(
          tester.element(find.byType(FinanceIntelligenceApp)));

      final uploadNotifier =
          container.read(uploadLifecycleControllerProvider.notifier);
      await uploadNotifier.startUploadAndFinalize(tempFile);
      await tester.pumpAndSettle();

      final uploadState = container.read(uploadLifecycleControllerProvider);
      expect(uploadState.status, equals(UploadStatus.queued));
      expect(uploadState.job, isNotNull);

      final finalizeJob = uploadState.job!;
      expect(finalizeJob.jobId, isNotEmpty);
      expect(finalizeJob.documentId, isNotEmpty);

      // 3. Poll Ingestion Job Status via Production Controller until PROCESSED_SUCCESS
      final pollingNotifier = container.read(
          ingestionStatusPollingControllerProvider(finalizeJob.jobId).notifier);
      pollingNotifier.startPolling(jobId: finalizeJob.jobId);

      int pollAttempts = 0;
      UiState<IngestionJob> pollState;
      do {
        await Future.delayed(const Duration(milliseconds: 500));
        await tester.pump();
        pollState = container.read(
            ingestionStatusPollingControllerProvider(finalizeJob.jobId));
        pollAttempts++;
      } while (pollState.data?.isTerminal != true && pollAttempts < 20);

      expect(pollState.data?.status, equals('PROCESSED_SUCCESS'));

      // 4. Refresh Document List to mark document ready/available
      final docListNotifier =
          container.read(documentListControllerProvider.notifier);
      await docListNotifier.loadDocuments(isRefresh: true);
      await tester.pumpAndSettle();

      final docListState = container.read(documentListControllerProvider);
      expect(docListState.data, isNotNull);
      expect(
          docListState.data!.any((d) => d.documentId == finalizeJob.documentId),
          isTrue);

      // 5. User Initiated Analysis (Yol A): User supplies prompt and passes authoritative document_id
      final analysisNotifier =
          container.read(analysisControllerProvider.notifier);
      await analysisNotifier.submitAnalysis(
        prompt: 'Garanti 2025 Q4 Toplam Aktif ve Özkaynak analizi yapınız.',
        idempotencyKey: 'idem-app-e2e-${DateTime.now().millisecondsSinceEpoch}',
        selectedDocumentIds: [finalizeJob.documentId],
      );
      await tester.pumpAndSettle();

      final analysisState = container.read(analysisControllerProvider);
      expect(analysisState.activeAnalysisId, isNotNull);
      expect(analysisState.activeAnalysisId, isNot(equals(finalizeJob.jobId)));

      // 6. Observe SSE Terminal State
      int sseWaitAttempts = 0;
      AnalysisStatusState currentStatus;
      do {
        await Future.delayed(const Duration(milliseconds: 1000));
        await tester.pump();
        currentStatus = container.read(analysisControllerProvider).statusState;
        sseWaitAttempts++;
      } while (currentStatus != AnalysisStatusState.completed &&
          currentStatus != AnalysisStatusState.failedTerminal &&
          sseWaitAttempts < 30);

      expect(currentStatus, equals(AnalysisStatusState.completed));
    });
  });
}
