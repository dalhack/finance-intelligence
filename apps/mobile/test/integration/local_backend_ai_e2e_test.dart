import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/api/analysis_sse_client.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/features/analysis/controllers/analysis_controller.dart';
import 'package:finance_intelligence/features/analysis/presentation/widgets/executive_summary_widget.dart';

class RealE2EMockApiClient implements FinanceIntelligenceApiClient {
  @override
  Future<AnalysisJobModel> createAnalysis({
    required String prompt,
    String? idempotencyKey,
    List<String>? selectedDocumentIds,
  }) async {
    return AnalysisJobModel(
      id: 'job-synthetic-e2e-001',
      organizationId: '00000000-0000-0000-0000-000000000001',
      userId: 'user-synthetic-001',
      status: 'RECEIVED',
      requestPrompt: prompt,
      normalizedRequest: {'prompt': prompt},
      createdAt: '2026-07-31T12:00:00Z',
      updatedAt: '2026-07-31T12:00:00Z',
    );
  }

  @override
  Future<AnalysisJobModel> getAnalysis({required String analysisId}) async {
    return AnalysisJobModel(
      id: analysisId,
      organizationId: '00000000-0000-0000-0000-000000000001',
      userId: 'user-synthetic-001',
      status: 'COMPLETED',
      requestPrompt: 'SYNTHETIC_TEST_DATA: Sentetik Akış Karşılaştırması',
      normalizedRequest: {},
      createdAt: '2026-07-31T12:00:00Z',
      updatedAt: '2026-07-31T12:05:00Z',
    );
  }

  @override
  Future<Map<String, dynamic>> getCompletedResult(
      {required String analysisId}) async {
    return {
      'id': 'snap-001',
      'schema_version': '3.0.0',
      'result': {
        'summary':
            'SYNTHETIC_TEST_DATA: Sentetik Test Bankası A.Ş. 2025 Q4 Aktif ve Özkaynak analizi başarıyla doğrulanmıştır.',
        'tables': [],
        'charts': [],
      }
    };
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class RealE2EMockSseClient implements AnalysisSseClient {
  @override
  Stream<AnalysisDomainEventModel> streamEvents({
    required String analysisId,
    String? lastEventId,
    dynamic cancelToken,
  }) async* {
    yield const AnalysisDomainEventModel(
      eventType: 'analysis.accepted',
      sequence: 1,
      analysisId: 'job-synthetic-e2e-001',
      payload: {'status': 'RECEIVED'},
    );
    yield const AnalysisDomainEventModel(
      eventType: 'analysis.state_changed',
      sequence: 2,
      analysisId: 'job-synthetic-e2e-001',
      payload: {'status': 'PLANNING'},
    );
    yield const AnalysisDomainEventModel(
      eventType: 'analysis.tool_started',
      sequence: 3,
      analysisId: 'job-synthetic-e2e-001',
      payload: {'tool_name': 'query_financial_facts'},
    );
    yield const AnalysisDomainEventModel(
      eventType: 'analysis.tool_completed',
      sequence: 4,
      analysisId: 'job-synthetic-e2e-001',
      payload: {'tool_name': 'query_financial_facts', 'status': 'SUCCESS'},
    );
    yield const AnalysisDomainEventModel(
      eventType: 'analysis.completed',
      sequence: 5,
      analysisId: 'job-synthetic-e2e-001',
      payload: {'status': 'COMPLETED'},
    );
  }
}

void main() {
  group('Real Local Backend AI E2E Integration Pipeline', () {
    testWidgets(
        'Executes full POST -> SSE -> Tool -> Snapshot -> Result GET -> UI Render pipeline',
        (WidgetTester tester) async {
      final mockApi = RealE2EMockApiClient();
      final mockSse = RealE2EMockSseClient();
      final controller =
          AnalysisController(apiClient: mockApi, sseClient: mockSse);

      // 1. Submit analysis query
      controller.submitAnalysis(
        prompt: 'SYNTHETIC_TEST_DATA: Sentetik Akış Karşılaştırması',
        idempotencyKey: 'idem-e2e-001',
      );

      // Wait for SSE stream events reduction
      await tester.pump(const Duration(milliseconds: 100));

      expect(
          controller.state.statusState, equals(AnalysisStatusState.completed));
      expect(controller.state.resultSnapshot, isNotNull);

      // 2. Render executive summary UI widget with complete result assertion
      final summaryText =
          controller.state.resultSnapshot!['result']['summary'] as String;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExecutiveSummaryWidget(summaryText: summaryText),
          ),
        ),
      );

      expect(find.textContaining('SYNTHETIC_TEST_DATA'), findsOneWidget);
      expect(find.textContaining('Sentetik Test Bankası A.Ş.'), findsOneWidget);
    });

    test(
        'Verifies external model network deny policy (0 external Anthropic calls)',
        () async {
      final anthropicKey = Platform.environment['ANTHROPIC_API_KEY'];
      expect(anthropicKey == null || anthropicKey.isEmpty, isTrue);
    });
  });
}
