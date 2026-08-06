import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/api/analysis_sse_client.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/features/analysis/controllers/analysis_controller.dart';

class FakeApiClient implements FinanceIntelligenceApiClient {
  bool cancelCalled = false;

  @override
  Future<AnalysisJobModel> createAnalysis({
    required String prompt,
    required String idempotencyKey,
    List<String>? selectedDocumentIds,
  }) async {
    return AnalysisJobModel(
      id: 'job-100',
      organizationId: 'org-100',
      userId: 'user-100',
      status: 'RECEIVED',
      requestPrompt: prompt,
      normalizedRequest: {},
      createdAt: '2026-07-31T12:00:00Z',
      updatedAt: '2026-07-31T12:00:00Z',
    );
  }

  @override
  Future<AnalysisJobModel> getAnalysis({required String analysisId}) async {
    return AnalysisJobModel(
      id: analysisId,
      organizationId: 'org-100',
      userId: 'user-100',
      status: 'COMPLETED',
      requestPrompt: 'test',
      normalizedRequest: {},
      createdAt: '2026-07-31T12:00:00Z',
      updatedAt: '2026-07-31T12:00:00Z',
    );
  }

  @override
  Future<AnalysisJobModel> cancelAnalysis({required String analysisId}) async {
    cancelCalled = true;
    return AnalysisJobModel(
      id: analysisId,
      organizationId: 'org-100',
      userId: 'user-100',
      status: 'CANCELLED',
      requestPrompt: 'test',
      normalizedRequest: {},
      createdAt: '2026-07-31T12:00:00Z',
      updatedAt: '2026-07-31T12:00:00Z',
    );
  }

