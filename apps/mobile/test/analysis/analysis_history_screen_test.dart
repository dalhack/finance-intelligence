import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/data/api/api_client.dart';
import 'package:finance_intelligence/features/analysis/presentation/analysis_history_screen.dart';

class MockHistoryApiClient implements FinanceIntelligenceApiClient {
  @override
  Future<List<AnalysisJobModel>> listAnalyses({
    int limit = 20,
    int offset = 0,
  }) async {
    return [
      AnalysisJobModel(
        id: 'job-h1',
        organizationId: 'org-1',
        userId: 'user-1',
        status: 'COMPLETED',
        requestPrompt: 'Garanti 2025 Q4 Aktif analizi',
        normalizedRequest: {},
        createdAt: '2026-07-31T10:00:00Z',
        updatedAt: '2026-07-31T10:05:00Z',
      ),
      AnalysisJobModel(
        id: 'job-h2',
        organizationId: 'org-1',
        userId: 'user-1',
        status: 'FAILED',
        requestPrompt: 'İş Bankası Özkaynak analizi',
        normalizedRequest: {},
        createdAt: '2026-07-31T11:00:00Z',
        updatedAt: '2026-07-31T11:02:00Z',
      ),
    ];
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets('AnalysisHistoryScreen renders list of analyses with badges',
      (WidgetTester tester) async {
    final mockApi = MockHistoryApiClient();

    await tester.pumpWidget(
      MaterialApp(
        home: AnalysisHistoryScreen(apiClient: mockApi),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Analiz Geçmişi'), findsOneWidget);
    expect(find.text('Garanti 2025 Q4 Aktif analizi'), findsOneWidget);
    expect(find.text('İş Bankası Özkaynak analizi'), findsOneWidget);
    expect(find.text('COMPLETED'), findsOneWidget);
    expect(find.text('FAILED'), findsOneWidget);
  });
}
