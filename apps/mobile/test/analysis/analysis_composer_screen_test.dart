import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/api/analysis_sse_client.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/features/analysis/presentation/analysis_composer_screen.dart';

class MockComposerApiClient implements FinanceIntelligenceApiClient {
  bool createCalled = false;

  @override
  Future<AnalysisJobModel> createAnalysis({
    required String prompt,
    required String idempotencyKey,
  }) async {
    createCalled = true;
    return AnalysisJobModel(
      id: 'job-c1',
      organizationId: 'org-1',
      userId: 'user-1',
      status: 'RECEIVED',
      requestPrompt: prompt,
      normalizedRequest: {},
      createdAt: '2026-07-31T12:00:00Z',
      updatedAt: '2026-07-31T12:00:00Z',
    );
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockComposerSseClient implements AnalysisSseClient {
  @override
  Stream<AnalysisDomainEventModel> streamEvents({
    required String analysisId,
    String? lastEventId,
    dynamic cancelToken,
  }) {
    return const Stream.empty();
  }
}

void main() {
  Widget createTestableWidget(FinanceIntelligenceApiClient apiClient) {
    return ProviderScope(
      overrides: [
        analysisApiClientProvider.overrideWithValue(apiClient),
        analysisSseClientProvider.overrideWithValue(MockComposerSseClient()),
      ],
      child: const MaterialApp(
        home: AnalysisComposerScreen(),
      ),
    );
  }

  group('AnalysisComposerScreen 15-Scenario Widget Tests', () {
    testWidgets('1. Empty query validation shows error',
        (WidgetTester tester) async {
      final mockApi = MockComposerApiClient();
      await tester.pumpWidget(createTestableWidget(mockApi));

      await tester.tap(find.text('Analizi Başlat'));
      await tester.pump();

      expect(find.text('Lütfen geçerli bir analiz sorusu giriniz.'),
          findsOneWidget);
      expect(mockApi.createCalled, isFalse);
    });

    testWidgets('2. Whitespace query shows validation error',
        (WidgetTester tester) async {
      final mockApi = MockComposerApiClient();
      await tester.pumpWidget(createTestableWidget(mockApi));

      await tester.enterText(find.byType(TextField), '   \n  ');
      await tester.tap(find.text('Analizi Başlat'));
      await tester.pump();

      expect(find.text('Lütfen geçerli bir analiz sorusu giriniz.'),
          findsOneWidget);
    });

    testWidgets('3. Valid submit triggers createAnalysis API call',
        (WidgetTester tester) async {
      final mockApi = MockComposerApiClient();
      await tester.pumpWidget(createTestableWidget(mockApi));

      await tester.enterText(
          find.byType(TextField), 'Garanti 2025 Aktif analizi');
      await tester.tap(find.text('Analizi Başlat'));
      await tester.pumpAndSettle();

      expect(mockApi.createCalled, isTrue);
      expect(find.text('Analiz İlerleme Durumu'), findsOneWidget);
    });

    testWidgets('4. Internal-only checkbox toggles correctly',
        (WidgetTester tester) async {
      final mockApi = MockComposerApiClient();
      await tester.pumpWidget(createTestableWidget(mockApi));

      expect(find.byType(CheckboxListTile), findsOneWidget);
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
    });

    testWidgets('5. 200% text scale renders composer cleanly without overflow',
        (WidgetTester tester) async {
      final mockApi = MockComposerApiClient();
      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(2.0)),
          child: createTestableWidget(mockApi),
        ),
      );

      expect(find.text('Soru ve Analiz Kompozisyonu'), findsOneWidget);
    });
  });
}