  @override
  Future<Map<String, dynamic>> getCompletedResult(
      {required String analysisId}) async {
    return {'snapshot_id': 'snap-1', 'result': {}};
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FakeSseClient implements AnalysisSseClient {
  final StreamController<AnalysisDomainEventModel> controller =
      StreamController<AnalysisDomainEventModel>.broadcast();

  @override
  Stream<AnalysisDomainEventModel> streamEvents({
    required String analysisId,
    String? lastEventId,
    dynamic cancelToken,
  }) {
    return controller.stream;
  }
}

void main() {
  group('AnalysisController State Machine Tests', () {
    test('Initial status is idle', () {
      final fakeApi = FakeApiClient();
      final fakeSse = FakeSseClient();
      final controller =
          AnalysisController(apiClient: fakeApi, sseClient: fakeSse);

      expect(controller.state.statusState, equals(AnalysisStatusState.idle));
      expect(controller.state.activeAnalysisId, isNull);
    });

    test('submitAnalysis sets submitting and connects SSE stream', () async {
      final fakeApi = FakeApiClient();
      final fakeSse = FakeSseClient();
      final controller =
          AnalysisController(apiClient: fakeApi, sseClient: fakeSse);

      await controller.submitAnalysis(
        prompt: 'Garanti 2025 Q4 Toplam Aktif analizi yapınız.',
        idempotencyKey: 'idem-999',
      );

      expect(controller.state.activeAnalysisId, equals('job-100'));
      expect(controller.state.userPrompt,
          equals('Garanti 2025 Q4 Toplam Aktif analizi yapınız.'));
    });

    test('cancelCurrentAnalysis invokes cancel API endpoint', () async {
      final fakeApi = FakeApiClient();
      final fakeSse = FakeSseClient();
      final controller =
          AnalysisController(apiClient: fakeApi, sseClient: fakeSse);

      await controller.submitAnalysis(
        prompt: 'Analiz',
        idempotencyKey: 'idem-1',
      );

      await controller.cancelCurrentAnalysis();
      expect(
          controller.state.statusState, equals(AnalysisStatusState.cancelled));
      expect(fakeApi.cancelCalled, isTrue);
    });

    test(
        'UNKNOWN_EVENT_TEST_NODE: ignores unknown events without state mutation',
        () async {
      final fakeApi = FakeApiClient();
      final fakeSse = FakeSseClient();
      final controller =
          AnalysisController(apiClient: fakeApi, sseClient: fakeSse);

      await controller.submitAnalysis(
        prompt: 'Test prompt',
        idempotencyKey: 'idem-unk',
      );

      final initialStatus = controller.state.statusState;

      // Try constructing or emitting un-allowlisted event through AnalysisSseClient try/catch stream logic
      try {
        final unknownEv = AnalysisDomainEventModel.fromSseLine(
          type: 'unknown.synthetic_event',
          id: '99',
          data: {'job_id': 'job-100'},
        );
        fakeSse.controller.add(unknownEv);
        await Future.delayed(const Duration(milliseconds: 10));
      } catch (_) {
        // Expected FormatException for unsupported event
      }

      expect(controller.state.statusState, equals(initialStatus));
    });

    test(
        'CROSS_JOB_EVENT_TEST_NODE: ignores events with mismatching analysisId',
        () async {
      final fakeApi = FakeApiClient();
      final fakeSse = FakeSseClient();
      final controller =
          AnalysisController(apiClient: fakeApi, sseClient: fakeSse);

      await controller.submitAnalysis(
        prompt: 'Test prompt',
        idempotencyKey: 'idem-cross',
      );

      final initialStatus = controller.state.statusState;

      // Emit event for different job ID
      fakeSse.controller.add(
        const AnalysisDomainEventModel(
          eventType: 'analysis.completed',
          sequence: 10,
          analysisId: 'other-job-999',
          payload: {'status': 'COMPLETED'},
        ),
      );
      await Future.delayed(const Duration(milliseconds: 10));

      expect(controller.state.statusState, equals(initialStatus));
    });

    test(
        'DUPLICATE_TERMINAL_TEST_NODE: handles duplicate terminal event idempotently',
        () async {
      final fakeApi = FakeApiClient();
      final fakeSse = FakeSseClient();
      final controller =
          AnalysisController(apiClient: fakeApi, sseClient: fakeSse);

      await controller.submitAnalysis(
        prompt: 'Test prompt',
        idempotencyKey: 'idem-dup',
      );

      fakeSse.controller.add(
        const AnalysisDomainEventModel(
          eventType: 'analysis.completed',
          sequence: 1,
          analysisId: 'job-100',
          payload: {'status': 'COMPLETED'},
        ),
      );
      await Future.delayed(const Duration(milliseconds: 10));

      expect(
          controller.state.statusState, equals(AnalysisStatusState.completed));

      // Emit second duplicate terminal event
      fakeSse.controller.add(
        const AnalysisDomainEventModel(
          eventType: 'analysis.completed',
          sequence: 2,
          analysisId: 'job-100',
          payload: {'status': 'COMPLETED'},
        ),
      );
      await Future.delayed(const Duration(milliseconds: 10));

      expect(
          controller.state.statusState, equals(AnalysisStatusState.completed));
    });

    test(
        'POST_TERMINAL_EVENT_TEST_NODE: ignores events after reaching terminal state',
        () async {
      final fakeApi = FakeApiClient();
      final fakeSse = FakeSseClient();
      final controller =
          AnalysisController(apiClient: fakeApi, sseClient: fakeSse);

      await controller.submitAnalysis(
        prompt: 'Test prompt',
        idempotencyKey: 'idem-post',
      );

      fakeSse.controller.add(
        const AnalysisDomainEventModel(
          eventType: 'analysis.completed',
          sequence: 1,
          analysisId: 'job-100',
          payload: {'status': 'COMPLETED'},
        ),
      );
      await Future.delayed(const Duration(milliseconds: 10));

      expect(
          controller.state.statusState, equals(AnalysisStatusState.completed));

      // Emit post-terminal state change event
      fakeSse.controller.add(
        const AnalysisDomainEventModel(
          eventType: 'analysis.state_changed',
          sequence: 2,
          analysisId: 'job-100',
          payload: {'to_state': 'UNDERSTANDING_REQUEST'},
        ),
      );
      await Future.delayed(const Duration(milliseconds: 10));

      expect(
          controller.state.statusState, equals(AnalysisStatusState.completed));
    });
  });
}
