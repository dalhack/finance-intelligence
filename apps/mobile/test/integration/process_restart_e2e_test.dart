import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:finance_intelligence/data/api/analysis_sse_client.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/data/storage/analysis_resume_store.dart';
import 'package:finance_intelligence/features/analysis/controllers/analysis_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Host Persistence Restart + Clarification E2E Tests', () {
    test(
        'Simulates complete host container restart with SharedPreferences persistence',
        () async {
      SharedPreferences.setMockInitialValues({});
      final prefs1 = await SharedPreferences.getInstance();

      final dio = Dio(BaseOptions(
        baseUrl: 'http://127.0.0.1:8000/api/v1',
        validateStatus: (status) => status != null && status < 500,
      ));

      final apiClient = FinanceIntelligenceApiClient(dio: dio);
      final sseClient = AnalysisSseClient(dio: dio);
      final resumeStore1 = SharedPreferencesAnalysisResumeStore(prefs1);
      final fp = computeSessionBindingHash("test_sub_process_restart");

      // Write a active resume record to disk store
      final initialRecord = AnalysisResumeRecord(
        analysisId: "c794ef64-9b2f-4c12-881a-4d2c88219099",
        lastAppliedSequence: 2,
        lastEventId: "2",
        lifecycleStatus: "NEEDS_CLARIFICATION",
        createdAt: DateTime.now().toUtc().toIso8601String(),
        lastConnectedAt: DateTime.now().toUtc().toIso8601String(),
        sessionBindingFingerprint: fp,
      );
      await resumeStore1.write(initialRecord);

      // First Controller
      final controller1 = AnalysisController(
        apiClient: apiClient,
        sseClient: sseClient,
        resumeStore: resumeStore1,
        sessionBindingFingerprint: fp,
      );

      // Dispose controller 1 and store reference to simulate process restart
      controller1.dispose();

      // Second Session (Simulate restart reading from disk store)
      final prefs2 = await SharedPreferences.getInstance();
      final resumeStore2 = SharedPreferencesAnalysisResumeStore(prefs2);

      final readRecord = await resumeStore2.read();
      expect(readRecord, isNotNull);
      expect(readRecord?.analysisId, "c794ef64-9b2f-4c12-881a-4d2c88219099");
      expect(readRecord?.lastAppliedSequence, 2);

      final controller2 = AnalysisController(
        apiClient: apiClient,
        sseClient: sseClient,
        resumeStore: resumeStore2,
        sessionBindingFingerprint: fp,
      );

      await controller2.restorePendingAnalysis();

      expect(controller2.state.isSubmitting, false);
      controller2.dispose();
    });
  });
}
